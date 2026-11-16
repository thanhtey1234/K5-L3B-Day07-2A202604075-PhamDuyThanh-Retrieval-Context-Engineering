"""OpenRouter tool calling with a zero-paid-cost policy and durable request ledger."""

from datetime import datetime, timezone
from contextlib import contextmanager
from decimal import Decimal, InvalidOperation
import json
from pathlib import Path
import sqlite3
import time
from typing import Any

import httpx


class QuotaPause(RuntimeError):
    """The job must checkpoint rather than turn an unattempted case into a failure."""


class ProviderError(RuntimeError):
    pass


class CostViolation(ProviderError):
    pass


class RequestLedger:
    def __init__(self, path, *, daily_budget=45, rpm=10):
        if daily_budget < 1 or rpm < 1:
            raise ValueError("Request budgets must be positive")
        self.path, self.daily_budget, self.rpm = Path(path), daily_budget, rpm
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connection() as db:
            db.execute("CREATE TABLE IF NOT EXISTS requests (started REAL NOT NULL, day TEXT NOT NULL)")

    @contextmanager
    def connection(self):
        db = sqlite3.connect(self.path, timeout=10)
        try:
            with db:
                yield db
        finally:
            db.close()

    @staticmethod
    def day():
        return datetime.now(timezone.utc).date().isoformat()

    def available(self):
        with self.connection() as db:
            used = db.execute("SELECT count(*) FROM requests WHERE day = ?", (self.day(),)).fetchone()[0]
        return max(0, self.daily_budget - used)

    def take(self):
        # IMMEDIATE makes concurrent UI/CLI requests share the same local budget.
        with self.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            day, now = self.day(), time.time()
            used = db.execute("SELECT count(*) FROM requests WHERE day = ?", (day,)).fetchone()[0]
            recent = db.execute("SELECT count(*) FROM requests WHERE started > ?", (now - 60,)).fetchone()[0]
            if used >= self.daily_budget:
                raise QuotaPause("Đã đạt ngân sách request trong ngày; chạy tiếp vào ngày sau.")
            if recent >= self.rpm:
                raise QuotaPause("Đạt giới hạn request/phút; giữ checkpoint và thử lại sau 60 giây.")
            db.execute("INSERT INTO requests VALUES (?,?)", (now, day))


