# paysim: transaction_only

Đây là tham số đã fit trên toàn bộ prefix ≤80%, đọc từ model đã lưu; không huấn luyện lại.

Ngưỡng frozen: 0.7. Score là tỷ lệ weighted class mass tại leaf, không phải calibrated probability. Feature index/categorical index phải đọc cùng training.json và saved_model_parameters.json (StringIndexer labelsArray). Amount scaling phải dùng amount_scales.csv và mã _prepare_amounts; không áp dụng điều kiện lên raw amount thay cho scaled_amount.

| leaf_id | condition | risk_score | alert_at_frozen_threshold | training_raw_count |
| --- | --- | --- | --- | --- |
| 1 | scaled_amount <= 1.1517823480932849 | 0.02093744068926844 | False | 5082365 |
| 3 | scaled_amount > 1.1517823480932849 AND type_index IN [0.0, 2.0, 3.0, 4.0] | 0.20395638796858115 | False | 29077 |
| 4 | scaled_amount > 1.1517823480932849 AND type_index NOT IN [0.0, 2.0, 3.0, 4.0] | 0.9389174204234455 | True | 2442 |
