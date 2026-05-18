# Benchmark Report: scifact_sample10

- Generated: 2026-05-16T12:04:36.104309+00:00
- Corpus documents: 5183
- Queries: 10
- Metric cutoff: @10

## Retrieval Metrics

| Mode | Precision | Recall | nDCG | MAP | MRR | Queries |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| baseline | 0.0800 | 0.7500 | 0.6849 | 0.6583 | 0.6667 | 10 |

## Notes

- `baseline` uses the benchmark query text only.
- `ontology` appends query-specific ontology expansion terms, reasoning lenses, and tacit context from the augmentation file.
- The JSON report includes per-query ontology audit records for stakeholder inspection.
