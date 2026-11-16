import streamlit as st

from day7_rag.io import safe_asset
from day7_rag.pdf import evidence_preview
from day7_rag.ui import corpus_root, read

st.title("Đối chiếu bằng chứng")
st.caption("Xem nguyên văn, trang nguồn và vùng tài liệu dùng để kiểm chứng câu trả lời.")
root = corpus_root()
if not (root / "chunks.json").exists():
    st.info("Chưa có tài liệu để xem.")
    st.stop()

recent = st.session_state["latest_evidence"].get(str(root), [])
scope = st.segmented_control("Phạm vi", ["Lượt hỏi gần nhất", "Toàn bộ tài liệu"],
                             default="Lượt hỏi gần nhất" if recent else "Toàn bộ tài liệu", key="evidence_scope")
chunks = recent if scope == "Lượt hỏi gần nhất" else read(root / "chunks.json")
if not chunks:
    st.info("Chưa có bằng chứng từ lượt hỏi. Chọn toàn bộ tài liệu để xem nguồn.")
    st.stop()
pages = sorted({c["page"] for c in chunks})
page = st.selectbox("Trang PDF", pages, key="evidence_page")
on_page = [c for c in chunks if c["page"] == page]
chunk_id = st.selectbox("Đoạn hoặc vùng", [c["id"] for c in on_page], key="evidence_id")
chunk = next(c for c in on_page if c["id"] == chunk_id)
left, right = st.columns([1, 1.4])
with left:
    st.subheader(f"Trang {page}")
    st.text(chunk["text"])
    st.caption(f"Loại nội dung: {chunk.get('content_type', 'text')}")
    if chunk.get("bbox"):
        st.caption(f"Vùng PDF (đơn vị point): {chunk['bbox']}")
    manifest = read(root / "manifest.json")
    url = manifest.get("source_url") or chunk["source"]
    if url.startswith(("http://", "https://")):
        if url.lower().endswith(".pdf"):
            url += f"#page={page}"
        st.link_button("Mở nguồn công bố", url, icon=":material/open_in_new:")
    if chunk["metadata"].get("vision_status") == "generated_unverified":
        st.warning("Mô tả hình do model tạo cần được đối chiếu với hình gốc.")
with right:
    if chunk.get("pdf"):
        try:
            st.image(evidence_preview(root, chunk), width="stretch",
                     alt=f"Trang {page} của tài liệu với vùng bằng chứng được đánh dấu")
        except (ValueError, OSError):
            st.warning("Chưa mở được PDF gốc. Kiểm tra file nguồn của corpus.")
    elif chunk.get("image"):
        st.image(str(safe_asset(root, chunk["image"])), width="stretch", alt=f"Bằng chứng gốc trang {page}")
    else:
        st.info("Corpus Day 6 hiện là bản OCR. Dùng liên kết nguồn để đối chiếu PDF chính thức.")
