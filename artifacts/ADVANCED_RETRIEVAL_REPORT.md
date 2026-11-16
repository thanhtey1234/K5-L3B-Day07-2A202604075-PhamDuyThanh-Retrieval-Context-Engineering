# Kết quả thực nghiệm Day 7

Chỉ tổng hợp artifact đã chạy; nhãn thủ công chưa có sẽ được ghi rõ.

| Cấu hình | Split | Chế độ | Hit@1 | Evidence Hit@3 | Context evidence | Lỗi | Request |
|---|---|---|---|---|---|---:|---:|
| A-dense | dev | retrieval | 1/15 (6.7%) | 4/15 (26.7%) | 1/15 (6.7%) | 0 | 0 |
| B-bm25 | dev | retrieval | 2/15 (13.3%) | 4/15 (26.7%) | 3/15 (20.0%) | 0 | 0 |
| C-hybrid | dev | retrieval | 3/15 (20.0%) | 5/15 (33.3%) | 4/15 (26.7%) | 0 | 0 |
| D-context | dev | retrieval | 3/15 (20.0%) | 5/15 (33.3%) | 6/15 (40.0%) | 0 | 0 |
| E-multihop | dev | retrieval | 3/15 (20.0%) | 5/15 (33.3%) | 6/15 (40.0%) | 0 | 0 |

## Đánh giá câu trả lời

- A-dense: chưa có đánh giá thủ công; không suy ra grounding từ retrieval hoặc citation ID.
- B-bm25: chưa có đánh giá thủ công; không suy ra grounding từ retrieval hoặc citation ID.
- C-hybrid: chưa có đánh giá thủ công; không suy ra grounding từ retrieval hoặc citation ID.
- D-context: chưa có đánh giá thủ công; không suy ra grounding từ retrieval hoặc citation ID.
- E-multihop: chưa có đánh giá thủ công; không suy ra grounding từ retrieval hoặc citation ID.
