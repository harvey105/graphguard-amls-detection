# paysim: motif_assisted

Đây là tham số đã fit trên toàn bộ prefix ≤80%, đọc từ model đã lưu; không huấn luyện lại.

Ngưỡng frozen: 0.7. Score là tỷ lệ weighted class mass tại leaf, không phải calibrated probability. Feature index/categorical index phải đọc cùng training.json và saved_model_parameters.json (StringIndexer labelsArray). Amount scaling phải dùng amount_scales.csv và mã _prepare_amounts; không áp dụng điều kiện lên raw amount thay cho scaled_amount.

| leaf_id | condition | risk_score | alert_at_frozen_threshold | training_raw_count |
| --- | --- | --- | --- | --- |
| 2 | scaled_amount <= 1.1517823480932849 AND type_index IN [0.0, 1.0, 2.0, 3.0] | 0.00958956511005541 | False | 4670401 |
| 5 | scaled_amount <= 1.1517823480932849 AND type_index NOT IN [0.0, 1.0, 2.0, 3.0] AND receiver_in_168h <= 0.5 AND scaled_amount <= 0.10177732205329212 | 0.6513443684938433 | False | 13528 |
| 7 | scaled_amount <= 1.1517823480932849 AND type_index NOT IN [0.0, 1.0, 2.0, 3.0] AND receiver_in_168h <= 0.5 AND scaled_amount > 0.10177732205329212 AND scaled_amount <= 0.67735129644551684 | 0.4650312255266671 | False | 36047 |
| 8 | scaled_amount <= 1.1517823480932849 AND type_index NOT IN [0.0, 1.0, 2.0, 3.0] AND receiver_in_168h <= 0.5 AND scaled_amount > 0.10177732205329212 AND scaled_amount > 0.67735129644551684 | 0.6582966206507004 | False | 4733 |
| 9 | scaled_amount <= 1.1517823480932849 AND type_index NOT IN [0.0, 1.0, 2.0, 3.0] AND receiver_in_168h > 0.5 | 0.00040143941605177524 | False | 357656 |
| 12 | scaled_amount > 1.1517823480932849 AND type_index IN [0.0, 2.0, 3.0, 4.0] AND type_index IN [0.0, 2.0, 3.0] | 0.0 | False | 16571 |
| 14 | scaled_amount > 1.1517823480932849 AND type_index IN [0.0, 2.0, 3.0, 4.0] AND type_index NOT IN [0.0, 2.0, 3.0] AND receiver_in_168h <= 0.5 | 0.7904492161821861 | True | 2167 |
| 15 | scaled_amount > 1.1517823480932849 AND type_index IN [0.0, 2.0, 3.0, 4.0] AND type_index NOT IN [0.0, 2.0, 3.0] AND receiver_in_168h > 0.5 | 0.0 | False | 10339 |
| 16 | scaled_amount > 1.1517823480932849 AND type_index NOT IN [0.0, 2.0, 3.0, 4.0] | 0.9389174204234455 | True | 2442 |
