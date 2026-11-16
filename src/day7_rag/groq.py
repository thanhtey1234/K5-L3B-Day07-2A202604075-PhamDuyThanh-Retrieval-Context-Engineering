"""Explicit Groq Free-tier adapter with shared request and token reservations.

Groq does not expose account billing tier in its model catalog. The user must
confirm Free tier locally; no zero-price catalog or cost report is invented.
"""

from contextlib import contextmanager
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from functools import lru_cache
import json
import math
from pathlib import Path
import re
import sqlite3
import time

import httpx

from .openrouter import CostViolation, ProviderError, QuotaPause


class TokenPause(QuotaPause):
    def __init__(self, message, wait_seconds=None):
        super().__init__(message)
        self.wait_seconds = wait_seconds


class TokenLedger:
    def __init__(self, path, *, daily_requests=900, daily_tokens=180000, tpm=7200, rpm=10):
        if not (1 <= daily_requests <= 1000 and 1 <= daily_tokens <= 200000
                and 1 <= tpm <= 8000 and 1 <= rpm <= 30):
            raise ValueError("Groq budgets must stay within the confirmed Free-tier limits")
        self.path = Path(path)
        self.daily_requests, self.daily_tokens, self.tpm, self.rpm = daily_requests, daily_tokens, tpm, rpm
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connection() as db:
            db.execute("CREATE TABLE IF NOT EXISTS reservations "
                       "(id INTEGER PRIMARY KEY, started REAL NOT NULL, day TEXT NOT NULL, tokens INTEGER NOT NULL)")

    @contextmanager
    def connection(self):
        db = sqlite3.connect(self.path, timeout=10)
        try:
            with db:
                yield db
        finally:
            db.close()

    def available(self):
        # Rolling 24h is more conservative than a calendar reset and cannot
        # reopen a provider budget early at local/UTC midnight.
        with self.connection() as db:
            n, tokens = db.execute("SELECT count(*), coalesce(sum(tokens),0) FROM reservations WHERE started > ?",
                                   (time.time() - 86400,)).fetchone()
        return {"requests": max(0, self.daily_requests - n), "tokens": max(0, self.daily_tokens - tokens)}

    def reserve(self, tokens):
        if tokens > self.tpm:
            raise ProviderError("Prompt và output dự phòng vượt token/phút; giảm context hoặc output trước khi chạy.")
        with self.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            now = time.time()
            recent = db.execute("SELECT started,tokens FROM reservations WHERE started > ? ORDER BY started",
                                (now - 86400,)).fetchall()
            if len(recent) >= self.daily_requests or sum(t for _, t in recent) + tokens > self.daily_tokens:
                raise TokenPause("Đạt ngân sách Groq trong 24 giờ; checkpoint được giữ.")
            minute = [(s, t) for s, t in recent if s > now - 60]
            if len(minute) >= self.rpm or sum(t for _, t in minute) + tokens > self.tpm:
                wait = max(1, math.ceil(minute[0][0] + 60 - now))
                raise TokenPause("Đang chờ ngân sách token/phút của Groq.", wait)
            row = db.execute("INSERT INTO reservations(started,day,tokens) VALUES (?,?,?)",
                             (now, datetime.now(timezone.utc).date().isoformat(), tokens))
            return row.lastrowid

    def settle(self, reservation, tokens):
        if type(tokens) is not int or tokens < 0:
            return  # Retain the conservative reservation if usage is missing.
        with self.connection() as db:
            db.execute("UPDATE reservations SET tokens=? WHERE id=?", (tokens, reservation))


@lru_cache(maxsize=2)
def load_tokenizer(cache_dir):
    from huggingface_hub import hf_hub_download
    from tokenizers import Tokenizer
    path = Path(hf_hub_download("Qwen/Qwen3.8-27B", "tokenizer.json", cache_dir=cache_dir,
                                revision="37561816e66b5b9153b1b64c10968c18c1e6f4a0"))
    return Tokenizer.from_file(str(path)), path.parent.name


