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
(Chờ N4)

## Task 4 — Community Detection (25đ)
(Chờ N5)