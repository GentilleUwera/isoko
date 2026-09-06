# Isoko: an experimental delay-tolerant learning transport

Runnable communications software, without a frontend or third-party Python dependencies. Python 3.11+.

**Status:** working research prototype; novelty and superiority are not established. Initial results reject the claim that the proposed dependency-aware heuristic is consistently better than a simple utility-per-byte baseline. See [results](results/initial/summary.md) and [research assessment](docs/RESEARCH.md).

## Run the end-to-end demonstration

From this directory:

```sh
python3 -m isoko demo --out runs/demo
python3 -m unittest discover -s tests -v
```

Use a new output directory for each run. Existing databases are never overwritten by `demo`.

The demonstration starts **three separate Python processes** representing cloud, relay, and learner. Each has its own SQLite database. The controller transports serialized data and ACK frames through deterministic virtual-time links; workers communicate over local subprocess pipes. Nodes restart at tick 16 and reopen their durable state. The controller remains running.

The generated learner answers are explicitly synthetic. The manual workflow below lets you enter your own question and answer.

The default seed-42 run, at 2,048 bytes/contact with 15% data loss and 15% ACK loss, delivered usable questions to 8 of 12 synthetic learners and returned 8 responses. Six ACKs were still pending at the horizon. This is a reproducible scenario, not an outcome promise. The lossless generous-capacity test reaches all 12 and returns all 12 responses.

Outputs:

- `cloud.sqlite`, `relay.sqlite`, `learner.sqlite`: durable packets, peer acknowledgments, retry and service state.
- `trace.jsonl`: every transmitted frame, arrival outcome, contact budget and node restart.
- `metrics.json`: usable delivery, reach, response return, data/ACK/loss/duplicate bytes.
- `workload.json`, `cloud-final.json`: exact source packets and final cloud records.

## Transfer your own question and answer

These commands are separate invocations: data survives between them. Filenames encode the node roles; use the names shown. Contact commands emulate one instantaneous contact at the specified virtual tick. They do not open network sockets.

```sh
python3 -m isoko.session add --db runs/manual/cloud.sqlite --text "What is 2 + 2?"
python3 -m isoko.session contact --source runs/manual/cloud.sqlite --target runs/manual/relay.sqlite --tick 0
python3 -m isoko.session contact --source runs/manual/relay.sqlite --target runs/manual/learner.sqlite --tick 2
python3 -m isoko.session inbox --db runs/manual/learner.sqlite
```

Copy the question's `id` from the inbox, then:

```sh
python3 -m isoko.session answer --db runs/manual/learner.sqlite --question QUESTION_ID --text "4" --tick 3
python3 -m isoko.session contact --source runs/manual/learner.sqlite --target runs/manual/relay.sqlite --tick 4
python3 -m isoko.session contact --source runs/manual/relay.sqlite --target runs/manual/cloud.sqlite --tick 6
python3 -m isoko.session inbox --db runs/manual/cloud.sqlite
```

`QUESTION_ID` is a placeholder to replace. Contact options include `--budget`, `--loss`, `--ack-loss`, `--seed` and `--policy`. Failed contacts leave the source queue intact. Advance at least four ticks before retrying a previously attempted packet. To demonstrate recovery, drop a contact with `--loss 1`, then run a later one with `--loss 0`. A zero-byte budget sends nothing.

## Communications mechanism

The candidate scheduler selects a packet together with its unacknowledged prerequisite closure, respecting the entire closure's serialized byte cost. It scores closure value per byte, with deadline urgency and a bounded service-age multiplier. Nodes use **their own ACK history**, not receiver inventory, to decide what the peer knows. Retries, duplicate suppression and expiry are part of the protocol implementation, not success counters added afterward.

ACKs consume capacity and can be lost. Duplicate reception is harmless at the packet-storage layer and causes another ACK. Idempotence applies to identical packet IDs; this is not a general exactly-once distributed transaction guarantee.

See [protocol and mathematical definition](docs/PROTOCOL.md) for precisely what is implemented and which features are not.

## Reproduce the experiments

```sh
python3 -m isoko benchmark --seeds 20 --out results/reproduction
```

560 runs = 20 seeds × 2 budgets × 2 loss settings × 7 policies. Experiments include an outage, delayed ACKs, node restarts, and both forward and reverse traffic. Baselines are FIFO, earliest deadline first, risk-only and utility density; ablations remove dependencies or the service-age multiplier. This is not a RAPID or RaDiO implementation.

Batch experiments use in-process adapters for speed, with the same serialization, SQLite logic and event model. A test verifies identical metrics between that adapter and the three-process implementation.

Included results use 20 paired seeds per setting. Approximate normal 95% intervals describe per-seed useful-value differences, without multiple-testing correction. The raw CSV includes adverse results; no winning seeds were selected.

## What this does not establish

- No physical LoRa radio, mesh routing, RF propagation, regulatory airtime compliance, battery measurement, or real-world delivery rate.
- No BPv7 interoperability: this is a custom JSON experimental protocol inspired by DTN concepts.
- No socket-level or kernel network emulation: frames travel over local IPC through a virtual-time impairment controller. Byte budgets include serialized protocol frames, not pipe-control JSON, IP headers or physical-layer overhead.
- No optimal scheduling, learned contact prediction, coding, fragmentation, compression, or hard fairness guarantee.
- Node restarts are supported; resuming a crashed controller and its in-flight event queue is not implemented.
- No production authentication, encryption, bounded-storage eviction or real student records. Packet hashing detects accidental content alteration; it does not authenticate a sender.
- Educational utility and workloads are assumptions, not learning outcomes. Synthetic text sizes and utility choices affect rankings.

The initial hypothesis is not supported strongly enough for a novelty/superiority claim. A credible submission should present this as an implemented evaluation platform with measured tradeoffs, unless a subsequent mechanism earns a stronger claim.

## Repository layout

`isoko/core.py` — durable protocol state, wire encoding, scheduling.

`isoko/worker.py` — isolated node process.

`isoko/experiment.py` — impairment controller, workload, trace and metrics.

`isoko/session.py` — manual author / contact / learner-answer workflow.

`tests/test_network.py` — protocol, process, restart and end-to-end checks.

`.github/workflows/test.yml` — automated tests on Python 3.11, 3.12 and 3.13. All three jobs passed in the [initial GitHub Actions run](https://github.com/GentilleUwera/isoko/actions/runs/34031300419).

Repository: https://github.com/GentilleUwera/isoko. Licensing and final authorship should be agreed with the team; no open-source license has been selected yet.