class Groq:
    def __init__(self, settings, *, client=None, tokenizer=None):
        if not settings.groq_key:
            raise ValueError("Thiếu GROQ_API_KEY trong .env hoặc biến môi trường.")
        if not settings.groq_free_confirmed:
            raise ValueError("Chỉ dùng tài khoản Groq Free: cần xác nhận GROQ_FREE_TIER_CONFIRMED=true sau khi kiểm tra gói.")
        if settings.groq_model != "qwen/qwen3.8-27b":
            raise ValueError("Groq adapter chỉ cho phép model ảnh/tools đã kiểm tra: qwen/qwen3.8-27b")
        if not 1 <= settings.groq_max_output <= 2048:
            raise ValueError("Groq output budget must be 1..2048")
        self.settings, self.tokenizer = settings, tokenizer
        self.http = client or httpx.Client(
            base_url="https://api.groq.com/openai/v1/", timeout=settings.timeout,
            headers={"Authorization": f"Bearer {settings.groq_key}"})
        self.ledger = TokenLedger(settings.work_dir / "groq_requests.sqlite3",
                                  daily_requests=settings.groq_daily_requests,
                                  daily_tokens=settings.groq_daily_tokens, tpm=settings.groq_tokens_per_minute)
        self.calls, self.model_info = [], None

    def close(self):
        self.http.close()

    def preflight(self):
        try:
            response = self.http.get("models")
            response.raise_for_status()
            models = [m for m in response.json().get("data", []) if m.get("id") == self.settings.groq_model]
        except (httpx.HTTPError, ValueError) as exc:
            raise ProviderError("Groq metadata request failed; kiểm tra key/kết nối.") from exc
        if not models or models[0].get("active") is False:
            raise ProviderError("Groq model không khả dụng; không tự chuyển model.")
        revision = "test-injected" if self.tokenizer else None
        if self.tokenizer is None:
            try:
                self.tokenizer, revision = load_tokenizer(str(self.settings.work_dir / "tokenizers"))
            except Exception as exc:
                raise ProviderError("Không tải được tokenizer Qwen để dự phòng token; chưa gọi inference.") from exc
        self.model_info = {"provider": "groq", "id": self.settings.groq_model,
                           "created": models[0].get("created"), "owned_by": models[0].get("owned_by"),
                           "context_length": models[0].get("context_window", 131072),
                           "input_modalities": ["text", "image"], "tools": True,
                           "account_policy": "user_confirmed_free_tier_not_api_verified",
                           "tokenizer_revision": revision, "reasoning_effort": "none",
                           "temperature": 0, "max_output_tokens": self.settings.groq_max_output,
                           "capabilities_source": "https://console.groq.com/docs/model/qwen/qwen3.8-27b"}
        return {"model": self.model_info, "local_remaining": self.ledger.available(),
                "rate_policy": {"tokens_per_minute": self.ledger.tpm, "daily_tokens": self.ledger.daily_tokens},
                "billing_note": "Free tier do người dùng xác nhận; API không trả trạng thái gói thanh toán."}

    def ensure_capacity(self, required=1):
        remaining = self.ledger.available()
        if remaining["requests"] < required or remaining["tokens"] < self.settings.groq_max_output:
            raise TokenPause("Không đủ ngân sách Groq dự phòng; checkpoint được giữ.")

    def estimate_tokens(self, payload):
        # Count the actual text with the model tokenizer, plus chat/tool framing
        # margin, documented image input charges and the full output allowance.
        assert self.tokenizer is not None
        clean = json.loads(json.dumps(payload))
        images = 0
        for message in clean["messages"]:
            if isinstance(message.get("content"), list):
                for part in message["content"]:
                    if part.get("type") == "image_url":
                        images += 1
                        part["image_url"] = {"url": "<image>"}
        if images > 3:
            raise ProviderError("Groq model hỗ trợ tối đa ba ảnh trong một request")
        encoded = self.tokenizer.encode(json.dumps(clean, ensure_ascii=False), add_special_tokens=False)
        return len(encoded.ids) + 512 + images * 2048 + self.settings.groq_max_output

    def complete(self, messages, tools):
        if self.model_info is None:
            self.preflight()
        choice = {"type": "function", "function": {"name": tools[0]["function"]["name"]}} if len(tools) == 1 else "required"
        payload = {"model": self.settings.groq_model, "messages": messages, "tools": tools,
                   "tool_choice": choice, "parallel_tool_calls": False,
                   "temperature": 0, "reasoning_effort": "none", "reasoning_format": "hidden",
                   "max_completion_tokens": self.settings.groq_max_output}
        estimate = self.estimate_tokens(payload)
        for attempt in range(3):
            self.ensure_capacity()
            while True:
                try:
                    reservation = self.ledger.reserve(estimate)
                    break
                except TokenPause as exc:
                    if exc.wait_seconds is None:
                        raise
                    time.sleep(min(60, exc.wait_seconds))
            started = time.perf_counter()
            call = {"model": self.settings.groq_model, "provider": "groq", "attempt": attempt + 1,
                    "reserved_tokens": estimate}
            self.calls.append(call)
            try:
                response = self.http.post("chat/completions", json=payload)
            except httpx.HTTPError as exc:
                call.update(error="network", elapsed_ms=(time.perf_counter() - started) * 1000)
                if attempt == 2:
                    raise ProviderError("Groq network failure after 3 attempts") from exc
                time.sleep(2 ** attempt)
                continue
            call.update(http_status=response.status_code, elapsed_ms=(time.perf_counter() - started) * 1000)
            call["rate_limits"] = {k: response.headers[k] for k in (
                "x-ratelimit-remaining-requests", "x-ratelimit-remaining-tokens",
                "x-ratelimit-reset-tokens", "retry-after") if k in response.headers}
            if response.status_code == 429:
                call["error"] = "rate_limit"
                retry = response.headers.get("retry-after", "")
                if attempt < 2 and retry.isdigit() and int(retry) <= 60:
                    time.sleep(max(1, int(retry)))
                    continue
                raise TokenPause("Groq trả 429; checkpoint được giữ, không chuyển provider.")
            if response.status_code >= 500 and attempt < 2:
                call["error"] = "upstream"
                time.sleep(2 ** attempt)
                continue
            if response.status_code != 200:
                try:
                    error = response.json().get("error", {})
                    for key in ("code", "type", "param"):
                        value = error.get(key)
                        if isinstance(value, str) and re.fullmatch(r"[A-Za-z0-9_./:-]{1,80}", value):
                            call[f"error_{key}"] = value
                except (ValueError, AttributeError):
                    pass
                if response.status_code == 400 and call.get("error_code") == "tool_use_failed" and attempt < 2:
                    # Retry malformed provider-side tool output without retaining
                    # failed_generation or private reasoning in public artifacts.
                    time.sleep(1)
                    continue
                raise ProviderError(f"Groq HTTP {response.status_code}; không chuyển provider.")
            try:
                data = response.json()
                usage = data.get("usage") or {}
                call.update(request_id=data.get("id"), usage=usage, response_model=data.get("model"))
                self.ledger.settle(reservation, usage.get("total_tokens"))
                if usage.get("cost") is not None and Decimal(str(usage["cost"])) != 0:
                    raise CostViolation("Groq báo cost khác 0; dừng free-only job.")
                message = data["choices"][0]["message"]
                if not message.get("tool_calls"):
                    raise ProviderError("Groq model did not return the required tool call")
                return {"role": "assistant", "content": None, "tool_calls": message["tool_calls"]}
            except (ValueError, KeyError, IndexError, TypeError, InvalidOperation) as exc:
                raise ProviderError("Malformed Groq completion") from exc
        raise ProviderError("Groq attempts exhausted")
