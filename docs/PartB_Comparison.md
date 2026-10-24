# So sánh hai full datasets — kết quả mới đã nghiệm thu

| Dataset | Family | Precision | Recall | F1 | AP | Alerts |
| --- | --- | --- | --- | --- | --- | --- |
| IBM AML | transaction_only | 9.07% | 48.30% | 15.27% | 5.62% | 9,584 |
| IBM AML | full_fusion [selected] | 10.09% | 27.79% | 14.80% | 5.87% | 4,956 |
| PaySim | transaction_only | 81.01% | 19.67% | 31.65% | 17.00% | 1,032 |
| PaySim | full_fusion | 58.31% | 26.00% | 35.96% | 28.98% | 1,895 |
| PaySim | validation-selected: without_centrality | 58.12% | 26.09% | 36.02% | 26.58% | 1,908 |

IBM target là laundering; PaySim target là fraud. Chỉ so sánh các family trên cùng test của từng dataset; không gộp F1 hai datasets hoặc xem khác biệt F1 là một thuật toán tốt hơn trên cùng bài toán.

Chi tiết9 families, coverage, temporal metrics, review budgets và runtime nằm ở[PartB_Experiments.md](PartB_Experiments.md). Hai full notebooks có code/kernel thực thi và embedded graphs.

## IBM AML — đóng góp có điều kiện của graph features

| Contrast | Enhanced | Reference | ΔF1 | ΔAP |
| --- | --- | --- | --- | --- |
| motif_alone | motif_assisted | transaction_only | -0.00166 | +0.00045 |
| centrality_alone | transaction_centrality | transaction_only | +0.00155 | +0.00212 |
| community_alone | transaction_community | transaction_only | +0.00000 | +0.00000 |
| all_graph | full_fusion | transaction_only | -0.00465 | +0.00247 |
| motif_in_fusion | full_fusion | without_motifs | -0.00227 | -0.00088 |
| centrality_in_fusion | full_fusion | without_centrality | -0.00298 | +0.00202 |
| community_in_fusion | full_fusion | without_community | -0.00713 | +0.00040 |

Mỗi family có threshold được chọn trên cùng validation budget. Các chênh lệch này là matched ablation của toàn pipeline, không phải causal attribution hoặc bằng chứng statistical significance.

## PaySim — đóng góp có điều kiện của graph features

| Contrast | Enhanced | Reference | ΔF1 | ΔAP |
| --- | --- | --- | --- | --- |
| motif_alone | motif_assisted | transaction_only | +0.04364 | +0.09581 |
| centrality_alone | transaction_centrality | transaction_only | +0.05118 | +0.05713 |
| community_alone | transaction_community | transaction_only | +0.05392 | +0.03289 |
| all_graph | full_fusion | transaction_only | +0.04310 | +0.11978 |
| motif_in_fusion | full_fusion | without_motifs | -0.00808 | +0.06266 |
| centrality_in_fusion | full_fusion | without_centrality | -0.00054 | +0.02397 |
| community_in_fusion | full_fusion | without_community | +0.00000 | +0.00000 |

Mỗi family có threshold được chọn trên cùng validation budget. Các chênh lệch này là matched ablation của toàn pipeline, không phải causal attribution hoặc bằng chứng statistical significance.

## Những khác biệt cần giải thích

- PaySim dùng simulation hours và một đơn vị amount; IBM có timestamp/currency. Không cộng nominal currencies.
- Zero cycle/relay fraud coverage của PaySim là negative finding; không sửa labels hoặc cấu trúc để ép thành vòng laundering.
- LPA label partition không phải fraud class. Internal edges0 không đồng nghĩa toàn bộ fraud labels0.
- Full fusion không mặc định thắng baseline; giữ lựa chọn validation và báo cả trade-off P/R/F1/AP cùng temporal variation.
- Giới hạn: synthetic data, reused internal holdout, nominal row-level Wilson CI chưa điều chỉnh dependence; GPU chưa được backend dùng.


---

## Tài liệu / kết quả lịch sử theo scope khi ghi

# Part B — Cross-dataset Comparison: Task 1–4

> **Scope/date:** các bảng bên dưới là kết quả bàn giao trước full-system ngày 23/10. IBM full-system đã PASS; PaySim dừng theo user tại8/15cells/snapshot5 và gate chung còn pending. Xem [hướng dẫn code và notebook](Code_Explainer.md); không lấy sample hay motif-only test ở đây làm kết quả fusion mới.

