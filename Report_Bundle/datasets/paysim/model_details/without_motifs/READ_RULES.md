# paysim: without_motifs

Đây là tham số đã fit trên toàn bộ prefix ≤80%, đọc từ model đã lưu; không huấn luyện lại.

Ngưỡng frozen: 0.5. Score là tỷ lệ weighted class mass tại leaf, không phải calibrated probability. Feature index/categorical index phải đọc cùng training.json và saved_model_parameters.json (StringIndexer labelsArray). Amount scaling phải dùng amount_scales.csv và mã _prepare_amounts; không áp dụng điều kiện lên raw amount thay cho scaled_amount.

| leaf_id | condition | risk_score | alert_at_frozen_threshold | training_raw_count |
| --- | --- | --- | --- | --- |
| 1 | scaled_amount <= 1.1517823480932849 | 0.02093744068926844 | False | 5082365 |
| 4 | scaled_amount > 1.1517823480932849 AND type_index IN [0.0, 2.0, 3.0, 4.0] AND type_index IN [0.0, 2.0, 3.0] | 0.0 | False | 16571 |
| 6 | scaled_amount > 1.1517823480932849 AND type_index IN [0.0, 2.0, 3.0, 4.0] AND type_index NOT IN [0.0, 2.0, 3.0] AND dst_inDegree <= 0.5 | 0.7298500875722682 | True | 2944 |
| 7 | scaled_amount > 1.1517823480932849 AND type_index IN [0.0, 2.0, 3.0, 4.0] AND type_index NOT IN [0.0, 2.0, 3.0] AND dst_inDegree > 0.5 | 0.0 | False | 9562 |
| 10 | scaled_amount > 1.1517823480932849 AND type_index NOT IN [0.0, 2.0, 3.0, 4.0] AND scaled_amount <= 1.8117980692313906 AND dst_pagerank <= 3.8231711972968716 | 0.8936251076386464 | True | 1403 |
| 12 | scaled_amount > 1.1517823480932849 AND type_index NOT IN [0.0, 2.0, 3.0, 4.0] AND scaled_amount <= 1.8117980692313906 AND dst_pagerank > 3.8231711972968716 AND dst_inDegree <= 27.5 | 0.7792852180284234 | True | 525 |
| 13 | scaled_amount > 1.1517823480932849 AND type_index NOT IN [0.0, 2.0, 3.0, 4.0] AND scaled_amount <= 1.8117980692313906 AND dst_pagerank > 3.8231711972968716 AND dst_inDegree > 27.5 | 0.34228284629684247 | False | 70 |
| 14 | scaled_amount > 1.1517823480932849 AND type_index NOT IN [0.0, 2.0, 3.0, 4.0] AND scaled_amount > 1.8117980692313906 | 0.9982707795280972 | True | 444 |
