import streamlit as st

from day7_rag.io import fingerprint, save_json
from day7_rag.pdf import evidence_preview
from day7_rag.reporting import display_rate
from day7_rag.ui import ROOT, read, run_paths, settings

st.title("Thí nghiệm và đánh giá")
st.caption("Kết quả từng cấu hình, trace và nhãn đánh giá được lưu để kiểm tra lại.")
paths = run_paths()
# Prefer working copies over identical packaged artifacts, retaining distinct
# model/corpus/code manifests as separate experiments.
unique_paths = {}
for run_path in paths:
    unique_paths[fingerprint(read(run_path)["manifest"])] = run_path
paths = list(unique_paths.values())
if not paths:
    st.info("Chưa có lượt benchmark. Xem lệnh chạy trong README; bảng điểm chỉ xuất hiện sau khi có kết quả.")
    st.stop()
rows = []
for path in paths:
    run = read(path)
    summary_path = path.parent / "retrieval_summary.json"
    summary = read(summary_path) if summary_path.exists() else {}
    source_id = next((c["source_id"] for r in run["records"] for c in r.get("original_results", [])), "")
    source_label = {"wdr2023": "World Development Report 2023",
                    "luat_an_ninh_mang_116-2025": "Luật An ninh mạng"}.get(source_id, source_id or "Chưa có kết quả")
    rows.append({"Tài liệu": source_label, "Cấu hình": run["manifest"]["experiment"]["name"], "Split": run["manifest"]["split"],
                 "Model": (run["manifest"].get("model") or {}).get("id", "Không gọi model"),
                 "Chế độ": run["manifest"]["mode"], "Trạng thái": run["state"],
                 "Hit@1": display_rate(summary.get("hit_at_1")),
                 "Evidence Hit@3": display_rate(summary.get("evidence_hit_at_3")),
                 "Context evidence": display_rate(summary.get("context_evidence_rate")),
                 "Lỗi": summary.get("errors"), "Request": summary.get("request_count")})
st.dataframe(rows, hide_index=True, alt="So sánh các lượt benchmark đã chạy theo cấu hình và split")
names = {str(p.relative_to(ROOT)) if p.is_relative_to(ROOT) else str(p): p for p in paths}
preferred = next((i for i, p in enumerate(paths) if "basic-agent-groq-dev" in str(p) and p.parent.name == "A-dense"), 0)
name = st.selectbox("Lượt chạy", list(names), index=preferred, key="run_choice")
path = names[name]
run = read(path)
if run.get("pending"):
    st.info(run["pending"]["reason"])
records = run["records"]
if run["state"] == "running":
    st.info("Benchmark đang chạy. Có thể chấm các câu đã hoàn tất; tải lại trang để thấy câu mới.")
if not records:
    st.info("Lượt chạy chưa hoàn thành câu nào.")
    st.stop()
review_path = path.parent / "reviews.json"
reviews = read(review_path) if review_path.exists() else []
ai_path = path.parent / "reviews.ai.json"
ai_summary_path = path.parent / "audit_summary.ai.json"
ai_labels = read(ai_path) if ai_path.exists() else []
ai_summary = read(ai_summary_path) if ai_summary_path.exists() else None
ai_complete = bool(ai_summary and ai_summary.get("evaluation_mode") == "ai_source_review_not_human_verified"
                   and ai_summary.get("human_verified") is False and ai_summary.get("run_hash") == fingerprint(run)
                   and ai_summary.get("review_hash") == fingerprint(ai_labels))
if ai_complete:
    st.subheader("Đánh giá tự động có đối chiếu nguồn")
    st.warning("Nhãn dưới đây do AI chấm theo yêu cầu của bạn, chưa được con người xác minh đầy đủ. Đây không phải điểm môn học.")
    st.caption(f"Đã chấm AI {len(ai_labels)}/{len(records)} câu. Nhãn thủ công cũ được giữ riêng.")
    metrics = st.columns(3)
    for column, label, field in zip(metrics, ("Grounded đầy đủ", "Citation hỗ trợ", "Từ chối đúng"),
                                    ("grounded_complete", "citation_validity", "abstention")):
        column.metric(label, display_rate(ai_summary[field]))
    with st.expander("Nhãn và lý do AI cho từng câu"):
        st.dataframe([{"Câu": r["query_id"], "Context": r.get("context_grade"),
                       "Đáp án": r.get("answer_grade"), "Citation hỗ trợ": str(r.get("citation_support")),
                       "Từ chối đúng": r.get("abstention_correct"), "Lý do": r.get("reason")}
                      for r in ai_labels], hide_index=True, alt="Nhãn AI tách biệt với đánh giá thủ công")
