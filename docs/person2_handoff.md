# TÀI LIỆU BÀN GIAO KỸ THUẬT: TASK 1 — DATA ENGINEERING & GRAPH CONSTRUCTION
* **Người thực hiện (Author):** Person 2 (Data Engineering Lead)
* **Người tiếp nhận (Target Audience):** Person 1 (Lead), Person 3, Person 4, Person 5, Person 6, Person 7
* **Trạng thái (Status):** Đã hoàn tất & Kiểm định 100% (Fully Verified & Certified)
* **Phạm vi hoàn thành (Deliverables):** `src/utils/etl_mapping.py`, `src/export_parquet.py`, `src/graph_analysis.py` (Đạt 15/15 điểm Task 1, PaySim), `src/ibm_aml/etl.py` (Bonus — IBM AML, đã sửa bug Bank ID).

---

## 1. HƯỚNG DẪN ĐỒNG BỘ MÃ NGUỒN VÀ DỮ LIỆU (REPOSITORY & DATA ONBOARDING)

Do Person 2 là người khởi tạo dự án và đẩy mã nguồn (push code) lên đầu tiên, các thành viên cần thực hiện chuẩn xác các bước sau để thiết lập môi trường cục bộ (local environment):

### 1.1. Sao chép mã nguồn (Clone Repository) & Cài đặt môi trường
```powershell
# 1. Clone repository về máy
git clone <URL_REPO_CUA_NHOM>
cd graphguard_amls_detection

# 2. Khởi tạo môi trường ảo Python (Virtual Environment)
python -m venv .venv

# 3. Kích hoạt môi trường (Windows PowerShell)
.\.venv\Scripts\Activate.ps1

# 4. Cài đặt các gói phụ thuộc bắt buộc (Dependencies)
pip install -r requirements.txt
```
*Yêu cầu môi trường:* Python $\ge 3.10$, Java JDK $\ge 8$ (khuyến nghị JDK 11 hoặc 17), `pyspark==3.5.1`, `graphframes-py==0.12.2`.

### 1.2. Cơ chế lưu trữ & Đồng bộ dữ liệu (Data Sync & Git Policy)
Để tuân thủ giới hạn dung lượng của GitHub và tối ưu hóa thời gian tải mã nguồn, cấu hình `.gitignore` đã phân tách dữ liệu thành 2 tầng:

| Thư mục / Tệp tin | Trạng thái Git | Dung lượng | Giải thích & Cách thức truy cập |
| :--- | :---: | :---: | :--- |
| `data/raw/` | **Bị loại trừ (Ignored)** | ~493.5 MB (PaySim) + ~500 MB (IBM AML) | Chứa file CSV gốc. Không đẩy lên GitHub. |
| `data/processed/*.parquet` (PaySim) | **Bị loại trừ (Ignored)** | ~273 MB | Đồ thị PaySim đầy đủ đã làm sạch. Không đẩy lên GitHub. |
| `data/processed/ibm_aml/*.parquet` | **Bị loại trừ (Ignored)** | ~192.3 MB | Đồ thị IBM AML đầy đủ đã làm sạch (đã sửa bug Bank ID). Không đẩy lên GitHub. |
| `data/processed/sample/` (cả 2 dataset) | **Được theo dõi (Tracked)** | ~6.5 MB (PaySim) + ~4.8 MB (IBM) | **ĐÃ CÓ SẴN TRÊN REPO.** Đồ thị mẫu thu nhỏ (~100k cạnh mỗi bộ) để lập trình thử nghiệm. |

#### Cách sở hữu Đồ thị Đầy đủ (`data/processed/*.parquet`):
Các thành viên có thể lựa chọn 1 trong 2 phương án:
* **Cách 1 (Tự sinh cục bộ - Khuyến nghị):** Sau khi kéo repo về, tải file CSV gốc từ Kaggle bỏ vào `data/raw/`, rồi chạy:
  ```powershell
  python src/export_parquet.py        # PaySim, ~90-120 giây
  python src/ibm_aml/etl.py            # IBM AML, ~60-90 giây
  ```
* **Cách 2 (Tải trực tiếp qua Google Drive):** Tải thư mục nén `processed.zip` do Person 2 cung cấp qua liên kết Google Drive chung của nhóm, giải nén trực tiếp vào thư mục `data/processed/`.

---

## 2. ĐẶC TẢ DỮ LIỆU ĐỒ THỊ ĐÃ XUẤT XƯỞNG — PAYSIM (GRAPH DATA SPECIFICATIONS)

Toàn bộ dữ liệu thô đã được chuyển đổi sang định dạng nén tối ưu **Parquet (Snappy compressed)**, đảm bảo toàn vẹn tham chiếu (Referential Integrity), không có cạnh treo (0 dangling edges), không có giá trị rỗng (0 null values).

