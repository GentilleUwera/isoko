"""Wire format, durable node state, and local-information scheduling."""
import hashlib
import json
import sqlite3
from pathlib import Path

POLICIES = ('isoko', 'fifo', 'edf', 'risk', 'density', 'no_dependencies', 'no_fairness')


def encode(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode('utf-8')


def packet(learner, kind, text, created=0, deadline=36, risk=.5, gap=.5, deps=(), value=1., destination='learner'):
    p = dict(learner=learner, kind=kind, text=text, created=created, deadline=deadline,
             risk=risk, gap=gap, deps=list(deps), value=value, destination=destination)
    p['id'] = hashlib.sha256(encode(p)).hexdigest()[:24]
    return p


def validate(p):
    copy = dict(p)
    identity = copy.pop('id')
    if hashlib.sha256(encode(copy)).hexdigest()[:24] != identity:
        raise ValueError('Packet integrity check failed')
    if p['deadline'] < p['created'] or not 0 <= p['risk'] <= 1 or not 0 <= p['gap'] <= 1:
        raise ValueError('Invalid packet metadata')


class Node:
    def __init__(self, path):
        self.name = Path(path).stem
        self.db = sqlite3.connect(path)
        self.db.executescript('''
          CREATE TABLE IF NOT EXISTS packets(id TEXT PRIMARY KEY, body TEXT NOT NULL, received INTEGER NOT NULL);
          CREATE TABLE IF NOT EXISTS known(peer TEXT, id TEXT, PRIMARY KEY(peer,id));
          CREATE TABLE IF NOT EXISTS attempts(peer TEXT, id TEXT, tick INTEGER, PRIMARY KEY(peer,id));
          CREATE TABLE IF NOT EXISTS service(peer TEXT, learner TEXT, tick INTEGER, PRIMARY KEY(peer,learner));
        ''')

    def receive(self, p, tick):
        validate(p)
        if tick > p['deadline']:
            return {'accepted': False, 'duplicate': False}
        with self.db:
            cur = self.db.execute('INSERT OR IGNORE INTO packets VALUES(?,?,?)', (p['id'], encode(p).decode(), tick))
        return {'accepted': True, 'duplicate': cur.rowcount == 0}

    def items(self):
        return [dict(json.loads(body), received=tick) for body, tick in self.db.execute('SELECT body,received FROM packets ORDER BY id')]

    def ack(self, peer, identity):
        with self.db:
            self.db.execute('INSERT OR IGNORE INTO known VALUES(?,?)', (peer, identity))

    def attempted(self, peer, p, tick):
        with self.db:
            self.db.execute('INSERT OR REPLACE INTO attempts VALUES(?,?,?)', (peer, p['id'], tick))
            self.db.execute('INSERT OR REPLACE INTO service VALUES(?,?,?)', (peer, p['learner'], tick))

    def select(self, peer, tick, budget, policy='isoko', retry=4):
        if policy not in POLICIES:
            raise ValueError('Unknown scheduling policy')
        known = {r[0] for r in self.db.execute('SELECT id FROM known WHERE peer=?', (peer,))}
        attempts = dict(self.db.execute('SELECT id,tick FROM attempts WHERE peer=?', (peer,)))
        service = dict(self.db.execute('SELECT learner,tick FROM service WHERE peer=?', (peer,)))
        pool = {}
        for original in self.items():
            p = {k: v for k, v in original.items() if k != 'received'}
            if p['destination'] == self.name:
                continue
            # Static routes: cloud -> relay -> learner; reverse for responses.
            if (peer == 'cloud' and p['destination'] != 'cloud') or (peer == 'learner' and p['destination'] != 'learner'):
                continue
            if p['id'] not in known and p['created'] <= tick <= p['deadline']:
                pool[p['id']] = p
        ready = {k: p for k, p in pool.items() if tick - attempts.get(k, -retry) >= retry}

        def closure(identity, trail=()):
            if identity in known:
                return []
            if identity in trail or identity not in ready:
                return None
            p = ready[identity]
            result = []
            if policy != 'no_dependencies':
                for dep in p['deps']:
                    branch = closure(dep, trail + (identity,))
                    if branch is None:
                        return None
                    result.extend(branch)
            result.append(p)
            return list({x['id']: x for x in result}.values())

        options = []
        for identity, p in ready.items():
            group = closure(identity) if policy in ('isoko', 'no_fairness', 'no_dependencies') else [p]
            if group is None:
                continue
            size = sum(len(encode({'type': 'data', 'packet': x})) for x in group)
            if size > budget:
                continue
            urgency = 1 / (1 + max(0, p['deadline'] - tick))
            utility = sum(x['value'] * (1 + x['risk'] + x['gap']) for x in group)
            if policy == 'fifo': key = -p['created']
            elif policy == 'edf': key = -p['deadline']
            elif policy == 'risk': key = p['risk']
            elif policy == 'density': key = p['value'] * (1 + p['risk'] + p['gap']) / size
            else:
                age = tick - service.get(p['learner'], p['created'])
                fairness = 1 if policy == 'no_fairness' else 1 + min(2, max(0, age) / 12)
                key = utility * (1 + urgency) * fairness / size
            options.append((key, identity, group))
        if not options:
            return []
        return max(options, key=lambda o: (o[0], o[1]))[2]

    def close(self):
        self.db.close()
