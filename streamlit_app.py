from pathlib import Path
import sys

import streamlit as st

sys.path.insert(0, str(Path(__file__).parent / "src"))
from day7_rag.ui import ROOT, settings

st.set_page_config(page_title="Day 7 · Hỏi đáp có bằng chứng", page_icon=":material/library_books:", layout="wide")
st.session_state.setdefault("conversations", {})
st.session_state.setdefault("latest_evidence", {})
st.session_state.setdefault("pending_questions", {})

with st.sidebar:
    st.title("Kho tri thức")
    choices = {"Luật An ninh mạng · Day 6": "day6", "World Development Report 2023": "wdr2023"}
    corpus = st.selectbox("Tài liệu", list(choices), key="corpus_choice")
    cfg = settings()
    root = (ROOT / cfg.work_dir / "corpora" / choices[corpus]).resolve()
    st.session_state["corpus_path"] = str(root)
    st.caption("Agent tìm bằng chứng trong tài liệu, trả lời có nguồn hoặc nêu rõ giới hạn.")
    if not (root / "chunks.json").exists():
        st.info("Tài liệu chưa sẵn sàng. Xem hướng dẫn chuẩn bị dữ liệu trong README.")
    st.divider()
    st.caption(f"{cfg.provider.title()} · {cfg.active_model}")
    st.caption("API đã cấu hình" if cfg.active_key else "Chưa cấu hình API — vẫn có thể tra cứu từ khóa và xem nguồn.")

page = st.navigation([
    st.Page("app_pages/chat.py", title="Hỏi đáp", icon=":material/chat:", default=True, url_path="chat"),
    st.Page("app_pages/evidence.py", title="Bằng chứng", icon=":material/find_in_page:", url_path="evidence"),
    st.Page("app_pages/experiments.py", title="Thí nghiệm", icon=":material/science:", url_path="experiments"),
])
page.run()