reviewable = [r["query_id"] for r in records if r["status"] != "error"]
saved_ids = {r["query_id"] for r in reviews} & set(reviewable)
remaining = [qid for qid in reviewable if qid not in saved_ids]
if run["manifest"]["mode"] == "agent":
    st.subheader(f"Chấm thủ công{' (tùy chọn)' if ai_complete else ''} · {run['manifest']['experiment']['name']}")
    st.progress(len(saved_ids) / len(reviewable) if reviewable else 0,
                text=f"Đã lưu {len(saved_ids)}/{len(reviewable)} câu — còn {len(remaining)} câu chưa chấm")
    if remaining:
        st.info("Mỗi lần Lưu nhãn chỉ lưu một câu. Để tổng hợp theo luồng thủ công, cần chấm tất cả câu của lượt này."
                if ai_complete else "Mỗi lần Lưu nhãn chỉ lưu một câu. Cần chấm tất cả câu trong lượt này trước khi tổng hợp.")

        def select_unreviewed():
            st.session_state["review_query"] = remaining[0]

        st.button("Đến câu chưa chấm tiếp theo", key="next_unreviewed", on_click=select_unreviewed)
    elif run["state"] == "complete":
        st.success("Đã lưu nhãn cho tất cả câu của lượt này. Báo lại để kiểm tra và tổng hợp nhãn.")
queued = st.session_state.pop("queued_review_query", None)
if queued and queued["run"] == str(path) and queued["query_id"] in reviewable:
    st.session_state["review_query"] = queued["query_id"]
query_id = st.selectbox("Câu hỏi", [r["query_id"] for r in records], key="review_query",
                        format_func=lambda qid: f"{'Đã lưu' if qid in saved_ids else 'Chưa chấm'} · {qid}"
                        if run["manifest"]["mode"] == "agent" else qid)
record = next(r for r in records if r["query_id"] == query_id)
review_key = fingerprint({"run": str(path.resolve()), "query": query_id})[:12]
saved = next((r for r in reviews if r["query_id"] == query_id), {})
benchmark = "advanced" if query_id.startswith("advanced-") else "basic"
case_path = ROOT / "data" / "benchmarks" / benchmark / f"{run['manifest']['split']}.json"
case = next((q for q in read(case_path) if q["id"] == query_id), {}) if case_path.exists() else {}
if record.get("question"):
    st.subheader(record["question"])
st.markdown(record["answer"] or "Chỉ đo retrieval; chưa có câu trả lời từ agent.")
if case:
    st.caption("Benchmark: có đáp án trong tài liệu." if case["answerable"] else "Benchmark: thiếu bằng chứng để trả lời.")
    with st.expander("Đáp án tham chiếu để đối chiếu"):
        st.caption("Annotation này cần kiểm tra bản gốc; không tự tạo nhãn đánh giá.")
        st.text(case.get("expected_answer") or case.get("absence_reason", ""))
        for gold in case.get("gold", []):
            if isinstance(gold, dict):
                st.caption(f"Nguồn {gold['source_id']} · Trang {gold['page']}")
                st.text(gold.get("evidence", ""))
with st.expander("Trace và context"):
    st.json(record)
