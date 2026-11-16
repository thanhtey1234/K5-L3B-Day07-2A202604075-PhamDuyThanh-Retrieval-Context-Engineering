# Đánh giá tự động có đối chiếu nguồn

**Nhãn do AI chấm theo yêu cầu người dùng; chưa được con người xác minh đầy đủ. Không phải điểm môn học.**

| Cấu hình | Split | Grounded đầy đủ | Citation hỗ trợ | Từ chối đúng | Từ chối sai | Request |
|---|---|---:|---:|---:|---:|---:|
| A-dense | dev | 4/15 | 4/5 | 2/2 | 10/15 | 44 |
| D-context | dev | 6/15 | 6/7 | 2/2 | 8/15 | 43 |
| A-dense | test | 2/5 | 2/2 | 2/2 | 3/5 | 15 |
| D-context | test | 3/5 | 3/3 | 2/2 | 2/5 | 19 |

Grounded đầy đủ yêu cầu: đáp án và context đều 2/2, có citation và mọi citation hỗ trợ đúng. Câu có đáp án nhưng agent từ chối nhận điểm 0. Lỗi vẫn nằm trong mẫu số. Citation không được chấm đúng chỉ vì ID tồn tại.

Groq không trả cost trong usage đã nhận; số tiền không được gán 0. Token/request/latency và nhãn từng câu được giữ trong artifact. Nhãn thủ công ban đầu được giữ riêng trong reviews.json.
