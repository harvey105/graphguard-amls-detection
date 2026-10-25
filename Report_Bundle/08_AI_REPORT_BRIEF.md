# Brief dùng ngay cho AI viết report/slides

Copy phần yêu cầu bên dưới, gửi kèm các file được nhắc tới. Có thể làm việc hoàn toàn offline với bundle; không yêu cầu bạn cùng nhóm chạy notebook.

> Hãy viết report Big Data GraphGuard bằng tiếng Việt, bám sát kết quả có sẵn. Đọc 01_EXECUTIVE_SUMMARY.md, 02_METHODS_AND_PARAMETERS.md, hai báo cáo03/04, 05_COMPARISON_AND_FUSION.md và 06_RELIABILITY_AND_VALIDATION.md. Lấy số chuẩn từ tables/dataset_overview.csv, all_18_test_models.csv, baseline_vs_validation_selected.csv và evaluation_splits.csv. Khi cần motif/reliability/budget/importance, đọc CSV tương ứng dưới datasets/<dataset>/tables/. Trình bày objective, data, ETL/integrity, Degree/PageRank, LPA, strict-past motifs, feature fusion, optimizer/temporal evaluation, results và kết luận có dẫn nguồn tương đối trong bundle. Mỗi con số chỉ rõ dataset,full/test/validation, family và threshold. Dùng dàn ý07 để tạo slides; dùngPNG sẵn có, không tạo số liệu giả hay train lại.

## Quy tắc kiểm tra nội dung trước khi nộp

- Full IBM variant=HI-Small đã chọn, không phải mọi biến thể IBM; full PaySim6,362,620 rows.
- IBM selected=full_fusion,.5; PaySim selected=without_centrality,.7. Giữ validation winner; không dùng test để reselect.
- CSV rates0–1, Markdown rates%; delta×100=điểm phần trăm. AP không phải accuracy, weighted score không phải calibrated probability.
- Full descriptive analytics không phải future predictive features. Label chỉ để train/evaluate/audit, không được gọi là input phát hiện fraud.
- Không gộp chỉ số hai datasets thành mộtF1; không trộn `baseline_summary`, `motif_coverage` với classifier TP.
- PaySimcycle=0 là quan sát thật. IBM case witness có giao dịch strict-past trước test; không cộng chúng thành số testTP.
- Examples/top10/top50 chỉ minh họa từ full results; performance dùng test_metrics, không suy bằng tần suất trong examples.
- Không gọi toàn bộcommunity là criminal; không khẳng định mọi giao dịch vòng tròn đều fraud hoặc tree dùng cycle nếu importance=0.
- Nêu đúng trade-off: IBMselected giảm alerts/tăngP/AP nhưng không tăngR/F1 trên test; PaySimselected tăngR/F1/AP nhưngP thấp hơnbaseline.
- Không tự viết số đã không được export; nếu cần statistic mới, ghi rõ không có trong bundle.

## Gợi ý phân chia viết bài

Người viết phương pháp đọc02 + exact_feature_allowlists vàsource; người viếtIBM đọc03 + datasets/ibm_aml; người viếtPaySim đọc04; người tổng hợp đọc05/06 + tables. Người thiết kếslides dùng07 + PNG. Người kiểm chứng dùngmanifest vàvalidation/bundle_checks.json. Không cần nhận raw data hoặc càiSpark.
