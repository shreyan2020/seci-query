import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from sota_literature_workflow import WorkflowError, WorkflowTraceLogger, _dedupe_records, _parse_embeddings_payload


class SotaLiteratureWorkflowTests(unittest.TestCase):
    def test_dedupe_records_merges_sources_by_doi(self):
        records = [
            {
                "doi": "10.1000/example",
                "title": "Short abstract paper",
                "abstract": "short",
                "sources": ["openalex"],
            },
            {
                "doi": "https://doi.org/10.1000/example",
                "title": "Short abstract paper",
                "abstract": "this abstract is longer and should be kept",
                "sources": ["semantic_scholar"],
            },
        ]

        deduped = _dedupe_records(records)

        self.assertEqual(len(deduped), 1)
        self.assertEqual(deduped[0]["sources"], ["openalex", "semantic_scholar"])
        self.assertEqual(deduped[0]["abstract"], "this abstract is longer and should be kept")

    def test_trace_logger_writes_jsonl_and_keeps_trace(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            log_path = os.path.join(tmpdir, "workflow.jsonl")
            old_value = os.environ.get("SOTA_WORKFLOW_LOG_PATH")
            os.environ["SOTA_WORKFLOW_LOG_PATH"] = log_path
            try:
                logger = WorkflowTraceLogger(run_id="test_run")
                index = logger.start("capability_check", inputs={"query": "example"})
                event = logger.end(index, status="missing_capability", message="example missing", errors=["missing embedding backend"])

                self.assertEqual(event.run_id, "test_run")
                self.assertEqual(event.stage, "capability_check")
                self.assertEqual(event.status, "missing_capability")
                self.assertTrue(os.path.exists(log_path))
                with open(log_path, encoding="utf-8") as handle:
                    self.assertIn('"stage": "capability_check"', handle.read())
            finally:
                if old_value is None:
                    os.environ.pop("SOTA_WORKFLOW_LOG_PATH", None)
                else:
                    os.environ["SOTA_WORKFLOW_LOG_PATH"] = old_value

    def test_workflow_error_exposes_failed_stage_and_trace(self):
        logger = WorkflowTraceLogger(run_id="test_failure")
        index = logger.start("llm_query_decomposition")

        with self.assertRaises(WorkflowError) as context:
            logger.fail(index, "llm_query_decomposition", "LLM failed", RuntimeError("connection refused"))

        self.assertEqual(context.exception.stage, "llm_query_decomposition")
        self.assertEqual(context.exception.trace[-1].status, "error")
        self.assertIn("connection refused", str(context.exception))

    def test_parse_embeddings_payload_accepts_openai_style_data(self):
        embeddings = _parse_embeddings_payload(
            {
                "data": [
                    {"embedding": [1, 2, 3]},
                    {"embedding": [0.5, 0.25, 0.125]},
                ]
            }
        )

        self.assertEqual(embeddings, [[1.0, 2.0, 3.0], [0.5, 0.25, 0.125]])


if __name__ == "__main__":
    unittest.main()
