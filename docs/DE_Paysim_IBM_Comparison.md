# **PAYSIM DATASET**

- **Quy mô mạng lưới:** 9.073.900 đỉnh (Vertices), 6.362.620 cạnh (Edges)
- **Giao dịch gian lận:** 8.213 cạnh (Tỷ lệ: 0.1291%)
- T**ự giao dịch (Self-loops):** 0 cạnh (0.0%)
- **Chu trình 3 đỉnh khép kín (3-node cycles):** 0 chu trình (Acyclic)


### **1. Đánh giá Nghiệm thu Hạ tầng (Infrastructure & Data Quality Verdict)**

Toàn bộ quy trình ETL và khởi tạo GraphFrame trên PaySim đã hoàn tất với độ chuẩn xác tuyệt đối:

* **Kiểm định chất lượng (Data Quality Report):** Đạt chuẩn `[PASS]` ở tất cả các hạng mục: $0$ giá trị `null`, $0$ cạnh treo (dangling edges), bảo toàn $100\%$ số dòng từ file CSV thô ($6.362.620$ cạnh).

* **Tối ưu hóa lưu trữ Big Data:** 
  * Định dạng nén Snappy Parquet đã rút gọn tập dữ liệu thô (~500 MB) xuống còn **$110.3\text{ MB}$ cho Vertices** và **$162.6\text{ MB}$ cho Edges** (tổng cộng $272.9\text{ MB}$).
  * Phân vùng 8 partitions tối ưu hóa việc đọc song song trên môi trường đa lõi (multi-core).

* **Tạo lập đồ thị con cảm ứng (Induced Sample Subgraph):** Xuất bản thành công đồ thị mẫu thu nhỏ tại `data/processed/sample/paysim/` gồm **$100.729$ cạnh** và **$194.195$ đỉnh**, bảo toàn nguyên vẹn **$153$ cạnh gian lận** và cam kết $0$ cạnh treo phục vụ lập trình thử nghiệm.


### **2. Phân tích Chuyên sâu Cấu trúc Mạng (Topological Deep-Dive)**

#### **2.1. Phân phối Bậc Lệch Cực Đoan (Extreme Power-Law Degree Asymmetry)**

Kết quả thăm dò cấu trúc bậc (Degree Probe) bộc lộ sự bất đối xứng điển hình của mạng lưới thanh toán bán lẻ:

* **Bậc vào (In-Degree) — Điểm tụ tiền:** Đỉnh nhận nhiều giao dịch nhất lên tới **$113$ cạnh vào** (tài khoản `C1286084959`), theo sau là các tài khoản nhận $109, 105, 102, 101$ giao dịch. Đây là các điểm nút gom tiền (Fan-in hubs).

* **Bậc ra (Out-Degree) — Nguồn phát tiền:** Ngược lại hoàn toàn, bậc ra tối đa của toàn bộ mạng lưới **chỉ dừng lại ở mức $3$ cạnh** (các tài khoản `C1902386530`, `C1976208114`...). Tuyệt đại đa số người dùng thông thường chỉ phát sinh từ 1 đến 2 giao dịch gửi.

     $\to$ **Hàm ý kiến trúc Big Data:** Hiện tượng lệch bậc này là minh chứng thực nghiệm không thể chối cãi cho **sự vượt trội của Vertex Cut so với Edge Cut (Mục 3.2)**. Nếu dùng Edge Cut, các đỉnh hub có bậc vào $>100$ sẽ tạo ra điểm nghẽn truyền thông (network bottleneck) khủng khiếp khi dồn toàn bộ cạnh về một máy. Vertex Cut giải quyết triệt để vấn đề này bằng cách phân tán cạnh và nhân bản đỉnh đại diện.

#### **2.2. Điểm Nghẽn Liên thông: 1.769 Tài khoản Cầu nối (Routing Hubs)**

* Trong tổng số **$9.073.900$ tài khoản**, có $6.353.307$ tài khoản thuần gửi và $2.722.362$ tài khoản thuần nhận.
* Chỉ có duy nhất **$1.769$ tài khoản** ($0.0195\%$) đóng cả hai vai trò: vừa gửi vừa nhận tiền.
    $\to$ **Ý nghĩa cấu trúc:** $1.769$ tài khoản này chính là các **cây cầu liên thông duy nhất** kết nối các thành phần rời rạc trong mạng lưới. Nếu loại bỏ $1.769$ tài khoản này, toàn bộ đồ thị sẽ sụp đổ thành hàng triệu cây nhị phân độc lập. Đây chính là mục tiêu trọng điểm mà thuật toán PageRank (Task 2) và Label Propagation (Task 4) sẽ khoanh vùng.

