# Comment review IBM ETL — N4 Khánh, Part B Task 1

Phạm vi phân công: review ETL của N2 theo `BDA - PCCV - Trang tính1.csv` (mốc 28/09/2026), tập **HI-Small**. Review thực hiện ngày 29/09/2026 trên `src/ibm_aml/etl.py`, hai CSV gốc và Parquet full. Phần xử lý comment ở mốc fix 29/09 được ghi ở cuối tài liệu.

> **Hướng dẫn đọc:** Phần “Kết quả review trước khi sửa” mô tả mã ở thời điểm Khánh kiểm tra. Phần “Fix IBM ETL” mô tả mã **hiện tại** sau commit `30e66f2`. Ba comment review bên dưới đã được xử lý; chúng không phải ba lỗi còn bỏ ngỏ.

## Bắt đầu từ đâu: ETL, đỉnh và cạnh là gì?

**ETL** là bước đọc dữ liệu gốc, chuyển sang dạng dự án cần dùng, rồi lưu kết quả. IBM HI-Small có hai CSV dùng để xây đồ thị:

| File đầu vào | Nội dung | Kết quả sau ETL |
|---|---|---|
| `HI-Small_accounts.csv` | Danh sách tài khoản, ngân hàng và loại pháp nhân | Bảng **vertices**: mỗi tài khoản là một **đỉnh** |
| `HI-Small_Trans.csv` | Danh sách giao dịch, tài khoản gửi và tài khoản nhận | Bảng **edges**: mỗi giao dịch là một **cạnh có hướng** từ người gửi đến người nhận |

Ví dụ minh họa: tài khoản `A` ở ngân hàng `001` gửi tiền cho tài khoản `B` ở ngân hàng `002`. ETL tạo hai ID đỉnh `1_A` và `2_B`, rồi tạo cạnh có `src = 1_A`, `dst = 2_B`. `src` là tài khoản gửi; `dst` là tài khoản nhận. Bank ID được bỏ số 0 đứng đầu trước khi ghép ID, nên `001` và `1` cùng thành `1`. **Quy tắc chuẩn hóa Bank ID đã tồn tại trước đợt sửa 29/09**; đợt sửa giữ nguyên quy tắc đó. Cần ghép cả ngân hàng và tài khoản vì hai ngân hàng có thể dùng cùng một mã tài khoản.

Kết quả được lưu thành **Parquet** ở `data/processed/ibm_aml/vertices.parquet` và `edges.parquet`; Spark đọc các bảng này ở bước sau. Dự án còn có bản **sample** nhỏ hơn ở `data/processed/sample/ibm_aml/` để thử nghiệm nhanh.

### Ba thuật ngữ xuất hiện trong báo cáo

| Thuật ngữ | Nghĩa dễ hiểu | Ví dụ lỗi |
|---|---|---|
| **Schema** | Danh sách tên cột và kiểu dữ liệu của bảng | Tài liệu yêu cầu cột `timestamp`, nhưng bảng không có cột đó |
| **Null** | Giá trị bị thiếu, hoặc Spark không đọc/ép kiểu được | `Timestamp` ghi sai định dạng nên thời gian sau ETL thành `null` |
| **Dangling edge** | Cạnh nhắc tới một tài khoản không có trong bảng đỉnh | Giao dịch `A → B` nhưng bảng tài khoản không có `B` |

**Fallback vertex** là đỉnh tạm mang nhãn `External/Unknown` mà ETL có thể tạo khi không tìm thấy tài khoản thật. Chỉ thấy “0 dangling” chưa đủ: đỉnh tạm có thể làm cạnh hết treo, trong khi dữ liệu tài khoản vẫn thiếu. Vì vậy kết quả tốt phải có **cả 0 dangling lẫn 0 fallback**.

## Ba thay đổi, giải thích bằng ví dụ

### 1. Thêm cột để bảng kết quả khớp tài liệu

