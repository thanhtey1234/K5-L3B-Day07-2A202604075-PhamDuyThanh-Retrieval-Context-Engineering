# Day 7 · Agentic RAG có bằng chứng

**Phạm Duy Thanh — 2A202604075, K5-L3B.** CLI và giao diện Streamlit dùng chung package `day7_rag`; kế thừa Day 6 và mở rộng hỏi đáp theo báo cáo có bảng, hình, biểu đồ.

## Bản triển khai cá nhân

- Adapter PostgreSQL/pgvector Day 6 **chỉ đọc**, BM25, dense và hybrid RRF; năm cấu hình A–E trong `configs/`.
- Agent OpenRouter/Groq thật: `search`, `view_image`, `final_answer`; citation, từ chối, lỗi riêng và checkpoint khi hết quota. OpenRouter chỉ nhận model `:free`; Groq yêu cầu xác nhận tài khoản Free. Không tự đổi model/provider.
- Pipeline PDF toàn tài liệu, vùng text/bảng/ảnh có trang và bbox; embedding local và cache theo model/revision/nội dung.
- Benchmark cơ bản **24 câu**, nâng cao **48 câu**, file dev/test riêng. Kết quả cơ bản đã được AI chấm theo yêu cầu người dùng, có provenance và đối chiếu nguồn; chưa được con người xác minh đầy đủ.
- Giao diện hỏi đáp, tìm từ khóa, xem nguồn và xem/chấm trace. Mở trang hoặc đổi widget không tự gọi API.

Đã kiểm chứng **53 test**, 10 lượt retrieval dev thật, A/D agent dev 17 câu và A/D test 7 câu mỗi lượt. **D được chọn và freeze trên dev trước test**; AI chấm test D grounded đầy đủ 3/5 câu có đáp án, từ chối đúng 2/2 câu thiếu evidence. Vision smoke thật có `search → view_image → answer`. Chưa có bằng chứng đạt bonus nâng cao. [Bảng đánh giá AI](artifacts/AUTOMATED_EVALUATION.md) · [Luồng chấm AI và tái lập](docs/AUTOMATED_REVIEW.md) · [Kiểm chứng](artifacts/VALIDATION.md).

Kết quả chốt được giữ duy nhất trong `artifacts/runs/`; các bản sao chạy thử trong `work/` đã dọn. `work/` giữ dữ liệu nguồn, cache model/embedding và sổ quota cần để ứng dụng hoạt động. Không cần gọi lại API để xem kết quả đã có.

Bản nộp có thể đóng gói bằng `python scripts/package_submission.py`: kiểm tra hash dev/test/nhãn/frozen, quét key thật trước khi tạo ZIP, không kèm `.env`, Git metadata, model/cache hoặc source download. File sinh ở `output/Day7_2A202604075_PhamDuyThanh_submission.zip`; inventory/checksum từng file ở `artifacts/SUBMISSION_FILES.json`.

### Chạy nhanh trên Windows PowerShell

Cần `uv`, Docker Desktop cho dense/hybrid và mạng ở lần tải đầu. Môi trường đã kiểm chứng: Python **3.12.14**; dependency khóa trong `requirements.lock.txt`.

```powershell
& ./scripts/setup.ps1
# Điền OPENROUTER_API_KEY trong .env trên máy, không commit hoặc gửi key qua chat.
.venv/Scripts/python.exe -m day7_rag doctor
.venv/Scripts/python.exe scripts/prepare_sources.py --corpus day6
.venv/Scripts/python.exe -m streamlit run streamlit_app.py
```

Khi chưa có API key, chọn **Tìm từ khóa** để dùng corpus thật và xem nguồn. Sửa `.env` xong cần khởi động lại app đang chạy để nạp lại cấu hình. UI cũng đọc `.streamlit/secrets.toml`, file này được Git bỏ qua.

Linux/macOS: tạo venv Python 3.12, cài `requirements.lock.txt`, rồi `python -m pip install --no-deps -e .`; dùng `.venv/bin/python`. Lock hiện được kiểm chứng trên Windows.

### Day 6 và cơ sở dữ liệu

Mẫu `.env` trỏ tới lab local `127.0.0.1:55433/day6_lab`, bảng `public.chunks`, **`strategy_b`**, embedding `AITeamVN/Vietnamese_Embedding` 1024 chiều. Adapter kiểm tra nội dung, ID, nguồn, trang và chiều vector trước khi so sánh. Không đổi embedding cho index cũ.

```powershell
docker desktop start
.venv/Scripts/python.exe -m day7_rag doctor --database
.venv/Scripts/python.exe -m day7_rag export-day6 --output work/corpora/day6-export
```