#### **2.3. Bản chất Đồ thị Phẳng Acyclic: Nguyên nhân PaySim có 0 Chu trình**

* **Kết quả thực nghiệm:** Tự giao dịch (`Self-loops`) = $0$; Chu trình 3 đỉnh ($A \to B \to C \to A$) = $0$.
* **Bản chất mô phỏng:** Trình giả lập PaySim sinh dữ liệu dựa trên nhật ký tiền di động (Mobile Money) tại châu Phi, tập trung vào kịch bản chiếm đoạt tài khoản (Account Takeover). Luồng tiền luôn có tính chất **thoát ly hệ thống (System-Exit)**:
  $$\text{Nạn nhân} \xrightarrow{\text{TRANSFER}} \text{Tài khoản trung gian (Mule)} \xrightarrow{\text{CASH\_OUT}} \text{Rút tiền mặt}$$
    
     $\to$ **Định hướng Task 3:** PaySim là đồ thị phi chu trình (Acyclic). Do đó, Task 3 bắt buộc phải chuyển hướng (pivot) từ việc tìm chu trình khép kín sang tìm **Mẫu hình chuyển tiếp 2 bước (2-Hop Relay Motif)**: `TRANSFER` $\to$ `CASH_OUT`.


### **3. Ý nghĩa Nghiệp vụ Chống Rửa tiền (AML Domain Insights)**

* **Sự phá sản của hệ thống cảnh báo tĩnh (Static Rule Failure):**
  * Dataset ghi nhận $8.213$ giao dịch gian lận thực tế (chỉ nằm ở `TRANSFER` và `CASH_OUT`).
  * Tuy nhiên, hệ thống luật truyền thống (`amount > 200,000` thông qua cờ `isFlaggedFraud`) **chỉ bắt được đúng 16 giao dịch** ($\text{Recall} = 0.19\%$, bỏ lọt $99.81\%$).

* **Thương nhân (`Merchant`) đóng vai trò Hố đen (Sink Nodes):**
  * Toàn bộ $2.150.401$ tài khoản Merchant (tiền tố `M`) chỉ nhận tiền từ giao dịch `PAYMENT` và không bao giờ chuyển tiền đi tiếp ($\text{Out-Degree} = 0$).
  * $\to$ **Cảnh báo Task 2 (PageRank):** Nếu không có hệ số suy giảm $d = 0.85$ (Teleportation factor), toàn bộ rank của mạng lưới sẽ bị hút cạn vào các Merchant này (Sink-node trapping).

---

# **IBM AML DATASET**

- **Quy mô mạng lưới:** 518.581 đỉnh (Vertices), 5.078.345 cạnh (Edges)
- **Giao dịch gian lận:** 5.177 cạnh (Tỷ lệ: 0.1019%)
- **Tỷ lệ tự giao dịch (Self-loops):** 591.212 cạnh (11.64%)

> ⚠️ **Toàn bộ số liệu Vertices/Boundary trong phiên bản trước của tài liệu này (1.033.669 đỉnh, 515.088 tài khoản "External/Unknown") đã bị loại bỏ và thay thế ở đây.** Đó là hệ quả của một bug ETL, không phải đặc điểm thật của dataset. Chi tiết ở Mục 0.

### **0. ⚠️ Bản Sửa Lỗi Trọng Yếu: Bug Chuẩn Hóa Bank ID**