class OpenRouter:
    def __init__(self, settings, *, client=None):
        if not settings.api_key:
            raise ValueError("Thiếu OPENROUTER_API_KEY; cấu hình trong .env hoặc biến môi trường.")
        if settings.base_url.rstrip("/") != "https://openrouter.ai/api/v1":
            raise ValueError("Free-only mode requires the official OpenRouter endpoint")
        if not settings.model.endswith(":free"):
            raise ValueError("Chỉ chấp nhận model ID kết thúc bằng :free")
        self.settings = settings
        self.http = client or httpx.Client(
            base_url=settings.base_url.rstrip("/") + "/", timeout=settings.timeout,
            headers={"Authorization": f"Bearer {settings.api_key}", "X-Title": "Day7 Evidence RAG"},
        )
        self.ledger = RequestLedger(settings.work_dir / "requests.sqlite3",
                                    daily_budget=settings.daily_budget, rpm=settings.requests_per_minute)
        self.model_info = None
        self.remote_remaining = None
        self.calls = []

    def close(self):
        self.http.close()

    def _get(self, path):
        try:
            response = self.http.get(path)
            response.raise_for_status()
            return response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise ProviderError(f"OpenRouter metadata request failed: {path}") from exc

    def preflight(self):
        listing = self._get("models")
        models = [m for m in listing.get("data", []) if m.get("id") == self.settings.model]
        if not models:
            raise ProviderError("Model miễn phí đã chọn không còn trong catalog; chọn lại trên dev.")
        info = models[0]
        params = set(info.get("supported_parameters", []))
        modalities = info.get("architecture", {}).get("input_modalities", [])
        if not {"tools", "tool_choice"}.issubset(params) or "image" not in modalities:
            raise ProviderError("Model phải hỗ trợ tools, tool_choice và ảnh")
        pricing = info.get("pricing", {})
        if not {"prompt", "completion"}.issubset(pricing):
            raise ProviderError("Không xác minh được giá model")
        try:
            if any(Decimal(str(v)) != 0 for v in pricing.values()):
                raise ProviderError("Free-only guard: catalog reports a nonzero price")
        except InvalidOperation as exc:
            raise ProviderError("Không xác minh được giá model") from exc
        key = self._get("key").get("data", {})
        free = key.get("free_model_daily_requests", {})
        remaining = free.get("remaining")
        self.remote_remaining = remaining if type(remaining) is int else None
        self.model_info = {k: info.get(k) for k in
                           ("id", "canonical_slug", "context_length", "architecture", "pricing", "supported_parameters")}
        return {"model": self.model_info, "local_remaining": self.ledger.available(),
                "remote_remaining": self.remote_remaining}

    def ensure_capacity(self, required=1):
        available = self.ledger.available()
        if self.remote_remaining is not None:
            available = min(available, self.remote_remaining)
        if available < required:
            raise QuotaPause(f"Còn {available} request, cần dự phòng {required}; tiếp tục sau khi quota reset.")

    def complete(self, messages, tools):
        if self.model_info is None:
            self.preflight()
        assert self.model_info is not None
        payload = {"model": self.settings.model, "messages": messages, "tools": tools,
                   "tool_choice": "required", "temperature": 0, "max_tokens": 2048,
                   "provider": {"require_parameters": True, "allow_fallbacks": False}}
        if "reasoning" in self.model_info.get("supported_parameters", []):
            payload["reasoning"] = {"enabled": False, "exclude": True}
        for attempt in range(3):
            self.ensure_capacity()
            self.ledger.take()
            if self.remote_remaining is not None:
                self.remote_remaining = max(0, self.remote_remaining - 1)
            started = time.perf_counter()
            call: dict[str, Any] = {"model": self.settings.model, "attempt": attempt + 1}
            self.calls.append(call)
            try:
                response = self.http.post("chat/completions", json=payload)
            except httpx.HTTPError as exc:
                call.update(error="network", elapsed_ms=(time.perf_counter() - started) * 1000)
                if attempt == 2:
                    raise ProviderError("OpenRouter network failure after 3 attempts") from exc
                time.sleep(2 ** attempt)
                continue
            call.update(http_status=response.status_code, elapsed_ms=(time.perf_counter() - started) * 1000)
            if response.status_code == 429:
                call["error"] = "rate_limit"
                retry = response.headers.get("Retry-After", "")
                if attempt == 2 or not retry.isdigit() or int(retry) > 30:
                    raise QuotaPause("OpenRouter trả 429; checkpoint đã được giữ.")
                time.sleep(max(1, int(retry)))
                continue
            if response.status_code >= 500 and attempt < 2:
                call["error"] = "upstream"
                time.sleep(2 ** attempt)
                continue
            if response.status_code != 200:
                raise ProviderError(f"OpenRouter HTTP {response.status_code}; không chuyển model tự động")
            try:
                data = response.json()
                call.update(request_id=data.get("id"), provider=data.get("provider"),
                            usage=data.get("usage", {}), response_model=data.get("model"))
                if Decimal(str(call["usage"].get("cost", 0))) != 0:
                    raise CostViolation("Free-only guard: API reported a nonzero cost; stopping")
                message = data["choices"][0]["message"]
                if not message.get("tool_calls"):
                    raise ProviderError("Model did not return the required tool call")
                # Reasoning fields are deliberately not retained in artifacts/UI.
                return {"role": "assistant", "content": message.get("content"),
                        "tool_calls": message["tool_calls"]}
            except (ValueError, KeyError, IndexError, TypeError) as exc:
                raise ProviderError("Malformed OpenRouter completion") from exc
        raise ProviderError("OpenRouter attempts exhausted")


def tool(name, description, properties, required):
    return {"type": "function", "function": {"name": name, "description": description,
            "parameters": {"type": "object", "properties": properties,
                           "required": required, "additionalProperties": False}}}


SEARCH = tool("search", "Search the selected corpus for evidence. Reformulate only from the user's question or retrieved data.",
              {"query": {"type": "string", "minLength": 1}}, ["query"])
VIEW = tool("view_image", "Inspect an original image/crop from the currently selected evidence.",
            {"chunk_id": {"type": "string"}}, ["chunk_id"])
FINAL = tool("final_answer", "Finish with a Vietnamese cited answer, or explicitly abstain when evidence is insufficient.",
             {"status": {"type": "string", "enum": ["answered", "abstain"]},
              "answer": {"type": "string", "description": "Vietnamese answer. For answered status, insert literal [chunk-id] citations after claims in this text, using the exact IDs from current evidence. Listing IDs only in the citations field is insufficient."},
              "citations": {"type": "array", "items": {"type": "string"},
                            "description": "Unique current-evidence chunk IDs, exactly matching all [chunk-id] citations written inside answer."}},
             ["status", "answer", "citations"])


def parse_call(call):
    try:
        name = call["function"]["name"]
        arguments = json.loads(call["function"]["arguments"])
        if not isinstance(arguments, dict):
            raise ValueError("arguments must be an object")
        return name, arguments
    except (KeyError, ValueError, TypeError) as exc:
        raise ProviderError("Invalid tool arguments") from exc
