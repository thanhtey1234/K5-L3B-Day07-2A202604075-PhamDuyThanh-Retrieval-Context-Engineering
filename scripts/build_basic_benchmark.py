"""Materialize curated source-based cases, independently of retrieval results.

Gold quotes are resolved by physical source page plus a manually chosen phrase,
never by a retriever. Day 6's already-exposed test questions are not reused.
"""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from day7_rag.contracts import normalize, validate_cases
from day7_rag.io import load_json, save_json

DEV = [
    (1, "An ninh thông tin mạng bảo đảm ba thuộc tính nào của thông tin?", "Tính nguyên vẹn, tính bảo mật và tính khả dụng.", "tính khả dụng"),
    (6, "Bộ Ngoại giao phối hợp với những bộ nào trong hợp tác quốc tế về an ninh mạng?", "Bộ Công an và Bộ Quốc phòng.", "Bộ Ngoại giao có trách nhiệm"),
    (8, "Theo Điều 8, hệ thống thông tin cấp độ 5 có thể gây mức tổn hại nào?", "Có thể làm tổn hại đặc biệt nghiêm trọng tới an ninh quốc gia.", "đ) Cấp độ 5"),
    (10, "Chủ quản hệ thống thông tin quan trọng về an ninh quốc gia phải thông báo kết quả tự kiểm tra định kỳ trước tháng nào?", "Trước tháng 10 hằng năm, bằng văn bản cho lực lượng chuyên trách có thẩm quyền.", "trước tháng 10"),
    (12, "Theo Điều 12, ngoài trường hợp có hành vi vi phạm được liệt kê, hệ thống có thể được kiểm tra khi ai đề nghị?", "Khi có đề nghị của chủ quản hệ thống thông tin.", "Khi có đề nghị của chủ quản"),
    (17, "Ai đăng ký tài khoản khi trẻ em sử dụng dịch vụ giá trị gia tăng trên không gian mạng?", "Cha, mẹ hoặc người giám hộ đăng ký bằng thông tin của họ và giám sát, quản lý nội dung trẻ em sử dụng.", "Trẻ em sử dụng dịch vụ giá trị gia tăng"),
    (20, "Cơ quan nào chủ trì phòng, chống khủng bố mạng đối với hệ thống thông tin quân sự?", "Bộ Quốc phòng chủ trì, phối hợp với bộ, ngành liên quan.", "5. Bộ Quốc phòng chủ trì"),
    (22, "Điều 22 mô tả xung đột thông tin trên không gian mạng do bao nhiêu tổ chức thực hiện?", "Hai hoặc nhiều tổ chức trong nước và nước ngoài sử dụng biện pháp công nghệ, kỹ thuật thông tin gây tổn hại.", "Xung đột thông tin là việc hai"),
    (26, "Dịch vụ khôi phục dữ liệu có nằm trong danh sách dịch vụ an ninh mạng ở Điều 28 không?", "Có, dịch vụ khôi phục dữ liệu được liệt kê tại khoản 2 Điều 28.", "Dịch vụ khôi phục dữ liệu"),
    (28, "Theo Điều 34, người quản trị hệ thống thông tin cấp độ 3–5 trong cơ quan nhà nước được miễn tập huấn chuyên sâu trong trường hợp nào?", "Trường hợp cá nhân đã được đào tạo chuyên ngành an ninh mạng.", "trừ các cá nhân đã được đào tạo"),
    (29, "Theo Điều 36, những chủ thể nào có quyền nghiên cứu, phát triển an ninh mạng?", "Cơ quan, tổ chức, cá nhân có liên quan.", "có quyền nghiên cứu, phát triển"),
    (29, "Ai chịu trách nhiệm xây dựng hoạt động phổ biến kiến thức an ninh mạng cho địa phương?", "Ủy ban nhân dân cấp tỉnh.", "Ủy ban nhân dân cấp tỉnh"),
    (30, "Đơn vị không thuộc nhóm được ngân sách nhà nước bảo đảm theo khoản 1 Điều 38 lấy kinh phí bảo vệ an ninh mạng từ đâu?", "Tự bảo đảm kinh phí cho cơ quan, tổ chức, đơn vị mình.", "tự bảo đảm kinh phí"),
    (32, "Theo khoản 2 Điều 40, chủ quản hệ thống sử dụng ngân sách nhà nước phải chỉ định ai phụ trách an ninh mạng?", "Chỉ định cá nhân hoặc bộ phận phụ trách an ninh mạng.", "Chỉ định cá nhân, bộ phận"),
    (33, "Doanh nghiệp cung cấp dịch vụ trên không gian mạng phải làm gì ngay khi xảy ra sự cố an ninh mạng?", "Ngay lập tức triển khai phương án ứng cứu khẩn cấp và đồng thời báo cáo ngay lực lượng chuyên trách.", "Khi xảy ra sự cố an ninh mạng"),
]
TEST = [
    (36, "Khoản 17 Điều 43 bãi bỏ khoản nào của Luật Thư viện số 46/2019/QH14?", "Bãi bỏ khoản 3 Điều 49.", "Bãi bỏ khoản 3 Điều 49"),
    (36, "Theo điều khoản chuyển tiếp, giấy phép kinh doanh sản phẩm, dịch vụ an toàn thông tin mạng đã cấp trước ngày luật có hiệu lực còn giá trị đến khi nào?", "Đến hết thời hạn được ghi trên giấy phép.", "2. Các loại giấy phép kinh doanh"),
    (33, "Thông tin định danh địa chỉ IP của người dùng Internet phải được doanh nghiệp cung cấp cho lực lượng nào?", "Lực lượng chuyên trách bảo vệ an ninh mạng để thực hiện biện pháp bảo vệ an ninh mạng.", "định danh địa chỉ IP"),
    (28, "Kiến thức an ninh mạng được đưa vào môn học và chương trình bồi dưỡng nào theo Điều 33?", "Môn học giáo dục quốc phòng và an ninh trong nhà trường và chương trình bồi dưỡng kiến thức quốc phòng và an ninh.", "Nội dung giáo dục, bồi dưỡng kiến thức"),
    (32, "Ban Cơ yếu Chính phủ giúp bộ trưởng nào quản lý nhà nước về mật mã dân sự và an ninh mạng trong phạm vi quản lý?", "Giúp Bộ trưởng Bộ Quốc phòng.", "Ban Cơ yếu Chính phủ giúp Bộ trưởng"),
]
ABSENT = {
    "dev": [
        ("Báo cáo thống kê của luật cho biết có chính xác bao nhiêu vụ tấn công ransomware tại Việt Nam trong năm 2026?", "Luật quy định trách nhiệm và biện pháp; không có bảng thống kê số vụ ransomware năm 2026.", ["ransomware"]),
        ("Luật chỉ định hãng phần mềm diệt virus nào bắt buộc mọi cá nhân phải mua?", "Không quy định tên hãng phần mềm diệt virus bắt buộc cho mọi cá nhân.", ["diệt virus"]),
    ],
    "test": [
        ("Theo riêng văn bản luật này, mức phạt tiền cụ thể bằng bao nhiêu đồng khi cá nhân làm lộ mật khẩu tài khoản?", "Văn bản có quy định xử lý vi phạm nhưng không ấn định mức tiền phạt cụ thể cho tình huống này; cần văn bản khác.", ["mức phạt"]),
        ("Địa chỉ API và mã xác thực kỹ thuật nào được luật công bố để doanh nghiệp gửi báo cáo sự cố tới Bộ Công an?", "Văn bản không công bố endpoint API hoặc mã xác thực kỹ thuật cho báo cáo sự cố.", ["API", "endpoint"]),
    ],
}


