# Part B — Cross-dataset Comparison: Task 1–4

> **Scope/date:** các bảng bên dưới là kết quả bàn giao trước full-system ngày 23/10. IBM full-system đã PASS; PaySim dừng theo user tại8/15cells/snapshot5 và gate chung còn pending. Xem [checkpoint](../agent_job.md); không lấy sample hay motif-only test ở đây làm kết quả fusion mới.

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
