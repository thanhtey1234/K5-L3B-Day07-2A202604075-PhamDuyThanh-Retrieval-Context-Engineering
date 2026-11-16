from dataclasses import replace
import json
from pathlib import Path
import tempfile
import unittest

import httpx

from day7_rag.config import Settings
from day7_rag.openrouter import OpenRouter, ProviderError, SEARCH


class OpenRouterTests(unittest.TestCase):
    def client(self, directory, *, price="0", modalities=None, params=None, completion=None):
        cfg = Settings(api_key="test-only-not-a-real-key", work_dir=Path(directory))
        self.requests = []

        def handle(request):
            self.requests.append(request)
            if request.url.path.endswith("/models"):
                data = {"data": [{"id": cfg.model, "canonical_slug": "revision-1",
                                  "architecture": {"input_modalities": modalities or ["text", "image"]},
                                  "supported_parameters": params or ["tools", "tool_choice"],
                                  "pricing": {"prompt": price, "completion": "0"}}]}
            elif request.url.path.endswith("/key"):
                data = {"data": {"free_model_daily_requests": {"remaining": 50}}}
            else:
                data = completion or {"id": "gen-test", "usage": {"cost": 0}, "choices": [{"message": {
                    "tool_calls": [{"id": "tool", "type": "function", "function": {"name": "search", "arguments": '{"query":"q"}'}}]}}]}
            return httpx.Response(200, json=data)

        http = httpx.Client(base_url=cfg.base_url + "/", transport=httpx.MockTransport(handle))
        return OpenRouter(cfg, client=http)

    def test_free_only_and_capabilities_checked_before_inference(self):
        with tempfile.TemporaryDirectory() as d:
            for kwargs in ({"price": "0.01"}, {"modalities": ["text"]}, {"params": ["max_tokens"]}):
                client = self.client(d, **kwargs)
                with self.assertRaises(ProviderError):
                    client.preflight()
                self.assertFalse(any(r.method == "POST" for r in self.requests))

    def test_payload_cannot_fall_back_to_paid_models(self):
        with tempfile.TemporaryDirectory() as d:
            client = self.client(d)
            client.complete([{"role": "user", "content": "q"}], [SEARCH])
            post = next(r for r in self.requests if r.method == "POST")
            payload = json.loads(post.content)
            self.assertTrue(payload["model"].endswith(":free"))
            self.assertFalse(payload["provider"]["allow_fallbacks"])
            self.assertNotIn("models", payload)
            self.assertEqual(client.ledger.available(), 44)

    def test_paid_id_rejected_and_secrets_not_in_settings_repr(self):
        cfg = Settings(api_key="secret-value", database_url="postgresql://private")
        self.assertNotIn("secret-value", repr(cfg))
        self.assertNotIn("postgresql://private", repr(cfg))
        with self.assertRaises(ValueError):
            OpenRouter(replace(cfg, model="paid/model"))


if __name__ == "__main__":
    unittest.main()
