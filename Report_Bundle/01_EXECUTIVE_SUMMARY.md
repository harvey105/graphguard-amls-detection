# Mục tiêu và kết quả chính

GraphGuard đánh giá khả năng xếp hạng/cảnh báo giao dịch nghi vấn bằng thuộc tính giao dịch và ba nguồn ngữ cảnh đồ thị: **Degree/PageRank (C), motif/history (M), LPA/community context (L)**. IBM dùng nhãn laundering; PaySim dùng nhãn fraud. Đầu ra là score và alert cho từng giao dịch, được so với ground truth sau inference; không phải chứng minh pháp lý một đường dây rửa tiền.

## Toàn bộ dữ liệu được xử lý

| dataset | transactions | accounts | positives | prevalence | communities | selected_family | threshold |
| --- | --- | --- | --- | --- | --- | --- | --- |
| ibm_aml | 5078345 | 518581 | 5177 | 0.10% | 314722 | full_fusion | 0.5 |
| paysim | 6362620 | 9073900 | 8213 | 0.13% | 5433491 | without_centrality | 0.7 |

## Baseline và family được chọn trên validation

| dataset | model | threshold | TP | FP | FN | TN | alerts | precision | recall | F1 | average_precision |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| ibm_aml | transaction_only | 0.5 | 869 | 8715 | 930 | 1007307 | 9584 | 9.07% | 48.30% | 15.27% | 5.62% |
| ibm_aml | full_fusion | 0.5 | 500 | 4456 | 1299 | 1011566 | 4956 | 10.09% | 27.79% | 14.80% | 5.87% |
| paysim | transaction_only | 0.7 | 836 | 196 | 3414 | 1244290 | 1032 | 81.01% | 19.67% | 31.65% | 17.00% |
| paysim | without_centrality | 0.7 | 1109 | 799 | 3141 | 1243687 | 1908 | 58.12% | 26.09% | 36.02% | 26.58% |

**IBM:** full fusion tăng precision từ 9.07% lên 10.09%, AP từ 5.62% lên 5.87%, giảm alerts từ 9,584 xuống 4,956. Recall giảm từ 48.30% xuống 27.79% và F1 từ 15.27% xuống 14.80%; vì vậy không viết “mọi chỉ số đều tăng”. Family vẫn là full_fusion vì chọn trên validation trước khi đọc test.

**PaySim:** family T+M+L tăng recall từ 19.67% lên 26.09%, F1 từ 31.65% lên 36.02%, AP từ 17.00% lên 26.58%; precision thay đổi từ 81.01% xuống 58.12%, alerts tăng từ 1,032 lên 1,908. Full fusion T+C+M+L vẫn có đầy đủ trong bảng 9 families, không thay winner bằng kết quả test tốt hơn ở một metric.

## Thông điệp dùng trong report

“Hệ thống hoàn tất xử lý full graph cho hai dataset, kết hợp đặc trưng đồ thị vào mô hình giao dịch và đánh giá theo thời gian. Hiệu quả thể hiện qua PR/AP, confusion matrix, review budget và ablation riêng từng dataset; lợi ích phụ thuộc cấu trúc dữ liệu và trade-off cảnh báo.”

IBM có cycle witness thật; PaySim không có cycle trong dữ liệu full đã xử lý và relay không bao phủ positive test. Motif là một nhóm bằng chứng cấu trúc; classifier sử dụng cả các đặc trưng khác. Không suy diễn một transaction fraud đồng nghĩa mọi cạnh witness hay community đều fraud.

Nguồn số chính: [dataset_overview.csv](tables/dataset_overview.csv), [18 test models](tables/all_18_test_models.csv), [baseline vs selected](tables/baseline_vs_validation_selected.csv).