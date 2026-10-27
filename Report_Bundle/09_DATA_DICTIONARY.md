# Từ điển các bảng số liệu

Tất cả CSV giữ precision gốc, UTF-8 (CSV gốc và derived dùng BOM khi có). Display Markdown làm tròn tỷ lệ để đọc; luôn dùng CSV khi tính. Header-only không đồng nghĩa lỗi. `fraud` là sốpositive theo nhãn dataset, không phải sốalert.

## ibm_aml

### baseline_currencies.csv

Chi tiết currency của baseline IBM; header-only ở PaySim là không áp dụng. **Số dòng: 15.** [Mở CSV](datasets/ibm_aml/tables/baseline_currencies.csv).

| column | meaning_or_unit |
| --- | --- |
| payment_currency | Giữ nguyên ngữ nghĩa tên cột; vai trò bảng và context được giải thích ở phần tương ứng. |
| count | Số đếm; không làm tròn khi tính toán. |

### baseline_examples.csv

Ví dụ witness lấy từ kết quả full baseline; không phải sampled input, không dùng tính benchmark. **Số dòng: 54.** [Mở CSV](datasets/ibm_aml/tables/baseline_examples.csv).

| column | meaning_or_unit |
| --- | --- |
| a | Giữ nguyên ngữ nghĩa tên cột; vai trò bảng và context được giải thích ở phần tương ứng. |
| b | Giữ nguyên ngữ nghĩa tên cột; vai trò bảng và context được giải thích ở phần tương ứng. |
| c | Giữ nguyên ngữ nghĩa tên cột; vai trò bảng và context được giải thích ở phần tương ứng. |
| transaction_combinations | Giữ nguyên ngữ nghĩa tên cột; vai trò bảng và context được giải thích ở phần tương ứng. |

### baseline_summary.csv

Baseline truy vấn gốc trên full graph; label audit để mô tả, không phải predictive test. **Số dòng: 1.** [Mở CSV](datasets/ibm_aml/tables/baseline_summary.csv).

| column | meaning_or_unit |
| --- | --- |
| dataset | Giữ nguyên ngữ nghĩa tên cột; vai trò bảng và context được giải thích ở phần tương ứng. |
| fraud_edges | Giữ nguyên ngữ nghĩa tên cột; vai trò bảng và context được giải thích ở phần tương ứng. |
| label_audit_raw_cycles | Giữ nguyên ngữ nghĩa tên cột; vai trò bảng và context được giải thích ở phần tương ứng. |
| directed_account_cycles | Giữ nguyên ngữ nghĩa tên cột; vai trò bảng và context được giải thích ở phần tương ứng. |
| transaction_combinations | Giữ nguyên ngữ nghĩa tên cột; vai trò bảng và context được giải thích ở phần tương ứng. |
| USD_above_10000_cycles | Giữ nguyên ngữ nghĩa tên cột; vai trò bảng và context được giải thích ở phần tương ứng. |

### community_size_distribution.csv

Phân bố kích thước toàn bộ cộng đồng LPA; count là số cộng đồng. **Số dòng: 69.** [Mở CSV](datasets/ibm_aml/tables/community_size_distribution.csv).

| column | meaning_or_unit |
| --- | --- |
| member_count | Số đếm; không làm tròn khi tính toán. |
| count | Số đếm; không làm tròn khi tính toán. |

### community_top50.csv

50 cộng đồng lớn nhất của full LPA; positive_tx_count chỉ audit nhãn, không gọi toàn cộng đồng là gian lận. **Số dòng: 50.** [Mở CSV](datasets/ibm_aml/tables/community_top50.csv).

| column | meaning_or_unit |
| --- | --- |
| label | Định danh; giữ nguyên chuỗi/64-bit, không dùng số thực Excel để tránh mất chữ số. |
| member_count | Số đếm; không làm tròn khi tính toán. |
| unique_banks_count | Giữ nguyên ngữ nghĩa tên cột; vai trò bảng và context được giải thích ở phần tương ứng. |
| total_tx_count | Giữ nguyên ngữ nghĩa tên cột; vai trò bảng và context được giải thích ở phần tương ứng. |
| positive_tx_count | Giữ nguyên ngữ nghĩa tên cột; vai trò bảng và context được giải thích ở phần tương ứng. |
| internal_tx_count | Giữ nguyên ngữ nghĩa tên cột; vai trò bảng và context được giải thích ở phần tương ứng. |
| cross_tx_count | Giữ nguyên ngữ nghĩa tên cột; vai trò bảng và context được giải thích ở phần tương ứng. |

### degree_distribution.csv

Phân bố total degree của toàn bộ tài khoản, kể cả degree 0; sum account_count = V, sum degree*count = 2E. **Số dòng: 303.** [Mở CSV](datasets/ibm_aml/tables/degree_distribution.csv).

| column | meaning_or_unit |
| --- | --- |
| degree | Giữ nguyên ngữ nghĩa tên cột; vai trò bảng và context được giải thích ở phần tương ứng. |
| account_count | Số đếm; không làm tròn khi tính toán. |

### feature_importance.csv

Impurity-based importance từng feature/family; số 0 là không được tree dùng, không phải bằng chứng nhân quả. **Số dòng: 195.** [Mở CSV](datasets/ibm_aml/tables/feature_importance.csv).

| column | meaning_or_unit |
| --- | --- |
| feature | Giữ nguyên ngữ nghĩa tên cột; vai trò bảng và context được giải thích ở phần tương ứng. |
| importance | Impurity feature importance của fitted tree; tổng theo family ~1. |
| family | Mã family; tra tables/model_families.csv. |

### graph_contributions.csv

Chênh lệch chỉ số giữa các family tại threshold riêng đã freeze; ablation quan sát, không causal contribution. **Số dòng: 7.** [Mở CSV](datasets/ibm_aml/tables/graph_contributions.csv).

| column | meaning_or_unit |
| --- | --- |
| contrast | Giữ nguyên ngữ nghĩa tên cột; vai trò bảng và context được giải thích ở phần tương ứng. |
| enhanced | Mã family; tra tables/model_families.csv. |
| reference | Mã family; tra tables/model_families.csv. |
| delta_precision | Tỷ lệ 0–1; delta là chênh lệch tỷ lệ (×100 = điểm phần trăm). |
| delta_recall | Tỷ lệ 0–1; delta là chênh lệch tỷ lệ (×100 = điểm phần trăm). |
| delta_F1 | Tỷ lệ 0–1; delta là chênh lệch tỷ lệ (×100 = điểm phần trăm). |
| delta_average_precision | Tỷ lệ 0–1; delta là chênh lệch tỷ lệ (×100 = điểm phần trăm). |

### motif_coverage.csv

Coverage 9 nhóm motif ở full/test; covered_positives không phải TP của classifier; các nhóm chồng lấp. **Số dòng: 18.** [Mở CSV](datasets/ibm_aml/tables/motif_coverage.csv).

| column | meaning_or_unit |
| --- | --- |
| scope | full = toàn bộ input của run; test = toàn bộ holdout sau cutoff80%. |
| motif | Giữ nguyên ngữ nghĩa tên cột; vai trò bảng và context được giải thích ở phần tương ứng. |
| transactions | Số đếm; không làm tròn khi tính toán. |
| positives | Số đếm; không làm tròn khi tính toán. |
| covered_transactions | Số đếm; không làm tròn khi tính toán. |
| covered_positives | Số đếm; không làm tròn khi tính toán. |
| positive_coverage | Tỷ lệ 0–1; delta là chênh lệch tỷ lệ (×100 = điểm phần trăm). |
| positive_fraction_when_present | Tỷ lệ 0–1; delta là chênh lệch tỷ lệ (×100 = điểm phần trăm). |
| population_prevalence | Tỷ lệ 0–1; delta là chênh lệch tỷ lệ (×100 = điểm phần trăm). |
| interpretation | Giữ nguyên ngữ nghĩa tên cột; vai trò bảng và context được giải thích ở phần tương ứng. |

