import json
import base64
from pathlib import Path
import tempfile
import unittest

from day7_rag.agent import run_agent
from day7_rag.config import Experiment
from day7_rag.context import pack_context, token_upper_bound
from day7_rag.contracts import has_evidence, runtime_question, validate_cases, validate_chunks
from day7_rag.io import safe_asset
from day7_rag.openrouter import CostViolation, QuotaPause, RequestLedger
from day7_rag.retrieval import BM25, Retrieval, matches_filter, rrf
from day7_rag.store import filter_sql
from convert_day6 import convert_question


def chunk(cid="c1", text="Hoàn tiền trong 7 ngày.", page=1, **extra):
    return {"id": cid, "text": text, "source_id": "doc", "source": "doc.pdf", "page": page,
            "metadata": {"year": 2025, "enabled": True}, **extra}


def action(name, **arguments):
    return {"role": "assistant", "content": None, "tool_calls": [{"id": "call1", "type": "function",
            "function": {"name": name, "arguments": json.dumps(arguments)}}]}


class FakeClient:
    """Only for behavioral tests. Never exposed by CLI as a quality benchmark."""
    def __init__(self, actions):
        self.actions, self.calls, self.messages = iter(actions), [], []

    def ensure_capacity(self, required=1):
        pass

    def complete(self, messages, tools):
        self.messages.append(messages)
        value = next(self.actions)
        if isinstance(value, Exception):
            raise value
        self.calls.append({"usage": {"cost": 0}})
        return value


