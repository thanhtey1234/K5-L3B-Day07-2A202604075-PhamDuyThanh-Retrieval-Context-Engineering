# Báo cáo cá nhân — Day 7 Agentic RAG

**Phạm Duy Thành · 2A202604075 · L3B · 16/11/2026.**

## Kết quả và phạm vi

Đã triển khai CLI và web Streamlit, kết nối Day 6 thật, thử dense/BM25/hybrid, chạy năm cấu hình retrieval dev, hai cấu hình agent dev và hai lượt held-out test cơ bản. **D-context được chọn trên dev và freeze trước test.** Trace, nhãn, checksum và cấu hình đóng băng nằm trong artifacts/.

Người dùng yêu cầu chuyển từ chấm thủ công sang chấm tự động. **Nhãn ngữ nghĩa do trợ lý AI đối chiếu nguồn, chưa được con người xác minh đầy đủ; không phải điểm giảng viên.** Nhãn ghi reviewer AI, trang nguồn và lý do, không đánh dấu giả reviewed_original_source=true. File reviews.json thủ công ban đầu được giữ riêng.

## Dữ liệu, nguồn và kiến trúc

- Day 6: Luật An ninh mạng 116/2025/QH15, 37 trang scan, 235 paragraph chunk strategy_b, PostgreSQL/pgvector và AITeamVN/Vietnamese_Embedding 1024 chiều. Giữ nguyên OCR và index; adapter chỉ đọc public.chunks. Kho cũ giữ cả 209 chunk A và 235 chunk B.
- Nguồn OCR pin tại repo Day 6 commit 663df9fa1c0f7c5bafcb1e21f47433e5137d3057. PDF gốc từ Cổng Thông tin điện tử Chính phủ có SHA-256 eded93a3e2820913c6d0801a24977b4588d65c7da1838a952e43faed9af78b08. PDF không có text native; AI đọc các trang render liên quan. Điều khoản trang 36 có phần tiếp tục sang 37.
- Basic benchmark: dev 15 có đáp án + 2 thiếu evidence; test 5 + 2. Gold không được chuyển cho agent; runtime chỉ nhận câu hỏi/filter. Annotation có giới hạn OCR và chưa được xác minh độc lập đầy đủ.
- Model chính: Groq qwen/qwen3.8-27b, tài khoản Free do người dùng xác nhận; temperature 0, reasoning none, output tối đa 1024. API catalog không xác minh được gói thanh toán. Không tự đổi model/provider khi lỗi.
- Agent gọi search, có thể view_image, kết thúc bằng final_answer; mỗi bước một tool. Context hợp nhất ranking, bỏ trùng, tính cả header nguồn trong ngân sách byte UTF-8 bảo thủ. Citation phải có trong context và đáp án; hình/bảng cần được xem trước khi cite. Lỗi hệ thống, từ chối và checkpoint quota tách riêng.
- BM25 dùng Unicode; hybrid dùng RRF k=60, không cộng score khác thang đo. Embedding pin revision/cache theo nội dung; runtime kiểm tra corpus export khớp index thật.

## Cấu hình và giả thuyết

A dense top-3; B BM25 top-3; C hybrid top-3. D hybrid top-6, context 6000 byte thay cho 3000. E giữ D và tăng search lên 4. Các lượt retrieval-only A–E đều chạy thật; E chưa có agent run nên không suy ra lợi ích multi-hop từ retrieval-only.

Giả thuyết C: lexical signal tên bộ/điều bù miss của dense. Giả thuyết D: thêm đoạn/context giữ đủ điều kiện ở khoản lân cận. A/D agent dùng cùng corpus, cases và model. Package inference hash: c8c3c8eb7a1295bf1798d9075c0a79d5b0dbe796539499be60564dfb431bd80f.

## Agent — kết quả AI chấm có đối chiếu nguồn

Grounded đầy đủ yêu cầu đáp án/context đều 2, có citation và mọi citation hỗ trợ đúng. Câu có đáp án nhưng agent từ chối nhận 0. Grounded chỉ tính câu có đáp án; abstention chỉ tính câu thiếu evidence. Nhãn từng câu và lý do ở reviews.ai.json.

| Split | Cấu hình | Grounded đầy đủ | Citation hỗ trợ | Từ chối đúng | Từ chối sai trên câu có đáp án |
|---|---|---:|---:|---:|---:|
| Dev | A | 4/15 | 4/5 | 2/2 | 10/15 |
| Dev | D | 6/15 | 6/7 | 2/2 | 8/15 |
| Test | A | 2/5 | 2/2 | 2/2 | 3/5 |
| Test | D | **3/5** | **3/3** | **2/2** | **2/5** |

Tính cả từ chối đúng, test A đạt 4/7, D đạt 5/7 theo rubric AI này. Không dùng tỷ lệ này làm điểm môn học hoặc bonus nâng cao. Hai câu D chưa trả lời được vẫn giữ kết quả; không sửa prompt/config sau test.