### pr_curve_full_fusion.csv

Exact precision-recall bins của family nêu trong tên file; không phải sampled PR curve. **Số dòng: 16.** [Mở CSV](datasets/ibm_aml/tables/pr_curve_full_fusion.csv).

| column | meaning_or_unit |
| --- | --- |
| risk_score | Score/ngưỡng 0–1; score từ weighted tree, không phải calibrated probability. |
| positives | Số đếm; không làm tròn khi tính toán. |
| transactions | Số đếm; không làm tròn khi tính toán. |
| precision | Tỷ lệ 0–1; delta là chênh lệch tỷ lệ (×100 = điểm phần trăm). |
| recall | Tỷ lệ 0–1; delta là chênh lệch tỷ lệ (×100 = điểm phần trăm). |

### pr_curve_motif_assisted.csv

Exact precision-recall bins của family nêu trong tên file; không phải sampled PR curve. **Số dòng: 12.** [Mở CSV](datasets/ibm_aml/tables/pr_curve_motif_assisted.csv).

| column | meaning_or_unit |
| --- | --- |
| risk_score | Score/ngưỡng 0–1; score từ weighted tree, không phải calibrated probability. |
| positives | Số đếm; không làm tròn khi tính toán. |
| transactions | Số đếm; không làm tròn khi tính toán. |
| precision | Tỷ lệ 0–1; delta là chênh lệch tỷ lệ (×100 = điểm phần trăm). |
| recall | Tỷ lệ 0–1; delta là chênh lệch tỷ lệ (×100 = điểm phần trăm). |

### pr_curve_transaction_centrality.csv

Exact precision-recall bins của family nêu trong tên file; không phải sampled PR curve. **Số dòng: 12.** [Mở CSV](datasets/ibm_aml/tables/pr_curve_transaction_centrality.csv).

| column | meaning_or_unit |
| --- | --- |
| risk_score | Score/ngưỡng 0–1; score từ weighted tree, không phải calibrated probability. |
| positives | Số đếm; không làm tròn khi tính toán. |
| transactions | Số đếm; không làm tròn khi tính toán. |
| precision | Tỷ lệ 0–1; delta là chênh lệch tỷ lệ (×100 = điểm phần trăm). |
| recall | Tỷ lệ 0–1; delta là chênh lệch tỷ lệ (×100 = điểm phần trăm). |

### pr_curve_transaction_community.csv

Exact precision-recall bins của family nêu trong tên file; không phải sampled PR curve. **Số dòng: 6.** [Mở CSV](datasets/ibm_aml/tables/pr_curve_transaction_community.csv).

| column | meaning_or_unit |
| --- | --- |
| risk_score | Score/ngưỡng 0–1; score từ weighted tree, không phải calibrated probability. |
| positives | Số đếm; không làm tròn khi tính toán. |
| transactions | Số đếm; không làm tròn khi tính toán. |
| precision | Tỷ lệ 0–1; delta là chênh lệch tỷ lệ (×100 = điểm phần trăm). |
| recall | Tỷ lệ 0–1; delta là chênh lệch tỷ lệ (×100 = điểm phần trăm). |

### pr_curve_transaction_novelty.csv

Exact precision-recall bins của family nêu trong tên file; không phải sampled PR curve. **Số dòng: 6.** [Mở CSV](datasets/ibm_aml/tables/pr_curve_transaction_novelty.csv).

| column | meaning_or_unit |
| --- | --- |
| risk_score | Score/ngưỡng 0–1; score từ weighted tree, không phải calibrated probability. |
| positives | Số đếm; không làm tròn khi tính toán. |
| transactions | Số đếm; không làm tròn khi tính toán. |
| precision | Tỷ lệ 0–1; delta là chênh lệch tỷ lệ (×100 = điểm phần trăm). |
| recall | Tỷ lệ 0–1; delta là chênh lệch tỷ lệ (×100 = điểm phần trăm). |

### pr_curve_transaction_only.csv

Exact precision-recall bins của family nêu trong tên file; không phải sampled PR curve. **Số dòng: 6.** [Mở CSV](datasets/ibm_aml/tables/pr_curve_transaction_only.csv).

| column | meaning_or_unit |
| --- | --- |
| risk_score | Score/ngưỡng 0–1; score từ weighted tree, không phải calibrated probability. |
| positives | Số đếm; không làm tròn khi tính toán. |
| transactions | Số đếm; không làm tròn khi tính toán. |
| precision | Tỷ lệ 0–1; delta là chênh lệch tỷ lệ (×100 = điểm phần trăm). |
| recall | Tỷ lệ 0–1; delta là chênh lệch tỷ lệ (×100 = điểm phần trăm). |

### pr_curve_without_centrality.csv

Exact precision-recall bins của family nêu trong tên file; không phải sampled PR curve. **Số dòng: 12.** [Mở CSV](datasets/ibm_aml/tables/pr_curve_without_centrality.csv).

| column | meaning_or_unit |
| --- | --- |
| risk_score | Score/ngưỡng 0–1; score từ weighted tree, không phải calibrated probability. |
| positives | Số đếm; không làm tròn khi tính toán. |
| transactions | Số đếm; không làm tròn khi tính toán. |
| precision | Tỷ lệ 0–1; delta là chênh lệch tỷ lệ (×100 = điểm phần trăm). |
| recall | Tỷ lệ 0–1; delta là chênh lệch tỷ lệ (×100 = điểm phần trăm). |

### pr_curve_without_community.csv

Exact precision-recall bins của family nêu trong tên file; không phải sampled PR curve. **Số dòng: 14.** [Mở CSV](datasets/ibm_aml/tables/pr_curve_without_community.csv).

| column | meaning_or_unit |
| --- | --- |
| risk_score | Score/ngưỡng 0–1; score từ weighted tree, không phải calibrated probability. |
| positives | Số đếm; không làm tròn khi tính toán. |
| transactions | Số đếm; không làm tròn khi tính toán. |
| precision | Tỷ lệ 0–1; delta là chênh lệch tỷ lệ (×100 = điểm phần trăm). |
| recall | Tỷ lệ 0–1; delta là chênh lệch tỷ lệ (×100 = điểm phần trăm). |

### pr_curve_without_motifs.csv

Exact precision-recall bins của family nêu trong tên file; không phải sampled PR curve. **Số dòng: 11.** [Mở CSV](datasets/ibm_aml/tables/pr_curve_without_motifs.csv).

| column | meaning_or_unit |
| --- | --- |
| risk_score | Score/ngưỡng 0–1; score từ weighted tree, không phải calibrated probability. |
| positives | Số đếm; không làm tròn khi tính toán. |
| transactions | Số đếm; không làm tròn khi tính toán. |
| precision | Tỷ lệ 0–1; delta là chênh lệch tỷ lệ (×100 = điểm phần trăm). |
| recall | Tỷ lệ 0–1; delta là chênh lệch tỷ lệ (×100 = điểm phần trăm). |

### reliability_summary.csv

Tóm tắt F1 validation và biến thiên F1 5 khoảng test cho từng family. **Số dòng: 9.** [Mở CSV](datasets/ibm_aml/tables/reliability_summary.csv).

