"""Curated WDR cases. Locations/answers come from source pages, never retrieval.

The published JSON is an annotation draft requiring a human source audit. Visual
questions refer to original figure regions, not to an LLM-generated description.
"""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from day7_rag.contracts import normalize, validate_cases
from day7_rag.evaluation import validate_benchmark
from day7_rag.io import load_json, save_json

# Each evidence item is (physical PDF page, exact locator phrase, modality).
DEV = [
    ("table", "Trong Table O.1, nước xuất cư nên làm gì với diaspora và người trở về để chuyển giao kiến thức?", "Hợp tác với diaspora và người trở về để thúc đẩy chuyển giao kiến thức và hội nhập kinh tế toàn cầu.", [(46, "Knowledge.", "table")]),
    ("table", "Ở cột hợp tác song phương, Table O.1 khuyến nghị tài trợ phát triển loại kỹ năng nào?", "Kỹ năng có nhu cầu ở cả thị trường lao động quốc gia và toàn cầu.", [(46, "Skills development.", "table")]),
    ("table", "Table O.1 liệt kê ba durable solutions truyền thống nào?", "Tự nguyện trở về, hội nhập tại chỗ hoặc tái định cư.", [(46, "voluntary return, local", "table")]),
    ("table", "Trong hàng New voices của Table O.1, tiếng nói của migrants và refugees cần hệ thống nào?", "Hệ thống đại diện và trách nhiệm giải trình để tổ chức tiếng nói của họ.", [(46, "representation and accountability", "table")]),
    ("image", "Trong panel b của Figure O.2, động cơ nào gắn với nghĩa vụ tiếp nhận thay vì lựa chọn có tiếp nhận không?", "Nỗi sợ bị tổn hại tại nước xuất xứ, gắn với người tị nạn và nhu cầu bảo vệ quốc tế cao.", [(35, "Figure O.2", "image")]),
    ("image", "Figure O.4 đặt mục tiêu chung nào cho hai nhóm ở phần stronger match?", "Maximize gains for all, tối đa hóa lợi ích cho tất cả.", [(38, "Figure O.4", "image")]),
    ("image", "Các mũi tên bên ngoài ma trận trong Figure 1.1 nhấn mạnh cần tăng cường điều gì cho tất cả người di cư?", "Tăng cường mức độ phù hợp kỹ năng và thuộc tính của tất cả người di cư với nước đến.", [(51, "Figure 1.1", "image")]),
    ("chart", "Trong Figure O.1, đơn vị trục dân số và đại lượng trục đứng là gì?", "Dân số tính bằng triệu người; trục đứng là tuổi, tính bằng năm.", [(33, "Figure O.1", "image")]),
    ("chart", "Chú thích Figure 5.2 phân biệt dữ liệu 2021 với 2022–2023 như thế nào?", "2021 là ước tính; 2022 và 2023 là dự báo.", [(158, "Figure 5.2", "image")]),
    ("chart", "Trong Figure 7.2, trục số người dùng đơn vị gì và dữ liệu năm 2022 chốt ở thời điểm nào?", "Triệu người; dữ liệu tính đến giữa năm 2022.", [(236, "Figure 7.2", "image")]),
    ("multi-hop", "Dùng Box O.1 ở hai trang, lấy 31 triệu người di cư tại GCC chia cho tổng 184 triệu: tỷ lệ xấp xỉ bao nhiêu?", "31/184 × 100 ≈ 16,85%, phù hợp với tỷ lệ làm tròn khoảng 17% trong báo cáo.", [(31, "184 million migrants", "text"), (32, "31 million economic migrants", "text")]),
    ("multi-hop", "Theo hai trang Glossary, asylum-seeker khác refugee ở tình trạng được xét bảo vệ như thế nào?", "Asylum-seeker đã nộp đơn nhưng chưa có quyết định cuối cùng; refugee đã được nước tiếp nhận trao bảo vệ quốc tế theo các căn cứ được nêu.", [(27, "not yet received a final decision", "text"), (28, "A person who has been granted international protection", "text")]),
    ("multi-hop", "Đối chiếu Figure O.1 với phần Overview về Italy: xu hướng cơ cấu tuổi và quy mô dân số tới 2100 là gì?", "Cơ cấu dân số già hóa; Overview dự báo dân số giảm từ 59 triệu xuống 32 triệu vào 2100.", [(33, "Figure O.1", "image"), (32, "32 million, by 2100", "text")]),
    ("text", "Glossary dùng thuật ngữ economic migrant cho người di chuyển vì nhóm lý do nào?", "Vì những lý do ngoài bị đàn áp hoặc nguy cơ tổn hại nghiêm trọng, như cải thiện điều kiện sống bằng việc làm hoặc đoàn tụ gia đình.", [(27, "economic migrant", "text")]),
    ("text", "Theo Glossary, naturalized citizen là ai?", "Người di cư đã có quốc tịch tại nước đến.", [(28, "naturalized citizen", "text")]),
]