### 2.1. Bảng cấu trúc Đỉnh: `vertices.parquet`
* **Đầy đủ (Full):** 9.073.900 đỉnh | **Bản mẫu (Sample):** 193.143 đỉnh

| Tên trường (Field) | Kiểu dữ liệu | Ý nghĩa nghiệp vụ | Ghi chú kỹ thuật |
| :--- | :---: | :--- | :--- |
| `id` | `String` | Định danh tài khoản duy nhất | Khóa chính đồ thị (Vertex ID). Khớp 1-1 giữa `nameOrig` và `nameDest`. |
| `account_type` | `String` | Phân loại thực thể | Gồm 2 nhóm: `Customer` (tiền tố C) và `Merchant` (tiền tố M). |
| `balance` | `Double` | Số dư tài khoản đã giải quyết | Đã áp dụng quy tắc số dư tại mốc thời gian mới nhất (xem Mục 4). |

### 2.2. Bảng cấu trúc Cạnh: `edges.parquet`
* **Đầy đủ (Full):** 6.362.620 cạnh (8.213 nhãn gian lận) | **Bản mẫu (Sample):** 100.111 cạnh (153 nhãn gian lận)

| Tên trường (Field) | Kiểu dữ liệu | Ý nghĩa nghiệp vụ | Ghi chú kỹ thuật |
| :--- | :---: | :--- | :--- |
| `src` | `String` | Tài khoản gửi (Originator) | Khóa ngoại trỏ về `vertices.id` (Source node). |
| `dst` | `String` | Tài khoản nhận (Recipient) | Khóa ngoại trỏ về `vertices.id` (Destination node). |
| `amount` | `Double` | Số tiền giao dịch | Dùng lọc ngưỡng giao dịch (Transaction threshold). |
| `step` | `Integer` | Đơn vị thời gian mô phỏng | $1 \dots 744$ (tương đương 30 ngày). **Không đổi sang datetime.** |
| `type` | `String` | Loại hình giao dịch | `CASH_OUT`, `PAYMENT`, `CASH_IN`, `TRANSFER`, `DEBIT`. |
| `isFraud` | `Short` | Nhãn gian lận mặt đất (Ground-truth) | `1`: Gian lận đã xác thực; `0`: Bình thường. |

---

## 3. MẪU MÃ NGUỒN TÁI SỬ DỤNG (REUSABLE CODE TEMPLATE) — PAYSIM

Tất cả các thành viên phụ trách các tác vụ downstream **không đọc file CSV thô nữa**, chỉ cần tái sử dụng khối mã nguồn chuẩn hóa sau đây trong các tệp tin được phân công tương ứng:

* `src/metrics.py` (Áp dụng cho **Person 3** — Task 2: PageRank & Degree Distribution)
* `src/motif_finding.py` (Áp dụng cho **Person 4** — Task 3: Motif Search)
* `src/community_detection.py` (Áp dụng cho **Person 5 & Person 6** — Task 4: LPA & Connected Components)
* `src/graph_analysis.py` (Áp dụng cho **Person 1** — Kiểm tra, đánh giá đồ thị tổng thể)

```python
"""
Mẫu nạp đồ thị GraphFrames chuẩn hóa dùng chung cho Task 2, Task 3, Task 4
"""
from pyspark.sql import SparkSession
from graphframes import GraphFrame

def get_graph_session(app_name: str) -> SparkSession:
    """Khởi tạo PySpark Session liên kết với Maven Package của GraphFrames"""
    return (
        SparkSession.builder
        .appName(app_name)
        .master("local[*]")
        .config("spark.driver.memory", "6g")
        .config("spark.driver.maxResultSize", "2g")
        .config("spark.sql.shuffle.partitions", "8")
        # Phối hợp package JVM chính thức cho Spark 3.5
        .config("spark.jars.packages", "io.graphframes:graphframes-spark3_2.12:0.12.2")
        .getOrCreate()
    )

# 1. Khởi tạo session
spark = get_graph_session("GraphGuard-Analytics")
spark.sparkContext.setLogLevel("WARN")

# 2. Đường dẫn dữ liệu (Dùng "data/processed/sample" khi dev/test, đổi sang "data/processed" khi chạy báo cáo)
DATA_DIR = "data/processed/sample"  # <-- Đổi thành "data/processed" cho Full Graph

# 3. Tải đồ thị (Thời gian tải < 3 giây nhờ định dạng Parquet)
vertices_df = spark.read.parquet(f"{DATA_DIR}/vertices.parquet")
edges_df = spark.read.parquet(f"{DATA_DIR}/edges.parquet")

# 4. Khởi tạo đối tượng GraphFrame
graph = GraphFrame(vertices_df, edges_df)

# Sẵn sàng thực thi các thuật toán: graph.pageRank, graph.find, graph.labelPropagation
```

