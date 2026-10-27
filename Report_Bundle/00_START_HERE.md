# GraphGuard — FULL report & slides bundle

Mở **[00_START_HERE.html](00_START_HERE.html)** bằng trình duyệt để đọc offline, xem hình và notebook có sẵn output. Không cần Python, Java, Spark, Jupyter hay dataset gốc để viết report/slides từ bundle này.

## Đọc theo mục đích

1. [Tóm tắt kết quả](01_EXECUTIVE_SUMMARY.md): quy mô full, kết quả chính, thông điệp báo cáo.
2. [Phương pháp và tham số](02_METHODS_AND_PARAMETERS.md): pipeline, 9 families, ngưỡng và cách chia thời gian.
3. [IBM đầy đủ](03_IBM_FULL_RESULTS.md) và [PaySim đầy đủ](04_PAYSIM_FULL_RESULTS.md): bảng, benchmark, case, biểu đồ và diễn giải riêng dataset.
4. [So sánh và fusion](05_COMPARISON_AND_FUSION.md), [reliability](06_RELIABILITY_AND_VALIDATION.md).
5. [Dàn ý slides + lời trình bày](07_SLIDES_OUTLINE.md), [brief cho AI viết report](08_AI_REPORT_BRIEF.md).
6. [Từ điển CSV](09_DATA_DICTIONARY.md), [bản đồ file](10_FILE_MAP.md), [hướng dẫn từng code cell](notebooks/CELL_GUIDE.md).

## Phạm vi chính xác

Chỉ lấy hai run `scope=full`, `status=completed` đã nghiệm thu ngày 24/10/2026. IBM sử dụng **toàn bộ HI-Small được chọn trong project**, không phải toàn bộ mọi biến thể của bộ dữ liệu IBM. PaySim sử dụng toàn bộ dataset được chọn. Test là holdout theo thời gian của mỗi full dataset; không train trên test.

Các file examples, top10/top50 và case evidence là **minh họa trích từ full results**, không phải sampled dataset thay thế full benchmark. Mọi benchmark chính tính trên toàn bộ holdout của full run. Không đưa output sample, toy-run, failed/partial run hay kế hoạch cá nhân vào bộ kết quả.

Bundle là snapshot kết quả để báo cáo, không phải bộ dữ liệu để huấn luyện lại: không đóng gói raw CSV, toàn bộ feature/prediction Parquet và checkpoints nhiều GB. Mọi bảng tổng hợp/PR/CI/case/hình đã xuất đều có; model đã fit cũng được lưu riêng. Không thể tự tính một thống kê mới chưa được export trên hàng triệu giao dịch chỉ bằng bundle này.

## Sử dụng trên máy yếu

Giải nén một lần; mở HTML để đọc, PNG để chèn slides, CSV UTF-8 BOM để mở Excel. Notebook HTML là bản xem tĩnh có code + output; không bấm Run notebook. Với AI, gửi brief, hai báo cáo dataset và CSV cần dùng; không cần tải toàn bộ code nếu chỉ viết nội dung.

Tỷ lệ trong CSV nằm trong [0,1]; Markdown chuyển thành %. Mọi số đếm giữ nguyên. Không cộng USD với currency khác; không gộp F1 của hai dataset. Giữ nguyên số 0 nếu artifacts ghi nhận 0.

## Nguồn và toàn vẹn

[BUNDLE_MANIFEST.json](BUNDLE_MANIFEST.json) ghi nguồn, SHA-256 và kích thước từng file; [CHECKSUMS.sha256](CHECKSUMS.sha256) dùng kiểm tra khi chuyển máy. [Kết quả kiểm tra bundle](validation/bundle_checks.json) chỉ xác nhận đóng gói và tính nhất quán của exports hiện có, không phải chạy lại pipeline. Original report/run giữ nguyên byte; đường dẫn Windows trong bản gốc là provenance của máy tạo kết quả, không phải đường dẫn bắt buộc trên máy người đọc.

Không chạy lại Spark, ETL, notebook hoặc training khi tạo bundle. Không push Git.