| column | meaning_or_unit |
| --- | --- |
| model | Mã family; tra tables/model_families.csv. |
| threshold | Score/ngưỡng 0–1; score từ weighted tree, không phải calibrated probability. |
| mean_F1 | Tỷ lệ 0–1; delta là chênh lệch tỷ lệ (×100 = điểm phần trăm). |
| worst_F1 | Tỷ lệ 0–1; delta là chênh lệch tỷ lệ (×100 = điểm phần trăm). |
| std_F1 | Tỷ lệ 0–1; delta là chênh lệch tỷ lệ (×100 = điểm phần trăm). |
| test_period_min_F1 | Tỷ lệ 0–1; delta là chênh lệch tỷ lệ (×100 = điểm phần trăm). |
| test_period_max_F1 | Tỷ lệ 0–1; delta là chênh lệch tỷ lệ (×100 = điểm phần trăm). |
| test_period_std_F1 | Tỷ lệ 0–1; delta là chênh lệch tỷ lệ (×100 = điểm phần trăm). |
| positive_periods | Giữ nguyên ngữ nghĩa tên cột; vai trò bảng và context được giải thích ở phần tương ứng. |

### review_budgets.csv

Exact top-K review ở 0.1%, 0.5%, 1% test; tie-break cố định, không tối ưu sau test. **Số dòng: 27.** [Mở CSV](datasets/ibm_aml/tables/review_budgets.csv).

| column | meaning_or_unit |
| --- | --- |
| model | Mã family; tra tables/model_families.csv. |
| review_fraction | Tỷ lệ 0–1; delta là chênh lệch tỷ lệ (×100 = điểm phần trăm). |
| K | Số đếm; không làm tròn khi tính toán. |
| transactions | Số đếm; không làm tròn khi tính toán. |
| fraud | Số đếm; không làm tròn khi tính toán. |
| TP_at_K | Số đếm; không làm tròn khi tính toán. |
| precision_at_K | Tỷ lệ 0–1; delta là chênh lệch tỷ lệ (×100 = điểm phần trăm). |
| recall_at_K | Tỷ lệ 0–1; delta là chênh lệch tỷ lệ (×100 = điểm phần trăm). |
| tie_policy | Giữ nguyên ngữ nghĩa tên cột; vai trò bảng và context được giải thích ở phần tương ứng. |

### selected_amounts_by_currency.csv

Tổng payment_amount theo currency và TP/FP/FN/TN; không cộng các currency thành một USD total. **Số dòng: 59.** [Mở CSV](datasets/ibm_aml/tables/selected_amounts_by_currency.csv).

| column | meaning_or_unit |
| --- | --- |
| payment_currency | Giữ nguyên ngữ nghĩa tên cột; vai trò bảng và context được giải thích ở phần tương ứng. |
| case | Giữ nguyên ngữ nghĩa tên cột; vai trò bảng và context được giải thích ở phần tương ứng. |
| transactions | Số đếm; không làm tròn khi tính toán. |
| payment_amount | Số tiền theo payment_currency trên cùng dòng; không tự đổi sang USD. |

### selected_case_evidence.csv

Giao dịch thật và history witness của một selected-model test TP; witness có thể nằm trước test. **Số dòng: 3.** [Mở CSV](datasets/ibm_aml/tables/selected_case_evidence.csv).

| column | meaning_or_unit |
| --- | --- |
| event_id | Định danh; giữ nguyên chuỗi/64-bit, không dùng số thực Excel để tránh mất chữ số. |
| src | Định danh; giữ nguyên chuỗi/64-bit, không dùng số thực Excel để tránh mất chữ số. |
| dst | Định danh; giữ nguyên chuỗi/64-bit, không dùng số thực Excel để tránh mất chữ số. |
| step | IBM: epoch seconds; PaySim: step theo giờ. Xem protocol. |
| type | Giữ nguyên ngữ nghĩa tên cột; vai trò bảng và context được giải thích ở phần tương ứng. |
| amount | Số tiền theo payment_currency trên cùng dòng; không tự đổi sang USD. |
| payment_currency | Giữ nguyên ngữ nghĩa tên cột; vai trò bảng và context được giải thích ở phần tương ứng. |
| isFraud | Giữ nguyên ngữ nghĩa tên cột; vai trò bảng và context được giải thích ở phần tương ứng. |
| example_model | Giữ nguyên ngữ nghĩa tên cột; vai trò bảng và context được giải thích ở phần tương ứng. |
| evidence_kind | Giữ nguyên ngữ nghĩa tên cột; vai trò bảng và context được giải thích ở phần tương ứng. |

### selected_cold_start.csv

Test theo lịch sử seen/unseen của family được validation chọn; phân rã counts, không chia ngẫu nhiên. **Số dòng: 3.** [Mở CSV](datasets/ibm_aml/tables/selected_cold_start.csv).

| column | meaning_or_unit |
| --- | --- |
| history_group | Giữ nguyên ngữ nghĩa tên cột; vai trò bảng và context được giải thích ở phần tương ứng. |
| transactions | Số đếm; không làm tròn khi tính toán. |
| fraud | Số đếm; không làm tròn khi tính toán. |
| alerts | Số đếm; không làm tròn khi tính toán. |
| TP | Số đếm; không làm tròn khi tính toán. |
| FP | Số đếm; không làm tròn khi tính toán. |
| FN | Số đếm; không làm tròn khi tính toán. |
| TN | Số đếm; không làm tròn khi tính toán. |
| precision | Tỷ lệ 0–1; delta là chênh lệch tỷ lệ (×100 = điểm phần trăm). |
| recall | Tỷ lệ 0–1; delta là chênh lệch tỷ lệ (×100 = điểm phần trăm). |
| F1 | Tỷ lệ 0–1; delta là chênh lệch tỷ lệ (×100 = điểm phần trăm). |
| prevalence | Tỷ lệ 0–1; delta là chênh lệch tỷ lệ (×100 = điểm phần trăm). |
| alert_rate | Tỷ lệ 0–1; delta là chênh lệch tỷ lệ (×100 = điểm phần trăm). |

### test_metrics.csv

Toàn bộ test của 9 families tại từng threshold đã chọn trên validation; ma trận nhầm lẫn + PR/F1/AP + CI. **Số dòng: 9.** [Mở CSV](datasets/ibm_aml/tables/test_metrics.csv).

| column | meaning_or_unit |
| --- | --- |
| model | Mã family; tra tables/model_families.csv. |
| threshold | Score/ngưỡng 0–1; score từ weighted tree, không phải calibrated probability. |
| transactions | Số đếm; không làm tròn khi tính toán. |
| fraud | Số đếm; không làm tròn khi tính toán. |
| alerts | Số đếm; không làm tròn khi tính toán. |
| TP | Số đếm; không làm tròn khi tính toán. |
| FP | Số đếm; không làm tròn khi tính toán. |
| FN | Số đếm; không làm tròn khi tính toán. |
| TN | Số đếm; không làm tròn khi tính toán. |
| precision | Tỷ lệ 0–1; delta là chênh lệch tỷ lệ (×100 = điểm phần trăm). |
| recall | Tỷ lệ 0–1; delta là chênh lệch tỷ lệ (×100 = điểm phần trăm). |
| F1 | Tỷ lệ 0–1; delta là chênh lệch tỷ lệ (×100 = điểm phần trăm). |
| prevalence | Tỷ lệ 0–1; delta là chênh lệch tỷ lệ (×100 = điểm phần trăm). |
| alert_rate | Tỷ lệ 0–1; delta là chênh lệch tỷ lệ (×100 = điểm phần trăm). |
| average_precision | Tỷ lệ 0–1; delta là chênh lệch tỷ lệ (×100 = điểm phần trăm). |
| selected_on_validation | Giữ nguyên ngữ nghĩa tên cột; vai trò bảng và context được giải thích ở phần tương ứng. |
| precision_low95 | Tỷ lệ 0–1; delta là chênh lệch tỷ lệ (×100 = điểm phần trăm). |
| precision_high95 | Tỷ lệ 0–1; delta là chênh lệch tỷ lệ (×100 = điểm phần trăm). |
| recall_low95 | Tỷ lệ 0–1; delta là chênh lệch tỷ lệ (×100 = điểm phần trăm). |
| recall_high95 | Tỷ lệ 0–1; delta là chênh lệch tỷ lệ (×100 = điểm phần trăm). |