---

## 4. CẢI TIẾN KỸ THUẬT & XỬ LÝ ĐIỂM MƠ HỒ SO VỚI PLAN BAN ĐẦU — PAYSIM
*(Phần dành cho Person 1 & Person 7 đưa vào Báo cáo kỹ thuật — Technical Report Part A & B)*

Trong quá trình triển khai, Person 2 đã chủ động phát hiện và xử lý các điểm nghẽn kỹ thuật mà bản kế hoạch ban đầu (Proposal Mục 4.1) chưa định nghĩa rõ:

1. **Quy tắc giải quyết xung đột số dư (Balance Tie-Breaking Rule):**
   * *Vấn đề ban đầu:* Bản kế hoạch yêu cầu lấy số dư từ `oldbalanceOrg` hoặc `oldbalanceDest`, nhưng dữ liệu thực tế tồn tại **1.769 tài khoản đóng cả 2 vai trò** gửi và nhận tại nhiều mốc thời gian (`step`) khác nhau.
   * *Giải pháp của Person 2:* Thiết lập quy tắc chọn số dư sau giao dịch (`newbalance`) tại mốc thời gian lớn nhất (`max(step)`). Sử dụng hàm tổng hợp phân tán `F.max_by("balance", "step")`, giúp giảm thiểu chi phí xáo trộn phân vùng (Shuffle Overhead) so với kỹ thuật cửa sổ (Window Function).
2. **Bổ sung thuộc tính cạnh (Edge Attribute Enrichment):**
   * *Vấn đề ban đầu:* Schema đề xuất ở Mục 4.1 chỉ có `(src, dst, amount, timestamp)`.
   * *Cải tiến của Person 2:* Bổ sung trực tiếp `type` (loại giao dịch) và `isFraud` (nhãn thực tế) vào bảng `edges`. Điều này giúp Person 4 và Person 5 lọc motif và đối chiếu cộng đồng gian lận trực tiếp trên đồ thị mà không phải thực hiện các phép nối bảng (Join) tốn kém ngược lại CSV gốc.
3. **Hiện đại hóa hệ sinh thái GraphFrames (Dependency Modernization):**
   * *Vấn đề:* Bản đề cương cũ nhắc đến `graphframes` trên PyPI (vốn đã ngừng cập nhật từ 2018).
   * *Cải tiến của Person 2:* Nâng cấp lên thư viện chuẩn hiện hành `graphframes-py==0.12.2` đồng bộ với Maven Central `io.graphframes:graphframes-spark3_2.12:0.12.2`, ngăn ngừa lỗi không tương thích trên Spark 3.5.1.

---

## 5. CẢNH BÁO & YÊU CẦU HÀNH ĐỘNG THEO TỪNG TASK — PAYSIM

### 5.1. Dành cho Person 1 (Lead & Đồng phụ trách Task 1)
* Mã nguồn kiểm định chính thức cho **Task 1 (15 điểm)** nằm tại `src/graph_analysis.py`.
* Chạy lệnh `python src/graph_analysis.py` để lấy toàn bộ log kiểm chứng `[PASS]` đưa vào Báo cáo. Chạy thêm `python src/graph_analysis.py --from-raw --sample` để lấy kết quả kiểm tra chéo với dữ liệu gốc (Raw Spot-check).

### 5.2. Dành cho Person 3 (Task 2: Degree Distribution & PageRank)
* **Phân phối bậc lệch mạnh (Heavy Power-law Degree Distribution):**
  * Bậc vào tối đa (Max In-Degree): **113** (tập trung tại các tài khoản nhận tiền).
  * Bậc ra tối đa (Max Out-Degree): **3** (phần lớn người dùng chỉ gửi từ 1 đến 3 lần).
* **Ứng dụng vào báo cáo:** Đây là bằng chứng thực nghiệm quan trọng hỗ trợ phần lý thuyết **Vertex Cut vs Edge Cut (Mục 3.2)**: Việc cắt theo cạnh (Edge Cut) sẽ gây áp lực truyền thông mạng rất lớn tại các đỉnh gom tiền (Hubs). Vertex Cut là lựa chọn tối ưu bắt buộc.
* **Cảnh báo PageRank:** Các tài khoản có PageRank cao nhất chủ yếu là tài khoản gom tiền hợp pháp (hoặc tài khoản đại lý). Cần ghi chú rõ điều kiện hạn chế (Caveat Mục 3.3): *PageRank cao không đồng nghĩa với gian lận*.