* **Triệu chứng ban đầu:** ETL phiên bản đầu ghi nhận $1.033.669$ đỉnh, trong đó $515.088$ đỉnh ($\approx 50\%$) rơi vào nhóm dự phòng `External/Unknown` — được diễn giải (sai) là "dòng tiền chảy ra ngân hàng/định chế ngoài liên minh".
* **Nguyên nhân thật:** File `HI-Small_Trans.csv` đệm số 0 ở đầu mã ngân hàng (`"001241"`, `"00701"`), trong khi `HI-Small_accounts.csv` lưu mã dạng số nguyên thuần (`"1241"`, `"701"`). Composite key `Bank_ID + "_" + Account_Number` giữa hai file do đó KHÔNG khớp nhau cho mọi tài khoản thuộc các ngân hàng bị đệm số 0 — mỗi tài khoản như vậy bị tạo thành **2 đỉnh riêng biệt trong đồ thị**: một đỉnh đúng (từ `accounts.csv`) và một đỉnh "ma" trùng lặp (từ `edges.csv`, bị gắn nhãn sai thành `External/Unknown`). Đây là lỗi tách đôi danh tính (identity-splitting bug), không phải một đặc điểm nghiệp vụ.
* **Đã sửa:** Chuẩn hóa Bank ID về cùng dạng số nguyên trước khi ghép composite key ở cả hai phía (vertices và edges).
* **Kết quả kiểm chứng sau khi sửa (từ `test_ibm_aml_etl.py`, cả `fastmode` và `--from-raw`):**

| Chỉ số | Trước khi sửa | **Sau khi sửa (Đã kiểm chứng)** |
| :--- | :--- | :--- |
| Tổng số Đỉnh (Vertices) | 1.033.669 | **518.581** |
| Đỉnh `External/Unknown` | 515.088 | **0** |
| Đỉnh phục hồi đúng danh tính | — | **2.185 đỉnh** (từ các ngân hàng `1241`, `701`, `1244`, `31125`) |
| Referential Integrity | `[PASS]` (nhờ fallback che lỗi) | `[PASS]` (khớp thật, không cần fallback) |

  $\to$ Tổng đỉnh mới ($518.581$) khớp **chính xác 100%** với số dòng của `accounts.csv` — xác nhận đồ thị hiện tại phản ánh đúng thực thể tài khoản, không còn đỉnh trùng lặp.

### **1. Mạng lưới Đóng (Closed Network) — Đảo ngược Kết luận Trước Đó**

* **Con số thực tế sau khi sửa:** $518.581$ đỉnh, khớp $100\%$ với `accounts.csv`, **$0$ tài khoản ngoại lai**.
* **Ý nghĩa:** Kết luận cũ ("mạng lưới mở, tiền chảy ra 515K tổ chức bên ngoài liên minh") là diễn giải sai một triệu chứng bug, không phải một phát hiện nghiệp vụ. Với dữ liệu `HI-Small` cụ thể này, **mọi tài khoản xuất hiện trong giao dịch đều được định danh đầy đủ trong `accounts.csv`** — cùng đặc điểm "Đóng" (Closed) như PaySim, chỉ khác về quy mô và cấu trúc thực thể.


### **2. Phân phối Thực thể Doanh nghiệp (`account_type`) — Nhận diện "Công ty Vỏ bọc"**

Khác với PaySim chỉ có Khách hàng (`Customer`) và Người bán (`Merchant`), cấu trúc đỉnh của IBM AML bộc lộ tính chất thương mại rõ rệt. Các số liệu dưới đây **không đổi** so với trước (chúng luôn là số thật, chỉ có nhóm `External/Unknown` song song là ảo) — nhưng nay chiếm **$100\%$ tổng số đỉnh**, không còn là "nhóm nội bộ" cạnh một nhóm ngoại lai nữa:

| Phân loại tài khoản (`account_type`) | Số lượng đỉnh | Tỷ lệ trong **toàn bộ mạng lưới** | Ý nghĩa trong điều tra tội phạm tài chính |
| :--- | :---: | :---: | :--- |
| **Partnership (Công ty Hợp danh)** | 189.683 | 36.58% | Các thực thể kinh doanh có nhiều chủ sở hữu, thường dùng trong ủy thác đầu tư. |
| **Corporation (Tập đoàn / Doanh nghiệp)** | 172.351 | 33.24% | Các pháp nhân doanh nghiệp lớn, nơi dòng tiền luân chuyển phức tạp. |
| **Sole Proprietorship (Hộ kinh doanh cá thể)**| 149.048 | 28.74% | Doanh nghiệp tư nhân một chủ — mắt xích cực kỳ phổ biến để lập **Công ty Ma (Shell Company)** rửa tiền. |
| **Country (Tài khoản Cấp Quốc gia)** | 6.692 | 1.29% | Các tài khoản giao dịch quốc tế/ngân hàng trung ương. |
| **Individual (Cá nhân)** | 740 | 0.14% | Tài khoản cá nhân đơn lẻ. |
| **Direct** | 67 | 0.01% | Kênh kết nối thanh toán trực tiếp. |
| **Tổng** | **518.581** | **100.00%** | Khớp chính xác với `accounts.csv`. |

   $\to$ **Gợi ý đắt giá cho Task 4 (Community Detection):** Khi Person 5 & 6 gom cụm các Fraud Rings, họ có thể phân tích xem: *Băng nhóm gian lận này được ngụy trang dưới dạng Tập đoàn (`Corporation`) hay các Hộ kinh doanh cá thể (`Sole Proprietorship`)?* Đây là phân tích nghiệp vụ ở tầm chuyên gia.


