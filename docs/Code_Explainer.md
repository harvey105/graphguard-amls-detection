# Code Explainer — GraphGuard full system

Hướng dẫn đọc code từ input đến kết quả cuối. Hai notebook cùng kiến trúc, chạy riêng từng dataset và giữ một transaction index chung cho mọi nhánh trong dataset đó.

## 1. Bắt đầu từ notebook

| Nội dung | [IBM notebook](../notebooks/IBM_full_system.ipynb) — cell | [PaySim notebook](../notebooks/PaySIM_full_system.ipynb) — cell |
|---|---|---|
| Runtime, protocol, edge contract và full index | 1–4 | 1–4 |
| Full raw reconciliation | 5 | 5 |
| Degree/PageRank kernels và full analytics | 6–8 | 6–8 |
| LPA kernel và community profiles | 9–10 | 9–10 |
| Motif queries và baseline | 11–12 | 11–13 |
| Causal motif kernels, disk stages và coverage | 13–20 | 14–21 |
| Historical snapshots và common feature table | 21–23 | 22–24 |
| Preprocessing, weighted tree, scoring và metrics | 24–28 | 25–29 |
| Walk-forward validation, khóa family/ngưỡng | 29 | 30 |
| Frozen test, models và predictions | 30 | 31 |
| Benchmark, PR curve và review budgets | 31 | 32 |
| Temporal reliability, intervals và importance | 32 | 33 |
| TP/FP/FN examples và witness | 33 | 34 |
| Independent acceptance và runtime benchmark | 34 | 35 |
| Đóng session | 35 | 36 |

Đây là số **code cells**; Markdown giải thích nằm xen giữa. Notebook chứa định nghĩa kernel quan trọng và truyền chúng vào pipeline để thực thi. Verifier đối chiếu AST với `.py`, rồi kiểm tra execution order, saved outputs và source hashes.

## 2. Raw → graph → một transaction index

- [PaySim mapping](../src/paysim/etl_mapping.py): `build_vertices_df`, `build_edges_df`; đổi origin/destination thành `src`/`dst`, giữ type, amount, simulation hour và nhãn.
- [IBM ETL](../src/ibm_aml/etl.py): `build_ibm_vertices`, `build_ibm_edges`; tạo bank/account IDs, timestamp, currency, payment format và target laundering.
- [Graph utilities](../src/common/graph_utils.py): `load_graph`, `save_graph`, `check_integrity`.
- [Pipeline](../src/motif/pipeline.py): `start_full_system` tạo index cho từng physical row; `full_system_raw_reconciliation` đối chiếu raw mapping và Parquet bằng multiset hai chiều.

`event_id` phân biệt từng physical transaction, kể cả những dòng có cùng nội dung. `event_key` phục vụ tie-breaking và không chứa nhãn. Các nhánh dùng cùng index để join và đánh giá.

## 3. Degree/PageRank và communities

| Thành phần | Source / hàm chính | Vai trò |
|---|---|---|
| Degree | [metrics.py](../src/paysim/metrics.py): `account_degree_metrics` | Đếm in/out degree, giữ mọi account; kiểm tra tổng degree = 2E |
| PageRank | [metrics.py](../src/paysim/metrics.py): `pagerank_update`, `dataframe_pagerank` | 10 vòng, reset 0,15, giữ multiplicity và normalize tổng rank = N |
| LPA | [community_detection.py](../src/paysim/community_detection.py): `lpa_update`, `dataframe_lpa` | 5 vòng neighbor voting, message hai chiều, tie chọn nhãn nhỏ nhất |
| Full exports | [pipeline.py](../src/motif/pipeline.py): `full_system_centrality`, `full_system_communities` | All-account metrics, assignments và profiles theo community/currency |
| Independent checks | [project_audit.py](../src/common/project_audit.py): `verify_full_system_communities` | Đối chiếu membership và transaction totals bằng phép tính độc lập |

Các full backends được dùng chung cho cả hai datasets; [IBM metrics adapter](../src/ibm_aml/metrics.py) và [IBM community adapter](../src/ibm_aml/community_detection.py) giữ entry point riêng. Community ID là mã phân hoạch; fraud counts trong phần mô tả là hậu kiểm bằng nhãn.

## 4. Motifs và features đúng thời điểm

[features.py](../src/motif/features.py) tổ chức code theo từng phép tính:

- `_sweep_counts`: activation/expiry events và prefix sums cho cửa sổ 24/168 giờ.
- `build_star_features`: sender/receiver history, fan-in/out và typed relay.
- `build_reciprocal_features`: lịch sử hai chiều và same-partner counts.
- `build_motif_features`: kết hợp các nhóm, giữ một row cho mỗi giao dịch.
- `materialize_motif_stage`: ghi/đọc Parquet để cắt lineage trên đĩa.

[IBM motif module](../src/ibm_aml/motif_finding.py) có `find_topological_cycles` và `build_temporal_cycle_features`: tìm account triples rồi ghép các giao dịch theo thứ tự thời gian và currency. Kernel này cũng dùng được cho PaySim qua cùng edge contract; đơn vị thời gian lấy từ `DatasetSpec`.

[PaySim motif module](../src/paysim/motif_finding.py) có `find_relays`; [toy cycle module](../src/motif/toy_cycle.py) định nghĩa GraphFrames pattern ba đỉnh. Baseline queries được trình bày riêng với causal features của detector.

## 5. Snapshots → feature fusion → model

[Pipeline](../src/motif/pipeline.py) dùng `historical_system_snapshot`, `join_system_snapshot` và `full_system_feature_table` để tạo Degree/PageRank và LPA từ các prefix quá khứ. Mỗi decision row phải có `snapshot_as_of < step`; block warm-up có defaults và seen flags được khai báo rõ.

[Config](../src/motif/config.py) định nghĩa windows, folds, threshold grid và `SYSTEM_FAMILY_GROUPS`. **T** là thông tin giao dịch; **C/M/L** lần lượt là centrality, motifs và community. Có tám tổ hợp C/M/L trên nền T, thêm một transaction+novelty control, tổng chín families.

[Modeling](../src/motif/modeling.py) chứa:

| Hàm | Code cần giải thích |
|---|---|
| `prepare_training_prefix` | Fit amount q90/category indexer chỉ trên training prefix; join truth và materialize một lần cho chín trees |
| `family_feature_names` | Explicit feature allowlists cho từng family |
| `fit_prepared_model` | VectorAssembler + weighted decision tree; depth 5, min-leaf 50, seed 2026 |
| `score_transactions` | Transform features không có nhãn bằng model đã fit |
| `frozen_prediction` | Tạo alert theo ngưỡng đã khóa; gắn truth sau scoring |
| `metrics_at_threshold` | Tính TP/FP/FN/TN, precision, recall và F1 |
| `precision_recall_curve` | Gộp score ties để tính PR curve và exact average precision |

## 6. Benchmark, reliability và chứng cứ

`full_system_validation` chạy ba expanding folds, chọn family/ngưỡng theo validation rồi lưu frozen rule. `full_system_test` refit đến cutoff 80%, đánh giá phần sau cutoff và export cả chín phương án. Selected model được reload để replay toàn test.

`full_system_motif_benchmark` đo structural coverage sau construction. `full_system_reliability` cung cấp validation mean/worst/std F1, năm chronological test periods, Wilson intervals, cold-start groups và matched ablation contrasts. [Presentation module](../src/motif/presentation.py) tạo charts và `system_case_evidence` truy xuất giao dịch/witness thật.

Đọc kết quả theo ba câu hỏi: **query tìm được cấu trúc gì → cấu trúc bao phủ nhãn nào → model có thêm thông tin dự đoán như thế nào?** Dùng [báo cáo thực nghiệm](PartB_Experiments.md) và [so sánh](PartB_Comparison.md) để đối chiếu đầy đủ số liệu.

## 7. Kiểm chứng và tái lập

- [Project gate](../scripts/check_project.ps1): entry point của `make check`, chạy tuần tự trên native Windows.
- [Notebook runner](../scripts/run_n4_notebook.py): kiểm tra source copies và lưu output sau từng cell.
- [Independent audit](../src/common/project_audit.py): coverage, source/input/output hashes, metrics từ predictions và notebook/source consistency.
- [Native/oracle tests](../tests/test_project_audit.py), [guard tests](../tests/test_hardware_guard.py), [motif protocol tests](../tests/test_motif_v2.py).

Quy trình setup, tải input và chạy full được ghi trong [README](../README.md#5-chạy-lại-trên-windows-powershell). Các liên kết trong tài liệu này đều trỏ tới source, notebook hoặc tài liệu có trong repo.