### 5.3. Dành cho Person 4 (Task 3: Motif Finding) — CẢNH BÁO MỨC ĐỘ CAO
* **Hiện tượng thực tế:** Qua kiểm định vét cạn (Exhaustive verification) trên toàn bộ 6,36 triệu giao dịch, **PaySim có chính xác 0 chu trình 3 đỉnh khép kín ($A \to B \to C \to A$)**.
* **Nguyên nhân nghiệp vụ:** Mô hình sinh dữ liệu PaySim thiết kế hành vi gian lận là dòng tiền thoát khỏi hệ thống tài chính (System Exit):
  $$\text{Tài khoản bị hack} \xrightarrow{\text{TRANSFER}} \text{Tài khoản trung gian (Mule)} \xrightarrow{\text{CASH\_OUT}} \text{Đại lý tiền mặt}$$
* **Hành động bắt buộc:** Person 4 cần thảo luận ngay với Person 1 để chọn 1 trong 2 giải pháp:
  * *Giải pháp 1:* Điều chỉnh mẫu Motif sang dạng chuỗi chuyển tiếp 2 bước có thật (2-hop relay pattern): `(a)-[e1]->(b); (b)-[e2]->(c)` với điều kiện lọc `e1.type = 'TRANSFER' AND e2.type = 'CASH_OUT' AND e1.amount > 10000`.
  * *Giải pháp 2 (ĐÃ KÍCH HOẠT):* Chạy song song trên **IBM AML** — xem Mục 3.3 phần IBM ở dưới, dataset này thật sự có chu trình 3 đỉnh, nhưng cần đọc kỹ cảnh báo về ngưỡng lọc và multigraph trước khi báo cáo số liệu.

### 5.4. Dành cho Person 5 & Person 6 (Task 4: Community Detection / LPA)
* Dữ liệu chứa **1.769 tài khoản cầu nối (Bridge/Hub accounts)** (đóng vai trò cả gửi và nhận), tạo nên cấu trúc cụm kết nối chặt rất rõ rệt cho thuật toán Lan truyền nhãn (Label Propagation Algorithm - LPA).
* **Cảnh báo kỹ thuật chống sập bộ nhớ:** Thuật toán LPA tạo ra đồ thị phụ thuộc rất sâu (lineage chain dài) qua các vòng lặp. Các bạn **bắt buộc phải thiết lập thư mục kiểm tra (Checkpoint Directory)** trước khi chạy thuật toán:
  ```python
  spark.sparkContext.setCheckpointDir("checkpoints")
  communities = graph.labelPropagation(maxIter=5)
  ```
  Nếu thiếu lệnh này, Spark sẽ gặp lỗi tràn ngăn xếp (`java.lang.StackOverflowError`).

### 5.5. Lưu ý chung về trường thời gian (Simulation Timestamp)
* Cột `step` chỉ là **chỉ số giờ mô phỏng (Simulation-hour proxy)** từ 1 đến 744 (tương ứng chu kỳ 30 ngày), **hoàn toàn không phải mốc thời gian thực (Wall-clock datetime)**. 
* Tuyệt đối không tự ý chuyển đổi `step` thành datetime giả định để tránh làm biến dạng thứ tự logic thời gian trong phân tích chuỗi sự kiện.

---
# **IBM DATASET IMPLEMENTATION NOTES**

> **Dành cho:** Toàn bộ thành viên nhóm phụ trách **Task 2 (Người 3)**, **Task 3 (Người 4)**, và **Task 4 (Người 5 & 6)**.
> **Mục tiêu:** Tránh các lỗi ngầm (silent bugs) khi viết câu truy vấn thuật toán trên 2 bộ dữ liệu đồ thị phân tán.
> **⚠️ Phiên bản này thay thế hoàn toàn phiên bản trước** — phiên bản trước được viết dựa trên một ETL run có bug (xem Mục 0). Nếu bạn đã đọc phiên bản cũ, hãy đọc lại từ đầu, đặc biệt Mục 0 và Mục 3.3(B).

## **0. ⚠️ CRITICAL BUG FIX: Chuẩn hóa Bank ID — ĐỌC TRƯỚC KHI ĐỘNG VÀO CODE IBM AML**

### Triệu chứng
Lần chạy ETL đầu tiên báo cáo **1.033.669 đỉnh**, trong đó **515.088 đỉnh (~50%)** rơi vào nhóm dự phòng `External/Unknown`. Diễn giải ban đầu (SAI) là "50% tài khoản thuộc các tổ chức tài chính ngoài liên minh".

### Nguyên nhân thật
`HI-Small_Trans.csv` đệm số 0 ở đầu mã ngân hàng (ví dụ `"001241"`), còn `HI-Small_accounts.csv` lưu mã dạng số nguyên thuần (`"1241"`). Composite key `Bank_ID + "_" + Account_Number` giữa hai file **không khớp nhau** cho mọi tài khoản thuộc ngân hàng bị đệm số 0 → mỗi tài khoản như vậy bị **tách thành 2 đỉnh riêng biệt** trong đồ thị: một đỉnh đúng (từ `accounts.csv`) và một đỉnh "ma" (từ `edges.csv`, bị gắn nhãn sai `External/Unknown`).

