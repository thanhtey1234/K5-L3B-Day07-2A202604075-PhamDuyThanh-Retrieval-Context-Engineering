# Benchmark cá nhân Day 7

| Bộ | Dev có đáp án / thiếu evidence | Test có đáp án / thiếu evidence |
|---|---:|---:|
| Basic | 15 / 2 | 5 / 2 |
| Advanced | 15 / 3 | 24 / 6 |

Advanced test có 6 bảng, 5 ảnh/sơ đồ, 5 biểu đồ, 4 multi-hop và 4 text. Mỗi câu thuộc một nhóm chính. Basic test dùng các nội dung khác với năm câu test Day 6 đã công khai; không lấy kết quả Day 6 làm test độc lập.

Đây là **bản annotation được soạn từ nguồn**, có đáp án tham chiếu và vị trí evidence. `source_review` ghi rõ cần con người đối chiếu PDF trước khi nộp. Nhãn câu trả lời của agent hoàn toàn riêng, chỉ tạo sau khi chạy thật. Không có nhãn grounding hay điểm bonus giả.

- Basic dùng corpus Day 6 37 trang ở commit `663df9fa1c0f7c5bafcb1e21f47433e5137d3057`; OCR được giữ nguyên, gồm lỗi nhận dạng.
- Advanced dùng *World Development Report 2023: Migrants, Refugees, and Societies*, PDF 348 trang, SHA-256 `9577adf6a2849918eaf406aa975082b278b26cd880277b4d4e87336f6200ee84`. World Bank, 2023, doi:10.1596/978-1-4648-1941-4, CC BY 3.0 IGO. Một số ảnh/thành phần có quyền riêng.
- Đây là phần chuyển thể phục vụ nghiên cứu/học tập, không được World Bank bảo trợ. Bản dịch câu hỏi/đáp án tiếng Việt do người soạn tạo, không phải bản dịch chính thức của World Bank.

`scripts/build_basic_benchmark.py` và `scripts/build_advanced_benchmark.py` tái tạo JSON từ các lựa chọn thủ công theo trang và cụm từ, **không dùng retrieval hoặc đáp án model để tìm gold**. Nếu thay đổi extractor làm đổi region ID, phải tái tạo và audit benchmark trước khi freeze; không cập nhật benchmark test dựa trên kết quả test.

Chỉ chạy `dev.json` để thử nghiệm. Các file `test.json` được dùng để kiểm tra schema/chuẩn bị evidence trước khi seal, chưa được dùng để chọn cấu hình. Chạy test cần file freeze tạo từ một lượt agent dev đã được chấm. Nếu đã dùng test để điều chỉnh, chuẩn bị test mới thay vì chỉ đổi run directory.
