import json
import tempfile
import unittest
from pathlib import Path
from isoko.core import Node, packet, encode, POLICIES
from isoko.experiment import run

class ProtocolTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / 'cloud.sqlite'
        self.node = Node(self.path)
    def tearDown(self):
        self.node.close()
        self.tmp.cleanup()
    def test_integrity_expiry_duplicates(self):
        p=packet('A','question','é: 1+1?',deadline=5)
        self.assertFalse(self.node.receive(p,0)['duplicate'])
        self.assertTrue(self.node.receive(p,1)['duplicate'])
        self.assertEqual(len(self.node.items()),1)
        self.assertFalse(self.node.receive(p,6)['accepted'])
        with self.assertRaises(ValueError): self.node.receive(dict(p,text='changed'),0)
    def test_durable_ack(self):
        p=packet('A','question','?')
        self.node.receive(p,0)
        self.node.ack('relay',p['id'])
        self.node.close()
        self.node=Node(self.path)
        self.assertEqual(len(self.node.items()),1)
        self.assertEqual(self.node.select('relay',10,10000),[])
    def test_dependency_closure_and_budget(self):
        q=packet('A','question','?',value=.01)
        h=packet('A','hint','hint',deps=[q['id']],value=100)
        for p in (q,h): self.node.receive(p,0)
        cost=sum(len(encode(dict(type='data',packet=p))) for p in (q,h))
        self.assertEqual([p['id'] for p in self.node.select('relay',0,cost)],[q['id'],h['id']])
        self.assertLessEqual(sum(len(encode(dict(type='data',packet=p))) for p in self.node.select('relay',0,cost-1)),cost-1)
        self.assertEqual(self.node.select('relay',0,0),[])
    def test_missing_dependency_and_retry(self):
        p=packet('A','hint','hint',deps=['missing'])
        self.node.receive(p,0)
        self.assertEqual(self.node.select('relay',0,10000),[])
        self.assertEqual(len(self.node.select('relay',0,10000,'no_dependencies')),1)
        self.node.attempted('relay',p,0)
        self.assertEqual(self.node.select('relay',1,10000,'no_dependencies'),[])
        self.assertEqual(len(self.node.select('relay',4,10000,'no_dependencies')),1)
    def test_destination_not_forwarded(self):
        self.node.receive(packet('A','response','1',destination='cloud'),0)
        self.assertEqual(self.node.select('relay',0,10000),[])

class EndToEndTests(unittest.TestCase):
    def test_process_equivalence_roundtrip(self):
        with tempfile.TemporaryDirectory() as d:
            a=run(Path(d)/'a',processes=True,budget=100000,loss=0,ack_loss=0)
            b=run(Path(d)/'b',budget=100000,loss=0,ack_loss=0)
            self.assertTrue(a.pop('processes'))
            b.pop('processes')
            self.assertEqual(a,b)
            self.assertEqual(a['learners_reached'],12)
            self.assertEqual(a['responses_returned'],12)
            self.assertEqual(a['orphan_packets'],0)
    def test_loss_and_zero_capacity(self):
        with tempfile.TemporaryDirectory() as d:
            for i,kw in enumerate(({'loss':1},{'budget':0})):
                r=run(Path(d)/str(i),**kw)
                self.assertEqual(r['learners_reached'],0)
                self.assertEqual(r['responses_returned'],0)
    def test_ack_loss_idempotence(self):
        with tempfile.TemporaryDirectory() as d:
            r=run(d,budget=100000,loss=0,ack_loss=1,learners=2)
            self.assertEqual(r['responses_returned'],2)
            self.assertGreater(r['duplicate_bytes'],0)
    def test_capacity_and_reproducibility(self):
        with tempfile.TemporaryDirectory() as d:
            for policy in POLICIES:
                path=Path(d)/policy
                r=run(path,policy=policy,loss=.3,budget=1024)
                logs=[json.loads(s) for s in (path/'trace.jsonl').read_text().splitlines()]
                for e in logs:
                    if e['event']=='contact': self.assertLessEqual(e['used'],e['capacity'])
                self.assertEqual(sum(e['bytes'] for e in logs if e['event']=='transmit'),r['data_bytes']+r['ack_bytes'])
                again=run(Path(d)/(policy+'again'),policy=policy,loss=.3,budget=1024)
                self.assertEqual(r,again)
                self.assertEqual((path/'trace.jsonl').read_bytes(),(Path(d)/(policy+'again')/'trace.jsonl').read_bytes())
    def test_existing_run_preserved(self):
        with tempfile.TemporaryDirectory() as d:
            run(d,ticks=1)
            with self.assertRaises(ValueError): run(d)

if __name__=='__main__': unittest.main()

class ManualTests(unittest.TestCase):
    def test_manual_lesson_and_answer(self):
        from isoko.session import contact
        with tempfile.TemporaryDirectory() as d:
            paths={n:Path(d)/(n+'.sqlite') for n in ('cloud','relay','learner')}
            q=packet('A','question','What is 2+2?',deadline=100)
            node=Node(paths['cloud']); node.receive(q,0); node.close()
            self.assertEqual(contact(paths['cloud'],paths['relay'],0,2048)['new_packets'],1)
            self.assertEqual(contact(paths['relay'],paths['learner'],2,2048)['new_packets'],1)
            node=Node(paths['learner'])
            self.assertEqual(node.items()[0]['text'],'What is 2+2?')
            response=packet('A','response',json.dumps({'question':q['id'],'answer':'4'}),3,100,destination='cloud')
            node.receive(response,3); node.close()
            contact(paths['learner'],paths['relay'],4,2048)
            contact(paths['relay'],paths['cloud'],6,2048)
            node=Node(paths['cloud'])
            self.assertEqual([p['text'] for p in node.items() if p['kind']=='response'],[response['text']])
            node.close()
