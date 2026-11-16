import tempfile
import unittest

from day7_rag.config import Experiment
from day7_rag.evaluation import audit_summary, freeze_config, package_hash, run_benchmark
from day7_rag.io import fingerprint
from day7_rag.retrieval import Retrieval
from test_rag_core import chunk


def case(cid="q", split="dev", answerable=True):
    value = {"id": cid, "split": split, "answerable": answerable, "question": "Hoàn tiền bao lâu?"}
    if answerable:
        value.update(expected_answer="7 ngày", gold=[{"source_id": "doc", "page": 1, "evidence": "7 ngày"}])
    else:
        value["absence_reason"] = "Original source checked"
    return value


class EvaluationTests(unittest.TestCase):
    def test_resume_is_idempotent_and_manifest_changes_rejected(self):
        e, chunks, cases = Experiment(method="bm25"), [chunk()], [case()]
        with tempfile.TemporaryDirectory() as d:
            r = Retrieval(chunks, e)
            first = run_benchmark(cases, chunks, r, e, d)
            second = run_benchmark(cases, chunks, r, e, d)
            self.assertEqual(first, second)
            self.assertEqual(len(second["records"]), 1)
            with self.assertRaises(ValueError):
                run_benchmark([case("another")], chunks, r, e, d)

    def test_test_split_requires_frozen_configuration(self):
        e, chunks = Experiment(method="bm25"), [chunk()]
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaisesRegex(ValueError, "frozen"):
                run_benchmark([case(split="test")], chunks, Retrieval(chunks, e), e, d, split="test")

    def test_advanced_counts_errors_in_full_denominator_and_no_rounding(self):
        cases = [case("ok", "test"), case("err", "test")]
        trace = {"query_id": "ok", "status": "answered", "answer": "7 ngày [c1]", "citations": ["c1"],
                 "context": {"ids": ["c1"], "chunks": [chunk()]}, "original_results": [chunk()],
                 "events": [{"event": "search"}]}
        error = {**trace, "query_id": "err", "status": "error"}
        job = {"state": "complete", "manifest": {"split": "test", "mode": "agent", "cases_hash": fingerprint(cases)}, "records": [trace, error]}
        labels = [{"query_id": "ok", "context_grade": 2, "answer_grade": 2,
                   "citation_support": [True], "reviewed_original_source": True, "reason": "Checked page 1"}]
        result = audit_summary(cases, job, labels, advanced=True)
        self.assertEqual(result["advanced_pass"], {"n": 1, "N": 2, "rate": .5})
        self.assertEqual(result["provider_errors"], 1)
        self.assertFalse(result["threshold_met"])

    def test_audit_rejects_unseen_citation_even_if_human_marks_true(self):
        trace = {"query_id": "q", "status": "answered", "answer": "7 ngày [missing]", "citations": ["missing"],
                 "context": {"ids": ["c1"], "chunks": [chunk()]}, "original_results": [chunk()], "events": []}
        job = {"state": "complete", "manifest": {"split": "dev", "mode": "agent", "cases_hash": fingerprint([case()])}, "records": [trace]}
        labels = [{"query_id": "q", "context_grade": 2, "answer_grade": 2, "citation_support": [True],
                   "reviewed_original_source": True, "reason": "Claimed"}]
        with self.assertRaisesRegex(ValueError, "absent"):
            audit_summary([case()], job, labels)

    def test_freeze_binds_review_to_real_dev_run(self):
        e, chunks = Experiment(method="bm25"), [chunk()]
        job = {"state": "complete", "manifest": {"split": "dev", "mode": "agent", "experiment": e.public(),
               "corpus_hash": fingerprint(chunks), "model": {"id": "test:free"}, "code_hash": package_hash()}}
        summary = {"run_hash": "unrelated", "review_hash": "x"}
        with self.assertRaises(ValueError):
            freeze_config(chunks, [case(split="test")], e, e, job, summary)


if __name__ == "__main__":
    unittest.main()
