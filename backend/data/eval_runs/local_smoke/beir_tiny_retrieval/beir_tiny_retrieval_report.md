# Benchmark Report: beir_tiny

- Generated: 2026-05-16T11:48:51.723020+00:00
- Corpus documents: 4
- Queries: 2
- Metric cutoff: @10

## Retrieval Metrics

| Mode | Precision | Recall | nDCG | MAP | MRR | Queries |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| baseline | 0.2000 | 0.8333 | 0.9536 | 0.8333 | 1.0000 | 2 |
| ontology | 0.2500 | 1.0000 | 0.9936 | 0.9583 | 1.0000 | 2 |

## Ontology Lift

| Metric | Delta |
| --- | ---: |
| precision_at_k | +0.0500 |
| recall_at_k | +0.1667 |
| ndcg_at_k | +0.0399 |
| map | +0.1250 |
| mrr | +0.0000 |

## Notes

- `baseline` uses the benchmark query text only.
- `ontology` appends query-specific ontology expansion terms, reasoning lenses, and tacit context from the augmentation file.
- The JSON report includes per-query ontology audit records for stakeholder inspection.