### **3. Phát hiện 591.212 Cạnh Tự giao dịch (`Self-loops`) — Khác biệt cốt lõi với PaySim**

* **Phát hiện:** Có tới **591.212 giao dịch** có `src == dst` (chiếm $11.64\%$ tổng số giao dịch). Số liệu này **không bị ảnh hưởng** bởi bug Bank ID ở Mục 0 (self-loop là thuộc tính của cạnh, không phụ thuộc việc đỉnh có bị tách đôi hay không).

* **Bản chất:** Trong ngân hàng thực tế, đây là các nghiệp vụ:
  * Tự tái đầu tư tiền nhàn rỗi (Reinvestment).
  * Chuyển tiền giữa các tài khoản phụ/tiểu khoản (Sub-accounts) trong cùng một ngân hàng.
  * Tự động quét số dư cuối ngày (Sweeping).

   $\to$ **Cảnh báo cho Task 2 & Task 3:** 
  * Khi Người 3 chạy PageRank, các self-loop này có thể làm tăng rank nội tại của đỉnh.
  * Khi Người 4 chạy Motif 3 đỉnh khép kín ($a \to b \to c \to a$), **bắt buộc phải loại trừ self-loop** bằng điều kiện: `a.id != b.id AND b.id != c.id AND a.id != c.id`, nếu không thuật toán sẽ bắt nhầm các vòng lặp tự thân tầm thường!

### **4. Miền giá trị Thời gian (`step` range)**

* **Khoảng thời gian:** `min = 1661965200` $\to$ `max = 1663492680`.
* **Quy đổi thời gian thực:** Từ **00:00:00 ngày 01/09/2022** đến **09:18:00 ngày 18/09/2022** (kéo dài đúng 18 ngày).
   $\to$ Khớp chính xác $100\%$ với mô tả của IBM trong bài báo NeurIPS 2023. Thứ tự thời gian chuẩn xác tính theo từng giây.

### **5. ⚠️ Giải Mã Toàn Diện "Con Số 287": Chu Trình 3 Đỉnh Trong IBM AML**

Đo lường thực nghiệm bằng `audit_ibm_post_fix.py` chạy trực tiếp trên `HI-Small_Patterns.txt` (file kịch bản gốc do IBM cấy sẵn) và trên GraphFrame đã sửa lỗi, thu được kết quả **100% giải thích được nguồn gốc con số "287"** từng được nhắc mơ hồ trong báo cáo Leader:

#### 5.1. Phân rã file kịch bản gốc theo độ dài chu trình

| Độ dài chu trình (hop) | Số chuỗi kịch bản `CYCLE` |
| :---: | :---: |
| 2-hop | 14 |
| **3-hop** | **9** |
| 4-hop | 7 |
| 5-hop | 3 |
| 6-hop | 1 |
| 7-hop | 5 |
| 8-hop | 4 |
| 10-hop | 6 |
| 11-hop | 4 |
| 12-hop | 1 |
| **Tổng cộng** | **54 chuỗi** |

* **Tổng số dòng giao dịch** trên toàn bộ 54 chuỗi (mọi độ dài) = **287 giao dịch**. Đây chính là nguồn gốc thật của con số "287" — nó đếm **giao dịch**, không phải **chu trình**, và bao gồm cả các chu trình dài tới 12 hop, không riêng chu trình 3 đỉnh.
* **Chu trình 3 đỉnh chuẩn (khớp đúng cú pháp Task 3, `(a)-[e1]->(b);(b)-[e2]->(c);(c)-[e3]->(a)`)** chỉ có **9 chuỗi** trong tổng số 54.

#### 5.2. Đối chiếu với truy vấn Motif thực tế trên đồ thị đã sửa