### test_temporal_stability.csv

9 families × 5 khoảng test; tổng counts theo family bằng test_metrics. **Số dòng: 45.** [Mở CSV](datasets/ibm_aml/tables/test_temporal_stability.csv).

| column | meaning_or_unit |
| --- | --- |
| model | Mã family; tra tables/model_families.csv. |
| test_period | Giữ nguyên ngữ nghĩa tên cột; vai trò bảng và context được giải thích ở phần tương ứng. |
| threshold | Score/ngưỡng 0–1; score từ weighted tree, không phải calibrated probability. |
| transactions | Số đếm; không làm tròn khi tính toán. |
| fraud | Số đếm; không làm tròn khi tính toán. |
| alerts | Số đếm; không làm tròn khi tính toán. |
| TP | Số đếm; không làm tròn khi tính toán. |
| FP | Số đếm; không làm tròn khi tính toán. |
| FN | Số đếm; không làm tròn khi tính toán. |
| TN | Số đếm; không làm tròn khi tính toán. |
| precision | Tỷ lệ 0–1; delta là chênh lệch tỷ lệ (×100 = điểm phần trăm). |
| recall | Tỷ lệ 0–1; delta là chênh lệch tỷ lệ (×100 = điểm phần trăm). |
| F1 | Tỷ lệ 0–1; delta là chênh lệch tỷ lệ (×100 = điểm phần trăm). |
| prevalence | Tỷ lệ 0–1; delta là chênh lệch tỷ lệ (×100 = điểm phần trăm). |
| alert_rate | Tỷ lệ 0–1; delta là chênh lệch tỷ lệ (×100 = điểm phần trăm). |
| precision_low95 | Tỷ lệ 0–1; delta là chênh lệch tỷ lệ (×100 = điểm phần trăm). |
| precision_high95 | Tỷ lệ 0–1; delta là chênh lệch tỷ lệ (×100 = điểm phần trăm). |
| recall_low95 | Tỷ lệ 0–1; delta là chênh lệch tỷ lệ (×100 = điểm phần trăm). |
| recall_high95 | Tỷ lệ 0–1; delta là chênh lệch tỷ lệ (×100 = điểm phần trăm). |
| average_precision | Tỷ lệ 0–1; delta là chênh lệch tỷ lệ (×100 = điểm phần trăm). |

### top10_pagerank.csv

10 tài khoản PageRank lớn nhất từ full descriptive analytics; không phải chỉ chạy trên 10 tài khoản. **Số dòng: 10.** [Mở CSV](datasets/ibm_aml/tables/top10_pagerank.csv).

| column | meaning_or_unit |
| --- | --- |
| id | Giữ nguyên ngữ nghĩa tên cột; vai trò bảng và context được giải thích ở phần tương ứng. |
| pagerank | Giữ nguyên ngữ nghĩa tên cột; vai trò bảng và context được giải thích ở phần tương ứng. |
| inDegree | Giữ nguyên ngữ nghĩa tên cột; vai trò bảng và context được giải thích ở phần tương ứng. |
| outDegree | Giữ nguyên ngữ nghĩa tên cột; vai trò bảng và context được giải thích ở phần tương ứng. |
| degree | Giữ nguyên ngữ nghĩa tên cột; vai trò bảng và context được giải thích ở phần tương ứng. |

### validation_average_precision.csv

AP validation theo từng family/fold; dùng cho đánh giá ranking. **Số dòng: 27.** [Mở CSV](datasets/ibm_aml/tables/validation_average_precision.csv).

| column | meaning_or_unit |
| --- | --- |
| fold | Giữ nguyên ngữ nghĩa tên cột; vai trò bảng và context được giải thích ở phần tương ứng. |
| family | Mã family; tra tables/model_families.csv. |
| average_precision | Tỷ lệ 0–1; delta là chênh lệch tỷ lệ (×100 = điểm phần trăm). |
| transactions | Số đếm; không làm tròn khi tính toán. |

### validation_leaderboard.csv

9 families × 12 thresholds; trung bình/worst/std 3 folds; đây là dữ liệu chọn mô hình. **Số dòng: 108.** [Mở CSV](datasets/ibm_aml/tables/validation_leaderboard.csv).

| column | meaning_or_unit |
| --- | --- |
| family | Mã family; tra tables/model_families.csv. |
| threshold | Score/ngưỡng 0–1; score từ weighted tree, không phải calibrated probability. |
| mean_F1 | Tỷ lệ 0–1; delta là chênh lệch tỷ lệ (×100 = điểm phần trăm). |
| worst_F1 | Tỷ lệ 0–1; delta là chênh lệch tỷ lệ (×100 = điểm phần trăm). |
| std_F1 | Tỷ lệ 0–1; delta là chênh lệch tỷ lệ (×100 = điểm phần trăm). |
| mean_precision | Giữ nguyên ngữ nghĩa tên cột; vai trò bảng và context được giải thích ở phần tương ứng. |
| TP | Số đếm; không làm tròn khi tính toán. |
| FP | Số đếm; không làm tròn khi tính toán. |
| FN | Số đếm; không làm tròn khi tính toán. |
| transactions | Số đếm; không làm tròn khi tính toán. |
| folds | Giữ nguyên ngữ nghĩa tên cột; vai trò bảng và context được giải thích ở phần tương ứng. |

### walk_forward.csv

3 folds × 9 families × 12 thresholds; mỗi dòng là validation fold, không phải final test. **Số dòng: 324.** [Mở CSV](datasets/ibm_aml/tables/walk_forward.csv).

| column | meaning_or_unit |
| --- | --- |
| fold | Giữ nguyên ngữ nghĩa tên cột; vai trò bảng và context được giải thích ở phần tương ứng. |
| family | Mã family; tra tables/model_families.csv. |
| threshold | Score/ngưỡng 0–1; score từ weighted tree, không phải calibrated probability. |
| transactions | Số đếm; không làm tròn khi tính toán. |
| fraud | Số đếm; không làm tròn khi tính toán. |
| alerts | Số đếm; không làm tròn khi tính toán. |
| TP | Số đếm; không làm tròn khi tính toán. |
| FP | Số đếm; không làm tròn khi tính toán. |
| FN | Số đếm; không làm tròn khi tính toán. |
| TN | Số đếm; không làm tròn khi tính toán. |
| precision | Tỷ lệ 0–1; delta là chênh lệch tỷ lệ (×100 = điểm phần trăm). |
| recall | Tỷ lệ 0–1; delta là chênh lệch tỷ lệ (×100 = điểm phần trăm). |
| F1 | Tỷ lệ 0–1; delta là chênh lệch tỷ lệ (×100 = điểm phần trăm). |
| prevalence | Tỷ lệ 0–1; delta là chênh lệch tỷ lệ (×100 = điểm phần trăm). |
| alert_rate | Tỷ lệ 0–1; delta là chênh lệch tỷ lệ (×100 = điểm phần trăm). |

## paysim

### baseline_currencies.csv

Chi tiết currency của baseline IBM; header-only ở PaySim là không áp dụng. **Số dòng: 0.** [Mở CSV](datasets/paysim/tables/baseline_currencies.csv).

| column | meaning_or_unit |
| --- | --- |
| payment_currency | Giữ nguyên ngữ nghĩa tên cột; vai trò bảng và context được giải thích ở phần tương ứng. |
| count | Số đếm; không làm tròn khi tính toán. |

### baseline_examples.csv

Ví dụ witness lấy từ kết quả full baseline; không phải sampled input, không dùng tính benchmark. **Số dòng: 30.** [Mở CSV](datasets/paysim/tables/baseline_examples.csv).