TEST = [
    ("table", "Theo Table O.1, nước xuất cư cần làm gì về kiều hối khi kỹ năng người di cư có nhu cầu cao?", "Tận dụng kiều hối để giảm nghèo và giảm chi phí chuyển kiều hối.", [(46, "Leverage remittances", "table")]),
    ("table", "Trong Table O.1, nước đến hỗ trợ công dân bản địa bị ảnh hưởng tiêu cực bằng hai nhóm công cụ nào?", "Bảo trợ xã hội và đầu tư công để hỗ trợ tác động tới việc làm và dịch vụ công.", [(46, "Support to nationals.", "table")]),
    ("table", "Table O.1 yêu cầu thỏa thuận lao động song phương làm gì với chi phí tuyển dụng?", "Giảm chi phí tuyển dụng, đồng thời cấu trúc và tạo thuận lợi cho các luồng di chuyển đôi bên cùng có lợi.", [(46, "Reduce recruitment costs.", "table")]),
    ("table", "Ở phần weak match, fear motive của Table O.1, self-reliance được thúc đẩy bằng quyền tiếp cận việc làm nào?", "Cho phép người tị nạn tiếp cận việc làm trong thị trường lao động chính thức.", [(46, "Self-reliance.", "table")]),
    ("table", "Trong Table O.1, nước quá cảnh cuối cùng nên phối hợp với nước đến như thế nào khi weak match và no fear motive?", "Phối hợp để tiếp nhận người di cư hoặc đưa họ trở về một cách nhân đạo.", [(46, "last transit country", "table")]),
    ("table", "Hàng Open data trong Table O.1 gắn việc mở dữ liệu cho nghiên cứu với điều kiện bảo vệ nào?", "Tôn trọng quyền riêng tư của người di cư và người tị nạn.", [(46, "Open data.", "table")]),
    ("image", "Trong Figure O.3, Indian engineers in Silicon Valley nằm ở góc nào theo cả match và motive?", "Góc trên trái: stronger match và opportunity at destination.", [(36, "Figure O.3", "image")]),
    ("image", "Figure O.3 đặt Syrian entrepreneur refugees in Türkiye khác Rohingya không được làm việc ở Bangladesh như thế nào?", "Cả hai ở phía fear motive; doanh nhân Syria ở stronger match, còn Rohingya không được làm việc nằm ở weaker match.", [(36, "Figure O.3", "image")]),
    ("image", "Trong Figure O.5, khối AT DESTINATION bên phải nêu ba hướng giúp người tị nạn có weak match?", "Tạo thuận lợi cho di chuyển trong nước, cho phép làm việc và đưa họ vào các hệ thống quốc gia.", [(41, "Figure O.5", "image")]),
    ("image", "Figure O.7 đặt những ví dụ nào trong hợp tác song phương và hợp tác đa phương?", "Song phương: thỏa thuận lao động và Global Skills Partnerships; đa phương: chia sẻ trách nhiệm đối với người tị nạn và thiết lập chuẩn mực.", [(45, "Figure O.7", "image")]),
    ("image", "Đường đứt nét ở góc dưới trái Figure O.6 phân biệt hai nhóm distressed migrants theo tiêu chí nào?", "Phân biệt người có một số nhu cầu bảo vệ quốc tế với người không có nhu cầu đó.", [(43, "Figure O.6", "image")]),
    ("chart", "Trong Figure 4.4a, hành lang nào có mức tăng thu nhập lớn nhất và giá trị là bao nhiêu?", "India–United Arab Emirates, tăng 298%. Đơn vị là phần trăm tăng thu nhập.", [(127, "Figure 4.4", "image")]),
    ("chart", "Theo Figure 5.3, kiều hối/GDP của Tonga cao hơn Lebanon bao nhiêu điểm phần trăm và dữ liệu thuộc năm nào?", "Tonga 50% và Lebanon 38%; chênh 12 điểm phần trăm, theo ước tính năm 2022.", [(159, "Figure 5.3", "image")]),
    ("chart", "Trong Figure 5.7, kênh nào có chi phí thấp nhất ở 2022 Q2, và đồ thị đo chi phí cho khoản kiều hối bao nhiêu USD?", "Mobile operator thấp nhất; đồ thị đo chi phí trung bình tính theo phần trăm khoản gửi 200 USD.", [(164, "Figure 5.7", "image")]),
    ("chart", "Trong Figure 7.6, tỷ trọng của Mỹ, Canada, Đức và Thụy Điển lần lượt là bao nhiêu và cộng lại bằng bao nhiêu?", "29%, 15%, 14%, 13%; tổng 71% người tị nạn được tái định cư.", [(243, "Figure 7.6", "image")]),
    ("chart", "Figure 7.9 và Figure 7.10 dùng đơn vị trục đứng khác nhau ra sao; chú giải 7.9 có những nhóm nào?", "Figure 7.9 dùng phần trăm tổng người tị nạn, gồm Returned, Resettled, Naturalized; Figure 7.10 dùng triệu người.", [(253, "Figure 7.9", "image")]),
    ("multi-hop", "Theo hai trang Glossary, emigrant và immigrant khác nhau ở góc nhìn của nước nào?", "Emigrant theo góc nhìn nước xuất cư; immigrant theo góc nhìn nước đến.", [(27, "emigrant", "text"), (28, "immigrant", "text")]),
    ("multi-hop", "Kết hợp Figure 4.4a và Figure 5.3: mức tăng thu nhập của lao động Tonga đến New Zealand và tỷ trọng kiều hối/GDP Tonga là bao nhiêu, với đơn vị riêng?", "Tăng thu nhập 263% cho hành lang Tonga–New Zealand; kiều hối bằng 50% GDP Tonga theo ước tính 2022. Hai tỷ lệ đo hai đại lượng khác nhau.", [(127, "Figure 4.4", "image"), (159, "Figure 5.3", "image")]),
    ("multi-hop", "Kết hợp phần đầu Chương 5 và phần chi phí chuyển tiền: quy mô kiều hối tới nước thu nhập thấp/trung bình năm 2021 là bao nhiêu và quy định nào hạn chế phát triển mobile digital money?", "Khoảng 605 tỷ USD năm 2021; các quy định chống rửa tiền và tài trợ khủng bố hạn chế tăng trưởng và khả năng cung cấp dịch vụ mobile digital money.", [(158, "US$605 billion in 2021", "text"), (164, "money laundering", "text")]),
    ("multi-hop", "Dùng Figure 7.2 và Figure 7.10 ở hai trang: hai dấu hiệu nào cho thấy số người tị nạn tăng trong khi các giải pháp chưa theo kịp?", "Số người tị nạn tăng hơn gấp đôi trong thập kỷ vừa qua; số người mới được ghi nhận vượt số giải pháp cho người tị nạn mỗi năm từ 2010 theo đồ thị và phần giải thích.", [(236, "Figure 7.2", "image"), (253, "Figure 7.10", "image")]),
    ("text", "Theo Glossary, internally displaced persons có nhất thiết vượt biên giới quốc gia không?", "Không; họ bị di dời trong phạm vi biên giới một quốc gia.", [(28, "internally displaced persons", "text")]),
    ("text", "Glossary mô tả nguyên tắc non-refoulement cấm điều gì?", "Cấm đưa người trở lại nơi họ có nguy cơ bị đàn áp, tra tấn hoặc tổn hại nghiêm trọng khác.", [(28, "legal principle prohibiting", "text")]),
    ("text", "Theo Glossary, distressed migrant có đáp ứng tiêu chí refugee status không và việc di chuyển thường có tính chất gì?", "Không đáp ứng các tiêu chí áp dụng cho quy chế người tị nạn; việc di chuyển thường không chính quy và không an toàn.", [(27, "distressed migrant", "text")]),
    ("text", "Trong Glossary, stateless person được định nghĩa như thế nào?", "Người không là công dân của bất kỳ quốc gia nào.", [(28, "stateless person", "text")]),
]

