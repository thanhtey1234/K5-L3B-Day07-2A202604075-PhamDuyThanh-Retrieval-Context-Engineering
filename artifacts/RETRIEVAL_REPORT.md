# Kết quả thực nghiệm Day 7

Chỉ tổng hợp artifact đã chạy; nhãn thủ công chưa có sẽ được ghi rõ.

| Cấu hình | Split | Chế độ | Hit@1 | Evidence Hit@3 | Context evidence | Lỗi | Request |
|---|---|---|---|---|---|---:|---:|
| A-dense | dev | retrieval | 10/15 (66.7%) | 11/15 (73.3%) | 11/15 (73.3%) | 0 | 0 |
| B-bm25 | dev | retrieval | 11/15 (73.3%) | 12/15 (80.0%) | 12/15 (80.0%) | 0 | 0 |
| C-hybrid | dev | retrieval | 8/15 (53.3%) | 14/15 (93.3%) | 14/15 (93.3%) | 0 | 0 |
| D-context | dev | retrieval | 8/15 (53.3%) | 14/15 (93.3%) | 15/15 (100.0%) | 0 | 0 |
| E-multihop | dev | retrieval | 8/15 (53.3%) | 14/15 (93.3%) | 15/15 (100.0%) | 0 | 0 |

## Đánh giá câu trả lời

- A-dense: chưa có đánh giá thủ công; không suy ra grounding từ retrieval hoặc citation ID.
- B-bm25: chưa có đánh giá thủ công; không suy ra grounding từ retrieval hoặc citation ID.
- C-hybrid: chưa có đánh giá thủ công; không suy ra grounding từ retrieval hoặc citation ID.
- D-context: chưa có đánh giá thủ công; không suy ra grounding từ retrieval hoặc citation ID.
- E-multihop: chưa có đánh giá thủ công; không suy ra grounding từ retrieval hoặc citation ID.
