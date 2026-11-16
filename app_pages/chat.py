import json
from datetime import datetime, timezone

import streamlit as st

from day7_rag.agent import run_agent
from day7_rag.config import Experiment
from day7_rag.io import fingerprint, save_json
from day7_rag.openrouter import ProviderError, QuotaPause
from day7_rag.providers import create_client
from day7_rag.retrieval import BM25
from day7_rag.ui import ROOT, corpus_root, read, runtime, settings

st.title("Hỏi đáp có bằng chứng")
st.caption("Chọn tài liệu, đặt câu hỏi và đối chiếu câu trả lời với nguồn gốc.")
root, cfg = corpus_root(), settings()
ready = (root / "chunks.json").exists()
mode = st.segmented_control("Cách tra cứu", ["Hỏi agent", "Tìm từ khóa"], default="Hỏi agent", key="chat_mode")
config_name = st.selectbox("Cấu hình truy xuất", ["A-dense", "B-bm25", "C-hybrid", "D-context", "E-multihop"],
                         index=3, key="experiment_choice")
experiment = Experiment.read(ROOT / "configs" / f"{config_name}.json")
key = str(root)
history = st.session_state["conversations"].setdefault(key, [])

if st.button("Cuộc trò chuyện mới", icon=":material/restart_alt:", key="reset_chat"):
    st.session_state["conversations"][key] = []
    st.session_state["latest_evidence"].pop(key, None)
    st.session_state["pending_questions"].pop(key, None)
    st.rerun()

for item in history:
    with st.chat_message(item["role"]):
        st.markdown(item["text"])

pending = st.session_state["pending_questions"].get(key)
resume = False
if pending:
    st.info(pending["result"]["reason"])
    resume = st.button("Tiếp tục câu đang chờ", key="resume_question", disabled=not cfg.active_key)
question = st.chat_input("Bạn muốn tìm hiểu điều gì trong tài liệu?", key="question", submit_mode="disable",
                         disabled=not ready or (mode == "Hỏi agent" and not cfg.active_key) or bool(pending))
if question or resume:
    prompt = pending["question"] if resume else question
    if not resume:
        history.append({"role": "user", "text": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)
    with st.chat_message("assistant"):
        if mode == "Tìm từ khóa" and not resume:
            rows = BM25(read(root / "chunks.json")).search(prompt, top_k=6)
            st.session_state["latest_evidence"][key] = rows
            if rows:
                text = "\n\n".join(f"**[{c['id']}] · Trang {c['page']}**\n\n{c['text']}" for c in rows)
                st.markdown(text)
                history.append({"role": "assistant", "text": text})
                st.caption("Kết quả từ khóa trực tiếp; chưa phải câu trả lời do agent tổng hợp.")
            else:
                st.info("Chưa tìm được đoạn khớp từ khóa. Thử diễn đạt lại câu hỏi.")
        else:
            client = None
            try:
                active_experiment = Experiment(**pending["experiment"]) if resume else experiment
                with st.status("Đang tìm bằng chứng", expanded=True) as status:
                    chunks, retriever = runtime(root, active_experiment, cfg)
                    client = create_client(cfg)
                    client.preflight()

                    def show_event(event):
                        if event["event"] == "search":
                            st.caption(f"Tìm: {event['query']} · {len(event['results'])} đoạn")
                        elif event["event"] == "view_image":
                            st.caption(f"Đối chiếu hình gốc trang {event['page']}")

                    result = run_agent(prompt, client, retriever, active_experiment, asset_root=root,
                                       checkpoint=pending["result"]["checkpoint"] if resume else None,
                                       on_event=show_event)
                    status.update(label="Đang chờ quota" if result["status"] == "pending" else "Đã kết thúc truy xuất",
                                  state="error" if result["status"] == "error" else "complete", expanded=False)
                if result["status"] == "pending":
                    st.session_state["pending_questions"][key] = {"question": prompt, "result": result,
                                                                 "experiment": active_experiment.public()}
                    st.info(result["reason"])
                else:
                    st.session_state["pending_questions"].pop(key, None)
                    history.append({"role": "assistant", "text": result["answer"]})
                    st.markdown(result["answer"])
                    st.session_state["latest_evidence"][key] = result["context"]["chunks"]
                    st.caption("Mở trang Bằng chứng để đối chiếu từng citation.")
                name = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S") + "-" + fingerprint(prompt)[:8]
                save_json(cfg.work_dir / "chat" / f"{name}.json", {"question": prompt, **result})
                with st.expander("Chi tiết truy xuất"):
                    st.json(result.get("events", []))
                st.download_button("Tải trace", json.dumps(result, ensure_ascii=False, indent=2),
                                   file_name="trace.json", mime="application/json", key="download_trace")
            except Exception as exc:
                message = str(exc) if isinstance(exc, (ValueError, ProviderError, QuotaPause)) else "Kiểm tra kết nối, quota và cấu hình trong README."
                st.error(message, title="Chưa thể trả lời")
            finally:
                if client:
                    client.close()