`BIG_Data_Group6.md` mục 9.2 là **schema contract**: những cột mà người viết bước tiếp theo được phép trông đợi. Trước khi sửa, ETL xuất tên cột chung của GraphGuard (`step`, `type`, `isFraud`...), nhưng chưa có đủ tên cột IBM mà contract yêu cầu (`timestamp`, `payment_format`, `isLaundering`...). Dữ liệu không mất, nhưng người khác làm theo tài liệu có thể gặp lỗi “không tìm thấy cột”.

Đợt sửa **thêm cột mới và giữ cột cũ** để mã GraphGuard đang dùng vẫn đọc được. Đây là hai tên cho cùng thông tin, không phải hai giao dịch khác nhau:

| Cột được thêm theo contract | Cột cũ được giữ | Cùng biểu diễn điều gì? |
|---|---|---|
| `vertices.bank_id` | Phần ngân hàng trong `vertices.id` | Mã ngân hàng đã chuẩn hóa |
| `edges.timestamp` | `edges.step` | Cùng thời điểm giao dịch; `timestamp` là kiểu thời gian, `step` là số giây Unix |
| `edges.currency` | `edges.payment_currency` | Loại tiền của `amount` |
| `edges.payment_format` | `edges.type` | Kênh thanh toán, ví dụ `Wire` |
| `edges.isLaundering` | `edges.isFraud` | Nhãn 0/1 từ `Is Laundering` của CSV |

Ví dụ, một dòng CSV có `Payment Format = Wire` thì cạnh sau ETL có **cả** `type = Wire` và `payment_format = Wire`. Test còn đối chiếu hai cột để chắc chúng bằng nhau. `amount` vẫn là `Amount Paid` theo tiền gốc; khi so sánh số tiền, cần xem `payment_currency`/`currency`. Mã nằm trong [`build_ibm_edges`](../src/ibm_aml/etl.py) và [`build_ibm_vertices`](../src/ibm_aml/etl.py).

### 2. Kiểm tra tên và thứ tự cột của CSV trước khi đọc

CSV giao dịch có **hai cột cùng tên `Account`**: cột thứ nhất là tài khoản gửi, cột thứ hai là tài khoản nhận. Spark đọc chúng theo **vị trí**; trong mã, cột thứ hai được gọi nội bộ là `Account_Dest`. Nếu file nguồn đổi vị trí cột mà ETL vẫn dùng sơ đồ cũ, cạnh có thể gắn nhầm `src` hoặc `dst`, dù tổng số dòng vẫn đúng.

Đợt sửa thêm `validate_csv_header`: hàm đọc dòng tiêu đề và so sánh **toàn bộ 11 tên cột theo đúng thứ tự** của file giao dịch, cũng như 5 tên cột của file tài khoản. Nếu thiếu, thêm, đổi tên hoặc đổi thứ tự cột, ETL báo `ValueError` trước khi xây đồ thị. Test cố đổi tên cột `Account` thứ hai và xác nhận ETL từ chối file đó. Xem [hàm kiểm tra header](../src/ibm_aml/etl.py) và [test CSV lỗi](../tests/test_ibm_aml_etl_guardrails.py).

### 3. Phát hiện dữ liệu thiếu trước khi xuất Parquet

**Khóa tài khoản cần đủ hai phần.** Cách ghép `concat_ws` cũ có thể bỏ qua một thành phần `null`: thiếu mã ngân hàng mà vẫn tạo được một chuỗi từ mã tài khoản còn lại. Nay dùng `concat`; nếu ngân hàng hoặc tài khoản thiếu, ID kết quả thành `null` để bước kiểm tra phát hiện.

**Kiểm tra tất cả cột.** Quality gate trước đây chỉ kiểm tra null ở một số cột như `id`, `src`, `dst`, `amount`. Ví dụ thời gian sai vẫn có thể tạo `step = null` mà không bị kiểm tra đó bắt. Nay ETL đếm `null` và chuỗi rỗng ở **mọi cột đầu ra**, kể cả thời gian, tiền tệ, số tiền nhận, nhãn và tên ngân hàng.