| Truy vấn | Kết quả | Diễn giải |
| :--- | :---: | :--- |
| 3-node cycle trong kịch bản gốc (thiết kế) | **9 chu trình** | Con số nền chuẩn để đối chiếu — chắc chắn đúng vì lấy trực tiếp từ file kịch bản IBM cấy sẵn. |
| 3-node cycle trên **toàn mạng gian lận** (`isFraud=1`, không lọc tiền tệ/ngưỡng) | **7.473 kết quả thô** | ⚠️ **CHƯA khử trùng theo multigraph** — xem cảnh báo Mục 5.3. KHÔNG được báo cáo là "7.473 vòng rửa tiền". |
| 3-node cycle với `payment_currency='US Dollar' AND amount>10000` trên **cả 3 cạnh** (đúng nguyên bản Task 3) | **0 chu trình** | Ngưỡng $10k gốc từ đề bài PaySim không phù hợp trực tiếp với IBM AML — xem giả thuyết Mục 5.4. |

#### 5.3. ⚠️ Cảnh báo phương pháp: 7.473 rất có thể là số đếm phóng đại (multigraph over-count)

IBM AML là **đa đồ thị (multigraph)** — hai tài khoản có thể có nhiều giao dịch lặp lại ở nhiều mốc thời gian khác nhau. `graph.find()` của GraphFrames đếm **mọi tổ hợp cạnh khớp mẫu**, không khử trùng theo tam giác đỉnh (node-triple). Một vòng rửa tiền thật gồm 3 tài khoản $(A,B,C)$ nhưng có, ví dụ, 20 giao dịch $A \to B$, 15 giao dịch $B \to C$, 10 giao dịch $C \to A$ sẽ tạo ra $20 \times 15 \times 10 = 3.000$ "chu trình" khớp mẫu — dù về bản chất chỉ là **một** vòng rửa tiền duy nhất, lặp lại nhiều lần (đúng đặc trưng hành vi *Structuring*).

$\to$ **Hành động bắt buộc cho Person 4 trước khi đưa số liệu vào báo cáo:**
```python
# Đếm số VÒNG RỬA TIỀN THẬT (theo tam giác đỉnh duy nhất), không phải số cạnh khớp mẫu:
distinct_fraud_rings = fraud_cycles.select("a.id", "b.id", "c.id").distinct().count()
print(f"Số vòng rửa tiền 3 đỉnh THỰC SỰ khác nhau: {distinct_fraud_rings:,}")
```

#### 5.4. Giả thuyết (chưa kiểm chứng độc lập): Structuring / Smurfing để né ngưỡng khai báo $10.000

Việc truy vấn với `amount > 10000` trên cả 3 cạnh trả về đúng $0$ kết quả, trong khi bỏ điều kiện này (chỉ giữ `isFraud=1`) cho ra 7.473 kết quả thô, **phù hợp** với một kỹ thuật rửa tiền có thật gọi là *Structuring/Smurfing*: chia nhỏ giao dịch dưới ngưỡng phải khai báo (Currency Transaction Report — CTR, luật Mỹ quy định ngưỡng $10.000) để tránh bị hệ thống giám sát gắn cờ tự động.

> ⚠️ **Đây là một giả thuyết hợp lý về mặt nghiệp vụ, KHÔNG phải một kết luận đã kiểm chứng.** Việc trả về 0 kết quả cũng có thể đơn giản là do các giao dịch gian lận tập trung ở các đồng tiền khác ngoài USD (dataset có 15 loại tiền tệ), không nhất thiết do cố tình chia nhỏ số tiền. **Trước khi đưa giả thuyết structuring vào báo cáo chính thức**, Person 4 nên chạy thêm truy vấn đối chiếu:
> ```python
> # Kiểm tra phân phối tiền tệ VÀ số tiền trong 5.177 giao dịch gian lận,
> # để xác định 0-kết-quả là do ngưỡng $10k hay do lệch tiền tệ (hoặc cả hai):
> full_graph.edges.filter("isFraud = 1").groupBy("payment_currency") \
>     .agg(F.count("*").alias("n"), F.avg("amount").alias("avg_amount"),
>          F.max("amount").alias("max_amount")) \
>     .orderBy(F.desc("n")).show(20)
> ```

