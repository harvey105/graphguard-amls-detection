# GraphGuard: Distributed Graph Analytics with GraphFrames

Dự án Big Data phát hiện rửa tiền (AML) sử dụng GraphFrames và PySpark.

## Datasets

- **PaySim** (chính): `data/processed/sample/paysim/`
- **IBM AML** (bonus): `data/processed/sample/ibm_aml/`

## Cấu trúc

```text
src/
├── common/    # Utility dùng chung
├── paysim/    # Pipeline PaySim
├── motif/     # Demo N4 ngày 21/9
└── ibm_aml/   # Pipeline IBM AML (bonus)
```

## Setup và chạy trên Windows PowerShell

Cần **Python 3.12** và **JDK 17** trên Windows. Kiểm tra với `py -3.12 --version` và `java -version`. Nếu thiếu, cài rồi mở PowerShell mới:

```powershell
winget install --id Python.Python.3.12 --exact
winget install --id EclipseAdoptium.Temurin.17.JDK --exact
```

Tại thư mục gốc repo, chạy script PowerShell để tạo `.venv` Windows, cài `requirements.txt`, kiểm tra `pip` và tải công cụ Hadoop 3.3.4 cho Windows (kiểm tra SHA256 trước khi dùng):

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\setup_windows.ps1
```

Chạy demo N4 ngày 21/9 và thực thi lại notebook bằng cùng môi trường:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\run_n4.ps1
```

Mở notebook trong VS Code với kernel `GraphGuard (.venv Windows)`. Xem [báo cáo motif N4](docs/N4_Motif_Toy_2026-09-21.md) để đọc truy vấn và kết quả. Không cần kích hoạt `.venv` hoặc thay đổi execution policy toàn hệ thống. Mã khởi tạo Spark tự cấu hình `JAVA_HOME`, `HADOOP_HOME`, `SPARK_HOME`, Python worker và ánh xạ đường dẫn repo có dấu/khoảng trắng sang một ổ đĩa tạm bằng `subst`.

Task 1 PaySim mẫu (khi cần): `& .\.venv\Scripts\python.exe -m src.paysim.graph_analysis --sample`. Các module Task 2–4 của PaySim/IBM còn theo lịch phân công trong CSV.

## Requirements

- Python 3.12 cho `requirements.txt` hiện tại
- Java JDK 17
- PySpark 3.5.1
- GraphFrames 0.12.2

## Team

N1 (Lead), N2 (DE), N3 (Metrics), N4 (Motif), N5/N6 (Community), N7 (Report)

Agent của repo dùng [AGENTS.md](AGENTS.md) và [skill GraphGuard PowerShell](.agents/skills/graphguard-powershell/SKILL.md).
