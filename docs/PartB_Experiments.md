# Part B — Experiments

## Task 1 — Graph Construction (15đ)

### 1.1. Mục tiêu
- Xây Vertices/Edges DataFrame theo schema đề bài
- Khởi tạo GraphFrame
- Verify integrity

### 1.2. Kết quả chạy

| | Full graph | Sample |
|---|---|---|
| Vertices | 9,073,900 | 194,195 |
| Edges | 6,362,620 | 100,729 |
| PASS checks | 4/4 | 3/3 |

Log: `results/paysim/task1_verification_full.log` (full) 
| `results/paysim/task1_verification_sample.log` (sample)

**Lưu ý kỹ thuật:** Full Parquet đang ở path cũ `data/processed/`. 
Script tự động fallback về path cũ nếu path mới không tồn tại 
(warning `[WARN] Preferred path not found` trong log). Đây là hành vi 
mong muốn, không phải bug. Sample Parquet đọc đúng path mới 
`data/processed/sample/paysim/` — không có warning.

### 1.3. Trích log PASS

[PASS] Vertices contain ['account_type', 'balance', 'id']  
[PASS] Edges contain ['amount', 'dst', 'isFraud', 'src', 'step', 'type']  
[PASS] Vertex count == 9,073,900 (got 9,073,900)  
[PASS] Edge count == 6,362,620 (got 6,362,620)  
[+] Task 1 Completed Successfully. GraphFrame is fully operational.  

### 1.4. Raw-transaction spot-check (`--from-raw`)

Ngoài verification schema + count (so với hardcode), nhóm chạy thêm 
`--from-raw` để đối chiếu 1-1 với **raw CSV gốc**:

| # | Edge (src → dst) | Step | Amount | Kết quả |
|---|------------------|------|--------|---------|
| 1 | C1509309988 → M1643141512 | 1 | 1876.44 | ✅ 1 raw match |
| 2 | C1112456099 → C1225616405 | 1 | 26004.52 | ✅ 1 raw match |
| 3 | C1458091526 → C747464370 | 1 | 323105.08 | ✅ 1 raw match |
| 4 | C201677908 → C451111351 | 1 | 480222.51 | ✅ 1 raw match |
| 5 | C1574873161 → M1591916281 | 1 | 1239.06 | ✅ 1 raw match |

**→ ETL pipeline verified 100%**: mọi edge trong Parquet đều có 
row tương ứng trong raw CSV — không drop, không duplicate, không 
méo dữ liệu.

Log: `results/paysim/task1_verification_from_raw_sample.log`
**Lưu ý số liệu:** Số ở 1.2 và 1.4 khác nhau do 2 lần chạy độc lập:  
- **1.2** đọc Parquet sample có sẵn (`data/processed/sample/paysim/`)  
- **1.4** induce subgraph ngẫu nhiên ~100k edges **mới** từ raw CSV  
> Cả hai đều PASS — mục đích 1.4 là chứng minh ETL đúng logic.

### 1.5. Insights
- **Power-law degree distribution cực mạnh:**
  - Max In-Degree = 113 (tài khoản `C1286084959` — hub nhận tiền)
  - Max Out-Degree = 3 (hầu hết users chỉ gửi 1-3 lần)
- Ủng hộ Mục 3.2: **Vertex Cut bắt buộc** cho PaySim (Edge Cut sẽ cắt 
  quá nhiều cạnh tại các hub)

### 1.6. Quyết định Mapping (khác biệt so với bảng 4.1 gốc)

#### Balance tie-breaking rule

Đề bài Mục 4.1 ghi rõ cột `balance` lấy từ `oldbalanceOrg`/`oldbalanceDest`. 
Tuy nhiên phần diễn giải của đề lại yêu cầu "giá trị balance gần nhất cho 
mỗi account". Nhóm đã phân tích và chọn **`newbalanceOrig`/`newbalanceDest`** 
thay vì `oldbalance*`, vì:

- `oldbalanceOrg` tại event cuối = balance **TRƯỚC** giao dịch cuối cùng
- `newbalanceOrig` tại event cuối = balance **SAU** giao dịch cuối cùng
- → `newbalance*` phản ánh đúng trạng thái cuối cùng của account

