# Prior work and novelty assessment

Research checked on 6 September 2026 through the Codex in-app browser. This is an initial screening, not an exhaustive literature review. Search snippets and AI overviews are not treated as evidence.

## Primary sources inspected

| Source | What was read | Implication for Isoko |
| --- | --- | --- |
| [RFC 9171: Bundle Protocol Version 7](https://www.rfc-editor.org/rfc/rfc9171.html), 2022 | Introduction, service discussion, processing and administrative-report sections | Store-carry-forward operation, intermittent contacts, expiration and reports are established. The standard leaves route computation outside its scope and explains that BP alone does not ensure end-to-end delivery. |
| [Balasubramanian, Levine and Venkataramani: DTN Routing as a Resource Allocation Problem](https://researchconnect.stonybrook.edu/en/publications/dtn-routing-as-a-resource-allocation-problem/), SIGCOMM 2007, [DOI](https://doi.org/10.1145/1282380.1282422) | Abstract and bibliographic record at an author's institution | RAPID translates routing objectives into packet utilities and includes deadline delivery objectives. Utility-based prioritization over disrupted networks is not new. The full algorithm has not been reproduced here. |
| [Chou and Sehgal: Rate-Distortion Optimized Receiver-Driven Streaming over Best-Effort Networks](https://www.microsoft.com/en-us/research/wp-content/uploads/2016/02/ChouS02a.pdf) | First-page abstract in the original Microsoft-hosted PDF | Receiver-side packet selection under a transmission-rate constraint to minimize reconstruction distortion is established. This is relevant adjacent work on application-aware communication utility, not a claim that its exact model equals Isoko's. |

## Working hypothesis, not a novelty claim

Dependency-closure scheduling, deadline urgency and service-age weighting might improve useful learning-content delivery over a shared, intermittent two-way link, when receiver knowledge arrives only through lossy acknowledgments.

The implementation makes that hypothesis concrete: an actual candidate algorithm, a consistent protocol stack, packet traces, four baselines and two ablations. A combination of established ideas is not automatically a research contribution.

## What the initial experiment says

At 1,024 bytes/contact and no loss, Isoko's mean assumed useful value exceeds FIFO by 6.025 units, but is 0.824 units below the density baseline. At 4,096 bytes/contact and 20% data/ACK loss, it is 4.047 units below density. Removing dependency closure also improves several settings.

The proposed mechanism therefore does not earn a superiority claim. A plausible explanation to investigate is conservative closure admission: stale ACK knowledge and whole-closure fit can delay content that a packetwise scheduler sends incrementally. This is an interpretation, not a demonstrated causal conclusion. The ablation provides evidence that dependency handling as implemented is not consistently beneficial.

## What remains before claiming novelty

1. Read the full RAPID paper and adjacent packet-dependency / rate-distortion scheduling work, including Chou–Miao and rich-acknowledgment work. The initial search identified this literature but did not complete a full-text comparison.
2. Check modern semantic/task-oriented communication, age/urgency-of-information scheduling, and deadline-aware DTN work. No absence claim is justified by this screening.
3. Specify an alternative mechanism addressing a demonstrated failure: for example, incremental prerequisite scheduling with explicit uncertainty about unacknowledged delivery. That direction may itself have prior art.
4. Implement the closest applicable published baseline faithfully, or explain why its model cannot be compared directly. Current density is a simple baseline, not RAPID under another name.
5. Evaluate on independent held-out seeds, richer dependency graphs, unequal contact opportunities, variable reverse-channel budgets, changing arrival rates, and sensitivity to utility definitions. Test against real traces if a legitimate dataset becomes available.
6. Only then write a narrowly scoped contribution statement, with differences mapped to sources and benefits supported by results.

Suggested current wording: “We implement and evaluate a persistent, dependency-aware delay-tolerant content-delivery prototype with explicit acknowledgment costs and reproducible synthetic impairments. Experiments expose tradeoffs and limitations relative to simpler scheduling policies.”
