"""Drive a localhost Streamlit agent API without making any LLM request."""
import argparse
from pathlib import Path
import json

import httpx

parser = argparse.ArgumentParser()
parser.add_argument("--url", default="http://127.0.0.1:8765")
args = parser.parse_args()
root = Path("work/qa")
root.mkdir(parents=True, exist_ok=True)
with httpx.Client(base_url=args.url, timeout=120) as client:
    protocol = client.get("/_stcore/agent/openapi.json").json()
    (root / "streamlit-openapi.json").write_text(json.dumps(protocol, ensure_ascii=False, indent=2), encoding="utf-8")
    print("Protocol:", protocol.get("info"))
    steps = [{}, {"widget_state": {"chat_mode": "Tìm từ khóa"}},
             {"trigger": {"key": "question", "value": "An ninh thông tin mạng bảo đảm tính khả dụng không?"}},
             {"page": "evidence"}, {"page": "experiments"}]
    session = None
    for i, body in enumerate(steps):
        if session:
            body["session_id"] = session
        response = client.post("/_stcore/agent/interact", json=body)
        response.raise_for_status()
        snapshot = response.json()
        session = snapshot.get("session_id", session)
        (root / f"ui-{i}.json").write_text(json.dumps(snapshot, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps(snapshot, ensure_ascii=False, indent=2))
        if snapshot.get("status") != "ready":
            raise RuntimeError("UI did not finish successfully")
print("All localhost UI checks passed; no inference endpoint was called.")