**Kiểm tra cả quan hệ giữa hai bảng.** ETL yêu cầu 0 ID sai dạng `bank_account`, 0 fallback, 0 dangling ở cả `src` và `dst`, số cạnh bằng số dòng giao dịch gốc và số đỉnh duy nhất bằng số dòng tài khoản gốc. Các điều kiện này chạy **trước khi ghi Parquet**; điều kiện quan trọng nào FAIL thì ETL dừng. Test tạo CSV nhỏ với ngân hàng trống, thời gian sai, số tiền nhận sai và nhãn sai để xác nhận các lỗi được nhìn thấy. Xem [quality gate](../src/ibm_aml/etl.py) và [test dữ liệu lỗi](../tests/test_ibm_aml_etl_guardrails.py).

**Vì sao trước và sau đều ghi “0 null”?** CSV HI-Small được kiểm tra vốn sạch, nên số lỗi đo được đều bằng 0. Giá trị của đợt sửa nằm ở **cách ETL xử lý trường hợp CSV tương lai bị lỗi**: nó sẽ nhận ra và dừng trước khi xuất Parquet. Phần số liệu lịch sử bên dưới nhắc **4 cột đỉnh và 9 cột cạnh**; sau khi thêm cột theo contract, bảng hiện tại có **5 cột đỉnh và 13 cột cạnh**. Đây là thay đổi schema, không phải số dòng dữ liệu tăng.

## Kết quả review trước khi sửa (để đối chiếu lịch sử)

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

## Comment Khánh đã đưa cho N2 tại thời điểm review

1. **Schema contract chưa thống nhất.** `BIG_Data_Group6.md` mục 9.2 yêu cầu vertices có `bank_id`, edges có `timestamp:timestamp`, `payment_format`, `currency`, `isLaundering`. ETL hiện xuất `step:int`, `type`, `payment_currency`, `isFraud` và không xuất `bank_id`. Mục 7.3 của cùng tài liệu chỉ là bảng ánh xạ dự kiến; các module GraphGuard hiện dùng schema thực tế. N2 cùng N1 cần chốt một contract rồi sửa ETL hoặc cập nhật đặc tả 9.2 và nơi tiêu thụ liên quan. Không nên ghi “schema conformant” so với mục 9.2 ở trạng thái hiện tại.
2. **Khóa bảo vệ header còn thiếu.** Raw transactions có hai header cùng tên `Account`. `etl.py` đổi cột thứ hai thành `Account_Dest` bằng schema vị trí và dùng `enforceSchema` mặc định. File hiện tại có đúng header/thứ tự nên ánh xạ đúng, nhưng nếu nguồn đổi thứ tự hay thêm cột, Spark có thể gán sai dữ liệu theo vị trí. N2 nên kiểm tra chính xác header 11 cột trước `spark.read.csv(...)` và fail sớm khi khác.
3. **Nên đưa kiểm tra đầy đủ vào gate ETL.** Suite hiện kiểm tra null `id`, `src`, `dst`, `account_type`, `amount`; `etl.py` chỉ chặn một phần và `0 dangling` có thể được fallback vertex che đi. Lần review này đã xác nhận độc lập `0` fallback và `0` null ở mọi cột cho bản HI-Small, nhưng ETL nên fail khi có null ở các cột bắt buộc còn lại (`step`, `isFraud`, currencies, `amount_received`, `type`, `bank_name`) hoặc fallback bất ngờ. Đặc biệt, `concat_ws` có thể bỏ qua thành phần null, nên `src`/`dst` không null tự nó chưa chứng minh khóa hợp lệ.

**Kết luận tại thời điểm review:** integrity của dữ liệu HI-Small hiện tại **PASS** (`0 dangling`, `0 null` sau ETL). Phần schema cần chốt contract và bổ sung kiểm tra header. Các điểm này đã được xử lý ở mục dưới.

## Fix IBM ETL theo comment N4 — 29/09/2026 (trạng thái hiện tại)

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
