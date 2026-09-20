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
└── ibm_aml/   # Pipeline IBM AML (bonus)
```

## Setup

1. `python -m venv .venv`
2. `\.venv\Scripts\Activate.ps1`
3. `pip install -r requirements.txt`

## Chạy

- Verify Task 1 PaySim: `python -m src.paysim.graph_analysis --sample`
- Task 2: `python -m src.paysim.metrics`
- Task 3: `python -m src.paysim.motif_finding`
- Task 4: `python -m src.paysim.community_detection`

## Requirements

- Python >= 3.10
- Java JDK 11 hoặc 17
- PySpark 3.5.1
- GraphFrames 0.12.2

## Team

N1 (Lead), N2 (DE), N3 (Metrics), N4 (Motif), N5/N6 (Community), N7 (Report)