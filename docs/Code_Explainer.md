# Code Explainer — GraphGuard

Giải thích code từng Part bằng ngôn ngữ đơn giản, phục vụ Q&A cuối kỳ.

**Người viết:** N1 (Lead)
**Cập nhật:** 25/09/2026

---

## Part 1 — Data Foundation

### File `src/paysim/etl_mapping.py`
- **Ai viết:** Person 2 — phụ trách ETL PaySim.
- **Làm gì:** Đổi bảng giao dịch PaySim thành hai bảng đỉnh và cạnh cho GraphFrames.
- **Input:** Bảng giao dịch thô `raw_df`.
- **Output:** `vertices_df` gồm `id`, `account_type`, `balance`; `edges_df` gồm `src`, `dst`, `amount`, `step`, `type`, `isFraud`.

**Logic chính:**
1. Gom `nameOrig` và `nameDest` thành danh sách tài khoản duy nhất.
2. Với 1.769 tài khoản vừa gửi vừa nhận, dùng `F.max_by("balance", "step")` để lấy số dư ở lần xuất hiện có `step` lớn nhất; dùng `newbalance*` vì đó là số dư sau giao dịch và phản ánh trạng thái cuối.
3. Suy ra loại tài khoản từ ký tự đầu của mã: `C` là Customer, `M` là Merchant.
4. Đổi tên cột giao dịch thành `src`/`dst`; giữ `step` là số nguyên, không đổi thành ngày giờ.
5. Giữ thêm `type` để tìm relay `TRANSFER → CASH_OUT`, vì PaySim không có chu trình 3 đỉnh; giữ `isFraud` để đối chiếu với nhãn gian lận thật.

**Câu hỏi thầy có thể hỏi:**
- "Tại sao dùng `max_by` thay vì lấy dòng bất kỳ?" → Vì cần số dư ở giao dịch cuối của mỗi tài khoản; `max_by` lấy giá trị đi cùng `step` lớn nhất và gọn hơn window function.
- "Vì sao dùng `newbalance*`, không dùng `oldbalance*`?" → `newbalance*` là số dư sau giao dịch cuối, còn `oldbalance*` vẫn là trạng thái trước giao dịch đó.
- "Tại sao `step` không đổi thành datetime?" → `step` chỉ là giờ mô phỏng từ 1 đến 744, không phải thời gian thực nên giữ nguyên số nguyên.

### File `src/paysim/export_parquet.py`
- **Ai viết:** Person 2 — Task 2.4, xuất dữ liệu và kiểm tra chất lượng.
- **Làm gì:** Đọc CSV PaySim, tạo graph tables, kiểm tra rồi lưu thành Parquet.
- **Input:** CSV PaySim tại `data/raw/paysim/` hoặc đường dẫn raw dự phòng.
- **Output:** Parquet đầy đủ trong `data/processed/paysim/` và sample khoảng 100.000 cạnh trong `data/processed/sample/paysim/`.

**Logic chính:**
1. Đọc CSV bằng schema cố định, tránh Spark tự đoán sai kiểu dữ liệu.
2. Gọi hai hàm ETL, cache kết quả và kiểm tra số đỉnh, số cạnh, null và cạnh treo.
3. Xác nhận có 9.073.900 đỉnh, 6.362.620 cạnh và số cạnh bằng số dòng raw.
4. Ghi Parquet nén Snappy; tạo sample cạnh rồi lấy đúng các đỉnh liên quan để sample không bị thiếu đỉnh.
5. Đọc lại Parquet từ đĩa, đếm lại và in schema để xác nhận dữ liệu đã ghi đúng.

**Câu hỏi thầy có thể hỏi:**
- "Làm sao biết có 0 dangling edges?" → Dùng `left_anti` join cạnh với bảng đỉnh ở cả `src` và `dst`; kết quả cả hai phía đều bằng 0 mới đạt.
- "Vì sao phải đọc lại Parquet sau khi ghi?" → Để kiểm tra file thực sự trên đĩa, không chỉ kiểm tra DataFrame còn nằm trong bộ nhớ.
- "Vì sao sample phải lấy cả vertices?" → Mỗi cạnh phải có đỉnh nguồn và đích tương ứng; nếu chỉ lấy cạnh thì có thể tạo graph thiếu đỉnh.

### File `src/paysim/graph_analysis.py`
- **Ai viết:** Person 2 và Person 1 — đồng sở hữu Task 1.
- **Làm gì:** Tạo GraphFrame và xác nhận graph PaySim hoạt động đúng.
- **Input:** Parquet đã xuất, hoặc CSV raw khi dùng `--from-raw`; có chế độ `--sample`.
- **Output:** GraphFrame, báo cáo schema/số lượng, kiểm tra raw và các metric degree cơ bản.

**Logic chính:**
1. Khởi tạo Spark có GraphFrames; tự chọn gói JVM phù hợp với phiên bản Spark đang cài.
2. Đọc Parquet hoặc chạy ETL trực tiếp từ CSV, sau đó tạo `GraphFrame(vertices_df, edges_df)`.
3. Kiểm tra cột bắt buộc, số lượng đỉnh/cạnh hoặc tính toàn vẹn của sample.
4. Khi chạy `--from-raw`, lấy vài cạnh trong graph và tìm dòng giao dịch tương ứng trong CSV gốc.
5. Chạy thử `inDegrees` và `outDegrees` để chứng minh GraphFrames thật sự hoạt động.

