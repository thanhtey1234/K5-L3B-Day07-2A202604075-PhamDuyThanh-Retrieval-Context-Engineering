# Code

Package triển khai ở `day7_rag/`: cấu hình, schema dữ liệu, embedding local, adapter Day 6, index phiên bản, retrieval, agent OpenRouter, PDF, benchmark và CLI. Giao diện nằm ở `streamlit_app.py` và `app_pages/` tại thư mục gốc.

Cài bằng `pip install -e .`, sau đó chạy `python -m day7_rag --help`. Xem [README chính](../README.md) và [thiết kế](../docs/IMPLEMENTATION.md). `starter/` được giữ làm ví dụ offline và kiểm thử tương thích; luồng chạy thật không dùng adapter mock.
