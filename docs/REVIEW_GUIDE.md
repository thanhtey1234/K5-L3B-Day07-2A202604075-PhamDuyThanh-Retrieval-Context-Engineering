# Chấm dev trên giao diện

Đây là luồng thủ công tùy chọn. Kết quả chốt hiện dùng nhãn AI theo yêu cầu người dùng; nhãn AI và thủ công được lưu riêng.

1. Mở `http://localhost:8501`, chọn **Thí nghiệm**.
2. Chọn lượt `artifacts/runs/basic-agent-groq-dev/A-dense`, sau đó làm tương tự với `D-context`. Đây là hai cấu hình khác nhau; chấm riêng từng đáp án.
3. Chọn từng câu. Đọc đáp án agent và **Đáp án tham chiếu để đối chiếu**. Annotation tham chiếu cũng cần kiểm tra nguồn, không mặc định là đúng.
4. Mở **Đối chiếu nguồn của câu đang chấm**: chọn ID nguồn, đọc nguyên văn context và bấm **Mở bản gốc để kiểm tra**. So sánh đúng trang PDF; lỗi OCR không phải bằng chứng bản gốc sai.
5. Với câu có đáp án trong tài liệu, chọn:
   - **Context 0/1/2:** thiếu / có một phần / đủ bằng chứng trả lời trọn câu.
   - **Câu trả lời 0/1/2:** sai hoặc thiếu / đúng một phần / đầy đủ, giữ đúng điều kiện và đơn vị.
   - Nếu agent từ chối câu có đáp án: câu trả lời **0**. Context vẫn chấm theo những đoạn thực sự được đưa cho agent.
6. Với từng citation, chỉ tích **Nguồn hỗ trợ citation** khi nội dung nguồn thực sự hỗ trợ khẳng định gắn với ID đó. ID tồn tại không đồng nghĩa citation hỗ trợ đúng.
7. Với câu benchmark thiếu evidence, chỉ tích **Từ chối đúng** khi agent thực sự từ chối và không bịa nội dung ngoài corpus. Với câu có đáp án, để ô này không tích.
8. Sau khi đọc bản gốc, tích **Đã đối chiếu với tài liệu gốc**, ghi lý do cụ thể và bấm **Lưu nhãn**. Ví dụ: “PDF trang 1 nêu đủ ba thuộc tính; đáp án giữ đúng nội dung và citation trỏ tới đoạn đó.” Không dùng ví dụ này khi chưa kiểm tra câu tương ứng.
9. Mỗi lần **Lưu nhãn** chỉ lưu **một câu**, không lưu cả lượt A/D. Dùng **Lưu và sang câu chưa chấm** để lưu câu hiện tại rồi chuyển tiếp, hoặc **Đến câu chưa chấm tiếp theo** ở đầu trang. Chấm đến khi thanh tiến độ ghi đủ **17/17** cho A, sau đó làm tương tự với D. Trang nạp lại nhãn cũ khi quay lại. Không bấm hỏi agent ngoài benchmark trong lúc đang dành quota cho thí nghiệm.

Có thể chấm câu đã hoàn tất khi job vẫn đang chạy; tải lại trang để thấy câu mới. Nhãn lưu tại thư mục lượt chạy trong `reviews.json`. Lỗi hệ thống được tính riêng, không đổi thành từ chối đúng. CLI `review` chỉ tổng hợp khi lượt chạy đầy đủ.

Khi hoàn tất cả A và D, nhắn “đã chấm xong A và D”. Sau đó kiểm tra nhãn, so sánh chất lượng trên dev, freeze cấu hình rồi mới chạy test. Không dùng test để sửa prompt, retrieval hoặc nhãn.
