"""Deterministic virtual-time links carrying serialized frames between durable nodes."""
import hashlib
import json
import random
import subprocess
import sys
from pathlib import Path
from .core import Node, encode, packet


class Local:
    def __init__(self, path): self.node = Node(path)
    def call(self, op, **kw): return getattr(self.node, op)(**kw)
    def close(self): self.node.close()


class Process:
    def __init__(self, path):
        self.child = subprocess.Popen([sys.executable, '-m', 'isoko.worker', str(path)], stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True)
    def call(self, op, **kw):
        self.child.stdin.write(json.dumps(dict(op=op, **kw)) + '\n')
        self.child.stdin.flush()
        response = json.loads(self.child.stdout.readline())
        if 'error' in response: raise RuntimeError(response['error'])
        return response['ok']
    def close(self):
        self.child.stdin.close()
        self.child.wait(timeout=10)
        self.child.stdout.close()
        if self.child.returncode: raise RuntimeError('Node process failed')


def workload(seed, learners=12):
    rng = random.Random(seed)
    packets = []
    for i in range(learners):
        learner = f'L{i:03}'
        created = rng.randrange(0, 9)
        deadline = created + rng.randrange(12, 29)
        risk, gap = round(rng.random(), 2), round(rng.random(), 2)
        q = packet(learner, 'question', 'What is 3/4 + 1/4? Give your answer as a whole number.', created, deadline, risk, gap, value=1)
        h = packet(learner, 'hint', 'Add the numerators; keep the common denominator. ' * rng.randrange(1, 5), created, deadline, risk, gap, [q['id']], value=.4)
        e = packet(learner, 'explanation', 'Four quarters make one whole. ' * rng.randrange(2, 15), created, deadline, risk, gap, [q['id'], h['id']], value=.6)
        packets.extend((q, h, e))
    return packets


