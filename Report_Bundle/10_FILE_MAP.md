# Bản đồ bundle

```text
00_START_HERE.md / .html     Mở đầu; HTML đọc offline bằng trình duyệt
01...09_*.md                Toàn bộ nội dung report, method, results, reliability, slides, dictionary
tables/                    Bảng tổng hợp 2 dataset + exact splits + feature lists + catalog
datasets/
  ibm_aml/                 Chỉ completed full IBM run
  paysim/                  Chỉ completed full PaySim run
    portable_summary.json  Summary và toàn bộ config/phases/metrics đã lưu
    tables/                Tất cả root CSV exports của full run; gồm9PRcurves
    figures/               PNG gốc: IBM13 / PaySim12
    examples/              TP/FP/FN minh họa của cả9families từ full test
    provenance/            report/run/artifact_index/frozen_rules giữ nguyên byte
    model_details/         Model archive + tree nodes/rules/vocab/scales/training của9families
comparison/                Full degree comparison CSV/PNG + provenance
notebooks/                 2 full notebooks có output +2HTML offline + cell guide
src/                       Exact source snapshot đã được hash trong hai accepted runs
scripts/run_n4_notebook.py Runner source dependency; không có job tự khởi chạy
tests/test_ibm_aml_etl.py   Source dependency được ghi trong accepted run, không thực thi
reference/                 PCCV và requirements cho ngữ cảnh
evidence/                  Existing full-only verifierlog + gate summary
validation/                Kết quả kiểm tra consistency khi đóng gói
BUNDLE_MANIFEST.json       Nguồn, SHA,bytes cho từng payload file
CHECKSUMS.sha256            Toàn bộ file trừ chính checksumfile
```

## Tìm code đúng phần

- [Full pipeline, historical snapshot, validation, frozen test](src/motif/pipeline.py)
- [Motif history/features và disk stages](src/motif/features.py)
- [Chronological3cycle IBM](src/ibm_aml/motif_finding.py), [relay PaySim](src/paysim/motif_finding.py)
- [Degree/PageRank](src/paysim/metrics.py), [LPA](src/paysim/community_detection.py)
- [Preprocessing,tree,exact metrics](src/motif/modeling.py), [evaluation](src/motif/evaluation.py)
- [Presentation,figures,case evidence](src/motif/presentation.py)
- [Independent audit](src/common/project_audit.py), [hardware guard](src/common/hardware_guard.py)
- [IBM ETL](src/ibm_aml/etl.py), [PaySim mapping](src/paysim/etl_mapping.py)

src/motif/toy_cycle.py là tên module của kernel3cycle dùng lại trong full pipeline; bundle không chứa toy/sample-run results. Folder source là snapshot để tra cứu, không là bản clone có đủ data/setup để chạy lại project. Dùng Git repo nếu cần phát triển tiếp.

## Provenance và cách chia sẻ

Chia sẻ ZIP toàn bộ; giữ cấu trúc khi giải nén. Original artifact_index liệt kê cả dữ liệu lớn không đóng gói để lưu chain of evidence, không có nghĩa các file đó nằm trong bundle. BUNDLE_MANIFEST mới là inventory thực tế của bundle. Các absolute producer paths trong original JSON/notebook được giữ để không làm sai chứng cứ gốc; các hướng dẫn mới dùng relative paths.

Chỉ reference và các full-run artifacts cần báo cáo được đưa vào. Không có agent_job.md, designs_Explain.md, designs.md hay Git credentials. Không có raw/full feature/prediction Parquet, partial/failed/sample benchmark. Không push Git khi đóng gói.