| column | meaning_or_unit |
| --- | --- |
| source_account | Giữ nguyên ngữ nghĩa tên cột; vai trò bảng và context được giải thích ở phần tương ứng. |
| middle_account | Giữ nguyên ngữ nghĩa tên cột; vai trò bảng và context được giải thích ở phần tương ứng. |
| cashout_account | Giữ nguyên ngữ nghĩa tên cột; vai trò bảng và context được giải thích ở phần tương ứng. |
| transfer_step | Giữ nguyên ngữ nghĩa tên cột; vai trò bảng và context được giải thích ở phần tương ứng. |
| cashout_step | Giữ nguyên ngữ nghĩa tên cột; vai trò bảng và context được giải thích ở phần tương ứng. |
| transfer_amount | Giữ nguyên ngữ nghĩa tên cột; vai trò bảng và context được giải thích ở phần tương ứng. |
| cashout_amount | Giữ nguyên ngữ nghĩa tên cột; vai trò bảng và context được giải thích ở phần tương ứng. |
| transfer_isFraud | Giữ nguyên ngữ nghĩa tên cột; vai trò bảng và context được giải thích ở phần tương ứng. |
| cashout_isFraud | Giữ nguyên ngữ nghĩa tên cột; vai trò bảng và context được giải thích ở phần tương ứng. |

### baseline_summary.csv

Baseline truy vấn gốc trên full graph; label audit để mô tả, không phải predictive test. **Số dòng: 1.** [Mở CSV](datasets/paysim/tables/baseline_summary.csv).

| column | meaning_or_unit |
| --- | --- |
| dataset | Giữ nguyên ngữ nghĩa tên cột; vai trò bảng và context được giải thích ở phần tương ứng. |
| raw_cycles | Giữ nguyên ngữ nghĩa tên cột; vai trò bảng và context được giải thích ở phần tương ứng. |
| relay_pairs | Giữ nguyên ngữ nghĩa tên cột; vai trò bảng và context được giải thích ở phần tương ứng. |
| same_hour | Giữ nguyên ngữ nghĩa tên cột; vai trò bảng và context được giải thích ở phần tương ứng. |
| fraud_transfer_edges | Giữ nguyên ngữ nghĩa tên cột; vai trò bảng và context được giải thích ở phần tương ứng. |
| fraud_cashout_edges | Giữ nguyên ngữ nghĩa tên cột; vai trò bảng và context được giải thích ở phần tương ứng. |

### community_size_distribution.csv

Phân bố kích thước toàn bộ cộng đồng LPA; count là số cộng đồng. **Số dòng: 99.** [Mở CSV](datasets/paysim/tables/community_size_distribution.csv).

| column | meaning_or_unit |
| --- | --- |
| member_count | Số đếm; không làm tròn khi tính toán. |
| count | Số đếm; không làm tròn khi tính toán. |

### community_top50.csv

50 cộng đồng lớn nhất của full LPA; positive_tx_count chỉ audit nhãn, không gọi toàn cộng đồng là gian lận. **Số dòng: 50.** [Mở CSV](datasets/paysim/tables/community_top50.csv).

| column | meaning_or_unit |
| --- | --- |
| label | Định danh; giữ nguyên chuỗi/64-bit, không dùng số thực Excel để tránh mất chữ số. |
| member_count | Số đếm; không làm tròn khi tính toán. |
| customer_count | Giữ nguyên ngữ nghĩa tên cột; vai trò bảng và context được giải thích ở phần tương ứng. |
| merchant_count | Giữ nguyên ngữ nghĩa tên cột; vai trò bảng và context được giải thích ở phần tương ứng. |
| total_tx_count | Giữ nguyên ngữ nghĩa tên cột; vai trò bảng và context được giải thích ở phần tương ứng. |
| positive_tx_count | Giữ nguyên ngữ nghĩa tên cột; vai trò bảng và context được giải thích ở phần tương ứng. |
| internal_tx_count | Giữ nguyên ngữ nghĩa tên cột; vai trò bảng và context được giải thích ở phần tương ứng. |
| cross_tx_count | Giữ nguyên ngữ nghĩa tên cột; vai trò bảng và context được giải thích ở phần tương ứng. |

### degree_distribution.csv

Phân bố total degree của toàn bộ tài khoản, kể cả degree 0; sum account_count = V, sum degree*count = 2E. **Số dòng: 101.** [Mở CSV](datasets/paysim/tables/degree_distribution.csv).

| column | meaning_or_unit |
| --- | --- |
| degree | Giữ nguyên ngữ nghĩa tên cột; vai trò bảng và context được giải thích ở phần tương ứng. |
| account_count | Số đếm; không làm tròn khi tính toán. |

### feature_importance.csv

Impurity-based importance từng feature/family; số 0 là không được tree dùng, không phải bằng chứng nhân quả. **Số dòng: 195.** [Mở CSV](datasets/paysim/tables/feature_importance.csv).

| column | meaning_or_unit |
| --- | --- |
| feature | Giữ nguyên ngữ nghĩa tên cột; vai trò bảng và context được giải thích ở phần tương ứng. |
| importance | Impurity feature importance của fitted tree; tổng theo family ~1. |
| family | Mã family; tra tables/model_families.csv. |

### graph_contributions.csv

Chênh lệch chỉ số giữa các family tại threshold riêng đã freeze; ablation quan sát, không causal contribution. **Số dòng: 7.** [Mở CSV](datasets/paysim/tables/graph_contributions.csv).

| column | meaning_or_unit |
| --- | --- |
| contrast | Giữ nguyên ngữ nghĩa tên cột; vai trò bảng và context được giải thích ở phần tương ứng. |
| enhanced | Mã family; tra tables/model_families.csv. |
| reference | Mã family; tra tables/model_families.csv. |
| delta_precision | Tỷ lệ 0–1; delta là chênh lệch tỷ lệ (×100 = điểm phần trăm). |
| delta_recall | Tỷ lệ 0–1; delta là chênh lệch tỷ lệ (×100 = điểm phần trăm). |
| delta_F1 | Tỷ lệ 0–1; delta là chênh lệch tỷ lệ (×100 = điểm phần trăm). |
| delta_average_precision | Tỷ lệ 0–1; delta là chênh lệch tỷ lệ (×100 = điểm phần trăm). |

### motif_coverage.csv

Coverage 9 nhóm motif ở full/test; covered_positives không phải TP của classifier; các nhóm chồng lấp. **Số dòng: 18.** [Mở CSV](datasets/paysim/tables/motif_coverage.csv).

| column | meaning_or_unit |
| --- | --- |
| scope | full = toàn bộ input của run; test = toàn bộ holdout sau cutoff80%. |
| motif | Giữ nguyên ngữ nghĩa tên cột; vai trò bảng và context được giải thích ở phần tương ứng. |
| transactions | Số đếm; không làm tròn khi tính toán. |
| positives | Số đếm; không làm tròn khi tính toán. |
| covered_transactions | Số đếm; không làm tròn khi tính toán. |
| covered_positives | Số đếm; không làm tròn khi tính toán. |
| positive_coverage | Tỷ lệ 0–1; delta là chênh lệch tỷ lệ (×100 = điểm phần trăm). |
| positive_fraction_when_present | Tỷ lệ 0–1; delta là chênh lệch tỷ lệ (×100 = điểm phần trăm). |
| population_prevalence | Tỷ lệ 0–1; delta là chênh lệch tỷ lệ (×100 = điểm phần trăm). |
| interpretation | Giữ nguyên ngữ nghĩa tên cột; vai trò bảng và context được giải thích ở phần tương ứng. |

### pr_curve_full_fusion.csv

Exact precision-recall bins của family nêu trong tên file; không phải sampled PR curve. **Số dòng: 11.** [Mở CSV](datasets/paysim/tables/pr_curve_full_fusion.csv).