ABSENT = {
    "dev": [
        ("Báo cáo xác nhận chính xác bao nhiêu người di cư toàn cầu vào ngày 01/01/2026?", "Báo cáo 2023 không cung cấp số liệu quan sát tại ngày 01/01/2026."),
        ("Báo cáo công bố biểu lệ phí visa Canada áp dụng từng tháng năm 2026 là bao nhiêu?", "Không có biểu phí visa Canada theo từng tháng năm 2026."),
        ("Báo cáo cho biết tên và số định danh của từng cá nhân trong 37 triệu người tị nạn là gì?", "Báo cáo dùng số liệu tổng hợp, không có danh sách định danh từng cá nhân."),
    ],
    "test": [
        ("Báo cáo xác nhận tổng kiều hối Việt Nam thực nhận cả năm 2026 là bao nhiêu USD?", "Không có số liệu thực nhận cả năm 2026 trong báo cáo xuất bản năm 2023."),
        ("Báo cáo công bố ngày có quyết định của hồ sơ xin tị nạn cá nhân số VN-2026-001 là ngày nào?", "Không có hồ sơ cá nhân VN-2026-001 hoặc lịch ra quyết định của hồ sơ này."),
        ("Trong báo cáo, ngân hàng nào ở Hà Nội có phí chuyển 200 USD thấp nhất vào ngày 16/11/2026?", "Có so sánh kênh chuyển tiền tổng quát nhưng không có bảng giá ngân hàng Hà Nội vào ngày yêu cầu."),
        ("Báo cáo chỉ định khoản bồi thường cụ thể cho riêng gia đình Nguyễn Văn A sau khi bị từ chối visa là bao nhiêu?", "Không có tình huống và quyết định bồi thường cá nhân được nêu trong câu hỏi."),
        ("Báo cáo cung cấp số điện thoại riêng của người di cư Tonga đứng sau cột số liệu Figure 5.3 là gì?", "Figure 5.3 là số liệu cấp quốc gia, không định danh hay công bố điện thoại cá nhân."),
        ("Báo cáo xác nhận chính xác số người sẽ tái định cư tại Canada ngày 01/01/2030 là bao nhiêu?", "Không có số quan sát hay dự báo chính xác cho một ngày tương lai cụ thể như vậy."),
    ],
}


