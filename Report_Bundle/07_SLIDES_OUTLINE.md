# Dàn ý slides và lời trình bày

Mỗi slide có thông điệp, nguồn và lưu ý đọc số. Chèn PNG gốc, không chụp ảnh bảng quá dài; bảng9models có thể để phụ lục. Các đường dẫn dưới đây đều thuộc bundle.

## Slide 1: Bài toán và đầu ra

**Nội dung chính:** Money laundering/fraud transaction screening; score + alert + graph context.

**Nguồn/visual:** [01_EXECUTIVE_SUMMARY.md](01_EXECUTIVE_SUMMARY.md).

**Lời trình bày:** Nêu IBM laundering và PaySim fraud là hai benchmark riêng; kết quả không phải phán quyết pháp lý.

## Slide 2: Hai full datasets

**Nội dung chính:** IBM 5,078,345 giao dịch/518,581 tài khoản; PaySim 6,362,620/9,073,900.

**Nguồn/visual:** [dataset_overview.csv](tables/dataset_overview.csv).

**Lời trình bày:** Nhấn mạnh full HI-Small variant của IBM và full PaySim được chọn; không phải sampled graph.

## Slide 3: Pipeline thống nhất

**Nội dung chính:** ETL → integrity → historical features → validation → freeze → test → evidence.

**Nguồn/visual:** [02_METHODS_AND_PARAMETERS.md](02_METHODS_AND_PARAMETERS.md).

**Lời trình bày:** Phân biệt full descriptive graph với strict-past predictive graph.

## Slide 4: Degree và PageRank

**Nội dung chính:** IBM mean degree≈19.59; PaySim≈1.40.

**Nguồn/visual:** [degree_distribution_paysim_vs_ibm.png](comparison/degree_distribution_paysim_vs_ibm.png).

**Lời trình bày:** Chọn degree figure so sánh; PageRank đo centrality, không tự dự đoán fraud.

## Slide 5: LPA/community context

**Nội dung chính:** IBM314,722 communities; PaySim5,433,491; dùng size/cross fraction, không dùng numeric label.

**Nguồn/visual:** [full_communities.png](datasets/ibm_aml/figures/full_communities.png).

**Lời trình bày:** Đính kèm PaySim full_communities; internal-edge=0 không phải fraud=0.

## Slide 6: Motif và chống leakage

**Nội dung chính:** History24/168h; cycle/relay chỉ dùng strict-past, ties không tạo history.

**Nguồn/visual:** [motif_coverage.png](datasets/ibm_aml/figures/motif_coverage.png).

**Lời trình bày:** Đặt cạnh PaySim motif_coverage. Coverage là structural support, không phải classifier recall.

## Slide 7: 9 families và optimizer

**Nội dung chính:** Feature-level fusion; maxDepth5/minLeaf50/seed2026; thresholds chọn bằng3folds.

**Nguồn/visual:** [model_families.csv](tables/model_families.csv).

**Lời trình bày:** T+C+M+L so với factorial subsets và novelty control; không chọn threshold trên test.

## Slide 8: Temporal protocol

**Nội dung chính:** Train40→val50; train50→val65; train65→val80; refit80→test.

**Nguồn/visual:** [temporal_protocol.png](datasets/ibm_aml/figures/temporal_protocol.png).

**Lời trình bày:** Dùng counts/timestamp thật trong evaluation_splits.csv; ties làm tỷ lệ không chính xác20%.

## Slide 9: IBM: operating point

**Nội dung chính:** TP500/FP4,456; precision10.09%, recall27.79%, F1=14.80%, AP=5.87%.

**Nguồn/visual:** [confusion.png](datasets/ibm_aml/figures/confusion.png).

**Lời trình bày:** Baseline P9.07%,R48.30%,F115.27%,AP5.62%; fusion giảm alerts9,584→4,956. Không nói mọi metric tăng.

## Slide 10: PaySim: operating point

**Nội dung chính:** TP1,109/FP799; precision58.12%, recall26.09%, F1=36.02%, AP=26.58%.

**Nguồn/visual:** [confusion.png](datasets/paysim/figures/confusion.png).

**Lời trình bày:** Winner T+M+L chọn ở validation; full fusion T+C+M+L có trong ablation, không đổi winner theo testAP.

## Slide 11: Ablation và ranking

**Nội dung chính:** Trình bày9families để thấy lợi ích từng cấu hình.

**Nguồn/visual:** [ablation_and_pr.png](datasets/ibm_aml/figures/ablation_and_pr.png).

**Lời trình bày:** Dùng thêm PaySim cùng tên. So sánhAP với prevalence và baseline, giữ đơn vị % nhất quán.

## Slide 12: Review budget

**Nội dung chính:** Đánh giá top0.1%,0.5%,1% với K=ceil(fN), tie-break cố định.

**Nguồn/visual:** [review_budgets.png](datasets/paysim/figures/review_budgets.png).

**Lời trình bày:** Lấy exactK/TP_at_K/precision/recall trong CSV; đừng suy từ threshold alerts ra topK.

## Slide 13: Reliability

**Nội dung chính:** 3validationfolds,5testperiods,Wilson95%,independent artifact verification.

**Nguồn/visual:** [temporal_stability.png](datasets/ibm_aml/figures/temporal_stability.png).

**Lời trình bày:** IBM selected test-periodF1≈3.32–28.79%; PaySim≈27.05–40.90%. Không cam kết ổn định ngoài dataset.

## Slide 14: Case giải thích được

**Nội dung chính:** IBM có chronology3-cycle witness; PaySim case là CASH_OUT TP không có motif witness.

**Nguồn/visual:** [selected_case.png](datasets/ibm_aml/figures/selected_case.png).

**Lời trình bày:** Đọc cả selected_case_evidence.csv; history witness không phải mọi cạnh đều là testTP hay nguyên nhân tree alert.

## Slide 15: Kết luận có số liệu hỗ trợ

**Nội dung chính:** Full pipeline, controlled fusion, measured precision/recall/workload và khác biệt datasets.

**Nguồn/visual:** [05_COMPARISON_AND_FUSION.md](05_COMPARISON_AND_FUSION.md).

**Lời trình bày:** Chốt bằng trade-off thực tế, không khẳng định phát hiện mọi fraud ring; dẫn nguồnCSV và mã định danh run.

## Slide 16: Phụ lục kiểm nghiệm/code

**Nội dung chính:** Saved output notebook, source snapshot,trained trees,hashmanifest.

**Nguồn/visual:** [CELL_GUIDE.md](notebooks/CELL_GUIDE.md).

**Lời trình bày:** Mở notebook HTML nếu thầy muốn đọc code; không cần chạy Spark lại trên máy thuyết trình.