| column | meaning_or_unit |
| --- | --- |
| risk_score | Score/ngưỡng 0–1; score từ weighted tree, không phải calibrated probability. |
| positives | Số đếm; không làm tròn khi tính toán. |
| transactions | Số đếm; không làm tròn khi tính toán. |
| precision | Tỷ lệ 0–1; delta là chênh lệch tỷ lệ (×100 = điểm phần trăm). |
| recall | Tỷ lệ 0–1; delta là chênh lệch tỷ lệ (×100 = điểm phần trăm). |

### pr_curve_motif_assisted.csv

Exact precision-recall bins của family nêu trong tên file; không phải sampled PR curve. **Số dòng: 8.** [Mở CSV](datasets/paysim/tables/pr_curve_motif_assisted.csv).

| column | meaning_or_unit |
| --- | --- |
| risk_score | Score/ngưỡng 0–1; score từ weighted tree, không phải calibrated probability. |
| positives | Số đếm; không làm tròn khi tính toán. |
| transactions | Số đếm; không làm tròn khi tính toán. |
| precision | Tỷ lệ 0–1; delta là chênh lệch tỷ lệ (×100 = điểm phần trăm). |
| recall | Tỷ lệ 0–1; delta là chênh lệch tỷ lệ (×100 = điểm phần trăm). |

### pr_curve_transaction_centrality.csv

Exact precision-recall bins của family nêu trong tên file; không phải sampled PR curve. **Số dòng: 7.** [Mở CSV](datasets/paysim/tables/pr_curve_transaction_centrality.csv).

| column | meaning_or_unit |
| --- | --- |
| risk_score | Score/ngưỡng 0–1; score từ weighted tree, không phải calibrated probability. |
| positives | Số đếm; không làm tròn khi tính toán. |
| transactions | Số đếm; không làm tròn khi tính toán. |
| precision | Tỷ lệ 0–1; delta là chênh lệch tỷ lệ (×100 = điểm phần trăm). |
| recall | Tỷ lệ 0–1; delta là chênh lệch tỷ lệ (×100 = điểm phần trăm). |

### pr_curve_transaction_community.csv

Exact precision-recall bins của family nêu trong tên file; không phải sampled PR curve. **Số dòng: 5.** [Mở CSV](datasets/paysim/tables/pr_curve_transaction_community.csv).

| column | meaning_or_unit |
| --- | --- |
| risk_score | Score/ngưỡng 0–1; score từ weighted tree, không phải calibrated probability. |
| positives | Số đếm; không làm tròn khi tính toán. |
| transactions | Số đếm; không làm tròn khi tính toán. |
| precision | Tỷ lệ 0–1; delta là chênh lệch tỷ lệ (×100 = điểm phần trăm). |
| recall | Tỷ lệ 0–1; delta là chênh lệch tỷ lệ (×100 = điểm phần trăm). |

### pr_curve_transaction_novelty.csv

Exact precision-recall bins của family nêu trong tên file; không phải sampled PR curve. **Số dòng: 5.** [Mở CSV](datasets/paysim/tables/pr_curve_transaction_novelty.csv).

| column | meaning_or_unit |
| --- | --- |
| risk_score | Score/ngưỡng 0–1; score từ weighted tree, không phải calibrated probability. |
| positives | Số đếm; không làm tròn khi tính toán. |
| transactions | Số đếm; không làm tròn khi tính toán. |
| precision | Tỷ lệ 0–1; delta là chênh lệch tỷ lệ (×100 = điểm phần trăm). |
| recall | Tỷ lệ 0–1; delta là chênh lệch tỷ lệ (×100 = điểm phần trăm). |

### pr_curve_transaction_only.csv

Exact precision-recall bins của family nêu trong tên file; không phải sampled PR curve. **Số dòng: 3.** [Mở CSV](datasets/paysim/tables/pr_curve_transaction_only.csv).

| column | meaning_or_unit |
| --- | --- |
| risk_score | Score/ngưỡng 0–1; score từ weighted tree, không phải calibrated probability. |
| positives | Số đếm; không làm tròn khi tính toán. |
| transactions | Số đếm; không làm tròn khi tính toán. |
| precision | Tỷ lệ 0–1; delta là chênh lệch tỷ lệ (×100 = điểm phần trăm). |
| recall | Tỷ lệ 0–1; delta là chênh lệch tỷ lệ (×100 = điểm phần trăm). |

### pr_curve_without_centrality.csv

Exact precision-recall bins của family nêu trong tên file; không phải sampled PR curve. **Số dòng: 8.** [Mở CSV](datasets/paysim/tables/pr_curve_without_centrality.csv).

| column | meaning_or_unit |
| --- | --- |
| risk_score | Score/ngưỡng 0–1; score từ weighted tree, không phải calibrated probability. |
| positives | Số đếm; không làm tròn khi tính toán. |
| transactions | Số đếm; không làm tròn khi tính toán. |
| precision | Tỷ lệ 0–1; delta là chênh lệch tỷ lệ (×100 = điểm phần trăm). |
| recall | Tỷ lệ 0–1; delta là chênh lệch tỷ lệ (×100 = điểm phần trăm). |

### pr_curve_without_community.csv

Exact precision-recall bins của family nêu trong tên file; không phải sampled PR curve. **Số dòng: 11.** [Mở CSV](datasets/paysim/tables/pr_curve_without_community.csv).

| column | meaning_or_unit |
| --- | --- |
| risk_score | Score/ngưỡng 0–1; score từ weighted tree, không phải calibrated probability. |
| positives | Số đếm; không làm tròn khi tính toán. |
| transactions | Số đếm; không làm tròn khi tính toán. |
| precision | Tỷ lệ 0–1; delta là chênh lệch tỷ lệ (×100 = điểm phần trăm). |
| recall | Tỷ lệ 0–1; delta là chênh lệch tỷ lệ (×100 = điểm phần trăm). |

### pr_curve_without_motifs.csv

Exact precision-recall bins của family nêu trong tên file; không phải sampled PR curve. **Số dòng: 7.** [Mở CSV](datasets/paysim/tables/pr_curve_without_motifs.csv).

| column | meaning_or_unit |
| --- | --- |
| risk_score | Score/ngưỡng 0–1; score từ weighted tree, không phải calibrated probability. |
| positives | Số đếm; không làm tròn khi tính toán. |
| transactions | Số đếm; không làm tròn khi tính toán. |
| precision | Tỷ lệ 0–1; delta là chênh lệch tỷ lệ (×100 = điểm phần trăm). |
| recall | Tỷ lệ 0–1; delta là chênh lệch tỷ lệ (×100 = điểm phần trăm). |

### reliability_summary.csv

Tóm tắt F1 validation và biến thiên F1 5 khoảng test cho từng family. **Số dòng: 9.** [Mở CSV](datasets/paysim/tables/reliability_summary.csv).

| column | meaning_or_unit |
| --- | --- |
| model | Mã family; tra tables/model_families.csv. |
| threshold | Score/ngưỡng 0–1; score từ weighted tree, không phải calibrated probability. |
| mean_F1 | Tỷ lệ 0–1; delta là chênh lệch tỷ lệ (×100 = điểm phần trăm). |
| worst_F1 | Tỷ lệ 0–1; delta là chênh lệch tỷ lệ (×100 = điểm phần trăm). |
| std_F1 | Tỷ lệ 0–1; delta là chênh lệch tỷ lệ (×100 = điểm phần trăm). |
| test_period_min_F1 | Tỷ lệ 0–1; delta là chênh lệch tỷ lệ (×100 = điểm phần trăm). |
| test_period_max_F1 | Tỷ lệ 0–1; delta là chênh lệch tỷ lệ (×100 = điểm phần trăm). |
| test_period_std_F1 | Tỷ lệ 0–1; delta là chênh lệch tỷ lệ (×100 = điểm phần trăm). |
| positive_periods | Giữ nguyên ngữ nghĩa tên cột; vai trò bảng và context được giải thích ở phần tương ứng. |

