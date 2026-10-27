# Reliability và evidence chain

## Những gì đã được kiểm chứng trong lượt chạy gốc

1. Full raw-vs-processed reconciliation hai chiều, endpoint integrity, unique event index, degree sum=2E, rank normalization, community membership totals.
2. One feature row/transaction; snapshot không ở tương lai; allowlist không có label/ID; strict-past motifs không lấy đồng timestamp làm quá khứ.
3. 3-fold walk-forward, freeze rules trước final test; 9 saved models reload trên full holdout.
4. Confusion counts và AP được kiểm tra độc lập trên persisted full predictions trong lần nghiệm thu gốc. [Log full acceptance gốc](evidence/existing_full_artifact_verification.log).
5. Notebook code digest, executed source hashes, visible copied functions và output hoàn tất đã được đối chiếu. Bản đóng gói kiểm tra lại bằng hash/AST, không thực thi notebook.

## Số liệu reliability có sẵn

### ibm_aml

| model | threshold | mean_F1 | worst_F1 | std_F1 | test_period_min_F1 | test_period_max_F1 | test_period_std_F1 | positive_periods |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| transaction_only | 0.5 | 6.03% | 0.00% | 5.24% | 4.42% | 32.99% | 11.70% | 5 |
| transaction_novelty | 0.5 | 6.03% | 0.00% | 5.24% | 4.42% | 32.99% | 11.70% | 5 |
| transaction_centrality | 0.5 | 5.85% | 0.00% | 5.10% | 4.48% | 33.21% | 11.75% | 5 |
| motif_assisted | 0.5 | 10.61% | 7.56% | 2.64% | 3.50% | 29.73% | 10.28% | 5 |
| transaction_community | 0.5 | 6.03% | 0.00% | 5.24% | 4.42% | 32.99% | 11.70% | 5 |
| full_fusion | 0.5 | 10.83% | 7.56% | 2.84% | 3.32% | 28.79% | 9.88% | 5 |
| without_centrality | 0.5 | 10.64% | 7.56% | 2.67% | 3.50% | 29.73% | 10.28% | 5 |
| without_motifs | 0.5 | 5.78% | 0.00% | 5.06% | 4.26% | 32.03% | 11.29% | 5 |
| without_community | 0.5 | 10.72% | 7.56% | 2.77% | 3.64% | 30.48% | 10.49% | 5 |

### paysim

| model | threshold | mean_F1 | worst_F1 | std_F1 | test_period_min_F1 | test_period_max_F1 | test_period_std_F1 | positive_periods |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| transaction_only | 0.7 | 7.01% | 2.15% | 4.66% | 27.03% | 34.04% | 2.68% | 5 |
| transaction_novelty | 0.7 | 14.95% | 7.56% | 6.41% | 26.24% | 41.06% | 6.18% | 5 |
| transaction_centrality | 0.5 | 14.98% | 7.56% | 6.44% | 26.10% | 40.71% | 6.17% | 5 |
| motif_assisted | 0.7 | 15.01% | 8.67% | 5.79% | 27.05% | 40.90% | 5.67% | 5 |
| transaction_community | 0.7 | 14.95% | 7.56% | 6.41% | 26.24% | 41.06% | 6.18% | 5 |
| full_fusion | 0.7 | 15.10% | 8.67% | 5.56% | 26.92% | 40.80% | 5.80% | 5 |
| without_centrality | 0.7 | 15.84% | 8.67% | 6.95% | 27.05% | 40.90% | 5.67% | 5 |
| without_motifs | 0.5 | 14.98% | 7.56% | 6.44% | 26.10% | 40.71% | 6.17% | 5 |
| without_community | 0.7 | 15.10% | 8.67% | 5.56% | 26.92% | 40.80% | 5.80% | 5 |


CI Wilson 95% nằm trong test_metrics.csv và test_temporal_stability.csv. Đây là khoảng tin cậy binomial theo giao dịch, chưa điều chỉnh account/time dependence. Các khoảng test thể hiện biến thiên quan sát được, không phải chứng nhận external generalization. Hai dataset là synthetic; holdout nội bộ đã được đọc trong quá trình phát triển, không gọi là untouched external benchmark.

## Kiểm tra khi đóng gói lần này

Chỉ kiểm tra consistency trên exports: source/report/artifact hashes, completed-full scope, confusions và PR→AP, exact K, period sums, degree/community identities, notebook code digest và AST source copies, links, ZIP integrity. Không chạy lại millions-row predictions hay gọi make check. Xem [bundle_checks.json](validation/bundle_checks.json).

Đây là bundle để viết report và đối chiếu các thông số đã xuất. Tự kiểm nghiệm một giả thuyết mới cần raw/full predictions không nằm trong bundle; không suy ra số mới từ vài examples. Trained models nằm trong model_details để đọc tree/threshold/vocab/scales mà không cần train lại.

## Diễn đạt khoa học đúng khi trình bày

- Đánh giá riêng ranking (AP/PR), operating point (precision/recall/F1/confusion) và khối lượng review (alerts/top-K).
- Giữ winner dựa validation, kể cả một metric test của family khác cao hơn.
- Báo cáo cả TP và FP/FN, không chỉ một case đẹp. Không gọi confidence95% là accuracy95%.
- Zero coverage hoặc zero importance là quan sát thật; không đổi nhãn để làm đẹp kết quả.
- Runtime/hardware là phép đo của máy/lần chạy gốc; phase records có thể cumulative và có checkpoint reuse, không biến chúng thành cam kết thời gian trên máy khác.
