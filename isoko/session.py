"""Manual store-and-forward workflow, with isolated worker processes per contact."""
import argparse
import json
import random
from pathlib import Path
from .core import Node, POLICIES, packet, encode
from .experiment import Process


def contact(source, target, tick, budget, loss=0., ack_loss=0., seed=42, policy='isoko'):
    if budget < 0 or not 0 <= loss <= 1 or not 0 <= ack_loss <= 1:
        raise ValueError('Invalid link settings')
    source, target = Path(source), Path(target)
    if source.resolve() == target.resolve(): raise ValueError('Contact requires distinct nodes')
    a, b = Process(source), Process(target)
    rng = random.Random(seed)
    used, accepted, duplicates, lost, acknowledgments = 0, 0, 0, 0, 0
    try:
        while used < budget:
            group = a.call('select', peer=target.stem, tick=tick, budget=budget-used, policy=policy)
            if not group: break
            # Send selected data group first; ACKs use what remains after it.
            receipts = []
            for p in group:
                wire = encode(dict(type='data', packet=p))
                used += len(wire)
                a.call('attempted',peer=target.stem,p=p,tick=tick)
                if rng.random() < loss:
                    lost += 1
                    continue
                result = b.call('receive',p=json.loads(wire)['packet'],tick=tick)
                if result['accepted']:
                    accepted += not result['duplicate']
                    duplicates += result['duplicate']
                    receipts.append(encode(dict(type='ack',id=p['id'])))
            for wire in receipts:
                if used + len(wire) > budget: continue
                used += len(wire)
                if rng.random() >= ack_loss:
                    a.call('ack',peer=target.stem,identity=json.loads(wire)['id'])
                    acknowledgments += 1
        return dict(bytes=used,budget=budget,new_packets=accepted,duplicates=duplicates,dropped_packets=lost,acknowledged=acknowledgments)
    finally:
        a.close()
        b.close()


def main():
    parser=argparse.ArgumentParser(description='Manual Isoko node operations; node filenames must be cloud.sqlite, relay.sqlite, learner.sqlite')
    sub=parser.add_subparsers(dest='command',required=True)
    add=sub.add_parser('add')
    add.add_argument('--db',required=True)
    add.add_argument('--text',required=True)
    add.add_argument('--learner',default='L001')
    add.add_argument('--deadline',type=int,default=100)
    add.add_argument('--tick',type=int,default=0)
    inbox=sub.add_parser('inbox')
    inbox.add_argument('--db',required=True)
    answer=sub.add_parser('answer')
    answer.add_argument('--db',required=True)
    answer.add_argument('--question',required=True)
    answer.add_argument('--text',required=True)
    answer.add_argument('--tick',type=int,required=True)
    link=sub.add_parser('contact')
    link.add_argument('--source',required=True)
    link.add_argument('--target',required=True)
    link.add_argument('--tick',type=int,required=True)
    link.add_argument('--budget',type=int,default=2048)
    link.add_argument('--loss',type=float,default=0.)
    link.add_argument('--ack-loss',type=float,default=0.)
    link.add_argument('--seed',type=int,default=42)
    link.add_argument('--policy',choices=POLICIES,default='isoko')
    args=parser.parse_args()
    if args.command=='contact':
        print(json.dumps(contact(args.source,args.target,args.tick,args.budget,args.loss,args.ack_loss,args.seed,args.policy),indent=2))
        return
    path=Path(args.db)
    path.parent.mkdir(parents=True,exist_ok=True)
    node=Node(path)
    try:
        if args.command=='inbox': result=node.items()
        elif args.command=='add':
            result=packet(args.learner,'question',args.text,args.tick,args.deadline)
            node.receive(result,args.tick)
        else:
            question=next((p for p in node.items() if p['id']==args.question and p['kind']=='question'),None)
            if question is None: raise ValueError('Question not present in this node')
            result=packet(question['learner'],'response',json.dumps(dict(question=args.question,answer=args.text)),args.tick,args.tick+100,destination='cloud')
            node.receive(result,args.tick)
        print(json.dumps(result,indent=2,ensure_ascii=False))
    finally: node.close()

if __name__=='__main__': main()