### review_budgets.csv

Exact top-K review ở 0.1%, 0.5%, 1% test; tie-break cố định, không tối ưu sau test. **Số dòng: 27.** [Mở CSV](datasets/paysim/tables/review_budgets.csv).

| column | meaning_or_unit |
| --- | --- |
| model | Mã family; tra tables/model_families.csv. |
| review_fraction | Tỷ lệ 0–1; delta là chênh lệch tỷ lệ (×100 = điểm phần trăm). |
| K | Số đếm; không làm tròn khi tính toán. |
| transactions | Số đếm; không làm tròn khi tính toán. |
| fraud | Số đếm; không làm tròn khi tính toán. |
| TP_at_K | Số đếm; không làm tròn khi tính toán. |
| precision_at_K | Tỷ lệ 0–1; delta là chênh lệch tỷ lệ (×100 = điểm phần trăm). |
| recall_at_K | Tỷ lệ 0–1; delta là chênh lệch tỷ lệ (×100 = điểm phần trăm). |
| tie_policy | Giữ nguyên ngữ nghĩa tên cột; vai trò bảng và context được giải thích ở phần tương ứng. |

### selected_amounts_by_currency.csv

Tổng payment_amount theo currency và TP/FP/FN/TN; không cộng các currency thành một USD total. **Số dòng: 4.** [Mở CSV](datasets/paysim/tables/selected_amounts_by_currency.csv).

| column | meaning_or_unit |
| --- | --- |
| payment_currency | Giữ nguyên ngữ nghĩa tên cột; vai trò bảng và context được giải thích ở phần tương ứng. |
| case | Giữ nguyên ngữ nghĩa tên cột; vai trò bảng và context được giải thích ở phần tương ứng. |
| transactions | Số đếm; không làm tròn khi tính toán. |
| payment_amount | Số tiền theo payment_currency trên cùng dòng; không tự đổi sang USD. |

### selected_case_evidence.csv

Giao dịch thật và history witness của một selected-model test TP; witness có thể nằm trước test. **Số dòng: 1.** [Mở CSV](datasets/paysim/tables/selected_case_evidence.csv).

| column | meaning_or_unit |
| --- | --- |
| event_id | Định danh; giữ nguyên chuỗi/64-bit, không dùng số thực Excel để tránh mất chữ số. |
| src | Định danh; giữ nguyên chuỗi/64-bit, không dùng số thực Excel để tránh mất chữ số. |
| dst | Định danh; giữ nguyên chuỗi/64-bit, không dùng số thực Excel để tránh mất chữ số. |
| step | IBM: epoch seconds; PaySim: step theo giờ. Xem protocol. |
| type | Giữ nguyên ngữ nghĩa tên cột; vai trò bảng và context được giải thích ở phần tương ứng. |
| amount | Số tiền theo payment_currency trên cùng dòng; không tự đổi sang USD. |
| payment_currency | Giữ nguyên ngữ nghĩa tên cột; vai trò bảng và context được giải thích ở phần tương ứng. |
| isFraud | Giữ nguyên ngữ nghĩa tên cột; vai trò bảng và context được giải thích ở phần tương ứng. |
| example_model | Giữ nguyên ngữ nghĩa tên cột; vai trò bảng và context được giải thích ở phần tương ứng. |
| evidence_kind | Giữ nguyên ngữ nghĩa tên cột; vai trò bảng và context được giải thích ở phần tương ứng. |

### selected_cold_start.csv

Test theo lịch sử seen/unseen của family được validation chọn; phân rã counts, không chia ngẫu nhiên. **Số dòng: 3.** [Mở CSV](datasets/paysim/tables/selected_cold_start.csv).

| column | meaning_or_unit |
| --- | --- |
| history_group | Giữ nguyên ngữ nghĩa tên cột; vai trò bảng và context được giải thích ở phần tương ứng. |
| transactions | Số đếm; không làm tròn khi tính toán. |
| fraud | Số đếm; không làm tròn khi tính toán. |
| alerts | Số đếm; không làm tròn khi tính toán. |
| TP | Số đếm; không làm tròn khi tính toán. |
| FP | Số đếm; không làm tròn khi tính toán. |
| FN | Số đếm; không làm tròn khi tính toán. |
| TN | Số đếm; không làm tròn khi tính toán. |
| precision | Tỷ lệ 0–1; delta là chênh lệch tỷ lệ (×100 = điểm phần trăm). |
| recall | Tỷ lệ 0–1; delta là chênh lệch tỷ lệ (×100 = điểm phần trăm). |
| F1 | Tỷ lệ 0–1; delta là chênh lệch tỷ lệ (×100 = điểm phần trăm). |
| prevalence | Tỷ lệ 0–1; delta là chênh lệch tỷ lệ (×100 = điểm phần trăm). |
| alert_rate | Tỷ lệ 0–1; delta là chênh lệch tỷ lệ (×100 = điểm phần trăm). |

### test_metrics.csv

Toàn bộ test của 9 families tại từng threshold đã chọn trên validation; ma trận nhầm lẫn + PR/F1/AP + CI. **Số dòng: 9.** [Mở CSV](datasets/paysim/tables/test_metrics.csv).

| column | meaning_or_unit |
| --- | --- |
| model | Mã family; tra tables/model_families.csv. |
| threshold | Score/ngưỡng 0–1; score từ weighted tree, không phải calibrated probability. |
| transactions | Số đếm; không làm tròn khi tính toán. |
| fraud | Số đếm; không làm tròn khi tính toán. |
| alerts | Số đếm; không làm tròn khi tính toán. |
| TP | Số đếm; không làm tròn khi tính toán. |
| FP | Số đếm; không làm tròn khi tính toán. |
| FN | Số đếm; không làm tròn khi tính toán. |
| TN | Số đếm; không làm tròn khi tính toán. |
| precision | Tỷ lệ 0–1; delta là chênh lệch tỷ lệ (×100 = điểm phần trăm). |
| recall | Tỷ lệ 0–1; delta là chênh lệch tỷ lệ (×100 = điểm phần trăm). |
| F1 | Tỷ lệ 0–1; delta là chênh lệch tỷ lệ (×100 = điểm phần trăm). |
| prevalence | Tỷ lệ 0–1; delta là chênh lệch tỷ lệ (×100 = điểm phần trăm). |
| alert_rate | Tỷ lệ 0–1; delta là chênh lệch tỷ lệ (×100 = điểm phần trăm). |
| average_precision | Tỷ lệ 0–1; delta là chênh lệch tỷ lệ (×100 = điểm phần trăm). |
| selected_on_validation | Giữ nguyên ngữ nghĩa tên cột; vai trò bảng và context được giải thích ở phần tương ứng. |
| precision_low95 | Tỷ lệ 0–1; delta là chênh lệch tỷ lệ (×100 = điểm phần trăm). |
| precision_high95 | Tỷ lệ 0–1; delta là chênh lệch tỷ lệ (×100 = điểm phần trăm). |
| recall_low95 | Tỷ lệ 0–1; delta là chênh lệch tỷ lệ (×100 = điểm phần trăm). |
| recall_high95 | Tỷ lệ 0–1; delta là chênh lệch tỷ lệ (×100 = điểm phần trăm). |

### test_temporal_stability.csv

9 families × 5 khoảng test; tổng counts theo family bằng test_metrics. **Số dòng: 45.** [Mở CSV](datasets/paysim/tables/test_temporal_stability.csv).