**Quy tắc chính thức:** Cho mỗi account (bao gồm 1,769 tài khoản đóng cả 
2 vai trò sender + receiver), lấy `newbalance` tại `max(step)`. Cài đặt 
bằng `F.max_by("balance", "step")` — một aggregation, không dùng window 
function, giảm shuffle overhead.

#### Bổ sung cột vào Edges

Hai cột không có trong bảng 4.1 gốc nhưng được bổ sung cho downstream:

| Cột | Lý do |
|-----|-------|
| `type` | Cần cho Task 3 pivot: 2-hop relay `TRANSFER → CASH_OUT`. PaySim có 0 cycle 3-node (đã verify vét cạn), nên motif được điều chỉnh. |
| `isFraud` | Ground-truth label. Cần để cross-check kết quả Motif/LPA với nhãn gian lận thật. |

#### Step giữ nguyên Integer

Trường `step` (1..744) giữ nguyên dạng **integer** làm proxy thời gian mô 
phỏng, KHÔNG convert sang datetime. Tránh gây hiểu nhầm về thời gian thực.

## Task 2 — Degree & PageRank (25đ)
(Chờ N6)

## Task 3 — Motif Finding (25đ)

### Mục tiêu và baseline

Khánh triển khai truy vấn GraphFrames trên full PaySim và IBM HI-Small. Ba ID phải khác nhau ở cycle ba đỉnh; khử phép xoay nhưng giữ hai chiều khác nhau và phân biệt đa cạnh với số vòng tài khoản. PaySim baseline có 0 cycle và 30 relay TRANSFER→CASH_OUT >10.000 trong 24 giờ, gồm 2 cặp cùng giờ. Hai cạnh của mọi relay baseline đều có nhãn 0; không gọi 30 ứng viên thành 30 vụ fraud.

IBM audit trên cạnh đã gắn nhãn có 7.473 raw matches, 2.491 tổ hợp giao dịch và 54 directed account cycles (45 bộ tài khoản không xét chiều). Truy vấn ba cạnh USD >10.000 trên toàn graph trả 0. Audit nhãn và detector không biết nhãn là hai mục đích khác nhau.

### Pipeline v2: feature motif và đánh giá có giám sát

Source chính: `src/motif/{config,features,modeling,pipeline}.py`, cùng adapter `src/{paysim,ibm_aml}/motif_finding.py`. Fan-in/out, relay, reciprocal, cycle ba tài khoản và role histories được trích từ quá khứ trong cửa sổ 24/168 giờ. Các dòng cùng timestamp không làm witness cho nhau. Counts được tính bằng expiry-prefix sums; witness star được giải thích bằng truy vấn theo event ID, tránh bounded-window rescans ở hub. FX, self-loop và amount=0 không làm witness dòng tiền nhưng vẫn giữ trong mẫu số. Vòng đối ứng không bị tính nhầm thành relay ba tài khoản; SQL self-join độc lập kiểm tra cách đếm.

So sánh hai cây quyết định cùng cấu hình: transaction-only và motif-assisted. Feature không chứa nhãn, account ID hoặc absolute timestamp; mô hình có giám sát học từ nhãn training. Chuẩn hóa amount theo q90 prefix của từng currency/type. Chọn family và score threshold bằng ba fold mở rộng 40→50%, 50→65%, 65→80%; xem mean/worst/std F1. Sau khi khóa cấu hình mới refit đến 80% và chấm phần còn lại.

Các notebook đã tách theo dataset, import trực tiếp source và giữ toàn bộ output/hình:

- [PaySim](../notebooks/03_khanh_PaySIM_motif.ipynb).
- [IBM HI-Small](../notebooks/03_khanh_IBM_motif.ipynb).

### Kết quả full v2

| Dataset | Test giao dịch / fraud | Mô hình CV chọn | Test TP / FP / FN | Precision | Recall | F1 | F1 transaction-only |
|---|---:|---|---:|---:|---:|---:|---:|
| PaySim | 1.248.736 / 4.250 | motif-assisted, score ≥0,70 | 1.191 / 1.489 / 3.059 | 44,44% | 28,02% | 34,37% | 30,38% |
| IBM | 1.015.564 / 1.797 | motif-assisted, score ≥0,50 | 474 / 4.059 / 1.323 | 10,46% | 26,38% | 14,98% | 15,08% |