with st.expander("Đối chiếu nguồn của câu đang chấm", on_change="rerun") as evidence:
    if evidence.open:
        chunks = record.get("context", {}).get("chunks", [])
        if chunks:
            cid = st.selectbox("Nguồn trong context", [c["id"] for c in chunks], key=f"source_{review_key}")
            chunk = next(c for c in chunks if c["id"] == cid)
            st.caption(f"[{cid}] · Trang {chunk['page']}")
            st.text(chunk["text"])
            folder = {"luat_an_ninh_mang_116-2025": "day6", "wdr2023": "wdr2023"}.get(chunk["source_id"])
            if folder:
                source_root = ROOT / settings().work_dir / "corpora" / folder
                manifest_path = source_root / "manifest.json"
                manifest = read(manifest_path) if manifest_path.exists() else {}
                url = manifest.get("source_url", "")
                if url.startswith(("https://", "http://")):
                    if url.lower().endswith(".pdf"):
                        url += f"#page={chunk['page']}"
                    st.link_button("Mở bản gốc để kiểm tra", url, key=f"original_{review_key}")
                if chunk.get("pdf"):
                    st.image(evidence_preview(source_root, chunk), width="stretch",
                             alt=f"Vùng bằng chứng gốc trang {chunk['page']}")
        else:
            st.info("Context trống; không có nguồn để hỗ trợ đáp án.")
if run["manifest"]["mode"] == "agent" and record["status"] != "error":
    st.subheader("Ghi nhãn thủ công")
    st.caption("Đối chiếu bản gốc trước khi ghi nhãn. CLI review sẽ kiểm tra đầy đủ nhãn và tổng hợp điểm.")
    if saved:
        st.success("Câu này đã có nhãn được lưu; có thể sửa nếu cần.")
    grades = [None, 0, 1, 2]
    with st.form(f"audit_{review_key}"):
        context_grade = st.selectbox("Context: 0 thiếu, 1 một phần, 2 đủ", grades,
                                    index=grades.index(saved.get("context_grade")),
                                    format_func=lambda v: "Chưa chấm" if v is None else str(v), key=f"cg_{review_key}")
        answer_grade = st.selectbox("Câu trả lời: 0 sai/thiếu, 1 một phần, 2 đủ", grades,
                                   index=grades.index(saved.get("answer_grade")),
                                   format_func=lambda v: "Chưa chấm" if v is None else str(v), key=f"ag_{review_key}")
        saved_support = saved.get("citation_support", [])
        supports = [st.checkbox(f"Nguồn hỗ trợ citation [{cid}]", key=f"support_{review_key}_{i}",
                                value=i < len(saved_support) and saved_support[i] is True)
                    for i, cid in enumerate(record["citations"])]
        abstention = st.checkbox("Từ chối đúng đối với câu không đủ evidence", key=f"ab_{review_key}",
                                value=saved.get("abstention_correct") is True)
        checked = st.checkbox("Đã đối chiếu với tài liệu gốc", key=f"checked_{review_key}",
                             value=saved.get("reviewed_original_source") is True)
        reason = st.text_area("Lý do, điều kiện và evidence đã đối chiếu", key=f"reason_{review_key}",
                              value=saved.get("reason", ""))
        submit = st.form_submit_button("Lưu nhãn", key=f"save_{review_key}")
        save_next = st.form_submit_button("Lưu và sang câu chưa chấm", key=f"save_next_{review_key}")
    if submit or save_next:
        if not checked or not reason.strip():
            st.error("Cần đối chiếu bản gốc và ghi lý do trước khi lưu.")
        elif case.get("answerable") and (context_grade is None or answer_grade is None):
            st.error("Cần chọn điểm context và câu trả lời cho câu có đáp án.")
        elif case.get("answerable") and record["status"] == "abstain" and answer_grade != 0:
            st.error("Câu có đáp án nhưng agent từ chối cần chấm câu trả lời 0; context chấm theo bằng chứng thực tế.")
        else:
            target = path.parent / "reviews.json"
            reviews = read(target) if target.exists() else []
            reviews = [r for r in reviews if r["query_id"] != query_id]
            reviews.append({"query_id": query_id, "context_grade": context_grade, "answer_grade": answer_grade,
                            "citation_support": supports, "abstention_correct": abstention,
                            "reviewed_original_source": checked, "reason": reason})
            save_json(target, reviews)
            if save_next:
                saved_now = {r["query_id"] for r in reviews}
                next_ids = [qid for qid in reviewable if qid not in saved_now]
                if next_ids:
                    st.session_state["queued_review_query"] = {"run": str(path), "query_id": next_ids[0]}
            st.rerun()
