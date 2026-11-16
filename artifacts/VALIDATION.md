# Kiểm chứng triển khai

Đã thực hiện ngày 16/11/2026; cấu hình môi trường cụ thể trong `environment.json`.

## Code và giao diện

- `python -m pytest -q -p no:cacheprovider`: **53 passed**, gồm Groq, nhãn độc lập giữa các lượt, lưu/chuyển câu không mất nhãn, provenance chấm AI và khóa test.
- `python -m unittest discover -s tests -q`: **53 tests, OK**; giữ toàn bộ 15 test gốc.
- `ty check src/day7_rag streamlit_app.py app_pages`: qua.
- Ruff trên package, scripts, UI và test mới: qua; `git diff --check`: qua.
- AppTest kiểm tra điều hướng, trạng thái thiếu API key, tìm từ khóa và xem evidence mà không gọi inference.
- Instance Streamlit thực trên localhost:8765 được kiểm tra bằng agent API: hỏi đáp/tìm từ khóa, bằng chứng Day 6, bảng WDR trang 46 và màn hình thí nghiệm đều trả `ready`, không có lỗi runtime trong log. Instance kiểm tra được dừng sau QA.
- Chưa kiểm tra giao diện bằng trình duyệt đồ họa: công cụ browser CUA không kết nối được native pipe. Kiểm tra runtime ở trên và render vùng PDF là các phép kiểm tra đã thực sự thực hiện.

## Dữ liệu và hạ tầng thật

- PostgreSQL **16.16**, pgvector **0.8.7**; connection kiểm tra bật read-only.
- Day 6 giữ nguyên `strategy_a: 209`, `strategy_b: 235` chunk; không ghi vào `public.chunks`.
- WDR có **348 trang**, **337 trang có text**, **1.396 chunk** sau khi gom block; 47 vùng bảng ứng viên và 170 trang có vùng trực quan theo heuristic. Không coi các số detector là coverage đã audit thủ công.
- Index WDR `5f652e08a083cf4ec690f49d` có **1.396 vector thật**, tất cả 1024 chiều. Model BAAI/bge-m3, revision `5617a9f61b028005a4858fdac845db406aefb181`, normalized, max length 2048. Index và source checksum ở `data-manifests/`.
- Hai bộ benchmark đã được validate với corpus thật: basic **24 câu**, advanced **48 câu**. Cả hai cần audit annotation cuối bằng bản gốc.

## Thực nghiệm đã chạy và phần chưa chạy

Có **10 lượt retrieval dev**: A–E cho từng corpus. Các lượt dùng cùng phiên bản code trong manifest, cùng corpus trong mỗi nhóm, query gốc được lưu, query embedding được làm ấm trước khi đo. Dùng PostgreSQL và model embedding thật; không có mock trong những artifact này. Kết quả trong `RETRIEVAL_REPORT.md` và `ADVANCED_RETRIEVAL_REPORT.md`.

API key được cấu hình local. Người dùng xác nhận Groq Free tier với giới hạn 1K request/ngày, 8K token/phút, 200K token/ngày. Adapter `qwen/qwen3.8-27b` có request/token ledger riêng và tokenizer cố định revision. Bằng chứng tích hợp được giữ trong các lượt dev/test hoàn chỉnh, gồm mọi attempt/retry của những lượt này. API Groq không trả cost, vì vậy không gán số 0 giả. Các snapshot sơ bộ và báo cáo trạng thái cũ không được dùng để tính kết quả chốt.

Đã dọn lịch sử thử sơ bộ, báo cáo trạng thái cũ, smoke cũ và file QA tạm theo xác nhận của người dùng. Các trace chốt, nhãn, cấu hình khóa, manifest nguồn và vision smoke được giữ; đã đối chiếu hash 21 file bằng chứng trước/sau khi dọn. Dữ liệu nguồn, cache model/embedding, sổ quota và log của ứng dụng đang chạy được giữ nguyên.

Runtime Streamlit đã kiểm tra điều hướng, tìm từ khóa, đối chiếu nguồn và hiển thị nhãn AI tách khỏi nhãn thủ công; mở trang không tự gọi inference hoặc lưu nhãn. Xem hướng dẫn chấm AI ở `../docs/AUTOMATED_REVIEW.md`; chấm thủ công là tùy chọn trong `../docs/REVIEW_GUIDE.md`.

Theo yêu cầu chuyển sang chấm tự động, đã tạo nhãn AI riêng cho đủ 17 câu dev của A/D, không đổi file nhãn thủ công ban đầu. D được chọn trên dev và freeze trước khi chạy test. **Cả A và D hoàn tất 7/7 câu held-out test cơ bản**, có nhãn AI và lý do đối chiếu PDF gốc. Grounded test A 2/5, D 3/5; citation hỗ trợ 2/2 và 3/3, từ chối đúng 2/2 ở cả hai. Nhãn AI chưa được con người xác minh; không phải điểm môn học. Frozen/trace/nhãn nằm trong `artifacts/runs/basic-agent-groq-*` và `frozen-basic-ai.json`.

Vision smoke thật bằng OpenRouter đã có đủ `search → view_image → answer`, đọc đúng đơn vị của Figure O.1 PDF trang 33. Scope visual-only/page filter được khai báo; không dùng làm điểm benchmark nâng cao. Chưa hoàn tất mô tả vision toàn corpus hoặc 30 câu test nâng cao. **Chưa có bằng chứng đạt 90% test nâng cao và chưa tuyên bố bonus.**

Raw-query retrieval nâng cao hiện còn thấp: đây là baseline native extraction với câu hỏi tiếng Việt, nguồn tiếng Anh và phép chấm đúng vùng cụ thể. Không đổi nhãn test để làm đẹp số liệu. Cần chạy bước vision, agent query transformation/multi-hop trên dev, audit nguồn và chốt cấu hình bằng chất lượng thực tế trước khi đánh giá test.
