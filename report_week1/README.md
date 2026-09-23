# Báo cáo hoàn thành tuần 1

Phạm vi được chốt theo `BDA - PCCV - Trang tính1.csv`. Các mục đã hoàn thành
trước lượt này được kiểm tra bằng artifact sẵn có và không chạy/làm lại chỉ để
tạo bản trùng lặp.

## Checklist

| Deliverable tuần 1 | Trạng thái | Bằng chứng |
|---|---|---|
| Task 1 PaySim + log `[PASS]` | DONE trước lượt này | `results/paysim/task1_verification_{full,sample}.log` |
| `get_graph_session()` + README | DONE trước lượt này | `src/common/spark_session.py`, `README.md` |
| N4 toy 3-cycle `graph.find()` | DONE trước lượt này | `src/motif/toy_cycle.py`, notebook, JSON |
| LPA update/convergence/non-determinism note | DONE trước lượt này | `docs/CC_vs_LPA_Note.md` |
| Review Task 1 và refactor `src/` | DONE trước lượt này | history + handoff docs |
| Mục 3.2 Vertex Cut vs Edge Cut | **DONE + REVIEWED** | `PartA_3.2_Vertex_Cut_vs_Edge_Cut.md` |
| Mục 3.3 PageRank | **DONE + REVIEWED + FIXED** | `docs/PartA_Theory.md`, review record |
| Mục 3.4 CC vs LPA | **DONE + REVIEWED** | `PartA_3.4_CC_vs_LPA.md` |
| Đánh giá community PaySim | **DONE** | `PaySim_Community_Assessment.md` |
| IBM schema research + ETL + Parquet | **DONE + PASS** | source, research note, manifest, run log |
| Biên bản sync cuối tuần | **DONE (technical record)** | `Weekly_Sync_2026-09-27.md` |

## Kết quả IBM AML

- Windows Python 3.12.10, JDK 17.0.20.1, `pip check`: PASS.
- 5.078.345 raw transactions/edges.
- 515.088 unique `bank::account` vertices.
- 5.177 laundering-labelled edges.
- 0 null required fields, 0 duplicate vertex IDs, 0 dangling src/dst.
- Full vertices/edges Parquet round-trip: PASS.

`ibm_aml_etl_run.log` là lượt build/round-trip khớp với implementation cuối.
Warning tên header là dự kiến vì file có hai cột literal cùng tên `Account`, còn
schema nội bộ đặt tên phân biệt và được Spark áp theo vị trí.

## Runtime note

Spark trên Windows có thể ghi warning lúc shutdown vì JAR tạm còn bị process
lock. Warning xuất hiện **sau** dòng `[PASS]` và không làm sai output/count;
manifest và exit code là tiêu chí kết quả. Không dùng WSL run làm bằng chứng.