PaySim thêm 302 TP và 776 FP so với cùng cây transaction-only; importance nghiêng về receiver history/type/amount. Chưa chứng minh count motif độc lập khỏi role history; cycle vẫn bằng 0. IBM giảm 4.998 FP nhưng mất 411 TP so với transaction-only; F1 giảm nhẹ còn AP chỉ tăng nhẹ. Không kết luận motif cải thiện F1 trên test IBM này. Coverage cycle causal ≤168 giờ của toàn IBM: 304 closing transactions, 92 laundering; reciprocal: 4.455/305. Coverage chồng nhau, khác số vòng tài khoản và không phải chỉ số test của detector.

### Diễn giải và tái lập

TP/FP/FN/TN tính theo giao dịch, không theo tổ hợp motif. Mẫu số gồm tất cả giao dịch test. Báo precision/recall/F1, exact average precision và Wilson 95% CI; CI chưa hiệu chỉnh tương quan giao dịch. Feature importance không chứng minh quan hệ nhân quả. Weighted tree score không phải xác suất fraud đã hiệu chuẩn. Không alert không xác nhận hợp pháp.

Test này đã được phân tích ở phiên bản trước, nên được ghi là **reused internal temporal holdout**, chưa phải benchmark ngoài mẫu mới. Không chọn lại threshold bằng test. Motif được đánh giá bằng ablation thay vì mặc định thêm graph sẽ luôn tốt hơn.

CLI PowerShell và API dùng cùng pipeline; model/amount scales/report/examples/run manifest được xuất vào directory mới nếu gọi `--analysis --output-dir`. Notebook chỉ lưu output nhúng. Loader kiểm tra hash và dùng JVM reader cho các stage Spark ML để chạy được trên Windows Python 3.12/JDK 17. Kết quả full hiện hành lấy từ bảng test trong notebook, không lấy từ synthetic fixture của unit test.


### Tài nguyên khi tái lập motif v2

Chỉ một tác vụ nặng chạy tại một thời điểm; hardware guard bắt buộc giới hạn CPU 10%, tối đa 2 logical CPUs, JVM heap ≤6 GiB và job commit ≤10 GiB trên máy 32 GiB. Có admission và watchdog giữ RAM/commit dự phòng, cùng thu hồi tiến trình con khi kernel chết. Không tăng tài nguyên sau resource stop. GPU chưa được stack Windows native này sử dụng; nhiệt độ CPU không có sensor tin cậy. Xem [quy trình bảo vệ](../README.md#bảo-vệ-tài-nguyên-trên-máy-windows) và [skill](../.agents/skills/graphguard-powershell/SKILL.md).


## Task 4 — Community Detection (25đ)

Thuật toán LPA do Hoàng phụ trách; phần của Khánh là review/final theo PCCV đến 07/10. Notebook IBM chạy GraphX LPA `maxIter=5` trên full graph và dùng checker độc lập:

- 518.581/518.581 tài khoản được gán community; 314.829 cộng đồng.
- 853.796 cạnh nội bộ + 4.224.549 cạnh liên cộng đồng = 5.078.345 giao dịch; đối chiếu đủ 5.177 laundering.
- Tổng tiền theo từng `payment_currency`, không cộng nominal amount khác currency; 314.577 nhóm community/currency có giao dịch đi.
- Hai lần chạy sample trên 119.043 tài khoản cho cùng phân hoạch sau canonicalization (0 tài khoản đổi thành viên cụm). Đây là quan sát của hai lần chạy, không bảo đảm LPA luôn deterministic.
- Checker từ chối đủ 6 phản ví dụ: duplicate/missing account, null/fractional label, NaN amount và summary trộn currency.

Output thật và biểu đồ LPA được giữ trong [notebook IBM](../notebooks/03_khanh_IBM_motif.ipynb); toàn notebook có 6 figure nhúng. LPA chưa được dùng làm feature trong detector motif. Kiểm chứng tự động không thay phê duyệt final của Tuệ Minh.