### Đã sửa & Kiểm chứng
Chuẩn hóa Bank ID về cùng dạng trước khi ghép composite key ở **cả hai phía** (vertices và edges) trong `src/ibm_aml/etl.py`.

| Chỉ số | Trước fix | **Sau fix (đã kiểm chứng qua `test_ibm_aml_etl.py`, cả fastmode và `--from-raw`)** |
| :--- | :---: | :---: |
| Tổng đỉnh | 1.033.669 | **518.581** (khớp 100% với `accounts.csv`) |
| Đỉnh `External/Unknown` | 515.088 | **0** |
| Đỉnh phục hồi đúng danh tính | — | **2.185** (ngân hàng `1241`, `701`, `1244`, `31125`) |
| Referential Integrity | `[PASS]` (nhờ fallback che lỗi) | `[PASS]` (khớp thật) |

### ⚠️ Hành động bắt buộc cho MỌI người khi viết code liên quan IBM AML
* **KHÔNG** tự ý tự viết lại logic ghép `Bank_ID + Account_Number` từ raw CSV — luôn dùng `build_ibm_vertices()`/`build_ibm_edges()` trong `src/ibm_aml/etl.py`, đã được sửa đúng.
* Nếu bất kỳ ai load raw CSV thủ công để debug (không qua `etl.py`), **phải tự chuẩn hóa Bank ID (bỏ số 0 đầu) trước khi so sánh/join theo Account ID**, nếu không sẽ tái tạo lại đúng bug này.
* Kiểm định trong `tests/test_ibm_aml_etl.py` yêu cầu đúng `EXPECTED_VERTEX_COUNT = 518_581` và đếm trực tiếp `External/Unknown == 0`.

---

## **1. Bản đồ Thư mục & Dữ liệu đã Chuẩn hóa (Data Locations)**

Toàn bộ dữ liệu thô đã được làm sạch và xuất xưởng dưới định dạng Parquet nén Snappy. Không thành viên nào đọc file CSV thô nữa:

| Bộ dữ liệu | Bản Đầy đủ (Full Graph) — Chạy báo cáo | Bản Mẫu (Sample Subgraph) — Dùng để Dev/Debug |
| :--- | :--- | :--- |
| **PaySim** | `data/processed/` (`vertices.parquet`, `edges.parquet`) — 272.9 MB | `data/processed/sample/` (~100k cạnh, 0 dangling) |
| **IBM AML (HI-Small)** | `data/processed/ibm_aml/` (`vertices.parquet`, `edges.parquet`) — khoảng **192 MB** (có thể đổi nhẹ khi ghi lại Parquet) | `data/processed/sample/ibm_aml/` (~100k cạnh, 0 dangling, **89 fraud** theo cách lấy mẫu mới) |

> ⚠️ **NGUYÊN TẮC HIỆU NĂNG SỐNG CÒN (SPARK CACHING):**
> Các hàm kiểm định (`check_integrity`) hoặc thuật toán lặp (PageRank, LPA, Motif) gọi rất nhiều action `.count()`. Nếu GraphFrame chưa được lưu trong RAM, Spark sẽ đọc lại từ đĩa và tính lại toàn bộ pipeline 6–7 lần liên tiếp.
> **Quy tắc bắt buộc:** Luôn gọi `.cache()` trên GraphFrame (hoặc Vertices/Edges DataFrame) ngay sau khi nạp từ Parquet, đặc biệt khi một GraphFrame bị dùng cho **nhiều truy vấn Motif liên tiếp** (xem ví dụ Mục 3.3.B).

## **2. Đặc tả Schema Đồ thị IBM AML (`vertices.parquet` / `edges.parquet`)**

*(Bảng tương đương Mục 2 của PaySim ở trên — bổ sung vì phiên bản trước của tài liệu này chưa có bảng đặc tả riêng cho IBM.)*

### 2.1. Bảng cấu trúc Đỉnh: `vertices.parquet`
* **Đầy đủ (Full):** 518.581 đỉnh, **0 fallback** | **Bản mẫu đã commit:** 119.146 đỉnh (bản tái tạo có thể dao động nhẹ)

