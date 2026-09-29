# Comment review IBM ETL — N4 Khánh, Part B Task 1

Phạm vi phân công: review ETL của N2 theo `BDA - PCCV - Trang tính1.csv` (mốc 28/09/2026), tập **HI-Small**. Review thực hiện ngày 29/09/2026 trên `src/ibm_aml/etl.py`, hai CSV gốc và Parquet full. Phần xử lý comment ở mốc fix 29/09 được ghi ở cuối tài liệu.

## Kết quả kiểm chứng

Chạy với Windows PowerShell, `.venv\Scripts\python.exe` **Python 3.12.10** và **JDK 17.0.20.1**; `pip check` báo không có dependency hỏng. Lệnh kiểm thử từ CSV gốc:

```powershell
& .\.venv\Scripts\python.exe .\tests\test_ibm_aml_etl.py --from-raw
```

Suite trả exit code 0 và tất cả kiểm tra PASS. Quét độc lập bằng Windows Python trên từng dòng CSV xác nhận header đúng thứ tự, mọi dòng transactions có 11 trường, mọi dòng accounts có 5 trường, không có ô trống trong cả hai file. Đọc Parquet full bằng Windows Spark và cộng null từng cột xác nhận **0 null ở cả 4 cột đỉnh và 9 cột cạnh**.

| Kiểm tra | Kết quả |
|---|---:|
| `HI-Small_Trans.csv` / cạnh tạo từ CSV | 5.078.345 / 5.078.345 |
| `HI-Small_accounts.csv` / đỉnh | 518.581 / 518.581 |
| Null `id`, `src`, `dst`; null ở các thuộc tính Parquet còn lại | 0 ở mọi cột |
| Cạnh treo phía `src` / `dst` | 0 / 0 |
| Đỉnh `External/Unknown` | 0 |
| Giao dịch `isFraud=1` | 5.177 |

Schema thực tế: vertices `id:string`, `account_type:string`, `bank_name:string`, `balance:double`; edges `src:string`, `dst:string`, `amount:double`, `amount_received:double`, `payment_currency:string`, `receiving_currency:string`, `step:int`, `type:string`, `isFraud:smallint`. Raw `From Bank` + `Account` thành `src`; `To Bank` + **cột `Account` thứ hai** thành `dst`; `Amount Paid` thành `amount`; `Amount Received` thành `amount_received`; `Timestamp` thành `step` (Unix epoch seconds); `Payment Format` thành `type`; `Is Laundering` thành `isFraud`. Bank ID được chuẩn hóa nhất quán trước khi ghép với account. Hai file gốc không có ô trống, và Parquet hiện tại cũng không có null sau ép kiểu.

## Comment cho N2 trước khi chốt IBM Task 1

1. **Schema contract chưa thống nhất.** `BIG_Data_Group6.md` mục 9.2 yêu cầu vertices có `bank_id`, edges có `timestamp:timestamp`, `payment_format`, `currency`, `isLaundering`. ETL hiện xuất `step:int`, `type`, `payment_currency`, `isFraud` và không xuất `bank_id`. Mục 7.3 của cùng tài liệu chỉ là bảng ánh xạ dự kiến; các module GraphGuard hiện dùng schema thực tế. N2 cùng N1 cần chốt một contract rồi sửa ETL hoặc cập nhật đặc tả 9.2 và nơi tiêu thụ liên quan. Không nên ghi “schema conformant” so với mục 9.2 ở trạng thái hiện tại.
2. **Khóa bảo vệ header còn thiếu.** Raw transactions có hai header cùng tên `Account`. `etl.py` đổi cột thứ hai thành `Account_Dest` bằng schema vị trí và dùng `enforceSchema` mặc định. File hiện tại có đúng header/thứ tự nên ánh xạ đúng, nhưng nếu nguồn đổi thứ tự hay thêm cột, Spark có thể gán sai dữ liệu theo vị trí. N2 nên kiểm tra chính xác header 11 cột trước `spark.read.csv(...)` và fail sớm khi khác.
3. **Nên đưa kiểm tra đầy đủ vào gate ETL.** Suite hiện kiểm tra null `id`, `src`, `dst`, `account_type`, `amount`; `etl.py` chỉ chặn một phần và `0 dangling` có thể được fallback vertex che đi. Lần review này đã xác nhận độc lập `0` fallback và `0` null ở mọi cột cho bản HI-Small, nhưng ETL nên fail khi có null ở các cột bắt buộc còn lại (`step`, `isFraud`, currencies, `amount_received`, `type`, `bank_name`) hoặc fallback bất ngờ. Đặc biệt, `concat_ws` có thể bỏ qua thành phần null, nên `src`/`dst` không null tự nó chưa chứng minh khóa hợp lệ.