def run(directory, seed=42, budget=2048, loss=.15, ack_loss=.15, delay=1, ticks=48, policy='isoko', processes=False, learners=12, outage=True):
    """Fresh run only. Node databases persist and workers restart at tick 16."""
    if budget < 0 or not 0 <= loss <= 1 or not 0 <= ack_loss <= 1 or delay < 1 or ticks < 1:
        raise ValueError('Invalid experiment configuration')
    root = Path(directory)
    root.mkdir(parents=True, exist_ok=True)
    if any(root.glob('*.sqlite')): raise ValueError('Use a fresh output directory; existing experiment preserved')
    adapter = Process if processes else Local
    nodes = {name: adapter(root / f'{name}.sqlite') for name in ('cloud', 'relay', 'learner')}
    packets = workload(seed, learners)
    events, log, pending_acks = [], [], []
    answered, useful = set(), {}
    attempts = {}
    byte_totals = dict(data_bytes=0, ack_bytes=0, dropped_bytes=0, duplicate_bytes=0)

    def draw(*parts):
        # Independent of scheduler PRNG consumption; matched by link, frame, and attempt.
        digest = hashlib.sha256(encode([seed, *parts])).digest()
        return int.from_bytes(digest[:8], 'big') / 2**64

    def send(frame, source, target, tick):
        wire = encode(frame)
        identity = frame.get('id') or frame['packet']['id']
        key = (source, target, frame['type'], identity)
        attempts[key] = attempts.get(key, 0) + 1
        dropped = draw(*key, attempts[key]) < (ack_loss if frame['type'] == 'ack' else loss)
        byte_totals['ack_bytes' if frame['type'] == 'ack' else 'data_bytes'] += len(wire)
        if dropped: byte_totals['dropped_bytes'] += len(wire)
        else: events.append((tick + delay, source, target, wire))
        log.append(dict(event='transmit', tick=tick, source=source, target=target, kind=frame['type'], id=identity, bytes=len(wire), dropped=dropped))
        return len(wire)

    try:
        for tick in range(ticks):
            if tick == 16:
                for node in nodes.values(): node.close()
                nodes = {name: adapter(root / f'{name}.sqlite') for name in nodes}
                log.append(dict(event='node_restart', tick=tick))
            for p in packets:
                if p['created'] == tick: nodes['cloud'].call('receive', p=p, tick=tick)
            due, events = [e for e in events if e[0] <= tick], [e for e in events if e[0] > tick]
            for _, source, target, wire in due:
                frame = json.loads(wire)
                if frame['type'] == 'ack':
                    nodes[target].call('ack', peer=source, identity=frame['id'])
                else:
                    p = frame['packet']
                    result = nodes[target].call('receive', p=p, tick=tick)
                    if result['accepted']:
                        pending_acks.append((target, source, p['id']))
                        if result['duplicate']: byte_totals['duplicate_bytes'] += len(wire)
                    log.append(dict(event='receive', tick=tick, node=target, id=p['id'], **result))
            received = {p['id']: p for p in nodes['learner'].call('items')}
            # Count utility only once all transitive prerequisites are usable.
            changed = True
            while changed:
                changed = False
                for identity, p in received.items():
                    if p['destination'] == 'learner' and identity not in useful and tick <= p['deadline'] and all(dep in useful for dep in p['deps']):
                        useful[identity] = tick
                        changed = True
            for identity, p in received.items():
                if p['kind'] == 'question' and identity in useful and identity not in answered:
                    response = packet(p['learner'], 'response', json.dumps({'question': identity, 'answer': '1', 'synthetic': True}), tick, ticks + 24, destination='cloud')
                    nodes['learner'].call('receive', p=response, tick=tick)
                    answered.add(identity)
            contacts = []
            if tick % 6 == 0: contacts.append(('cloud', 'relay'))
            if tick % 6 == 2: contacts.append(('relay', 'learner'))
            for a, b in contacts:
                capacity = 0 if outage and 12 <= tick < 18 else budget
                remaining = capacity
                # ACKs have strict priority and consume the same bidirectional budget.
                for ack in list(dict.fromkeys(pending_acks)):
                    source, target, identity = ack
                    frame = dict(type='ack', id=identity)
                    if {source, target} == {a, b} and len(encode(frame)) <= remaining:
                        remaining -= send(frame, source, target, tick)
                        pending_acks = [x for x in pending_acks if x != ack]
                # Alternate directions per contact to avoid fixed downlink precedence.
                pairs = [(a, b), (b, a)]
                if (tick // 6) % 2: pairs.reverse()
                for source, target in pairs:
                    while remaining:
                        group = nodes[source].call('select', peer=target, tick=tick, budget=remaining, policy=policy)
                        if not group: break
                        for p in group:
                            remaining -= send(dict(type='data', packet=p), source, target, tick)
                            nodes[source].call('attempted', peer=target, p=p, tick=tick)
                log.append(dict(event='contact', tick=tick, link=f'{a}-{b}', capacity=capacity, used=capacity-remaining))
        cloud = nodes['cloud'].call('items')
        received = {p['id']: p for p in nodes['learner'].call('items')}
        source = {p['id']: p for p in packets}
        useful_ids = set(useful) & set(source)
        reached = {source[i]['learner'] for i in useful_ids if source[i]['kind'] == 'question'}
        weights = lambda p: p['value'] * (1 + p['risk'] + p['gap'])
        metrics = dict(seed=seed, policy=policy, budget=budget, loss=loss, ack_loss=ack_loss, delay=delay, ticks=ticks,
                       useful_packets=len(useful_ids), usable_value=sum(weights(source[i]) for i in useful_ids),
                       possible_value=sum(weights(p) for p in packets), learners_reached=len(reached), learners=learners,
                       responses_returned=sum(p['kind']=='response' for p in cloud),
                       orphan_packets=sum(p['destination']=='learner' and p['id'] not in useful_ids for p in received.values()),
                       expired_or_undelivered=len(packets)-len(useful_ids), in_flight=len(events),
                       pending_acks=len(pending_acks), processes=processes, **byte_totals)
        (root / 'metrics.json').write_text(json.dumps(metrics, indent=2) + '\n')
        (root / 'trace.jsonl').write_text(''.join(json.dumps(e) + '\n' for e in log))
        (root / 'workload.json').write_text(json.dumps(packets, indent=2) + '\n')
        (root / 'cloud-final.json').write_text(json.dumps(cloud, indent=2) + '\n')
        return metrics
    finally:
        for node in nodes.values(): node.close()