| Tên trường (Field) | Kiểu dữ liệu | Ý nghĩa nghiệp vụ | Ghi chú kỹ thuật |
| :--- | :---: | :--- | :--- |
| `id` | `String` | `Bank_ID + "_" + Account_Number` (composite key, đã chuẩn hóa) | Bank ID đã bỏ số 0 đầu ở cả 2 phía trước khi ghép (Mục 0). |
| `account_type` | `String` | Loại pháp nhân | 6 giá trị: `Partnership`, `Corporation`, `Sole Proprietorship`, `Country`, `Individual`, `Direct`. **Không còn `External/Unknown`** sau fix. |
| `bank_name` | `String` | Tên ngân hàng sở hữu tài khoản | Lấy trực tiếp từ `accounts.csv`. |
| `balance` | `Double` | Luôn = `0.0` | IBM AML **không cung cấp** số dư hiện tại — khác PaySim, đừng dùng cột này cho phân tích số dư. |

### 2.2. Bảng cấu trúc Cạnh: `edges.parquet`
* **Đầy đủ (Full):** 5.078.345 cạnh (5.177 nhãn gian lận) | **Bản mẫu đã commit:** 99.883 cạnh (89 nhãn gian lận; bản tái tạo giữ đúng 89 fraud, số cạnh còn lại có thể dao động nhẹ)

| Tên trường (Field) | Kiểu dữ liệu | Ý nghĩa nghiệp vụ | Ghi chú kỹ thuật |
| :--- | :---: | :--- | :--- |
| `src` / `dst` | `String` | Composite key tài khoản gửi/nhận | Trỏ về `vertices.id`. `dangling_src = dangling_dst = 0` sau fix. |
| `amount` | `Double` | Số tiền đã trả (`Amount Paid`) | **KHÔNG quy đổi tiền tệ** — xem cột `payment_currency`. |
| `amount_received` | `Double` | Số tiền nhận được (`Amount Received`) | Có thể khác `amount` nếu 2 phía dùng tiền tệ khác nhau (phí quy đổi/tỷ giá). |
| `payment_currency` / `receiving_currency` | `String` | Tiền tệ giao dịch (2 phía) | **15 giá trị khác nhau** (`US Dollar`, `Euro`, `Yuan`...). Bắt buộc lọc theo cột này trước khi so sánh `amount`. |
| `step` | `Integer` | Unix Epoch Seconds | `min=1661965200, max=1663492680`. **KHÁC PaySim** — không phải giờ mô phỏng, không giới hạn `<=744`. |
| `type` | `String` | `Payment Format` gốc | `ACH`, `Wire`, `Credit Card`, `Cheque`, `Reinvestment`... |
| `isFraud` | `Short` | `Is Laundering` gốc | `1`: Rửa tiền đã xác thực; `0`: Bình thường. |

## **3. Bảng Đối chiếu Ngữ nghĩa Kỹ thuật (PaySim vs. IBM AML)**

| Thuộc tính / Khía cạnh | PaySim (`data/processed/`) | IBM AML (`data/processed/ibm_aml/`) | Lưu ý kỹ thuật cho Developer |
| :--- | :--- | :--- | :--- |
| **Trường thời gian (`step`)** | Số nguyên $1 \dots 744$ (Giờ mô phỏng 30 ngày) | Số nguyên Epoch Seconds (`1661965200` $\to$ `1663492680`) | **Tuyệt đối KHÔNG** áp điều kiện `step <= 744` trên IBM AML. Chỉ dùng toán tử so sánh thứ tự thời gian ($e_1.step \le e_2.step$). |
| **Đơn vị tiền tệ (`amount`)** | 1 đồng tiền duy nhất | **15 loại ngoại tệ khác nhau** | Khi lọc giá trị (`amount > threshold`), **bắt buộc phải lọc đồng nhất loại tiền tệ trước** trên tất cả các cạnh — và với IBM, nên kiểm tra phân phối tiền tệ *trong tập gian lận cụ thể* trước khi chốt ngưỡng (Mục 3.3.B). |
| **Vòng lặp tự thân (Self-loops)** | **0 cạnh** (`src == dst`) | **591.212 cạnh** (11.64% tổng cạnh) | Khi tìm chu trình (Task 3), **bắt buộc phải loại trừ các đỉnh trùng nhau** để không bắt nhầm self-loop. |
| **Bản chất chu trình 3 đỉnh** | Không có (0 cycle) | **9 chu trình chuẩn cấy theo thiết kế** (trong 54 chuỗi CYCLE mọi độ dài) — xem giải mã đầy đủ Mục 3.3.B | Task 3 trên PaySim pivot sang **2-hop relay**; trên IBM AML chạy **3-node cycle thật**, nhưng phải khử trùng multigraph trước khi báo cáo số liệu. |
| **Toàn vẹn tham chiếu** | 0 dangling edges | 0 dangling edges — **vì mọi tài khoản khớp thật với `accounts.csv` sau khi sửa bug Bank ID (Mục 0), KHÔNG còn nhờ cơ chế fallback che lỗi như trước.** | Hàm `check_integrity()` bóc tách riêng `dangling_src` và `dangling_dst` để chẩn đoán chính xác hai đầu cạnh. |
| **Số đỉnh (Vertices)** | 9.073.900 | **518.581** *(đã sửa từ 1.033.669)* | Nếu thấy bất kỳ code/tài liệu cũ nào ghi 1.033.669, đó là số liệu còn bug — không dùng lại. |

