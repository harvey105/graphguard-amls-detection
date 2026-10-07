# Bàn giao report: Degree distribution — PaySim và IBM AML

Ngày tạo và kiểm tra: **07/10/2026**. Phạm vi: **graph sample**, không phải full dataset.

## 1. File sử dụng

- [Biểu đồ PNG](../results/comparison/degree_distribution_paysim_vs_ibm.png): 3600 × 2100 pixels, 300 DPI; dùng trực tiếp trong report.
- [Dữ liệu CSV](../results/comparison/degree_distribution_paysim_vs_ibm.csv): bảng tần suất đầy đủ của các degree quan sát được.
- [Code tạo kết quả](../src/comparison/degree_distribution.py): module so sánh riêng cho hai dataset.

CSV có bốn cột:

| Cột | Ý nghĩa |
|---|---|
| `dataset` | PaySim hoặc IBM AML |
| `degree` | Total degree = in-degree + out-degree |
| `account_count` | Số account có đúng degree đó |
| `proportion` | `account_count / N`, với N là toàn bộ vertices của dataset tương ứng; giá trị từ 0 đến 1 |

Trên chart, `proportion` được hiển thị dưới dạng phần trăm. Ví dụ `0.01` trong CSV là **1%**, không phải 0.01%. Đây là phân phối tần suất tại từng degree (PMF), không phải phân phối tích lũy hay đường fit.

## 2. Nguồn và phương pháp

- Input PaySim: `data/processed/sample/paysim/vertices.parquet` và `edges.parquet`.
- Input IBM AML: `data/processed/sample/ibm_aml/vertices.parquet` và `edges.parquet`.
- Dùng `GraphFrame.degrees`, group theo degree và đếm account bằng Spark; chỉ chuyển bảng tổng hợp về pandas để xuất/vẽ.
- Giữ nguyên tất cả giao dịch trong sample; không lọc `isFraud` hoặc `isLaundering`.
- Cạnh song song được giữ nguyên. Mỗi self-loop đóng góp 1 vào in-degree và 1 vào out-degree, tức 2 vào total degree. Degree không phải số đối tác duy nhất.
- `graph.degrees` không chứa đỉnh cô lập. Lần chạy này xác nhận **0 đỉnh cô lập** ở cả hai sample. Nếu input sau này có đỉnh cô lập, CSV bổ sung degree 0; chart log không vẽ degree 0 nhưng mẫu số vẫn là toàn bộ vertices.
- Degree không xuất hiện không có dòng trong CSV và không có điểm trên chart. Không nối các điểm để tránh ngụ ý có dữ liệu ở các degree không quan sát được.

## 3. Số liệu cho report

| Chỉ tiêu trên sample | PaySim | IBM AML |
|---|---:|---:|
| Vertices | 194.195 | 119.043 |
| Edges | 100.729 | 99.869 |
| Account có degree 1 | 187.755 | 71.835 |
| Tỷ lệ account có degree 1 | 96,68% | 60,34% |
| Max total degree | 6 | 3.327 |
| Đỉnh cô lập | 0 | 0 |

IBM có 15 mức degree trên 11, mỗi mức có đúng 1 account; vì vậy các điểm này cùng nằm ở mức `1 / 119043`, tương đương khoảng **0,000840%**. Dãy điểm nằm ngang ở đáy không có nghĩa là nhiều account có cùng degree. PaySim có 2 account ở degree 6.

## 4. Caption đề xuất

> **Phân phối total degree trên graph sample PaySim và IBM AML.** Trục X là total degree (in-degree + out-degree); trục Y là tỷ lệ account có đúng degree đó trong từng sample. Hai trục dùng log scale để hiển thị đồng thời các nhóm phổ biến và nhóm hiếm; giá trị degree và tần suất không bị biến đổi. Mỗi giao dịch được tính là một cạnh; cạnh song song và self-loop được giữ nguyên. Biểu đồ mô tả dữ liệu quan sát được, không phải phép kiểm định power-law.

## 5. Đoạn nhận xét có thể đưa vào report

> Trên hai graph sample, PaySim tập trung mạnh ở degree 1, chiếm 96,68% account, so với 60,34% ở IBM AML. PaySim có total degree lớn nhất bằng 6; IBM AML có phạm vi rộng hơn, tới 3.327, với một số ít account có degree lớn. So sánh tỷ lệ account thay cho số đếm tuyệt đối giúp đối chiếu hai sample có số vertices khác nhau. Kết quả cho thấy sự khác biệt về phân phối degree trên các sample quan sát được; chưa đủ cơ sở để khái quát cho toàn bộ dataset hoặc kết luận phân phối tuân power-law.

## 6. Giới hạn cần giữ khi viết

- Theo code tạo sample hiện tại, PaySim lấy mẫu cạnh ngẫu nhiên với seed 42; IBM chọn riêng 89 cạnh có nhãn gian lận và lấy mẫu ngẫu nhiên phần cạnh còn lại với seed 42. Cả hai lấy các vertices liên quan đến cạnh được chọn. Đây là hai cách lấy mẫu khác nhau; chuẩn hóa thành tỷ lệ không loại bỏ ảnh hưởng của sampling.
- Không trộn max in-degree của full graph với max total degree của sample. Bảng trên chỉ so sánh **total degree của sample**.
- Log–log chỉ là cách hiển thị. Chưa thực hiện statistical fitting hay goodness-of-fit test: không khẳng định power-law, scale-free hoặc một dạng phân phối cụ thể.
- Degree lớn không chứng minh gian lận/rửa tiền; cũng không chứng minh dataset nào phát hiện fraud tốt hơn.

## 7. Chạy lại và kiểm tra

Từ thư mục gốc repo, chạy trong PowerShell, không cần activate `.venv`:

```powershell
& .\.venv\Scripts\python.exe -m src.comparison.degree_distribution
```

Lệnh đọc lại hai Parquet sample, ghi đè PNG và CSV so sánh. Không chạy ETL hoặc PageRank. File ghi chú này là bản bàn giao của lần chạy 07/10/2026; nếu thay input, cần cập nhật bảng và nhận xét theo CSV mới.

Đã kiểm tra:

- Tổng `account_count` khớp số vertices của mỗi sample.
- Tổng `proportion` bằng 1; từng tỷ lệ bằng `account_count / N`.
- Tổng `degree × account_count` bằng `2 × số edges`.
- Degree trong CSV không trùng và tăng dần trong mỗi dataset; PNG mở được và đã xem trực tiếp.
- Native Windows Python 3.11.9, JDK 17; `pip check` không báo dependency hỏng. Chưa xác minh bằng Python 3.12 theo chuẩn repo.
- Lệnh kết thúc mã 0. Spark còn cảnh báo không xóa được JAR trong thư mục tạm khi dừng; không ngăn xuất output.