**Câu hỏi thầy có thể hỏi:**
- "Verify với raw CSV thế nào?" → Với `--from-raw`, mỗi cạnh mẫu được đối chiếu theo `src`, `dst`, `step` và `amount` với CSV gốc.
- "Vì sao sample không so với số đỉnh cố định?" → Sample lấy ngẫu nhiên nên số dòng thay đổi; thay vào đó kiểm tra mọi đầu mút cạnh đều có trong vertices.
- "Tại sao cần GraphFrame thay vì chỉ DataFrame?" → GraphFrame hiểu riêng bảng đỉnh/cạnh và cung cấp phép đo như in-degree, out-degree.

### File `src/common/spark_session.py`
- **Ai viết:** Person 2 — tiện ích Spark dùng chung cho PaySim và IBM AML.
- **Làm gì:** Tạo SparkSession đã gắn GraphFrames và cấu hình phù hợp cho dự án.
- **Input:** Tên ứng dụng và tùy chọn bộ nhớ, số partition, checkpoint, cấu hình thêm.
- **Output:** Một `SparkSession` sẵn sàng chạy GraphFrames.

**Logic chính:**
1. Chuẩn bị runtime Windows trước khi Spark chạy.
2. Dựa vào phiên bản PySpark để chọn đúng tọa độ GraphFrames Spark 3 hoặc Spark 4.
3. Đặt driver memory, số partition, nén Parquet và các tối ưu AQE.
4. Giảm log xuống mức WARN để kết quả dễ đọc.
5. Nếu có `checkpoint_dir`, tạo thư mục và đăng ký cho các thuật toán lineage sâu như LPA/Connected Components.

**Câu hỏi thầy có thể hỏi:**
- "Tại sao phải chọn coordinate theo phiên bản Spark?" → GraphFrames phụ thuộc phiên bản Spark và Scala; chọn đúng giúp JVM tìm đúng gói tương thích.
- "Checkpoint dùng để làm gì?" → Lưu trạng thái trung gian, tránh lineage quá dài gây lỗi khi thuật toán lặp nhiều vòng.
- "Gọi `get_graph_session` nhiều lần có đổi cấu hình không?" → Không chắc; `getOrCreate()` có thể trả session cũ, nên muốn đổi cấu hình phải dừng session trước.

### File `src/common/graph_utils.py`
- **Ai viết:** Tiện ích dùng chung của nhóm, do Person 2 duy trì.
- **Làm gì:** Đọc, ghi và kiểm tra tính toàn vẹn của GraphFrame cho cả hai dataset.
- **Input:** SparkSession, thư mục Parquet hoặc một GraphFrame.
- **Output:** GraphFrame, các file Parquet, hoặc báo cáo kiểm tra dạng dictionary.

**Logic chính:**
1. `load_graph` kiểm tra đủ `vertices.parquet` và `edges.parquet`, rồi tạo GraphFrame.
2. `save_graph` ghi hai bảng ra thư mục đích bằng Parquet Snappy.
3. `check_integrity` đếm đỉnh/cạnh, tìm null và tìm cạnh có `src` hoặc `dst` không tồn tại.
4. Hàm cũng đếm self-loop; PaySim kỳ vọng 0, còn IBM AML có thể có self-loop.
5. Kết quả trả về dạng dictionary và có thể in báo cáo PASS/FAIL; nên cache DataFrame trước vì hàm gọi nhiều phép `count()`.

**Câu hỏi thầy có thể hỏi:**
- "`left_anti` dùng để kiểm tra gì?" → Nó giữ lại các cạnh không tìm thấy đỉnh tương ứng, nên đếm được dangling edges.
- "`dangling_edges` có thể đếm trùng không?" → Có về mặt lý thuyết nếu cùng một cạnh thiếu cả hai đầu; vì vậy hàm in riêng dangling ở phía nguồn và phía đích.
- "Vì sao phải cache trước khi kiểm tra?" → Mỗi `count()` là một hành động Spark; cache giúp không phải đọc và tính lại toàn bộ pipeline nhiều lần.

## Part 2 — Structural & Motif

**Placeholder — chờ N4/N6 bổ sung.**

Nội dung cần bổ sung: giải thích degree distribution, PageRank, motif/relay `TRANSFER → CASH_OUT`, cách đọc biểu đồ và cách đối chiếu `isFraud`.

## Part 3 — Community

**Placeholder — chờ N5 bổ sung.**

Nội dung cần bổ sung: giải thích thuật toán phát hiện cộng đồng, ý nghĩa của cluster và cách đánh giá cộng đồng có dấu hiệu bất thường.

## Part 4 — Integration

**Placeholder — chờ N7 bổ sung.**

Nội dung cần bổ sung: cách ghép kết quả ETL, structural analysis, motif và community thành kết luận AML cuối cùng.