## **4. Mẫu Code Chuẩn & Hướng dẫn Thực thi theo Từng Task**

### **4.1. Khởi tạo và Nạp Đồ thị (Mẫu dùng chung)**

```python
from src.common.spark_session import get_graph_session
from src.common.graph_utils import load_graph, check_integrity

# Khởi tạo Spark Session tích hợp Windows runtime và GraphFrames
spark = get_graph_session("Task-Runner", checkpoint_dir="checkpoints")

# 1. Nạp đồ thị (Khuyến nghị dev trên bản sample trước, sau đó đổi sang full):
# PaySim: load_graph(spark, "data/processed")
graph = load_graph(spark, "data/processed/sample/ibm_aml")

# 2. Cache để tránh recompute:
graph.vertices.cache()
graph.edges.cache()

# 3. Kiểm tra tính toàn vẹn nhanh:
check_integrity(graph)
```

### **4.2. Hướng dẫn Task 2 (Metrics & PageRank) — @Người 3**
* **Cảnh báo độ lệch bậc (Skewness):** Đồ thị tài chính có phân phối bậc lệch rất mạnh theo luật lũy thừa (Power-law). Cấu hình Spark đã bật sẵn `spark.sql.adaptive.skewJoin.enabled = true` để xử lý các phép join trên node Hub này.
* **Cảnh báo PageRank:** Self-loops trên IBM AML (591K cạnh) có thể tự tích lũy rank cho chính nó. Cần lưu ý đặc điểm này khi phân tích Top 10 tài khoản có PageRank cao nhất.
* **⚠️ Số đỉnh đã thay đổi sau bug fix (Mục 0):** Bất kỳ phân tích Degree/PageRank nào chạy trên bản dữ liệu cũ (1.033.669 đỉnh) đều **không còn hợp lệ** và cần chạy lại trên bản đã sửa (518.581 đỉnh).

### **4.3. Hướng dẫn Task 3 (Motif Finding) — @Người 4**
Đây là nơi dễ phát sinh lỗi logic nhất nếu không tuân thủ quy ước:

#### A. Trên PaySim: Truy vấn chuỗi chuyển tiếp 2 bước (2-hop Relay Pattern)

Do PaySim không có chu trình 3 đỉnh khép kín, Người 4 chạy mô hình tẩu tán tiền mặt:

```python
# Truy vấn chuỗi: Nạn nhân -> (TRANSFER) -> Mule -> (CASH_OUT) -> Tiền mặt
relay_motifs = graph_paysim.find("(a)-[e1]->(b); (b)-[e2]->(c)") \
    .filter("e1.type = 'TRANSFER' AND e2.type = 'CASH_OUT'") \
    .filter("e1.amount > 10000 AND e2.amount > 10000") \
    .filter("e1.step <= e2.step")  # Đảm bảo tính tuần tự theo giờ mô phỏng
```

#### B. Trên IBM AML: Truy vấn chu trình 3 đỉnh khép kín — ĐÃ KIỂM CHỨNG THỰC NGHIỆM

**Giải mã "con số 287":** Trong `HI-Small_Patterns.txt` có **54 chuỗi kịch bản CYCLE** (mọi độ dài từ 2 đến 12 hop), tổng cộng **287 dòng giao dịch**. Trong 54 chuỗi đó, chỉ **9 chuỗi** là chu trình 3 đỉnh đúng nghĩa (khớp cú pháp Task 3). Số **287 đếm giao dịch, không đếm chu trình, và bao gồm cả cycle dài hơn 3 hop** — đừng nhắc lại số 287 như thể nó là "số chu trình 3 đỉnh".

**Kết quả truy vấn Motif thực tế** (từ `audit_ibm_post_fix.py`, chạy trên đồ thị đã sửa bug):

| Truy vấn | Kết quả |
| :--- | :---: |
| 3-node cycle theo thiết kế gốc (từ Patterns.txt) | **9** |
| 3-node cycle trên toàn mạng gian lận (`isFraud=1`, không lọc tiền tệ/ngưỡng) | **7.473 motif rows thô**; **45 bộ ba đỉnh duy nhất** sau khi khử phép xoay và đa cạnh |
| 3-node cycle với `currency='US Dollar' AND amount>10000` trên cả 3 cạnh (nguyên bản Task 3) | **0** |

