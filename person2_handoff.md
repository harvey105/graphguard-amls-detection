# TÀI LIỆU BÀN GIAO KỸ THUẬT: TASK 1 — DATA ENGINEERING & GRAPH CONSTRUCTION
* **Người thực hiện (Author):** Person 2 (Data Engineering Lead)
* **Người tiếp nhận (Target Audience):** Person 1 (Lead), Person 3, Person 4, Person 5, Person 6, Person 7
* **Trạng thái (Status):** Đã hoàn tất & Kiểm định 100% (Fully Verified & Certified)
* **Phạm vi hoàn thành (Deliverables):** `src/utils/etl_mapping.py`, `src/export_parquet.py`, `src/graph_analysis.py` (Đạt 15/15 điểm Task 1).

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
| `data/raw/` | **Bị loại trừ (Ignored)** | ~493.5 MB | Chứa file CSV gốc `PS_..._log.csv`. Không đẩy lên GitHub. |
| `data/processed/*.parquet` | **Bị loại trừ (Ignored)** | ~273 MB | Chứa đồ thị đầy đủ (Full Graph) đã làm sạch. Không đẩy lên GitHub. |
| `data/processed/sample/` | **Được theo dõi (Tracked)** | ~6.5 MB | **ĐÃ CÓ SẴN TRÊN REPO.** Chứa đồ thị mẫu thu nhỏ (~100k cạnh) để lập trình thử nghiệm. |

#### Cách sở hữu Đồ thị Đầy đủ (`data/processed/*.parquet`):
Các thành viên có thể lựa chọn 1 trong 2 phương án:
* **Cách 1 (Tự sinh cục bộ - Khuyến nghị):** Sau khi kéo repo về, tải file CSV gốc từ Kaggle bỏ vào `data/raw/` rồi chạy lệnh:
  ```powershell
  python src/export_parquet.py
  ```
  Quá trình này mất khoảng 90–120 giây để tự động xuất ra toàn bộ thư mục `data/processed/`.
* **Cách 2 (Tải trực tiếp qua Google Drive):** Tải thư mục nén `processed.zip` do Person 2 cung cấp qua liên kết Google Drive chung của nhóm, giải nén trực tiếp vào thư mục `data/processed/`.

---

## 2. ĐẶC TẢ DỮ LIỆU ĐỒ THỊ ĐÃ XUẤT XƯỞNG (GRAPH DATA SPECIFICATIONS)

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

## 3. MẪU MÃ NGUỒN TÁI SỬ DỤNG (REUSABLE CODE TEMPLATE)

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

## 4. CẢI TIẾN KỸ THUẬT & XỬ LÝ ĐIỂM MƠ HỒ SO VỚI PLAN BAN ĐẦU
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

## 5. CẢNH BÁO & YÊU CẦU HÀNH ĐỘNG THEO TỪNG TASK

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
  * *Giải pháp 2:* Kích hoạt phương án dự phòng (Contingency Plan Mục 7.2) chuyển sang dataset **AMLSim** nếu đề bài bắt buộc phải có chu trình khép kín $A \to B \to C \to A$.

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