from copy import deepcopy
import unittest

from day7_rag.config import Experiment
from day7_rag.evaluation import package_hash
from day7_rag.io import fingerprint
from scripts.automated_review import MODE, freeze, summarize
from test_evaluation_pipeline import case
from test_rag_core import chunk


class AutomatedReviewTests(unittest.TestCase):
    def fixture(self, config=None):
        config = config or Experiment()
        cases, chunks = [case()], [chunk()]
        job = {"state": "complete", "manifest": {"mode": "agent", "split": "dev",
            "cases_hash": fingerprint(cases), "code_hash": package_hash(), "corpus_hash": fingerprint(chunks),
            "experiment": config.public(), "model": {"id": "test-model"}}, "records": [{
                "query_id": "q", "status": "answered", "answer": "7 ngày [c1]", "citations": ["c1"],
                "context": {"chunks": chunks, "ids": ["c1"]}, "original_results": chunks,
                "events": [{"event": "search"}]}]}
        labels = [{"query_id": "q", "reviewer_type": "ai", "reviewer": "test reviewer",
            "reviewed_original_source": False, "ai_reviewed_source": True, "source_pdf_sha256": "source-sha",
            "source_pages": [1], "reason": "Source supports the answer", "context_grade": 2,
            "answer_grade": 2, "citation_support": [True], "abstention_correct": False}]
        return cases, chunks, job, labels

    def test_ai_provenance_is_explicit_and_cannot_claim_human_review(self):
        cases, _, job, labels = self.fixture()
        summary = summarize(cases, job, labels, "source-sha")
        self.assertEqual(summary["evaluation_mode"], MODE)
        self.assertFalse(summary["human_verified"])
        self.assertEqual(summary["grounded_complete"]["n"], 1)
        labels[0]["reviewed_original_source"] = True
        with self.assertRaises(ValueError):
            summarize(cases, job, labels, "source-sha")

    def test_supported_citation_and_complete_split_are_still_required(self):
        cases, _, job, labels = self.fixture()
        job["records"][0]["context"]["ids"] = []
        with self.assertRaises(ValueError):
            summarize(cases, job, labels, "source-sha")
        _, _, job, labels = self.fixture()
        with self.assertRaises(ValueError):
            summarize(cases, job, [], "source-sha")
        with self.assertRaises(ValueError):
            summarize(cases, job, labels, "different-source")

    def test_freeze_binds_ai_review_to_unchanged_runtime_source_and_model(self):
        a, d = Experiment(), Experiment(name="D", top_k=6)
        cases, chunks, first, labels = self.fixture(a)
        _, _, second, _ = self.fixture(d)
        summaries = [summarize(cases, job, labels, "source-sha") for job in (first, second)]
        frozen = freeze(chunks, [case("test", "test")], a, d, [first, second], summaries, "source-sha")
        self.assertFalse(frozen["human_verified"])
        self.assertEqual(frozen["test_hash"], fingerprint([case("test", "test")]))
        changed = deepcopy(summaries)
        changed[1]["run_hash"] = "edited"
        with self.assertRaises(ValueError):
            freeze(chunks, [case("test", "test")], a, d, [first, second], changed, "source-sha")


if __name__ == "__main__":
    unittest.main()