⚠️ **CẢNH BÁO 1 — Đếm trùng do Multigraph và phép xoay:** IBM AML cho phép nhiều giao dịch giữa cùng 2 tài khoản. `graph.find()` đếm mọi **tổ hợp cạnh** khớp mẫu và mỗi chu trình có ba điểm bắt đầu. Trên bản hiện tại, 7.473 rows thô tương ứng 162 bộ ba có thứ tự sau `.select("a.id", "b.id", "c.id").distinct()`, nhưng chỉ **45 bộ ba tài khoản duy nhất** khi chuẩn hóa thứ tự ba ID. Số 45 là cấu trúc đồ thị trong tập gắn nhãn gian lận, không tự chứng minh 45 vụ rửa tiền độc lập. Dùng cách sau trước khi báo cáo số liệu:

```python
# 1. Nạp và cache đồ thị đầy đủ MỘT LẦN, dùng lại cho cả 2 truy vấn dưới đây
full_graph = load_graph(spark, "data/processed/ibm_aml")
full_graph.vertices.cache()
full_graph.edges.cache()

# 2. Truy vấn thô trên tập gian lận
fraud_graph = full_graph.filterEdges("isFraud = 1")
fraud_cycles = fraud_graph.find("(a)-[e1]->(b); (b)-[e2]->(c); (c)-[e3]->(a)") \
    .filter("a.id != b.id AND b.id != c.id AND a.id != c.id")

# 3. Sắp xếp ID để ba phép xoay của cùng một chu trình có chung khóa;
#    distinct loại thêm các tổ hợp đa cạnh trên cùng bộ ba đỉnh.
from pyspark.sql import functions as F
distinct_node_sets = fraud_cycles.select(
    F.array_sort(F.array(F.col("a.id"), F.col("b.id"), F.col("c.id"))).alias("nodes")
).distinct().count()
print(f"So bo ba dinh duy nhat trong fraud subgraph: {distinct_node_sets:,}")
```

⚠️ **CẢNH BÁO 2 — Ngưỡng $10.000 (giả thuyết, chưa kiểm chứng độc lập):** Truy vấn trên toàn đồ thị với cả ba cạnh USD và `amount > 10000` trả về $0$; truy vấn `isFraud=1` không lọc tiền tệ/ngưỡng cho 7.473 rows thô. Vì cả tập cạnh lẫn điều kiện lọc đều khác, hai số này không chứng minh hành vi **Structuring/Smurfing**. **Trước khi đưa giả thuyết này vào báo cáo, chạy đối chiếu:**

```python
full_graph.edges.filter("isFraud = 1").groupBy("payment_currency") \
    .agg(F.count("*").alias("n"), F.avg("amount").alias("avg_amount"), F.max("amount").alias("max_amount")) \
    .orderBy(F.desc("n")).show(20)
```

**Khuyến nghị cụ thể cho Người 4:** Không copy nguyên ngưỡng `$10.000` từ đề bài PaySim. Sau khi chạy đối chiếu ở trên, chọn ngưỡng phù hợp với phân phối `amount` thực tế theo từng `payment_currency`, và báo cáo rõ cả số motif rows thô lẫn `distinct_node_sets` (Cảnh báo 1). Không diễn giải số 0 ở ngưỡng USD >$10.000 thành bằng chứng tội phạm cố tình chia nhỏ giao dịch.

### **4.4. Hướng dẫn Task 4 (Community Detection / LPA) — @Người 5 & @Người 6**

* **Yêu cầu Checkpoint bắt buộc:** Thuật toán Label Propagation lặp qua nhiều thế hệ RDD. Nếu không cấu hình `setCheckpointDir` (đã được bọc tự động trong `get_graph_session(..., checkpoint_dir="checkpoints")`), Spark sẽ báo lỗi `java.lang.StackOverflowError`.
* **Phân tích Thực thể Doanh nghiệp (Chỉ có ở IBM AML):** Bảng đỉnh của IBM AML cung cấp cột `account_type` chi tiết (`Corporation`, `Partnership`, `Sole Proprietorship`...) — **không đổi và không bị ảnh hưởng bởi bug Bank ID**. Khi phát hiện ra các cụm gian lận (Fraud Rings), hãy đối chiếu xem các mắt xích này được ngụy trang dưới danh nghĩa pháp nhân nào để đưa vào báo cáo nghiệp vụ!

```python
# Chạy LPA trên IBM AML:
communities = graph_ibm.labelPropagation(maxIter=5)

# Thống kê loại hình doanh nghiệp tham gia vào các cụm gian lận:
communities.filter("isFraud = 1") \
           .groupBy("label", "account_type") \
           .count() \
           .orderBy("count", ascending=False) \
           .show(10)
```