$\to$ **Khuyến nghị cho Task 3 trên IBM AML:** Ngưỡng `$10.000` sao chép nguyên văn từ đề bài PaySim nhiều khả năng không phù hợp về quy mô/tiền tệ với IBM AML. Person 4 nên **hạ ngưỡng và/hoặc chạy trực tiếp trên tập `isFraud=1`** để có kết quả minh họa, miễn là đã khử trùng theo Mục 5.3 và đã đối chiếu nguyên nhân theo Mục 5.4 trước khi chốt số liệu cuối cùng.


### **6. Đặc tả Lưu trữ (Disk Footprint) — Đã đo lại 100% sau khi sửa bug**

| | Vertices Parquet | Edges Parquet | Tổng |
| :--- | :---: | :---: | :---: |
| **Full dataset** | 5.63 MB | 186.66 MB | **192.29 MB** |
| **Sample subgraph** | 1.23 MB | 3.61 MB | **4.84 MB** |

* Số liệu Vertices Parquet cũ (`≈25MB`, ước lượng từ thời còn bug) đã được thay bằng số đo thật (`5.63MB`) — không cố quy đổi tỷ lệ chính xác với số đỉnh cũ, vì hiệu ứng nén Parquet (dictionary/run-length encoding) không tuyến tính theo số dòng.
* Sample subgraph: **89 cạnh gian lận** (Tỷ lệ $0.0891\%$) trên $99.883$ cạnh / $119.146$ đỉnh — con số này **thay cho ước lượng cũ "101 fraud"**, được đo trực tiếp từ Parquet đã xuất bản, không phải ước lượng.

---

# **BẢNG SO SÁNH ĐỐI CHIẾU CHUYÊN SÂU: PAYSIM VS. IBM AML (HI-SMALL)**

*(Bảng tổng hợp đối chiếu toàn diện các tiêu chí kỹ thuật phục vụ Báo cáo Part B & Cross-Dataset Comparison — đã cập nhật toàn bộ số liệu IBM AML sau khi sửa bug Bank ID)*

