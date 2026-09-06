# Synthetic experiment

560 runs; seeds 1–20. Same workloads, contacts and keyed per-packet loss draws across policies.

Useful value is assumed utility, not measured learning. Approximate 95% normal intervals below use paired differences across seeds (Isoko minus comparator).

| Budget | Loss | Comparator | Mean useful-value difference | Approx. 95% interval |
|---:|---:|---|---:|---|
| 1024 | 0.0 | fifo | 6.025 | [4.895, 7.155] |
| 1024 | 0.0 | edf | 7.639 | [6.385, 8.893] |
| 1024 | 0.0 | risk | 4.143 | [3.128, 5.157] |
| 1024 | 0.0 | density | -0.824 | [-1.412, -0.237] |
| 1024 | 0.0 | no_dependencies | -0.248 | [-0.405, -0.091] |
| 1024 | 0.0 | no_fairness | -0.149 | [-0.666, 0.369] |
| 1024 | 0.2 | fifo | 5.647 | [4.795, 6.500] |
| 1024 | 0.2 | edf | 5.783 | [4.729, 6.837] |
| 1024 | 0.2 | risk | 4.440 | [2.978, 5.902] |
| 1024 | 0.2 | density | -0.528 | [-1.254, 0.198] |
| 1024 | 0.2 | no_dependencies | 0.107 | [-0.327, 0.540] |
| 1024 | 0.2 | no_fairness | -0.153 | [-0.597, 0.290] |
| 4096 | 0.0 | fifo | 2.335 | [0.865, 3.806] |
| 4096 | 0.0 | edf | -0.336 | [-2.223, 1.552] |
| 4096 | 0.0 | risk | -2.539 | [-4.688, -0.390] |
| 4096 | 0.0 | density | -4.934 | [-6.559, -3.310] |
| 4096 | 0.0 | no_dependencies | -4.613 | [-6.255, -2.971] |
| 4096 | 0.0 | no_fairness | 0.225 | [-0.070, 0.520] |
| 4096 | 0.2 | fifo | 5.285 | [3.635, 6.935] |
| 4096 | 0.2 | edf | 5.016 | [3.367, 6.664] |
| 4096 | 0.2 | risk | 0.620 | [-0.871, 2.111] |
| 4096 | 0.2 | density | -4.047 | [-5.156, -2.938] |
| 4096 | 0.2 | no_dependencies | -3.093 | [-4.164, -2.021] |
| 4096 | 0.2 | no_fairness | 0.000 | [0.000, 0.000] |

No correction for multiple comparisons. Inspect reach, returned responses and overhead in raw.csv. No universal superiority or novelty is established.