def locate(chunks, page, needle, modality):
    candidates = [c for c in chunks if c["page"] == page and
                  ((modality == "text" and c["content_type"] == "text") or
                   (modality == "table" and c["content_type"] == "table") or
                   (modality == "image" and c["id"] == f"wdr2023:p{page}:visual")) and
                  normalize(needle).casefold() in normalize(c["text"]).casefold()]
    if not candidates:
        raise ValueError(f"Curated locator not found: page {page}, {needle}, {modality}")
    c = min(candidates, key=lambda row: len(row["text"]))
    # Preserve the source's actual spelling and spacing in the evidence quote.
    haystack = normalize(c["text"])
    start = haystack.casefold().index(normalize(needle).casefold())
    quote = haystack[start:start + len(normalize(needle))]
    return {"source_id": "wdr2023", "page": page, "evidence": quote,
            "region_id": c["id"], "bbox": c["bbox"], "modality": modality,
            "locator": needle, "printed_page": page - 30 if page >= 31 else c["metadata"].get("page_label")}


def main():
    chunks = load_json("work/corpora/wdr2023/chunks.json")
    all_cases = []
    for split, specifications in (("dev", DEV), ("test", TEST)):
        cases = []
        for i, (group, question, answer, evidence) in enumerate(specifications, 1):
            case = {"id": f"advanced-{split}-{i:02d}", "split": split, "group": group,
                    "question": question, "answerable": True, "expected_answer": answer,
                    "evidence_sets": [[locate(chunks, *e) for e in evidence]],
                    "source_review": "Agent-authored source annotation; final human audit required",
                    "grading_note": "Check complete answer, units/conditions/calculation, original figure/table and supporting citations."}
            if len({e[0] for e in evidence}) > 1:
                case["requires_multiple_pages"] = True
            cases.append(case)
        for i, (question, reason) in enumerate(ABSENT[split], 1):
            cases.append({"id": f"advanced-{split}-absent-{i}", "split": split, "group": "unanswerable",
                          "question": question, "answerable": False, "expected_behavior": "search_and_abstain",
                          "absence_reason": reason, "absence_checks": "Full report scope, contents and dates inspected; confirm with original source before grading."})
        validate_cases(cases, chunks)
        save_json(Path("data/benchmarks/advanced") / f"{split}.json", cases)
        all_cases.extend(cases)
    validate_benchmark(all_cases, advanced=True)
    print(f"Prepared {len(all_cases)} advanced cases; held-out queries have not been run.")


if __name__ == "__main__":
    main()
