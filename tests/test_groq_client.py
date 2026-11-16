from dataclasses import replace
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import httpx

from day7_rag.config import Settings
from day7_rag.groq import Groq, TokenLedger, TokenPause
from day7_rag.openrouter import CostViolation, ProviderError, SEARCH
from day7_rag.providers import create_client


class TestTokenizer:
    def encode(self, text, **kwargs):
        return SimpleNamespace(ids=text.split())


class GroqTests(unittest.TestCase):
    def make_client(self, directory, *, cost=None, status=200):
        settings = Settings(provider="groq", groq_key="not-real-groq-key", groq_free_confirmed=True,
                            work_dir=Path(directory))
        self.requests = []

        def handle(request):
            self.requests.append(request)
            if request.method == "GET":
                return httpx.Response(200, json={"data": [{"id": settings.groq_model, "active": True}]})
            usage = {"prompt_tokens": 50, "completion_tokens": 10, "total_tokens": 60}
            if cost is not None:
                usage["cost"] = cost
            return httpx.Response(status, json={"id": "groq-gen", "usage": usage, "choices": [{"message": {
                "reasoning": "private and must not be logged", "tool_calls": [{"id": "c1", "type": "function",
                "function": {"name": "search", "arguments": '{"query":"q"}'}}]}}]},
                headers={"x-ratelimit-remaining-tokens": "7900"})

        http = httpx.Client(base_url="https://api.groq.com/openai/v1/", transport=httpx.MockTransport(handle))
        return Groq(settings, client=http, tokenizer=TestTokenizer())

    def test_free_confirmation_and_secrets(self):
        settings = Settings(provider="groq", groq_key="private-groq-key")
        self.assertNotIn("private-groq-key", repr(settings))
        with self.assertRaises(ValueError):
            create_client(settings)
        with self.assertRaises(ValueError):
            Groq(replace(settings, groq_free_confirmed=True, groq_model="other/model"))
        with self.assertRaises(ValueError):
            create_client(replace(settings, provider="unknown"))

    def test_provider_payload_usage_and_no_fake_cost(self):
        with tempfile.TemporaryDirectory() as d:
            client = self.make_client(d)
            result = client.complete([{"role": "user", "content": "q"}], [SEARCH])
            post = next(r for r in self.requests if r.method == "POST")
            self.assertEqual(post.url.host, "api.groq.com")
            payload = json.loads(post.content)
            self.assertNotIn("provider", payload)
            self.assertEqual(payload["tool_choice"], {"type": "function", "function": {"name": "search"}})
            self.assertFalse(payload["parallel_tool_calls"])
            self.assertEqual(payload["reasoning_effort"], "none")
            self.assertNotIn("cost", client.calls[0]["usage"])
            self.assertNotIn("private and must not be logged", json.dumps([result, client.calls]))
            self.assertEqual(client.ledger.available()["tokens"], 180000 - 60)
            self.assertNotIn("pricing", client.model_info)
            client.close()

    def test_cost_violation_halts(self):
        with tempfile.TemporaryDirectory() as d:
            client = self.make_client(d, cost=.01)
            with self.assertRaises(CostViolation):
                client.complete([], [SEARCH])
            client.close()

    def test_failed_tool_generation_retries_without_exposing_provider_reasoning(self):
        with tempfile.TemporaryDirectory() as d:
            client = self.make_client(d)
            bad = httpx.Response(400, json={"error": {"code": "tool_use_failed",
                "failed_generation": "private generation", "type": "invalid_request_error"}})
            good = httpx.Response(200, json={"choices": [{"message": {"tool_calls": [{
                "id": "c", "function": {"name": "search", "arguments": '{"query":"q"}'}}]}}]})
            with patch.object(client.http, "post", side_effect=[bad, good]), patch("day7_rag.groq.time.sleep"):
                result = client.complete([], [SEARCH])
            self.assertEqual(len(client.calls), 2)
            self.assertEqual(client.calls[0]["error_code"], "tool_use_failed")
            self.assertNotIn("private generation", json.dumps([result, client.calls]))
            client.close()
    def test_429_preserves_checkpoint(self):
        with tempfile.TemporaryDirectory() as d:
            client = self.make_client(d, status=429)
            with self.assertRaises(TokenPause):
                client.complete([], [SEARCH])
            self.assertEqual(len(client.calls), 1)
            self.assertEqual(client.calls[0]["error"], "rate_limit")
            client.close()

    def test_shared_token_limits_and_rolling_window(self):
        with tempfile.TemporaryDirectory() as d, patch("day7_rag.groq.time.time", return_value=200000):
            a = TokenLedger(Path(d) / "budget.db", daily_tokens=200, tpm=100)
            b = TokenLedger(Path(d) / "budget.db", daily_tokens=200, tpm=100)
            r = a.reserve(80)
            with self.assertRaises(TokenPause) as pause:
                b.reserve(30)
            self.assertEqual(pause.exception.wait_seconds, 60)
            a.settle(r, 20)
            b.reserve(30)
            self.assertEqual(a.available()["tokens"], 150)
            with patch("day7_rag.groq.time.time", return_value=200061):
                # New minute, but the shared daily consumption remains.
                self.assertEqual(a.available()["tokens"], 150)
                a.reserve(100)
                with self.assertRaises(TokenPause) as pause:
                    b.reserve(60)
                self.assertIsNone(pause.exception.wait_seconds)

    def test_images_reserved_by_tokens_not_base64_bytes_and_limits_enforced(self):
        with tempfile.TemporaryDirectory() as d:
            client = self.make_client(d)
            client.preflight()
            image = {"type": "image_url", "image_url": {"url": "data:image/png;base64," + "X" * 100000}}
            payload = {"messages": [{"role": "user", "content": [image]}]}
            self.assertLess(client.estimate_tokens(payload), 5000)
            payload["messages"][0]["content"] *= 4
            with self.assertRaises(ProviderError):
                client.estimate_tokens(payload)
            with self.assertRaises(ProviderError):
                client.ledger.reserve(8001)
            with self.assertRaises(ValueError):
                TokenLedger(Path(d) / "over.db", daily_tokens=200001)
            client.close()


if __name__ == "__main__":
    unittest.main()