Phương phụ trách tổng hợp so sánh; các nhánh dùng kết quả của Thảo/Tuệ Minh, Châu Anh, Khánh và Hoàng theo PCCV. So sánh dưới đây giữ rõ scope: core PaySim và mở rộng IBM có nhãn khác nhau; không gộp F1 thành một điểm AML chung.

| Nhánh | PaySim | IBM HI-Small | Diễn giải |
|---|---|---|---|
| Task 1 full graph | 9.073.900 accounts / 6.362.620 giao dịch | 518.581 / 5.078.345 | Full IBM raw–Parquet đã đối chiếu; PaySim full raw reconciliation chưa chạy lại trong audit mới |
| Task 2 sample | 194.195 accounts / 100.729 giao dịch | 119.043 / 99.869 | Degree/PageRank/reference và manifests PASS; đây là sample analytics |
| Task 4 sample | 186.932 communities | 86.223 communities | Top-50 và all-summary đều có; số cụm phụ thuộc population/topology, không đo trực tiếp fraud |
| LPA full review | Chưa có nghiệm thu full PaySim tương ứng | 314.829 communities / 518.581 accounts | Không so hai số sample/full như cùng phạm vi |
| Ý nghĩa nhãn | Mobile-money fraud | Synthetic laundering | Dùng nhãn đúng mục tiêu riêng; laundering đánh giá trực tiếp trên IBM |

Degree PMF comparison đã có ở `results/comparison/`, được gate đối chiếu trên sample. Hai dataset khác kích thước, tỷ lệ nhãn và topology; không suy ra graph này dễ phát hiện fraud hơn chỉ từ max degree hoặc số community. Community label là kết quả phân hoạch, không phải nhãn rửa tiền. Các hiện vật và ownership được dẫn đầy đủ trong [README](../README.md).

| Nội dung | PaySim | IBM AML HI-Small |
|---|---|---|
| Đơn vị thời gian | Giờ mô phỏng | Epoch seconds |
| Tiền tệ | Một đơn vị nội bộ | 15 currencies, giữ đơn vị gốc |
| Baseline cycle | 0 cycle ba tài khoản | Có cycle; audit nhãn không phải detector |
| Baseline relay/USD | 30 relay, hai cạnh đều nhãn 0 | Ba cạnh USD >10.000 cho 0 |
| Feature v2 | Fan-in/out, typed relay, reciprocal, cycle và role histories | Cùng các họ motif, thêm ràng buộc cùng currency và không FX |
| Điều cần kiểm định | Role history/motif có giúp hơn một giao dịch riêng lẻ? | Mở rộng khỏi USD/3-cycle có giúp bao phủ laundering? |
| Cách đánh giá | 3 fold thời gian + test nội bộ đã dùng trước | Cùng protocol, ngưỡng/mô hình học riêng |

| Kết quả full v2 trên reused internal test | PaySim | IBM HI-Small |
|---|---:|---:|
| CV-selected score threshold | 0,70 | 0,50 |
| TP / FP / FN | 1.191 / 1.489 / 3.059 | 474 / 4.059 / 1.323 |
| Precision / recall / F1 | 44,44% / 28,02% / 34,37% | 10,46% / 26,38% / 14,98% |
| Transaction-only F1 | 30,38% | 15,08% |
| Average precision: transaction-only → assisted | 12,45% → 20,71% | 5,60% → 5,65% |

PaySim cải thiện nhờ bộ graph context, chủ yếu receiver history; không tìm được fraud cycle. IBM có ví dụ TP khép vòng thật, nhưng F1 tổng thể giảm nhẹ; FP giảm cùng với recall giảm. Không gộp hai kết quả thành khẳng định motif giải quyết tốt mọi fraud.

Không so số motif thô giữa hai graph như thể chúng có cùng ý nghĩa. Không cộng các coverage motif chồng nhau thành tổng fraud. Cùng thuật toán có thể có đóng góp khác nhau giữa hai dataset; kết luận phải dựa vào ablation và TP/FP/FN thực tế trong notebook riêng:

- [PaySim](../notebooks/03_khanh_PaySIM_motif.ipynb).
- [IBM](../notebooks/03_khanh_IBM_motif.ipynb).

Các model có giám sát học từ prefix training, còn feature motif không nhận nhãn. Chỉ kết hợp PageRank/LPA từ snapshot đã quan sát; không dùng tỷ lệ fraud của nhãn test làm feature. Kết quả trên synthetic datasets và reused internal holdout chưa đủ chứng minh khả năng triển khai thực tế.
