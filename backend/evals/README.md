# Biomedical Evaluation Harness

This package evaluates the workbench against standardized biomedical retrieval data and produces stakeholder-friendly reports.

The first runner supports BEIR-style retrieval benchmarks such as TREC-COVID, BioASQ exports, NFCorpus, and SciFact. It compares:

- `baseline`: benchmark query only
- `ontology`: query plus ontology expansion terms, reasoning lenses, and tacit context from a JSON augmentation file

It also includes a normalized ontology/entity/relation extraction evaluator for datasets such as BioRED, CRAFT, BC5CDR, and ChemProt after conversion to the JSONL shape below.

## Suite Runner

Use the suite runner when you want one command to run multiple benchmark tasks and write aggregate reports.

From `backend`:

```powershell
python -m evals.run_suite `
  --config evals/suites/local_smoke.json `
  --output-dir data/eval_runs/local_smoke
```

Outputs:

- `data/eval_runs/local_smoke/suite_summary.json`
- `data/eval_runs/local_smoke/suite_summary.md`
- One subdirectory per benchmark task with its detailed JSON and Markdown reports.

The local smoke suite runs:

- BEIR-style retrieval over `evals/fixtures/beir_tiny`
- normalized extraction scoring over `evals/fixtures/extraction_tiny`

## Server Run

For a higher-resource server, copy the repository plus prepared benchmark data, then edit:

- `evals/suites/server_biomed_template.json`

Populate each task's `data_dir`, `gold`, `predictions`, and optional `augmentation_file`, then set `"enabled": true` for the tasks you want to run.

Linux/macOS server:

```bash
bash evals/scripts/run_server_suite.sh \
  evals/suites/server_biomed_template.json \
  data/eval_runs/server_biomed
```

Windows server:

```powershell
.\evals\scripts\run_server_suite.ps1 `
  -Config evals/suites/server_biomed_template.json `
  -OutputDir data/eval_runs/server_biomed
```

If you want to dry-run a template and see skipped tasks in the aggregate report, leave them disabled. If you want to force all tasks to run regardless of `enabled`, pass `--include-disabled` to the Python runner or `-IncludeDisabled` to the PowerShell script.

## Retrieval Smoke Test

From `backend`:

```powershell
python -m evals.run_benchmarks `
  --benchmark beir `
  --data-dir evals/fixtures/beir_tiny `
  --augmentation-file evals/fixtures/beir_tiny/ontology_augmentation.json `
  --name beir_tiny `
  --output-dir data/eval_runs/beir_tiny
```

Outputs:

- `data/eval_runs/beir_tiny/beir_tiny_retrieval_report.json`
- `data/eval_runs/beir_tiny/beir_tiny_retrieval_report.md`

## Standard Benchmarks To Use

Recommended first pass:

- BEIR `trec-covid`: biomedical ad hoc retrieval with relevance judgments.
- BEIR `nfcorpus`: biomedical/nutrition retrieval.
- BEIR `scifact`: scientific claim/evidence retrieval.
- BioASQ Task B exports: biomedical QA retrieval and answer evaluation.

Recommended second pass:

- BioRED: biomedical entity/relation extraction and novelty/background distinction.
- CRAFT: ontology concept annotation on full biomedical articles.
- BC5CDR / ChemProt: targeted biomedical relation extraction.

## Extraction Smoke Test

From `backend`:

```powershell
python -m evals.extraction_metrics `
  --gold evals/fixtures/extraction_tiny/gold.jsonl `
  --predictions evals/fixtures/extraction_tiny/predictions.jsonl `
  --output-dir data/eval_runs/extraction_tiny `
  --name extraction_tiny
```

This evaluator expects normalized JSONL exports. BioRED, CRAFT, BC5CDR, and ChemProt can be converted into this shape:

```json
{
  "paper_id": "PMID-or-dataset-id",
  "entities": [
    {"id": "e1", "label": "malonyl-CoA", "type": "chemical"}
  ],
  "relations": [
    {"source": "e1", "relation": "precursor_for", "target": "e2"}
  ]
}
```

## Augmentation File Format

The ontology mode expects a JSON object keyed by benchmark query id:

```json
{
  "q-1": {
    "expanded_terms": ["malonyl-CoA", "p-coumaric acid"],
    "reasoning_lenses": ["precursor supply bottleneck"],
    "tacit_context": ["Prefer direct yeast evidence before broad analogies."],
    "search_routing": ["literature", "paper_claims"]
  }
}
```

The report stores these additions in `ontology_audit`, so a stakeholder can inspect exactly what ontology context was added on top of each raw query.

## Metrics

Retrieval reports include:

- Precision@K
- Recall@K
- nDCG@K
- MAP
- MRR

These are standard information-retrieval metrics used by TREC/BEIR-style evaluations.

Extraction reports include:

- entity precision, recall, and F1
- relation precision, recall, and F1
- per-paper entity/relation breakdowns

The suite summary surfaces the primary metrics for each task and links to the detailed reports.

## Suggested Data Layout

The server template assumes this layout under `backend`:

```text
data/
  benchmarks/
    beir/
      trec-covid/
        corpus.jsonl
        queries.jsonl
        qrels/test.tsv
      nfcorpus/
      scifact/
    augmentations/
      trec-covid_ontology.json
      nfcorpus_ontology.json
      scifact_ontology.json
    extraction/
      biored/gold.jsonl
      craft/gold.jsonl
      bc5cdr/gold.jsonl
      chemprot/gold.jsonl
  predictions/
    biored_ontology.jsonl
    craft_ontology.jsonl
    bc5cdr_ontology.jsonl
    chemprot_ontology.jsonl
```

The runners do not download datasets. That keeps local smoke tests deterministic and makes server runs explicit about the exact benchmark snapshots being used.

## Download Public BEIR Data

To fetch public BEIR datasets into the expected local layout:

```powershell
python -m evals.fetch_beir --datasets scifact --output-root data/benchmarks/beir
```

For a quick real benchmark sample after downloading SciFact:

```powershell
python -m evals.generate_system_augmentations `
  --data-dir data/benchmarks/beir/scifact `
  --output-file data/benchmarks/augmentations/scifact_sample10_system.json `
  --audit-file data/benchmarks/augmentations/scifact_sample10_system_audit.json `
  --name scifact `
  --max-queries 10

python -m evals.run_suite `
  --config evals/suites/scifact_sample10.json `
  --output-dir data/eval_runs/scifact_sample10
```

This uses the real BEIR SciFact corpus and qrels, but caps the run to the first 10 scored test queries for local turnaround. The augmentation step uses only the benchmark query, then derives project goal, objective cluster, collaborator lens, tacit memory, and ontology query augmentation through the same deterministic backend modules used when user-provided context is absent. Remove `max_queries` from the suite config and generation command to run the full SciFact query set.
