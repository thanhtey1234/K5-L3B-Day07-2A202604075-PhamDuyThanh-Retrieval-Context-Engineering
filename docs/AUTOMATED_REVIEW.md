# Chấm AI theo yêu cầu người dùng

Người dùng yêu cầu chuyển sang chấm tự động và tiếp tục vào ngày 16/11/2026. Luồng này tách khỏi chấm thủ công, không đánh dấu giả `reviewed_original_source=true` và không ghi đè `reviews.json` đã có.

## Nguồn và nhãn

- PDF gốc: URL trong manifest Day 6, 37 trang scan, không có text native. SHA-256 `eded93a3e2820913c6d0801a24977b4588d65c7da1838a952e43faed9af78b08`.
- Trợ lý AI đọc trang PDF đã render, context thực, câu trả lời và đáp án tham chiếu. Mọi điểm được ghi riêng trong `reviews.ai.json` với reviewer AI, trang nguồn, checksum và lý do. Tìm keyword trên corpus OCR chỉ hỗ trợ kiểm tra phạm vi câu thiếu evidence; không coi việc không khớp keyword là chứng minh vắng mặt tuyệt đối.
- `scripts/automated_review.py` kiểm tra và tổng hợp các nhãn này. Script không tự suy ra đúng/sai từ ID hay keyword. Nhãn là đánh giá ngữ nghĩa của AI, không phải mô hình judge độc lập hay điểm giảng viên.
- Các field bắt buộc: `reviewer_type=ai`, `reviewed_original_source=false`, `ai_reviewed_source=true`; không giả xác nhận con người. Nhãn thủ công 1 câu ban đầu được giữ nguyên, kể cả khác với nhận định AI.
- Câu có đáp án nhưng agent từ chối nhận điểm 0. Grounded đầy đủ cần đáp án/context đều 2, có citation và mọi citation hỗ trợ đúng. Ví dụ dev-07 có đúng tên Bộ Quốc phòng nhưng cite khoản thuộc Điều 18 thay cho Điều 19: chấm một phần và citation không hỗ trợ.

## Tái lập

```powershell
.venv/Scripts/python.exe scripts/fetch_original_day6.py
.venv/Scripts/python.exe scripts/automated_review.py review --run artifacts/runs/basic-agent-groq-dev/A-dense --cases data/benchmarks/basic/dev.json --source-pdf work/corpora/day6/original-law.pdf
.venv/Scripts/python.exe scripts/automated_review.py review --run artifacts/runs/basic-agent-groq-dev/D-context --cases data/benchmarks/basic/dev.json --source-pdf work/corpora/day6/original-law.pdf
.venv/Scripts/python.exe scripts/automated_review.py freeze --dev-root artifacts/runs/basic-agent-groq-dev --corpus work/corpora/day6 --test-cases data/benchmarks/basic/test.json --source-pdf work/corpora/day6/original-law.pdf --output work/frozen-basic-ai.json
$env:HF_HUB_OFFLINE='1'
.venv/Scripts/python.exe scripts/run_frozen_test.py --corpus work/corpora/day6 --cases data/benchmarks/basic/test.json --frozen work/frozen-basic-ai.json --output work/runs/basic-agent-groq-test
```

Kết quả và nhãn ngữ nghĩa được giữ duy nhất trong `artifacts/runs/`; các lệnh review có thể tổng hợp offline từ đó. Chỉ chạy lệnh freeze/test nếu muốn tạo một lượt đánh giá mới; kết quả mới sinh ở `work/`, không ghi đè frozen/trace đã bàn giao. Chạy lại inference cần API và quota.

## Chọn cấu hình và khóa test

Chỉ so sánh A/D trên dev, cùng model/corpus/case/code. Chọn theo grounded đầy đủ, citation, abstention, context, rồi request/latency. Freeze AI có đủ hash code inference, corpus, test, model, dev trace, nhãn và phiên bản evaluator. Runner test vẫn dùng toàn bộ kiểm tra frozen config của package hiện có; không đưa gold/đáp án vào agent, không sửa cấu hình sau khi xem kết quả test.

Evaluator được thêm ngoài package inference để không làm đổi hash chỉ vì chuyển cách chấm. Mọi thay đổi hành vi agent/retrieval vẫn đổi hash package và cần dev/freeze mới. Cách chấm AI không thay thế xác minh độc lập; báo cáo phải giữ nhãn chưa được con người xác minh.

## Giới hạn

Không dùng tỷ lệ AI chấm để tuyên bố điểm môn học hoặc bonus 90% nâng cao. Kết quả thấp, citation sai, từ chối sai và lỗi hệ thống đều được giữ. PDF/OCR có thể lệch ngắt trang; điều khoản chuyển tiếp ở PDF trang 36 tiếp tục sang 37, nên AI đọc cả hai trang khi chấm câu test tương ứng.
