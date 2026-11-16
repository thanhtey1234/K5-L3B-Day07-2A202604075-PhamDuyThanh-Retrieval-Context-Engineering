import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from streamlit.testing.v1 import AppTest
from test_rag_core import chunk
from day7_rag.io import load_json, save_json

ROOT = Path(__file__).resolve().parents[1]


class WebTests(unittest.TestCase):
    def test_save_next_saves_only_current_review_and_opens_unreviewed_question(self):
        with tempfile.TemporaryDirectory() as d:
            directory = Path(d) / "runs" / "A"
            save_json(directory / "run.json", {"state": "complete", "manifest": {"mode": "agent", "split": "dev",
                "experiment": {"name": "A"}, "model": {"id": "test-model"}}, "records": [{
                "query_id": qid, "question": "Hoàn tiền bao lâu?", "status": "answered",
                "answer": "7 ngày [c1]", "citations": ["c1"], "original_results": [chunk()],
                "context": {"chunks": [chunk()], "ids": ["c1"]}} for qid in ("q1", "q2")]})
            with patch.dict("os.environ", {"RAG_WORK_DIR": d, "LLM_PROVIDER": "openrouter", "OPENROUTER_API_KEY": ""}), \
                    patch("day7_rag.providers.create_client", side_effect=AssertionError("No inference expected")):
                app = AppTest.from_file(str(ROOT / "streamlit_app.py"), default_timeout=20).run()
                app.switch_page("app_pages/experiments.py").run()
                app.selectbox(key="run_choice").set_value(str(directory / "run.json")).run()
                next(s for s in app.selectbox if s.label.startswith("Context:")).set_value(2)
                next(s for s in app.selectbox if s.label.startswith("Câu trả lời:")).set_value(2)
                next(c for c in app.checkbox if c.label == "Đã đối chiếu với tài liệu gốc").set_value(True)
                app.text_area[0].set_value("Test fixture: checked original source.")
                next(b for b in app.button if b.label == "Lưu và sang câu chưa chấm").click().run()
                self.assertFalse(app.exception)
                reviews = load_json(directory / "reviews.json")
                self.assertEqual([r["query_id"] for r in reviews], ["q1"])
                self.assertEqual(reviews[0]["citation_support"], [False])
                self.assertEqual(app.selectbox(key="review_query").value, "q2")
                self.assertIsNone(next(s for s in app.selectbox if s.label.startswith("Context:")).value)
                next(s for s in app.selectbox if s.label.startswith("Context:")).set_value(2)
                next(s for s in app.selectbox if s.label.startswith("Câu trả lời:")).set_value(2)
                next(c for c in app.checkbox if c.label == "Đã đối chiếu với tài liệu gốc").set_value(True)
                app.text_area[0].set_value("Test fixture: second source checked.")
                next(b for b in app.button if b.label == "Lưu nhãn").click().run()
                self.assertFalse(app.exception)
                self.assertEqual([r["query_id"] for r in load_json(directory / "reviews.json")], ["q1", "q2"])
                self.assertTrue(any("tất cả câu" in s.value for s in app.success))

    def test_grades_do_not_carry_between_runs_and_are_not_auto_saved(self):
        with tempfile.TemporaryDirectory() as d:
            dirs = [Path(d) / "runs" / name for name in ("A", "D")]
            for directory in dirs:
                save_json(directory / "run.json", {"state": "complete", "manifest": {"mode": "agent", "split": "dev",
                    "experiment": {"name": directory.name}, "model": {"id": "test-model"}}, "records": [{
                    "query_id": "q", "question": "Hoàn tiền bao lâu?", "status": "answered",
                    "answer": "7 ngày [c1]", "citations": ["c1"], "original_results": [chunk()],
                    "context": {"chunks": [chunk()], "ids": ["c1"]}}]})
            with patch.dict("os.environ", {"RAG_WORK_DIR": d, "LLM_PROVIDER": "openrouter", "OPENROUTER_API_KEY": ""}), \
                    patch("day7_rag.providers.create_client", side_effect=AssertionError("No inference expected")):
                app = AppTest.from_file(str(ROOT / "streamlit_app.py"), default_timeout=20).run()
                app.switch_page("app_pages/experiments.py").run()
                app.selectbox(key="run_choice").set_value(str(dirs[0] / "run.json")).run()
                self.assertFalse(app.exception)
                context = next(s for s in app.selectbox if s.label.startswith("Context:"))
                context.set_value(2).run()
                app.selectbox(key="run_choice").set_value(str(dirs[1] / "run.json")).run()
                self.assertFalse(app.exception)
                self.assertIsNone(next(s for s in app.selectbox if s.label.startswith("Context:")).value)
                self.assertFalse(any((p / "reviews.json").exists() for p in dirs))

    def test_navigation_and_keyword_search_work_without_api_requests(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d) / "corpora" / "day6"
            root.mkdir(parents=True)
            (root / "chunks.json").write_text(json.dumps([chunk()]), encoding="utf-8")
            (root / "manifest.json").write_text(json.dumps({"source_id": "doc", "source_url": "https://example.org"}), encoding="utf-8")
            with patch.dict("os.environ", {"RAG_WORK_DIR": d, "OPENROUTER_API_KEY": "", "LLM_PROVIDER": "openrouter"}), patch("day7_rag.openrouter.OpenRouter.complete", side_effect=AssertionError("No inference expected")):
                app = AppTest.from_file(str(ROOT / "streamlit_app.py"), default_timeout=20).run()
                self.assertFalse(app.exception)
                self.assertTrue(app.chat_input[0].disabled)
                app.segmented_control(key="chat_mode").set_value("Tìm từ khóa").run()
                app.chat_input[0].set_value("hoàn tiền").run()
                self.assertFalse(app.exception)
                self.assertTrue(any("7 ngày" in m.value for m in app.markdown))
                app.switch_page("app_pages/evidence.py").run()
                self.assertFalse(app.exception)
                self.assertTrue(any("7 ngày" in t.value for t in app.text))
                app.switch_page("app_pages/experiments.py").run()
                self.assertFalse(app.exception)


if __name__ == "__main__":
    unittest.main()