**Kết luận tại thời điểm review:** integrity của dữ liệu HI-Small hiện tại **PASS** (`0 dangling`, `0 null` sau ETL). Phần schema cần chốt contract và bổ sung kiểm tra header. Các điểm này đã được xử lý ở mục dưới.

## Fix IBM ETL theo comment N4 — 29/09/2026

Đã chọn contract tại `BIG_Data_Group6.md` mục 9.2 và **bổ sung cột** vào schema xuất ra, đồng thời giữ các tên cột GraphGuard đang dùng để các module hiện hữu tiếp tục hoạt động:

| Nguồn / giá trị | Cột contract được thêm | Cột GraphGuard giữ lại |
|---|---|---|
| `Bank ID` đã chuẩn hóa | `vertices.bank_id:string` | `vertices.id` dạng `bank_id_account` |
| `Timestamp` | `edges.timestamp:timestamp` | `edges.step:int` (epoch seconds) |
| `Payment Currency` | `edges.currency:string` | `edges.payment_currency:string` |
| `Payment Format` | `edges.payment_format:string` | `edges.type:string` |
| `Is Laundering` | `edges.isLaundering:smallint` | `edges.isFraud:smallint` |

`src/ibm_aml/etl.py` nay kiểm tra **header đúng toàn bộ và đúng thứ tự** trước khi Spark đọc từng CSV. Giao dịch phải có cả hai cột tên `Account` tại đúng vị trí 3 và 5. Nếu header lệch, ETL báo `ValueError` trước khi xây đồ thị. ID nay dùng `concat` để thành `null` khi Bank ID hoặc Account thiếu; bước quality gate sẽ bắt lỗi này. Quality gate đếm null/chuỗi rỗng của **mọi cột** trong vertices và edges bằng phép tổng hợp, kiểm tra định dạng khóa đỉnh/cạnh, `0` fallback, `0` dangling, số cạnh bằng raw transactions và số đỉnh duy nhất bằng raw accounts trước khi ghi Parquet. `tests/test_ibm_aml_etl.py` kiểm tra thêm contract, kiểu dữ liệu, mọi cột bắt buộc và tính nhất quán các cột cùng nghĩa. `tests/test_ibm_aml_etl_guardrails.py` kiểm tra header sai và dữ liệu bị thiếu/sai kiểu trên CSV nhỏ.

### Kiểm chứng sau fix trên Windows

```powershell
& .\.venv\Scripts\python.exe -m pip check
& .\.venv\Scripts\python.exe .\tests\test_ibm_aml_etl_guardrails.py
& .\.venv\Scripts\python.exe -m src.ibm_aml.etl
& .\.venv\Scripts\python.exe .\tests\test_ibm_aml_etl.py
& .\.venv\Scripts\python.exe .\tests\test_ibm_aml_etl.py --sample
```

Đã chạy bằng Windows Python 3.12.10, JDK 17.0.20.1. `pip check` sạch; ba ca CSV lỗi PASS; ETL full trả exit code 0 và toàn bộ quality gate PASS. Cả suite trên Parquet full và sample đều PASS, gồm kiểm tra kiểu/schema contract và tính nhất quán các cột alias. Full graph có **518.581 đỉnh / 5.078.345 cạnh / 5.177 nhãn gian lận**, 0 null/blank ở cả 5 cột đỉnh và 13 cột cạnh, 0 fallback, 0 dangling hai phía và 0 ID sai định dạng. Parquet full sau fix chiếm khoảng **205,42 MiB**. Sample tái tạo có **119.043 đỉnh / 99.869 cạnh / 89 nhãn gian lận**, khoảng **5,22 MiB**. Spark trên máy hiện tại in cảnh báo lúc dọn thư mục tạm sau khi hoàn tất; các lệnh vẫn trả exit code 0.

**Trạng thái fix:** ba comment review đã được xử lý trong mã và kiểm chứng trên bộ HI-Small. Contract mới đã có trong Parquet full và sample tái tạo.