| column | meaning_or_unit |
| --- | --- |
| model | Mã family; tra tables/model_families.csv. |
| test_period | Giữ nguyên ngữ nghĩa tên cột; vai trò bảng và context được giải thích ở phần tương ứng. |
| threshold | Score/ngưỡng 0–1; score từ weighted tree, không phải calibrated probability. |
| transactions | Số đếm; không làm tròn khi tính toán. |
| fraud | Số đếm; không làm tròn khi tính toán. |
| alerts | Số đếm; không làm tròn khi tính toán. |
| TP | Số đếm; không làm tròn khi tính toán. |
| FP | Số đếm; không làm tròn khi tính toán. |
| FN | Số đếm; không làm tròn khi tính toán. |
| TN | Số đếm; không làm tròn khi tính toán. |
| precision | Tỷ lệ 0–1; delta là chênh lệch tỷ lệ (×100 = điểm phần trăm). |
| recall | Tỷ lệ 0–1; delta là chênh lệch tỷ lệ (×100 = điểm phần trăm). |
| F1 | Tỷ lệ 0–1; delta là chênh lệch tỷ lệ (×100 = điểm phần trăm). |
| prevalence | Tỷ lệ 0–1; delta là chênh lệch tỷ lệ (×100 = điểm phần trăm). |
| alert_rate | Tỷ lệ 0–1; delta là chênh lệch tỷ lệ (×100 = điểm phần trăm). |
| precision_low95 | Tỷ lệ 0–1; delta là chênh lệch tỷ lệ (×100 = điểm phần trăm). |
| precision_high95 | Tỷ lệ 0–1; delta là chênh lệch tỷ lệ (×100 = điểm phần trăm). |
| recall_low95 | Tỷ lệ 0–1; delta là chênh lệch tỷ lệ (×100 = điểm phần trăm). |
| recall_high95 | Tỷ lệ 0–1; delta là chênh lệch tỷ lệ (×100 = điểm phần trăm). |
| average_precision | Tỷ lệ 0–1; delta là chênh lệch tỷ lệ (×100 = điểm phần trăm). |

### top10_pagerank.csv

10 tài khoản PageRank lớn nhất từ full descriptive analytics; không phải chỉ chạy trên 10 tài khoản. **Số dòng: 10.** [Mở CSV](datasets/paysim/tables/top10_pagerank.csv).

| column | meaning_or_unit |
| --- | --- |
| id | Giữ nguyên ngữ nghĩa tên cột; vai trò bảng và context được giải thích ở phần tương ứng. |
| pagerank | Giữ nguyên ngữ nghĩa tên cột; vai trò bảng và context được giải thích ở phần tương ứng. |
| inDegree | Giữ nguyên ngữ nghĩa tên cột; vai trò bảng và context được giải thích ở phần tương ứng. |
| outDegree | Giữ nguyên ngữ nghĩa tên cột; vai trò bảng và context được giải thích ở phần tương ứng. |
| degree | Giữ nguyên ngữ nghĩa tên cột; vai trò bảng và context được giải thích ở phần tương ứng. |

### validation_average_precision.csv

AP validation theo từng family/fold; dùng cho đánh giá ranking. **Số dòng: 27.** [Mở CSV](datasets/paysim/tables/validation_average_precision.csv).

| column | meaning_or_unit |
| --- | --- |
| fold | Giữ nguyên ngữ nghĩa tên cột; vai trò bảng và context được giải thích ở phần tương ứng. |
| family | Mã family; tra tables/model_families.csv. |
| average_precision | Tỷ lệ 0–1; delta là chênh lệch tỷ lệ (×100 = điểm phần trăm). |
| transactions | Số đếm; không làm tròn khi tính toán. |

### validation_leaderboard.csv

9 families × 12 thresholds; trung bình/worst/std 3 folds; đây là dữ liệu chọn mô hình. **Số dòng: 108.** [Mở CSV](datasets/paysim/tables/validation_leaderboard.csv).

| column | meaning_or_unit |
| --- | --- |
| family | Mã family; tra tables/model_families.csv. |
| threshold | Score/ngưỡng 0–1; score từ weighted tree, không phải calibrated probability. |
| mean_F1 | Tỷ lệ 0–1; delta là chênh lệch tỷ lệ (×100 = điểm phần trăm). |
| worst_F1 | Tỷ lệ 0–1; delta là chênh lệch tỷ lệ (×100 = điểm phần trăm). |
| std_F1 | Tỷ lệ 0–1; delta là chênh lệch tỷ lệ (×100 = điểm phần trăm). |
| mean_precision | Giữ nguyên ngữ nghĩa tên cột; vai trò bảng và context được giải thích ở phần tương ứng. |
| TP | Số đếm; không làm tròn khi tính toán. |
| FP | Số đếm; không làm tròn khi tính toán. |
| FN | Số đếm; không làm tròn khi tính toán. |
| transactions | Số đếm; không làm tròn khi tính toán. |
| folds | Giữ nguyên ngữ nghĩa tên cột; vai trò bảng và context được giải thích ở phần tương ứng. |

### walk_forward.csv

3 folds × 9 families × 12 thresholds; mỗi dòng là validation fold, không phải final test. **Số dòng: 324.** [Mở CSV](datasets/paysim/tables/walk_forward.csv).

| column | meaning_or_unit |
| --- | --- |
| fold | Giữ nguyên ngữ nghĩa tên cột; vai trò bảng và context được giải thích ở phần tương ứng. |
| family | Mã family; tra tables/model_families.csv. |
| threshold | Score/ngưỡng 0–1; score từ weighted tree, không phải calibrated probability. |
| transactions | Số đếm; không làm tròn khi tính toán. |
| fraud | Số đếm; không làm tròn khi tính toán. |
| alerts | Số đếm; không làm tròn khi tính toán. |
| TP | Số đếm; không làm tròn khi tính toán. |
| FP | Số đếm; không làm tròn khi tính toán. |
| FN | Số đếm; không làm tròn khi tính toán. |
| TN | Số đếm; không làm tròn khi tính toán. |
| precision | Tỷ lệ 0–1; delta là chênh lệch tỷ lệ (×100 = điểm phần trăm). |
| recall | Tỷ lệ 0–1; delta là chênh lệch tỷ lệ (×100 = điểm phần trăm). |
| F1 | Tỷ lệ 0–1; delta là chênh lệch tỷ lệ (×100 = điểm phần trăm). |
| prevalence | Tỷ lệ 0–1; delta là chênh lệch tỷ lệ (×100 = điểm phần trăm). |
| alert_rate | Tỷ lệ 0–1; delta là chênh lệch tỷ lệ (×100 = điểm phần trăm). |

## Các bảng gộp

- dataset_overview: quy mô và winner, một dòng/dataset.
- all_18_test_models: ghép hai test_metrics với cột dataset; không cộng metrics.
- baseline_vs_validation_selected: mỗi dataset hai dòng.
- evaluation_splits/full_time_blocks: trích counts nguyên từ saved notebook output, không đọc raw.
- exact_feature_allowlists: exact order trong từng fitted model; dùng đối chiếu tree split feature_index.
- existing_phase_measurements: thời gian/CPU phase và cumulative memory extrema; không phải một benchmark mới.
- model_families: ánh xạT/C/M/L cho9families.

## Saved model tables

Trong model_details/<family>: training.json ghiN/P/weight/features; amount_scales.csv làq90 đãfit; saved_model_parameters.json giữ stage metadata/vocab/node data nguyên ngữ nghĩa; tree_nodes.csv flatten cácnode; leaf_rules.csv là đường đi mỗi leaf vàscore/alert ởfrozen threshold. training_raw_count là raw training samples ởnode, impurityStats là weighted mass; không đồng nhất hai trường. categorical split dùng index từlabelsArray. Không dùng leaf rule trực tiếp trên raw amount; phải đi qua preprocessing đã ghi trong source.