Retrieval query gốc trên test có Hit@1 và Evidence Hit@3 5/5 ở cả A/D, nhưng context cuối của agent chỉ đạt 2/5 và 3/5. Query gốc được đo trước; model có thể viết lại query. Không coi retrieval tốt là bằng chứng trả lời tốt.

## Phân tích lỗi dev và đánh đổi

1. **dev-05 — đề nghị kiểm tra Điều 12:** A viết lại thành query ngắn, thiếu khoản cần thiết và từ chối. D lấy được p12_para_000, trả lời đúng chủ quản hệ thống đề nghị. Hybrid và top-k lớn hơn có ích ở trường hợp này.
2. **dev-06 — tài khoản trẻ em:** A chỉ có quyền trẻ em/trách nhiệm nhà cung cấp. D bổ sung p17_para_004, trả lời đúng cha/mẹ/người giám hộ. Context rộng hơn giữ được khoản cần thiết.
3. **dev-07 — citation sai căn cứ:** hai cấu hình nêu đúng Bộ Quốc phòng nhưng cite p19_para_005 thuộc Điều 18 về tấn công mạng; tiêu đề Điều 19 nằm cuối chunk. PDF p20 mới có khoản 5 Điều 19 về khủng bố mạng. Chấm đáp án một phần và citation không hỗ trợ, dù ID hợp lệ.
4. **Query quá ngắn:** dev-03/08/11 bị viết lại thành Điều 8/22/36, mất nội dung câu hỏi. Chunk chỉ chứa số trang hoặc tiêu đề được ưu tiên. Context agent vì vậy kém hơn retrieval query gốc. Chưa sửa sau test; cải tiến tiếp theo cần dev và bộ test độc lập mới nếu dùng test để chỉnh.

| Lượt | Attempt API | Prompt token được báo | Completion token được báo | Thời gian trong trace |
|---|---:|---:|---:|---:|
| Dev A | 44 | 33.338 | 2.729 | 560 giây |
| Dev D | 43 | 45.013 | 3.045 | 802 giây |
| Test A | 15 | 13.831 | 1.056 | 182 giây |
| Test D | 19 | 18.510 | 1.121 | 312 giây |

Attempt gồm retry/429/400, không phải số câu. Lỗi transient giữ trong calls; record cuối không có lỗi hệ thống. Chỉ cộng token khi API trả usage. **Groq không trả cost**, nên không gán số 0 giả; Free tier là xác nhận người dùng. Thời gian chịu ảnh hưởng quota/network, không bao gồm toàn bộ khoảng nghỉ giữa các lần resume và không phải latency dịch vụ ổn định. D dùng nhiều token/context hơn; số retry không chứng minh thuật toán ít request hơn.

## Nâng cao

Đã xử lý toàn bộ World Development Report 2023: Migrants, Refugees, and Societies: 348 trang, 337 trang có text, 1.396 chunk/vector 1024 chiều. Index riêng 5f652e08a083cf4ec690f49d; BAAI/bge-m3 revision 5617a9f61b028005a4858fdac845db406aefb181. Có 47 vùng bảng ứng viên và 170 trang có vùng trực quan theo heuristic, chưa coi là coverage đã audit. WDR theo CC BY 3.0 IGO, có điều kiện riêng với thành phần bên thứ ba; manifest giữ nguồn/checksum.

Benchmark nâng cao: dev 15 + 3, test 24 + 6, đủ nhóm bảng/ảnh/biểu đồ/multi-hop/text. Retrieval-only dev A–E đã chạy; D có context evidence 6/15 trong baseline native extraction. Mô tả vision toàn corpus chưa hoàn tất.

Đã chạy **kiểm tra chức năng vision thật** riêng bằng OpenRouter inclusionai/ling-3.2-flash:free: search → view_image → answer trên Figure O.1, PDF p33. Model đọc đúng Population là triệu người, Age là năm, cite wdr2023:p33:visual; API báo cost 0 cho ba completion. Filter trang/visual-only được khai báo. Đây **không phải benchmark nâng cao**, không suy ra accuracy toàn tài liệu. Chưa chạy đủ 30 câu test nâng cao; **chưa có bằng chứng đạt 27/30 và không tuyên bố bonus**. Quota miễn phí còn lại không đủ hoàn tất toàn bộ dev/test nâng cao.

## Tái lập và kiểm chứng

Python 3.12.14, dependency lock Windows, PostgreSQL 16.16/pgvector 0.8.7. **53 test tự động qua**, Ruff/ty qua; runtime Streamlit kiểm tra bằng agent API cho tìm kiếm, nguồn và nhãn AI. Test hành vi không được dùng làm điểm agent.

Lệnh setup/data/DB trong README; luồng AI ở docs/AUTOMATED_REVIEW.md. Scorer ghi riêng provenance AI và không làm đổi runtime hash. Cấu hình chốt ở artifacts/frozen-basic-ai.json; bảng ở artifacts/AUTOMATED_EVALUATION.md; trace/dev/test/nhãn đầy đủ trong artifacts/runs/basic-agent-groq-*. Key, DSN thực, cache, PDF lớn và ảnh render không đưa vào bản nộp; nguồn có script tải lại và checksum.
