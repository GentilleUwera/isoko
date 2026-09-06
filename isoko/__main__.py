import argparse
import csv
import json
import statistics
import tempfile
from pathlib import Path
from .core import POLICIES
from .experiment import run


def main():
    parser = argparse.ArgumentParser(description='Isoko: synthetic workloads over emulated links')
    sub = parser.add_subparsers(dest='command', required=True)
    demo = sub.add_parser('demo', help='Isolated durable node processes; mid-run restart')
    demo.add_argument('--out', default='runs/demo')
    demo.add_argument('--seed', type=int, default=42)
    demo.add_argument('--budget', type=int, default=2048)
    demo.add_argument('--loss', type=float, default=.15)
    demo.add_argument('--ack-loss', type=float, default=.15)
    demo.add_argument('--delay', type=int, default=1)
    demo.add_argument('--policy', choices=POLICIES, default='isoko')
    bench = sub.add_parser('benchmark')
    bench.add_argument('--out', default='results')
    bench.add_argument('--seeds', type=int, default=20)
    args = parser.parse_args()
    if args.command == 'demo':
        result = run(args.out, seed=args.seed, budget=args.budget, loss=args.loss, ack_loss=args.ack_loss, delay=args.delay, policy=args.policy, processes=True)
        print(json.dumps(result, indent=2))
        print(f'Node databases and trace: {args.out}')
    else:
        if args.seeds < 2: parser.error('Use at least two seeds')
        root = Path(args.out)
        root.mkdir(parents=True, exist_ok=True)
        if (root / 'raw.csv').exists(): parser.error('Choose a fresh output directory')
        rows = []
        with tempfile.TemporaryDirectory() as tmp:
            for budget in (1024, 4096):
                for loss in (0., .2):
                    for seed in range(1, args.seeds + 1):
                        for policy in POLICIES:
                            rows.append(run(Path(tmp) / str(len(rows)), seed=seed, budget=budget, loss=loss, ack_loss=loss, policy=policy))
        with (root / 'raw.csv').open('w', newline='') as out:
            writer = csv.DictWriter(out, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)
        lines = ['# Synthetic experiment', '', f'{len(rows)} runs; seeds 1–{args.seeds}. Same workloads, contacts and keyed per-packet loss draws across policies.', '',
                 'Useful value is assumed utility, not measured learning. Approximate 95% normal intervals below use paired differences across seeds (Isoko minus comparator).', '',
                 '| Budget | Loss | Comparator | Mean useful-value difference | Approx. 95% interval |', '|---:|---:|---|---:|---|']
        for budget in (1024, 4096):
            for loss in (0., .2):
                selected = {(r['seed'], r['policy']): r for r in rows if r['budget']==budget and r['loss']==loss}
                for other in POLICIES[1:]:
                    differences = [selected[s, 'isoko']['usable_value'] - selected[s, other]['usable_value'] for s in range(1, args.seeds+1)]
                    mean = statistics.mean(differences)
                    radius = 1.96 * statistics.stdev(differences) / len(differences)**.5
                    lines.append(f'| {budget} | {loss} | {other} | {mean:.3f} | [{mean-radius:.3f}, {mean+radius:.3f}] |')
        lines += ['', 'No correction for multiple comparisons. Inspect reach, returned responses and overhead in raw.csv. No universal superiority or novelty is established.']
        (root / 'summary.md').write_text('\n'.join(lines) + '\n')
        print(f'{len(rows)} runs saved to {root}')

if __name__ == '__main__': main()
