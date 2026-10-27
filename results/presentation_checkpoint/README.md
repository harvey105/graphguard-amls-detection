# Presentation Checkpoints (GraphGuard)

Thư mục này chứa bản sao nguyên byte (exact byte-for-byte snapshot) của các bảng biểu, biểu đồ PNG và file ca bằng chứng từ kết quả nghiệm thu full-run (`checkpoints/GraphGuard_FULL_Report_Bundle_2026-10-24/`).

Mục đích:
- Cung cấp checkpoint cần thiết để các notebook trình chiếu (`PaySIM_presentation_demo.ipynb` và `IBM_presentation_demo.ipynb`) có thể chạy và hiển thị kết quả trên bất kỳ máy nào mà không phụ thuộc vào thư mục `.gitignore` (`checkpoints/`).
- Bảo toàn trọn vẹn số liệu đối chiếu của đợt nghiệm thu full-run mà không chạy lại tính toán nặng.

## Cấu trúc thư mục

- `MANIFEST.json`: Bảng kê khai SHA-256 hash, kích thước và nguồn gốc tương ứng từ bundle gốc.
- `common/`: Bảng tổng quan dùng chung hai dataset (18 model benchmark, baseline vs selected, model families, temporal splits).
- `paysim/`: Toàn bộ bảng CSV, hình ảnh PNG và ca mẫu JSON từ kết quả full-run PaySim 6.362.620 giao dịch.
- `ibm_aml/`: Toàn bộ bảng CSV, hình ảnh PNG và ca mẫu JSON từ kết quả full-run IBM AML 5.078.345 giao dịch.

> [!NOTE]
> Mọi file ở đây là bản sao trung thực chỉ đọc, không tự tạo lại số mới và không sửa đổi hash so với báo cáo nghiệm thu 24/10/2026.