| Nhóm Tiêu chí Phân tích | PaySim (Synthetic Mobile Money) | IBM AML (HI-Small Multi-Agent) | Đánh giá Chuyên sâu & Ý nghĩa Kỹ thuật |
| :--- | :--- | :--- | :--- |
| **1. TỔNG QUAN & THIẾT KẾ** | | | |
| **Bản chất dữ liệu** | Mô phỏng ví điện tử di động (Mobile Money), 1 quốc gia. | Mô phỏng hệ sinh thái tài chính đa ngân hàng (NeurIPS 2023). | PaySim đơn miền; IBM AML đa miền, phản ánh chuẩn mực ngân hàng thương mại quốc tế. |
| **Mục đích mô phỏng gốc** | Gian lận chiếm đoạt tài khoản (Account Takeover Fraud). | Rửa tiền có tổ chức qua nhiều hình thái tội phạm (AML Typologies: CYCLE, FAN, RANDOM...). | PaySim bắt gian lận đơn lẻ; IBM bắt mạng lưới rửa tiền tinh vi. |
| **2. QUY MÔ & TỐI ƯU BIG DATA** | | | |
| **Số lượng Cạnh (Edges)** | **$6.362.620$ giao dịch** | **$5.078.345$ giao dịch** | Cả 2 đều đạt quy mô $>5\text{M}$ records, đáp ứng chuẩn bài toán Big Data. |
| **Số lượng Đỉnh (Vertices)** | **$9.073.900$ đỉnh** | **$518.581$ đỉnh** *(đã sửa từ 1.033.669 — xem Mục 0)* | Đồ thị PaySim có số đỉnh gấp **~17.5 lần** IBM; mật độ cạnh/đỉnh của IBM dày hơn PaySim khoảng **~14 lần** ($9.79$ vs $0.70$ cạnh/đỉnh). Cả hai tỷ lệ này đã được tính lại — số cũ ("gấp 9 lần", "gấp 7 lần") bị loại bỏ vì dựa trên số đỉnh còn bug. |
| **Kích thước Parquet (Full)** | $110.3\text{ MB}$ (V) + $162.6\text{ MB}$ (E) = **$272.9\text{ MB}$** | $5.63\text{ MB}$ (V) + $186.66\text{ MB}$ (E) = **$192.29\text{ MB}$** *(đo thật, thay ước lượng cũ ≈175MB)* | Vertices của IBM co lại đáng kể sau khi bỏ ~515K đỉnh trùng lặp; Edges không đổi vì số cạnh không bị ảnh hưởng bởi bug. |
| **Kích thước Sample Subgraph** | $100.729$ cạnh / $194.195$ đỉnh ($153$ fraud) | $99.883$ cạnh / $119.146$ đỉnh (**$89$ fraud**, đã sửa từ ước lượng cũ "101") | Bản sample của cả 2 đều đảm bảo $0$ dangling edges, sẵn sàng cho việc test code nhẹ. |
| **3. MÔ HÌNH THỰC THỂ & ĐỊNH DANH** | | | |
| **Không gian định danh (Namespace)** | **Toàn cục đơn lẻ:** Định danh trực tiếp qua `nameOrig`, `nameDest`. | **Khóa phức hợp (Composite Key):** Bắt buộc ghép `Bank_ID` + `Account_ID`, **phải chuẩn hóa Bank ID về cùng dạng số nguyên trước khi ghép** (xem Mục 0 — nguồn gốc bug lớn nhất của dataset này). | IBM yêu cầu bảo toàn chuỗi `StringType` cho Bank ID để tránh mất số $0$ đầu, NHƯNG cũng phải chuẩn hóa nhất quán giữa 2 file nguồn, nếu không sẽ tách đôi danh tính tài khoản. |
| **Phân loại thực thể (`account_type`)** | **2 loại cơ bản:** `Customer` ($76.3\%$), `Merchant` ($23.7\%$). | **6 loại doanh nghiệp:** `Partnership`, `Corporation`, `Sole Proprietorship`, `Country`, `Individual`, `Direct` — nay chiếm **100%** tổng đỉnh (không còn `External/Unknown`). | IBM phản ánh chân thực các loại hình pháp nhân dùng để lập công ty bình phong (Shell companies). |
| **Biên giới mạng lưới (Boundary)** | **Đóng (Closed):** Tất cả tài khoản giao dịch đều nằm trong hệ thống. | **Đóng (Closed)** — *(ĐẢO NGƯỢC kết luận cũ: trước đây tưởng "Mở" với 515K tài khoản ngoại lai; đó là bug, không phải đặc điểm thật)*. | Với bộ `HI-Small` cụ thể này, mọi tài khoản trong giao dịch đều được định danh đầy đủ trong `accounts.csv`. |
| **4. CẤU TRÚC ĐỒ THỊ (TOPOLOGY)** | | | |
| **Hình thái cấu trúc** | **Acyclic (Cây phi chu trình):** Cấu trúc phân nhánh hướng tâm. | **Directed Multigraph (Đa đồ thị):** Dày đặc, đa cạnh song song, có vòng. | IBM phức tạp hơn nhiều về mặt quan hệ topo học. |
| **Giao dịch tự thân (Self-loops)** | **$0$ giao dịch ($0.0\%$)** | **$591.212$ giao dịch ($11.64\%$)** — không đổi, không bị ảnh hưởng bởi bug Bank ID. | IBM phản ánh các nghiệp vụ tài chính thực tế: Reinvestment, Sweeping, Sub-accounts. |
| **Chu trình 3 đỉnh ($A \to B \to C \to A$)** | **$0$ chu trình (Khảo sát vét cạn toàn đồ thị)** | **$9$ chu trình chuẩn cấy theo thiết kế** (trong $54$ chuỗi CYCLE mọi độ dài, $2$–$12$ hop, tổng $287$ giao dịch — đây là nguồn gốc thật của "287"); truy vấn thực tế cho **7.473 kết quả thô** trên tập gian lận (chưa khử trùng multigraph, xem Mục 5.3) nhưng **$0$ kết quả** với ngưỡng gốc $10k+USD của Task 3 (giả thuyết structuring, xem Mục 5.4). | Minh chứng cốt lõi giải thích vì sao nhóm mở rộng sang IBM để cứu Task 3 — nhưng cần điều chỉnh ngưỡng lọc, không dùng nguyên $10k+USD của PaySim. |
| **Độ lệch bậc (Degree Skewness)** | Lệch cực đại: In-Degree max = $113$, Out-Degree max = $3$. | Chưa đo lại số cụ thể sau khi sửa bug (số đỉnh đã đổi, phân phối bậc thực tế cần chạy lại `metrics.py` để có số chính xác). | PaySim minh họa hoàn hảo cho Vertex Cut; số liệu IBM cần đo lại — không dùng số cũ vì đỉnh đã thay đổi. |
| **5. HÀNH VI TỘI PHẠM & GIAN LẬN** | | | |
| **Tỷ lệ gian lận (Fraud Rate)** | **$0.1291\%$** ($8.213$ giao dịch gian lận) | **$0.1019\%$** ($5.177$ giao dịch gian lận) — không đổi, không bị ảnh hưởng bởi bug. | Tỷ lệ gian lận ở mức $\sim 0.1\%$ phản ánh đúng hiện thực cực đoan của bài toán Imbalanced Data. |
| **Giai đoạn rửa tiền mô phỏng** | **Chỉ có Integration:** Chuyển tiền rồi rút sạch tiền mặt ra ngoài. | **Đủ 3 giai đoạn:** Bố trí (Placement), Phân lớp (Layering), Hội nhập (Integration). | IBM cho phép mô hình hóa trọn vẹn vòng đời rửa tiền (Money Laundering Lifecycle). |
| **Quy luật gian lận** | Cố định ở 2 loại: `TRANSFER` ($4.097$) và `CASH_OUT` ($4.116$). | Đa dạng qua nhiều kênh: Cheque, Credit Card, ACH, Wire, Reinvestment; nhiều khả năng dùng kỹ thuật Structuring (giả thuyết, Mục 5.4). | PaySim dễ bắt bằng filter đơn; IBM bắt buộc phải dùng thuật toán đồ thị + điều chỉnh ngưỡng theo dataset. |
| **6. ĐẶC TÍNH THỜI GIAN & TIỀN TỆ** | | | |
| **Biểu diễn thời gian (`step`)** | **Giờ mô phỏng:** Số nguyên tuần tự từ $1 \dots 744$ (30 ngày). | **Unix Epoch Seconds:** Số nguyên tính bằng giây (từ ngày $01/09 \dots 18/09/2022$). | IBM cung cấp độ phân giải thời gian chính xác tới từng giây; PaySim làm tròn theo giờ. |
| **Thuộc tính Tiền tệ (`currency`)** | Đơn nhất: 1 đồng tiền định danh nội bộ. | **Đa tiền tệ:** $15$ loại tiền tệ khác nhau. | Task 3 & 4 trên IBM bắt buộc phải lọc theo `payment_currency` trước khi so sánh `amount` — và cần kiểm tra phân phối tiền tệ trong tập gian lận cụ thể (Mục 5.4) trước khi chốt ngưỡng lọc. |
| **7. TÁC ĐỘNG TỚI CÁC TASK DOWNSTREAM** | | | |
| **Task 2: Degree & PageRank** | Tập trung phát hiện các Hub gom tiền cá nhân (Fan-in hubs). | Phân tích trung tâm thanh khoản của các Ngân hàng và Tập đoàn lớn — **cần chạy lại vì số đỉnh đã thay đổi sau bug fix**. | Nhóm so sánh phân phối Power-law giữa 2 dataset để chứng minh tính tổng quát. |
| **Task 3: Motif Finding** | **Pivot sang Relay Motif 2 bước:** `(a)-[TRANSFER]->(b)-[CASH_OUT]->(c)`. | **Chạy Motif 3 đỉnh khép kín thật**, nhưng phải: (1) khử trùng multigraph theo tam giác đỉnh, (2) không dùng nguyên ngưỡng $10k+USD của PaySim — cần đối chiếu phân phối tiền tệ/số tiền trong tập gian lận trước. | Đạt trọn vẹn điểm số barem: Vừa có chu trình khép kín thật (9 chuẩn theo thiết kế), vừa có chuỗi chuyển tiếp thực tế — nhưng phải trình bày đúng phương pháp, không báo cáo số thô chưa khử trùng. |
| **Task 4: Community Detection (LPA)** | Phát hiện các cụm lừa đảo dựa trên $1.769$ tài khoản cầu nối. | Phát hiện các liên minh rửa tiền xuyên ngân hàng giữa các Shell Companies — không bị ảnh hưởng bởi bug Bank ID vì `account_type` không đổi. | Khai thác trường `account_type` của IBM để định danh bản chất các công ty trong Fraud Ring. |
