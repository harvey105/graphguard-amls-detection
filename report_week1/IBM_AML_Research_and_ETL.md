# IBM AML HI-Small — nghiên cứu schema và thiết kế ETL tuần 1

## Nguồn và phạm vi

IBM AML-Data là dữ liệu giao dịch tổng hợp tạo bởi virtual world gồm bank,
individual và company; đây không phải dữ liệu cá nhân thật được anonymize. Mỗi
transaction có laundering label. Paper NeurIPS 2023 mô tả generator và cách
dùng benchmark cho graph learning. Code repository dùng Apache-2.0, nhưng chính
dataset dùng CDLA-Sharing-1.0 nên raw CSV không được commit vào repo.

- [IBM Research — Realistic Synthetic Financial Transactions for AML](https://research.ibm.com/publications/realistic-synthetic-financial-transactions-for-anti-money-laundering-models)
- [IBM AML-Data repository](https://github.com/IBM/AML-Data)

## Header thực tế và quyết định mapping

Header của file local:

```text
Timestamp,From Bank,Account,To Bank,Account,Amount Received,
Receiving Currency,Amount Paid,Payment Currency,Payment Format,Is Laundering
```

Hai cột đều mang tên `Account`; `Account.1` là tên mà pandas thường tự tạo sau
khi đọc header trùng, không phải tên literal trong CSV. `src` và `dst` vì vậy
được map theo **vị trí schema tường minh**, không lookup header mơ hồ.

| Raw | Graph output | Quy tắc |
|---|---|---|
| `From Bank` + Account thứ nhất | `src` | `trim(bank)::trim(account)` |
| `To Bank` + Account thứ hai | `dst` | `trim(bank)::trim(account)` |
| `Timestamp` | `timestamp` | parse `yyyy/MM/dd HH:mm` |
| `Amount Received` | `amount`, `amount_received` | nhận-side canonical amount |
| `Receiving Currency` | `currency`, `receiving_currency` | currency của `amount` |
| `Amount Paid`, `Payment Currency` | giữ nguyên | không quy đổi FX ngầm |
| `Payment Format` | `payment_format` | edge attribute |
| `Is Laundering` | `isLaundering:short` | edge ground-truth label |

Vertex contract: `id`, `bank_id`, `account_id`. Bank bắt buộc nằm trong ID để
hai account string giống nhau ở hai bank không bị nhập nhầm thành một vertex.

## Chạy và kiểm chứng

```powershell
& .\.venv\Scripts\python.exe -m src.ibm_aml.etl
```

Pipeline chỉ ghi Parquet sau khi toàn bộ check pass: raw count, edge count bằng
raw, vertex ID unique/non-null, edge field bắt buộc non-null, zero dangling src
và zero dangling dst. Sau khi ghi, pipeline đọc lại hai Parquet và so count.

Kết quả máy chạy nằm ở `ibm_aml_etl_manifest.json` và
`ibm_aml_etl_run.log` trong cùng thư mục này.
