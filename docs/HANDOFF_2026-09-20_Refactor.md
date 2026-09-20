# HANDOFF: Refactor cấu trúc repo GraphGuard (20/9/2026)

> **Người thực hiện:** Tuệ Minh (Lead)
> **Người nhận:** Cả nhóm (N2-N7)
> **Trạng thái:** Đã push lên `main` — cần pull về để tiếp tục làm việc

---

## 1. TÓM TẮT THAY ĐỔI

Repo đã được **refactor lại cấu trúc** để:
- Tách riêng code của **PaySim** và **IBM AML** (dataset bonus)
- Thêm thư mục `common/` cho utility dùng chung
- Chuẩn bị skeleton cho các task sắp tới (Task 2, 3, 4)
- Đảm bảo nhóm có nơi rõ ràng để lưu kết quả

**Lý do:** Hiện tại tất cả code nằm lẫn ở `src/`. Khi bắt đầu làm IBM AML (từ 23/9), nếu không tách ngay từ đầu sẽ bị conflict và khó quản lý.

---

## 2. NHỮNG GÌ ĐÃ THAY ĐỔI

### File đã di chuyển

| Đường dẫn cũ | Đường dẫn mới |
|--------------|---------------|
| `src/graph_analysis.py` | `src/paysim/graph_analysis.py` |
| `src/export_parquet.py` | `src/paysim/export_parquet.py` |
| `src/utils/etl_mapping.py` | `src/paysim/etl_mapping.py` |
| `data/processed/sample/vertices.parquet` | `data/processed/sample/paysim/vertices.parquet` |
| `data/processed/sample/edges.parquet` | `data/processed/sample/paysim/edges.parquet` |

Folder `src/utils/` đã được loại bỏ sau khi move file.

### File mới

| File | Vai trò |
|------|---------|
| `src/common/spark_session.py` | Khởi tạo Spark với GraphFrames dùng chung |
| `src/common/graph_utils.py` | Load, save và kiểm tra GraphFrame |
| `src/paysim/metrics.py` | Placeholder Task 2 PaySim |
| `src/paysim/motif_finding.py` | Placeholder Task 3 PaySim |
| `src/paysim/community_detection.py` | Placeholder Task 4 PaySim |
| `src/ibm_aml/etl.py` | Placeholder IBM ETL |
| `src/ibm_aml/metrics.py` | Placeholder Task 2 IBM |
| `src/ibm_aml/motif_finding.py` | Placeholder Task 3 IBM |
| `src/ibm_aml/community_detection.py` | Placeholder Task 4 IBM |
| `README.md` | Hướng dẫn setup và chạy |
| `docs/PartA_Theory.md` | Placeholder báo cáo lý thuyết |
| `docs/PartB_Experiments.md` | Placeholder báo cáo thí nghiệm |
| `docs/PartB_Comparison.md` | Placeholder báo cáo so sánh |
| `results/paysim/task1_verification_full.log` | Bằng chứng verify Task 1 trên full graph |
| `results/paysim/task1_verification_sample.log` | Bằng chứng verify Task 1 trên sample graph |

Ngoài ra, các package `__init__.py` và `.gitkeep` cho thư mục dữ liệu/kết quả đã được thêm.

### Cập nhật kỹ thuật

- `.gitignore` thêm rule cho `results/**/*.parquet` và `checkpoints/`.
- Import path đổi từ `src.utils.etl_mapping` sang `src.paysim.etl_mapping`.
- Code ưu tiên `data/processed/paysim/`, fallback về `data/processed/` kèm warning.
- Fallback kiểm tra sự tồn tại của cả `vertices.parquet` và `edges.parquet`, không chỉ thư mục chứa `.gitkeep`.
- Warning runtime dùng ASCII để tương thích Windows `cp1252`.

---

## 3. SAU KHI PULL VỀ

### Bước 1: Pull code mới

```powershell
cd <đường-dẫn-repo-của-bạn>\graphguard-amls-detection
git pull origin main
```

### Bước 2: Kích hoạt môi trường và kiểm tra

```powershell
.\.venv\Scripts\Activate.ps1
python -m src.paysim.graph_analysis --sample
```

Kỳ vọng cuối log:

```text
[+] Task 1 Completed Successfully. GraphFrame is fully operational.
```

### Bước 3: Chạy các task tiếp theo

```powershell
python -m src.paysim.metrics
python -m src.paysim.motif_finding
python -m src.paysim.community_detection
```

Các module Task 2-4 hiện là placeholder, chờ người phụ trách triển khai.

---

## 4. KẾT QUẢ VERIFY

- Task 1 FULL: exit code `0`.
- Task 1 SAMPLE: exit code `0`.
- Full graph: 9,073,900 vertices và 6,362,620 edges.
- Sample graph: 194,182 vertices và 100,728 edges.
- Sample referential integrity: `0 dangling src`, `0 dangling dst`.
- Cả hai log verification được lưu trong `results/paysim/`.

## 5. LƯU Ý VỀ DỮ LIỆU

- Raw CSV và full Parquet không được commit vì dung lượng lớn.
- Sample Parquet được track tại `data/processed/sample/paysim/`.
- Nếu full Parquet chưa nằm ở `data/processed/paysim/`, code sẽ fallback về vị trí cũ và in warning.