def main():
    root = Path("work/corpora/day6")
    chunks = load_json(root / "chunks.json")
    output = Path("data/benchmarks/basic")
    all_cases = []
    for split, specifications in (("dev", DEV), ("test", TEST)):
        cases = []
        for i, (page, question, answer, needle) in enumerate(specifications, 1):
            matches = [c for c in chunks if c["page"] == page and normalize(needle) in normalize(c["text"])]
            if not matches:
                raise ValueError(f"Curated evidence not found: {split}/{i}, page {page}, {needle}")
            selected = matches[0]
            cases.append({"id": f"basic-{split}-{i:02d}", "split": split, "question": question,
                          "answerable": True, "expected_answer": answer,
                          "gold": [{"source_id": selected["source_id"], "page": page, "evidence": selected["text"]}],
                          "source_review": "Agent-authored from Day 6 OCR; human PDF audit required before final submission"})
        for i, (question, reason, checks) in enumerate(ABSENT[split], 1):
            cases.append({"id": f"basic-{split}-absent-{i}", "split": split, "question": question,
                          "answerable": False, "expected_behavior": "search_and_abstain", "absence_reason": reason,
                          "absence_checks": checks, "source_review": "Full corpus inspected; final human audit required"})
        validate_cases(cases, chunks)
        save_json(output / f"{split}.json", cases)
        all_cases.extend(cases)
    print(f"Prepared {len(all_cases)} source-based basic cases; no retrieval or model generation used.")


if __name__ == "__main__":
    main()