Nguồn tái tạo là [repo Day 6](https://github.com/thanhtey1234/K5-L3B-Day06_PhamDuyThanh-2A202604075-DataIngestionEngineering), commit `663df9fa1c0f7c5bafcb1e21f47433e5137d3057`: 37 trang, 235 paragraph chunk, giữ nguyên OCR và ánh xạ chương của Day 6.

Nếu không có database cũ, dựng lab riêng bằng `docker compose -p day7_lab up -d --wait`, rồi `day7 index --corpus work/corpora/day6`. Không dựng container mới nếu cổng đã được database cũ sử dụng. Không xóa volume để sửa lỗi. Mọi index mới chỉ ghi trong schema `rag_day7`; khi corpus có `index.json`, runtime dùng index phiên bản đó, nếu không Day 6 dùng index gốc.

### OpenRouter và benchmark

**Groq Free (phương án bổ sung):** adapter hỗ trợ `qwen/qwen3.8-27b` với ảnh và tool calling. Giữ key OpenRouter và thêm cấu hình sau trong `.env` để chọn Groq rõ ràng:

```dotenv
LLM_PROVIDER=groq
GROQ_API_KEY=your_local_key
GROQ_MODEL=qwen/qwen3.8-27b
GROQ_FREE_TIER_CONFIRMED=true
GROQ_DAILY_REQUEST_BUDGET=900
GROQ_DAILY_TOKEN_BUDGET=180000
GROQ_TOKENS_PER_MINUTE=7200
GROQ_MAX_OUTPUT_TOKENS=1024
```

Chỉ đặt `GROQ_FREE_TIER_CONFIRMED=true` sau khi người dùng kiểm tra tài khoản đang Free. Groq không cung cấp trạng thái gói trong model catalog; code không thể chứng minh Free tier chỉ từ key và không giả giá model bằng 0. Adapter dùng endpoint Groq cố định, không tự chuyển model/provider, không bật built-in tools có phí. Usage thiếu cost được báo **chưa có cost report**. Tokenizer Qwen được cố định revision `37561816e66b5b9153b1b64c10968c18c1e6f4a0`, có margin cho framing và ảnh; số token thực lấy từ API. Ledger SQLite dùng chung CLI/UI, dự phòng token trước request, cập nhật theo usage, giới hạn trên cửa sổ 24 giờ. Khi chạm giới hạn phút, chương trình chờ; khi chạm ngân sách ngày, giữ checkpoint.

Để dành quota cho test, có thể chạy hai cấu hình dev trước:

```powershell
.venv/Scripts/python.exe -m day7_rag doctor --online
.venv/Scripts/python.exe scripts/run_dev.py --mode agent --configs configs/A-dense.json configs/D-context.json --rate-retries 5 --output work/runs/basic-agent-groq-dev
```

Giữ cùng model/provider khi so sánh A và D. Không tiếp tục output hoặc freeze của OpenRouter bằng Groq. Sau khi toàn bộ model/tokenizer đã được tải, có thể đặt `$env:HF_HUB_OFFLINE='1'` trong phiên PowerShell chạy benchmark để tránh kiểm tra mạng Hugging Face; API Groq vẫn hoạt động. Khởi động lại Streamlit sau khi đổi provider trong `.env`.

[Groq model và ảnh/tools](https://console.groq.com/docs/vision) · [Hạn mức tài khoản](https://console.groq.com/settings/limits) · [Gói thanh toán](https://console.groq.com/docs/billing-faqs).

Model mẫu là `inclusionai/ling-3.2-flash:free`. Preflight xác nhận ảnh, tools/tool_choice và mọi giá catalog bằng 0; khi model không còn phù hợp thì dừng để chọn lại trên dev. Không dùng fallback hoặc plugin trả phí. [Tool calling](https://openrouter.ai/docs/guides/features/tool-calling) · [Hạn mức](https://openrouter.ai/docs/api/reference/limits).

```powershell
.venv/Scripts/python.exe -m day7_rag doctor --online
.venv/Scripts/python.exe -m day7_rag ask --corpus work/corpora/day6 --config configs/C-hybrid.json --output work/chat/first.json "An ninh thông tin mạng bảo đảm những thuộc tính nào?"

.venv/Scripts/python.exe -m day7_rag validate --corpus work/corpora/day6 --cases data/benchmarks/basic/dev.json data/benchmarks/basic/test.json
.venv/Scripts/python.exe scripts/run_dev.py --mode retrieval --output artifacts/runs/basic-retrieval-dev
.venv/Scripts/python.exe scripts/run_dev.py --mode agent --output work/runs/basic-agent-dev
```

Mặc định 10 request/phút và 45 request/ngày UTC cho dự án. Tài khoản miễn phí có thể chỉ có 50 request/ngày; một câu cần nhiều request. Hết quota: giữ checkpoint và chạy lại **cùng lệnh/cùng output**. Không đổi model, corpus hoặc config giữa lượt chạy. Trace lưu context, tool call, lỗi, thời gian và usage; không lưu key, DSN hoặc private reasoning.

Context budget dùng **byte UTF-8 làm cận trên bảo thủ cho text token**, tính cả header nguồn. Actual prompt/completion tokens lấy từ API. Với retrieval-only, E chưa có agent để đo tác động multi-hop; không gọi đây là điểm agent.

Khi chạy benchmark mới, chương trình tạo `run.json`, `retrieval_summary.json` và `reviews.template.json`. Các template trống trong kết quả chốt đã được dọn; nhãn AI được giữ trong `reviews.ai.json`, nhãn thủ công đã có được giữ riêng trong `reviews.json`. Nếu chấm thủ công, điền nhãn từ bản gốc bằng trang **Thí nghiệm** hoặc template của lượt chạy mới. `review` yêu cầu lý do, xác nhận đọc nguồn, `context_grade`, `answer_grade`, từng `citation_support` và `abstention_correct` phù hợp. Không tự đánh dấu nhãn để vượt validator.

```powershell
.venv/Scripts/python.exe -m day7_rag review --run work/runs/basic-agent-dev/D-context --cases data/benchmarks/basic/dev.json --reviews work/runs/basic-agent-dev/D-context/reviews.json
# Chỉ dùng ví dụ D dưới đây sau khi D thực sự được chọn bằng dev đã chấm.
.venv/Scripts/python.exe -m day7_rag freeze --corpus work/corpora/day6 --config configs/D-context.json --dev-run work/runs/basic-agent-dev/D-context --test-cases data/benchmarks/basic/test.json --output work/frozen-basic.json
.venv/Scripts/python.exe -m day7_rag benchmark --corpus work/corpora/day6 --config configs/A-dense.json --cases data/benchmarks/basic/test.json --split test --mode agent --frozen work/frozen-basic.json --output work/runs/basic-agent-test/A-dense
.venv/Scripts/python.exe -m day7_rag benchmark --corpus work/corpora/day6 --config configs/D-context.json --cases data/benchmarks/basic/test.json --split test --mode agent --frozen work/frozen-basic.json --output work/runs/basic-agent-test/D-context
```

Chọn cấu hình theo grounded answer, citation, abstention, context rồi request/thời gian; phân tích ít nhất hai lỗi dev. Chưa có agent review thì chưa chốt chính thức. Dùng test để chỉnh thì phải tạo test mới. [Nguồn và schema benchmark](data/benchmarks/README.md).

### Tài liệu nâng cao

Chọn [World Development Report 2023](https://www.worldbank.org/en/publication/wdr2023), PDF 348 trang, CC BY 3.0 IGO và điều kiện riêng cho một số thành phần. Manifest ghi checksum/attribution. PDF, ảnh crop và vector cache trong `work/` không được commit.

```powershell
.venv/Scripts/python.exe scripts/prepare_sources.py --corpus wdr2023
.venv/Scripts/python.exe -m day7_rag extract --corpus work/corpora/wdr2023
.venv/Scripts/python.exe scripts/build_advanced_benchmark.py
.venv/Scripts/python.exe -m day7_rag validate --corpus work/corpora/wdr2023 --cases data/benchmarks/advanced/dev.json data/benchmarks/advanced/test.json --advanced
.venv/Scripts/python.exe -m day7_rag describe --corpus work/corpora/wdr2023
.venv/Scripts/python.exe -m day7_rag index --corpus work/corpora/wdr2023
```

`describe` bổ sung mô tả hình độc lập với câu hỏi, có cache và tiếp tục theo quota; cần hoàn thành trước khi freeze. Mô tả sinh được gắn chưa kiểm chứng; khi trả lời trực quan phải xem ảnh gốc. Bản native labels vẫn chạy được nhưng phải báo rõ giới hạn. Sau khi mô tả làm đổi corpus, index lại phiên bản mới.

Index nâng cao dùng **BAAI/bge-m3 local**, tách khỏi Day 6. CPU encode lần đầu có thể lâu. `extraction_report.json` ghi mọi trang, ứng viên bảng/ảnh và cảnh báo; detector có thể nhầm hoặc bỏ sót. Audit coverage và nguồn gốc trước khi nộp. PDF scan cần OCR/ngôn ngữ tương ứng; lỗi được ghi theo trang.

Chạy dev bằng runner trên với `--corpus work/corpora/wdr2023 --cases data/benchmarks/advanced/dev.json`. Sau khi freeze, chạy toàn bộ test 30 câu và tổng hợp bằng `review --advanced`. Lỗi tính không đạt; **27/30** mới đạt 90%. Không có tuyên bố bonus khi chỉ qua unit test/retrieval.

### Kiểm thử và bài nộp

```powershell
.venv/Scripts/python.exe -m pytest -q
.venv/Scripts/python.exe -m unittest discover -s tests -v
.venv/Scripts/ty.exe check src/day7_rag streamlit_app.py app_pages
.venv/Scripts/ruff.exe check src scripts app_pages streamlit_app.py tests/test_rag_core.py tests/test_openrouter_client.py tests/test_groq_client.py tests/test_evaluation_pipeline.py tests/test_web_app.py
```

CI chạy Windows/Python 3.12; test không gọi model trả phí. Kiểm tra runtime web bằng agent API: mở instance local với `--server.port=8765 --server.enableAgentApi=true`, rồi chạy `python scripts/check_web.py`. Cờ này chỉ dùng kiểm tra local, không bật trong config deploy.

Xuất bảng thực nghiệm bằng `day7 report --runs <các-thư-mục-run> --output <bao-cao.md>`. [Báo cáo cá nhân](report/individual/2A202604075_PhamDuyThanh.md) · [Thiết kế và giới hạn](docs/IMPLEMENTATION.md).

---

## Đề bài gốc

**Bài cá nhân · Python 3.11+ · tiếp nối Day 6**

Dùng embedding và vector store từ Day 6 để xây một agent biết tìm bằng chứng, trả lời có nguồn và nhận biết khi không đủ thông tin. Bạn tự chọn kiến trúc, số tool và cách tổ chức retrieval.

> **Tùy chọn:** [Gợi ý dùng AI để lập trình](AGENT_SETUP.md) giúp bạn làm lab; phần này không bắt buộc và không tính điểm.

## Bài cần làm

![Agent tìm tài liệu trong kho Day 6 và trả lời có nguồn](assets/retrieval-pipeline.svg)

1. Kết nối dữ liệu, embedding và vector store Day 6.
2. Xây agent dùng model thật và ít nhất một khả năng truy xuất dữ liệu. Agent có thể dùng nhiều tool và nhiều lượt gọi.
3. Thử **ít nhất 3 phương pháp retrieval khác nhau**, trong đó có dense retrieval dùng vector store Day 6. Tự chọn các phương pháp còn lại; xem [gợi ý](GUIDE.md#2-thử-các-phương-pháp-retrieval).
4. Thử nhiều cấu hình, benchmark, phân tích lỗi và chọn cấu hình tốt trên **dev**; sau đó đánh giá trên **test**.

Benchmark tối thiểu có **24 câu**: dev gồm 15 câu có đáp án và 2 câu thiếu bằng chứng; test gồm 5 câu có đáp án và 2 câu thiếu bằng chứng. Xem [benchmark](BENCHMARK.md) và [rubric](RUBRIC.md).

## Thử thách nâng cao · +15 điểm

Index một tài liệu thực tế từ **100 trang** có bảng, ảnh và biểu đồ; xây agent truy xuất và trả lời các câu hỏi về nội dung đó. Hoàn thành [thử thách nâng cao](ADVANCED.md) và đạt **ít nhất 90% benchmark test** để nhận 15 điểm bonus. Phần cơ bản tối đa 85 điểm; toàn bài tối đa 100 điểm.

## Bắt đầu

1. Đọc [hướng dẫn](GUIDE.md), [rubric](RUBRIC.md) và [quy tắc](RULES.md).
2. Tạo repo cá nhân theo [cách nộp bài](SUBMISSION.md), chuẩn bị đầu ra Day 6 và model hỗ trợ tool calling.
3. Dùng hoặc thay thế [starter](starter/README.md); bạn cần kết nối model và vector store thật.
4. Chạy `python -m unittest discover -s tests -v`. Test mock chỉ kiểm tra code, không phải benchmark agent thật.

![Các bước thử nghiệm trên dev và đánh giá trên test](assets/experiment-loop.svg)

Nộp code, cách chạy, cấu hình, benchmark, trace và [báo cáo cá nhân](report/individual/2A202604075_PhamDuyThanh.md). Thời gian ở [checkpoints](CHECKPOINTS.md) là gợi ý, có thể điều chỉnh theo lớp và phạm vi thử nghiệm.