class CoreTests(unittest.TestCase):
    def test_bm25_unicode_filters_and_empty_query(self):
        rows = [chunk(), chunk("c2", "Giao hàng trong 3 ngày.", year=2024)]
        index = BM25(rows)
        self.assertEqual(index.search("HOÀN TIỀN")[0]["id"], "c1")
        self.assertEqual(index.search("xyz khôngkhớp"), [])
        self.assertEqual(index.search("hoàn tiền", filters={"year": 2024}), [])
        self.assertTrue(matches_filter(rows[0], {"enabled": True, "page": 1}))

    def test_filter_values_are_bound_not_interpolated(self):
        clauses, values = filter_sql({"page": 1, "enabled": True, "chapter": "x' OR true --"})
        self.assertNotIn("x' OR", " ".join(clauses))
        self.assertEqual(values[0], 1)
        self.assertEqual(json.loads(values[1]), {"enabled": True})

    def test_rrf_ignores_raw_score_scale(self):
        a, b = chunk(), chunk("c2")
        rows = rrf([("dense", [{**b, "score": .9}, {**a, "score": .1}]),
                    ("bm25", [{**a, "score": 9999}, {**b, "score": 1}])])
        self.assertEqual(rows[0]["id"], "c1")
        self.assertAlmostEqual(rows[0]["score"], rows[1]["score"])
        self.assertEqual(set(rows[0]["contributions"]), {"dense", "bm25"})

    def test_context_refreshes_and_budget_counts_source_headers(self):
        old, new = chunk("old", "old"), chunk("new", "new")
        context = pack_context([[old], [new]], budget=50, max_chunks=1)
        self.assertEqual(context["ids"], ["new"])
        self.assertLessEqual(token_upper_bound(context["text"]), 50)
        self.assertEqual(pack_context([[old]], budget=1)["ids"], [])

    def test_multihop_uses_and_within_alternative_sets(self):
        first, second = chunk(), chunk("c2", "Điều kiện là có hóa đơn.", 2)
        case = {"evidence_sets": [[{"source_id": "doc", "page": 1, "evidence": "7 ngày"},
                                   {"source_id": "doc", "page": 2, "evidence": "có hóa đơn"}]]}
        self.assertFalse(has_evidence([first], case))
        self.assertTrue(has_evidence([first, second], case))

    def test_runtime_allowlist_and_unanswerable_conversion(self):
        q = {"id": "u", "split": "dev", "question": "q", "answerable": False,
             "absence_reason": "Checked original source", "expected_answer": "secret", "gold": ["secret"]}
        self.assertEqual(runtime_question(q), {"question": "q", "filters": None})
        converted = convert_question(q)
        self.assertFalse(converted["answerable"])
        self.assertEqual(converted["absence_reason"], q["absence_reason"])
        validate_cases([converted])

    def test_real_dense_required(self):
        retriever = Retrieval([chunk()], Experiment())
        with self.assertRaisesRegex(ValueError, "PostgreSQL"):
            retriever.search("q")

    def test_agent_calls_tool_and_only_cites_selected_context(self):
        client = FakeClient([action("search", query="hoàn tiền"),
                             action("final_answer", status="answered", answer="7 ngày [c1]", citations=["c1"])])
        e = Experiment(method="bm25")
        result = run_agent("Bao lâu?", client, Retrieval([chunk()], e), e)
        self.assertEqual(result["status"], "answered")
        self.assertEqual(result["context"]["ids"], ["c1"])
        self.assertEqual(result["events"][0]["query"], "hoàn tiền")
        self.assertNotIn("expected_answer", json.dumps(client.messages))

    def test_agent_invalid_citations_and_explicit_abstention(self):
        e = Experiment(method="bm25")
        for final in (action("final_answer", status="answered", answer="7 ngày [missing]", citations=["missing"]),
                      action("final_answer", status="abstain", answer="Chưa đủ bằng chứng.", citations=[])):
            client = FakeClient([action("search", query="q"), final])
            result = run_agent("q", client, Retrieval([chunk()], e), e)
            self.assertEqual(result["status"], "abstain")
            self.assertEqual(result["citations"], [])

    def test_pending_resumes_without_repeating_search(self):
        e = Experiment(method="bm25")
        client = FakeClient([action("search", query="hoàn tiền"), QuotaPause("quota")])
        r = Retrieval([chunk()], e)
        first = run_agent("q", client, r, e)
        self.assertEqual(first["status"], "pending")
        resumed = FakeClient([action("final_answer", status="answered", answer="7 ngày [c1]", citations=["c1"])])
        final = run_agent("q", resumed, r, e, checkpoint=first["checkpoint"])
        self.assertEqual(final["status"], "answered")
        self.assertEqual(sum(ev["event"] == "search" for ev in final["events"]), 1)
        self.assertEqual(len(final["model_calls"]), 2)

    def test_provider_error_is_not_an_abstention(self):
        e = Experiment(method="bm25")
        client = FakeClient([RuntimeError("secret key must not be logged")])
        result = run_agent("q", client, Retrieval([chunk()], e), e)
        self.assertEqual(result["status"], "error")
        self.assertNotIn("secret key", json.dumps(result))

    def test_ledger_shared_budget_and_asset_traversal(self):
        with tempfile.TemporaryDirectory() as d:
            a = RequestLedger(Path(d) / "requests.db", daily_budget=1)
            b = RequestLedger(Path(d) / "requests.db", daily_budget=1)
            a.take()
            self.assertEqual(b.available(), 0)
            with self.assertRaises(QuotaPause):
                b.take()
            with self.assertRaises(ValueError):
                safe_asset(d, "../secret.env")

    def test_chunk_validation_rejects_ambiguous_citation_ids(self):
        with self.assertRaises(ValueError):
            validate_chunks([chunk("[bad]")])

    def test_visual_answer_requires_actual_image_view(self):
        with tempfile.TemporaryDirectory() as d:
            Path(d, "tiny.png").write_bytes(base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+aZWkAAAAASUVORK5CYII="))
            rows = [chunk(content_type="image", image="tiny.png")]
            e = Experiment(method="bm25")
            final = action("final_answer", status="answered", answer="7 ngày [c1]", citations=["c1"])
            no_view = FakeClient([action("search", query="hoàn tiền"), final])
            self.assertEqual(run_agent("q", no_view, Retrieval(rows, e), e, asset_root=d)["status"], "abstain")
            viewed = FakeClient([action("search", query="hoàn tiền"), action("view_image", chunk_id="c1"), final])
            result = run_agent("q", viewed, Retrieval(rows, e), e, asset_root=d)
            self.assertEqual(result["status"], "answered")
            self.assertIn("data:image/png;base64", json.dumps(viewed.messages[-1]))
            self.assertNotIn("base64", json.dumps(result))

    def test_checkpoint_rejects_config_change(self):
        e = Experiment(method="bm25")
        r = Retrieval([chunk()], e)
        result = run_agent("q", FakeClient([QuotaPause("quota")]), r, e)
        with self.assertRaisesRegex(ValueError, "configuration"):
            run_agent("q", FakeClient([]), r, Experiment(method="bm25", max_searches=4), checkpoint=result["checkpoint"])

    def test_cost_policy_halts_a_benchmark_instead_of_continuing(self):
        from day7_rag.evaluation import run_benchmark
        from test_evaluation_pipeline import case
        with tempfile.TemporaryDirectory() as d:
            e = Experiment(method="bm25")
            client = FakeClient([CostViolation("Stop")])
            client.model_info = {"id": "test:free"}
            job = run_benchmark([case("q1"), case("q2")], [chunk()], Retrieval([chunk()], e), e, d, client=client)
            self.assertEqual(job["state"], "halted_cost_policy")
            self.assertEqual(len(job["records"]), 1)

    def test_invalid_configuration_and_filters_are_rejected(self):
        with self.assertRaises(ValueError):
            Experiment(name="../escape")
        e = Experiment(method="bm25")
        r = Retrieval([chunk()], e)
        with self.assertRaises(ValueError):
            r.search("q", top_k=0)
        with self.assertRaises(ValueError):
            r.search("q", filters={"year": float("nan")})


if __name__ == "__main__":
    unittest.main()
