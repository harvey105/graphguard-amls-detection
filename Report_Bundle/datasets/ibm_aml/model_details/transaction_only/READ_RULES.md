# ibm_aml: transaction_only

Đây là tham số đã fit trên toàn bộ prefix ≤80%, đọc từ model đã lưu; không huấn luyện lại.

Ngưỡng frozen: 0.5. Score là tỷ lệ weighted class mass tại leaf, không phải calibrated probability. Feature index/categorical index phải đọc cùng training.json và saved_model_parameters.json (StringIndexer labelsArray). Amount scaling phải dùng amount_scales.csv và mã _prepare_amounts; không áp dụng điều kiện lên raw amount thay cho scaled_amount.

| leaf_id | condition | risk_score | alert_at_frozen_threshold | training_raw_count |
| --- | --- | --- | --- | --- |
| 1 | type_index IN [1.0, 2.0, 3.0, 4.0, 5.0, 6.0] | 0.00525926947868985 | False | 3599180 |
| 3 | type_index NOT IN [1.0, 2.0, 3.0, 4.0, 5.0, 6.0] AND scaled_amount <= 0.016910214633845108 | 0.048012076024367904 | False | 228471 |
| 6 | type_index NOT IN [1.0, 2.0, 3.0, 4.0, 5.0, 6.0] AND scaled_amount > 0.016910214633845108 AND scaled_amount <= 0.2987789251452882 AND scaled_amount <= 0.084770401717523453 | 0.2459328369038959 | False | 119167 |
| 8 | type_index NOT IN [1.0, 2.0, 3.0, 4.0, 5.0, 6.0] AND scaled_amount > 0.016910214633845108 AND scaled_amount <= 0.2987789251452882 AND scaled_amount > 0.084770401717523453 AND fx_payment <= 0.5 | 0.5572272991967513 | True | 35501 |
| 9 | type_index NOT IN [1.0, 2.0, 3.0, 4.0, 5.0, 6.0] AND scaled_amount > 0.016910214633845108 AND scaled_amount <= 0.2987789251452882 AND scaled_amount > 0.084770401717523453 AND fx_payment > 0.5 | 0.0 | False | 7296 |
| 10 | type_index NOT IN [1.0, 2.0, 3.0, 4.0, 5.0, 6.0] AND scaled_amount > 0.016910214633845108 AND scaled_amount > 0.2987789251452882 | 0.06501907764929095 | False | 70909 |
