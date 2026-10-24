# Full-system đã hoàn tất trên hai datasets — 24/10/2026

**DONE FIXED — code, notebook execution và full project gate đã kiểm chứng trên native Windows; chưa push Git.** Software/data integrity PASS và predictive reliability là hai kết luận riêng.

| Dataset | Family | Precision | Recall | F1 | AP | Alerts |
| --- | --- | --- | --- | --- | --- | --- |
| IBM AML | transaction_only | 9.07% | 48.30% | 15.27% | 5.62% | 9,584 |
| IBM AML | full_fusion [selected] | 10.09% | 27.79% | 14.80% | 5.87% | 4,956 |
| PaySim | transaction_only | 81.01% | 19.67% | 31.65% | 17.00% | 1,032 |
| PaySim | full_fusion | 58.31% | 26.00% | 35.96% | 28.98% | 1,895 |
| PaySim | validation-selected: without_centrality | 58.12% | 26.09% | 36.02% | 26.58% | 1,908 |

Mọi family dùng cùng full input/index, causal features và test denominator trong từng dataset. IBM target là laundering; PaySim target là fraud. Không gộp F1 hai dataset hoặc xem một cảnh báo là kết luận pháp lý.

## IBM AML — `run_20261024T081350344149Z`

- Notebook: [IBM_full_system.ipynb](../notebooks/IBM_full_system.ipynb); 35 code cells, 24 definitions khớp module Python.
- Full input: 518,581 accounts / 5,078,345 transactions / 5,177 positives. Test: 1,017,821 rows / 1,799 positives.
- Frozen rule `full_fusion`, threshold=0.5; TP=500, FP=4,456, FN=1,299, TN=1,011,566.
- Precision95% Wilson: [9.28%, 10.96%]; recall95% Wilson: [25.77%, 29.91%]. Đây là nominal row-binomial CI, chưa điều chỉnh account/time correlation.
- F1 qua5 test periods: 3.32%–28.79%; đây là quan sát biến động, không phải chứng nhận ổn định cao.
- Peak job commit toàn các phase=6.27/8 GiB; minimum available host RAM=13.39 GiB; sampled maximum job CPU=91.67% (toàn máy).

| Family | Threshold | Precision | Recall | F1 | AP | Selected on validation |
| --- | --- | --- | --- | --- | --- | --- |
| transaction_only | 0.5 | 9.07% | 48.30% | 15.27% | 5.62% | False |
| transaction_novelty | 0.5 | 9.07% | 48.30% | 15.27% | 5.62% | False |
| transaction_centrality | 0.5 | 9.15% | 49.14% | 15.42% | 5.83% | False |
| motif_assisted | 0.5 | 10.67% | 25.85% | 15.10% | 5.67% | False |
| transaction_community | 0.5 | 9.07% | 48.30% | 15.27% | 5.62% | False |
| full_fusion | 0.5 | 10.09% | 27.79% | 14.80% | 5.87% | True |
| without_centrality | 0.5 | 10.67% | 25.85% | 15.10% | 5.67% | False |
| without_motifs | 0.5 | 8.84% | 50.31% | 15.03% | 5.95% | False |
| without_community | 0.5 | 10.95% | 26.63% | 15.52% | 5.83% | False |

### Độ ổn định theo thời gian của model được chọn

| Period (1–5) | Transactions | Positives | TP | FP | FN | F1 | AP |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | 203929 | 205 | 44 | 693 | 161 | 9.34% | 2.82% |
| 2 | 203134 | 141 | 19 | 985 | 122 | 3.32% | 1.13% |
| 3 | 203756 | 198 | 56 | 972 | 142 | 9.14% | 2.89% |
| 4 | 203828 | 159 | 42 | 886 | 117 | 7.73% | 2.45% |
| 5 | 203174 | 1096 | 339 | 920 | 757 | 28.79% | 16.89% |

### Motif coverage trên cùng test

| Motif | Covered transactions | Covered positives | Positive coverage |
| --- | --- | --- | --- |
| cycle3_count | 132 | 41 | 2.28% |
| relay_24h | 599171 | 461 | 25.63% |
| relay_168h | 740099 | 795 | 44.19% |
| reciprocal_24h | 257 | 39 | 2.17% |
| reciprocal_168h | 1579 | 109 | 6.06% |
| fanin_24h | 427877 | 909 | 50.53% |
| fanin_168h | 706216 | 1395 | 77.54% |
| fanout_24h | 608459 | 532 | 29.57% |
| fanout_168h | 709096 | 791 | 43.97% |

Coverage là hậu kiểm cấu trúc sau construction không dùng nhãn; các nhóm overlap. Coverage không phải TP hoặc recall của classifier.

### Ngân sách review (selected model)

| Budget | K | TP@K | Precision@K | Recall@K |
| --- | --- | --- | --- | --- |
| 0.10% | 1018 | 105 | 10.31% | 5.84% |
| 0.50% | 5090 | 505 | 9.92% | 28.07% |
| 1.00% | 10179 | 789 | 7.75% | 43.86% |

### Benchmark thực thi

| Phase | Seconds | Throughput / cost | Đơn vị | Job CPU % | Cumulative peak commit GiB |
| --- | --- | --- | --- | --- | --- |
| raw_reconciliation | 66.024 | 76,916.65 | input transactions/s | 46.5 | 5.22 |
| centrality_full | 39.927 | 127,190.75 | input transactions/s | 35.67 | 5.23 |
| communities_full | 69.736 | 72,822.43 | input transactions/s | 38.32 | 5.24 |
| motif_baseline | 11.112 | 824,369.06 | diagnostic prediction rows/s | 41.39 | 5.24 |
| motif_features | 149.841 | 33,891.56 | feature/audit rows/s | 62.5 | 6.21 |
| motif_benchmark | 7.586 | 669,436.46 | feature/audit rows/s | 50.67 | 6.21 |
| common_features | 749.761 | 6,773.29 | feature/audit rows/s | 41.18 | 6.27 |
| validation | 427.915 | 15.85 | s/fit incl. shared preprocessing | 50.93 | 6.27 |
| frozen_test | 238.956 | 38,335.04 | test predictions/s incl. refit/export | 48.16 | 5.99 |
| reliability | 7.449 | 1,229,747.48 | diagnostic prediction rows/s | 11.21 | 5.99 |

Graph throughput chuẩn hóa theo full input E, không phải số lần đọc vật lý sau mọi iteration. Validation cost chia27 fits; frozen-test throughput tính9 × test N và bao gồm refit/export/replay. CPU đo theo khoảng giữa phase milestones, có thể bao gồm hiển thị/I/O; peak commit là high-water mark tích lũy trong process. Các bước serial/I/O không cần duy trì90–100% CPU.

## PaySim — `run_20261024T084918669391Z`

- Notebook: [PaySIM_full_system.ipynb](../notebooks/PaySIM_full_system.ipynb); 36 code cells, 25 definitions khớp module Python.
- Full input: 9,073,900 accounts / 6,362,620 transactions / 8,213 positives. Test: 1,248,736 rows / 4,250 positives.
- Frozen rule `without_centrality`, threshold=0.7; TP=1,109, FP=799, FN=3,141, TN=1,243,687.
- Precision95% Wilson: [55.90%, 60.32%]; recall95% Wilson: [24.80%, 27.44%]. Đây là nominal row-binomial CI, chưa điều chỉnh account/time correlation.
- F1 qua5 test periods: 27.05%–40.90%; đây là quan sát biến động, không phải chứng nhận ổn định cao.
- Peak job commit toàn các phase=6.58/8 GiB; minimum available host RAM=13.02GiB; sampled maximum job CPU=90.06% (toàn máy).

| Family | Threshold | Precision | Recall | F1 | AP | Selected on validation |
| --- | --- | --- | --- | --- | --- | --- |
| transaction_only | 0.7 | 81.01% | 19.67% | 31.65% | 17.00% | False |
| transaction_novelty | 0.7 | 63.85% | 26.09% | 37.05% | 20.29% | False |
| transaction_centrality | 0.5 | 64.06% | 25.79% | 36.77% | 22.71% | False |
| motif_assisted | 0.7 | 58.12% | 26.09% | 36.02% | 26.58% | False |
| transaction_community | 0.7 | 63.85% | 26.09% | 37.05% | 20.29% | False |
| full_fusion | 0.7 | 58.31% | 26.00% | 35.96% | 28.98% | False |
| without_centrality | 0.7 | 58.12% | 26.09% | 36.02% | 26.58% | True |
| without_motifs | 0.5 | 64.06% | 25.79% | 36.77% | 22.71% | False |
| without_community | 0.7 | 58.31% | 26.00% | 35.96% | 28.98% | False |

### Độ ổn định theo thời gian của model được chọn

| Period (1–5) | Transactions | Positives | TP | FP | FN | F1 | AP |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | 254687 | 226 | 61 | 140 | 165 | 28.57% | 15.36% |
| 2 | 266247 | 216 | 66 | 206 | 150 | 27.05% | 16.10% |
| 3 | 271053 | 116 | 35 | 47 | 81 | 35.35% | 13.63% |
| 4 | 207968 | 1336 | 371 | 107 | 965 | 40.90% | 37.18% |
| 5 | 248781 | 2356 | 576 | 299 | 1780 | 35.65% | 29.08% |

### Motif coverage trên cùng test

| Motif | Covered transactions | Covered positives | Positive coverage |
| --- | --- | --- | --- |
| cycle3_count | 0 | 0 | 0.00% |
| relay_24h | 5 | 0 | 0.00% |
| relay_168h | 21 | 0 | 0.00% |
| reciprocal_24h | 0 | 0 | 0.00% |
| reciprocal_168h | 0 | 0 | 0.00% |
| fanin_24h | 240844 | 154 | 3.62% |
| fanin_168h | 602017 | 895 | 21.06% |
| fanout_24h | 186 | 0 | 0.00% |
| fanout_168h | 1226 | 1 | 0.02% |

Coverage là hậu kiểm cấu trúc sau construction không dùng nhãn; các nhóm overlap. Coverage không phải TP hoặc recall của classifier.

### Ngân sách review (selected model)

| Budget | K | TP@K | Precision@K | Recall@K |
| --- | --- | --- | --- | --- |
| 0.10% | 1249 | 900 | 72.06% | 21.18% |
| 0.50% | 6244 | 1523 | 24.39% | 35.84% |
| 1.00% | 12488 | 2044 | 16.37% | 48.09% |

### Benchmark thực thi

| Phase | Seconds | Throughput / cost | Đơn vị | Job CPU % | Cumulative peak commit GiB |
| --- | --- | --- | --- | --- | --- |
| raw_reconciliation | 58.007 | 109,687.11 | input transactions/s | 51.03 | 5.31 |
| centrality_full | 102.446 | 62,107.06 | input transactions/s | 59.36 | 5.93 |
| communities_full | 271.678 | 23,419.71 | input transactions/s | 56.99 | 5.99 |
| motif_baseline | 27.041 | 415,614.22 | diagnostic prediction rows/s | 57.52 | 5.99 |
| motif_features | 103.701 | 61,355.44 | feature/audit rows/s | 61.12 | 6.06 |
| motif_benchmark | 8.083 | 787,160.71 | feature/audit rows/s | 54.04 | 6.06 |
| common_features | 1133.274 | 5,614.37 | feature/audit rows/s | 49.93 | 6.58 |
| validation | 437.617 | 16.21 | s/fit incl. shared preprocessing | 51.11 | 6.58 |
| frozen_test | 257.488 | 43,647.18 | test predictions/s incl. refit/export | 46.65 | 6.58 |
| reliability | 7.900 | 1,422,610.63 | diagnostic prediction rows/s | 12.28 | 6.58 |

Graph throughput chuẩn hóa theo full input E, không phải số lần đọc vật lý sau mọi iteration. Validation cost chia27 fits; frozen-test throughput tính9 × test N và bao gồm refit/export/replay. CPU đo theo khoảng giữa phase milestones, có thể bao gồm hiển thị/I/O; peak commit là high-water mark tích lũy trong process. Các bước serial/I/O không cần duy trì90–100% CPU.

## Đã kiểm chứng và giới hạn

- AST source copies khớp Python; source/input/config/output hashes gắn đúng run. Không relabel outputs lịch sử.
- All-account metrics và all-community summaries; full raw reconciliation; full features/event index; causal snapshot checks;9matchedfamilies; selected-model reload toàn test; independent confusion/AP và selected temporal metrics đều PASS.
- Một lượt đầu bị JVM heap OOM do deserialized local checkpoints khi tăng concurrency. Đã dừng, kiểm tra stack, sửa sang Parquet stages và giới hạn writer/read buffers, xác minh tiny fixture rồi chạy full mới với cùng RAM caps. Lượt lỗi được giữ là failed; không dùng làm evidence đạt.
- IBM bị lỗi display sau validation; sửa notebook-only column rendering và verified resume cùng source/input/config. Frozen rule giữ nguyên. Phase runtimes có thể thuộc các kernel trong cùng logical run; không dùng elapsed của kernel cuối làm toàn bộ thời gian full run.
- Dữ liệu tổng hợp và reused internal temporal holdout. Cần untouched external holdout cho generalization; không kết luận mọi motif/community là laundering.
- GPU chưa có backend được xác minh; CPU 100% capacity, affinity toàn bộ, Spark concurrency theo heap; memory guard/mutex/spill giữ nguyên.
- Full project gate chạy đúng native PowerShell entry point của make check, exit0. Log chi tiết được tạo khi chạy [project gate](../scripts/check_project.ps1).


---

## Tài liệu / kết quả lịch sử theo scope khi ghi

# Part B — Experiments

> **Scope/date:** các bảng bên dưới là kết quả bàn giao trước full-system ngày 23/10. IBM full-system đã PASS; PaySim dừng theo user tại8/15cells/snapshot5 và gate chung còn pending. Xem [hướng dẫn code và notebook](Code_Explainer.md); không lấy sample hay motif-only test ở đây làm kết quả fusion mới.

## Task 1 — Graph Construction (15đ)

### 1.1. Mục tiêu
- Xây Vertices/Edges DataFrame theo schema đề bài
- Khởi tạo GraphFrame
- Verify integrity

### 1.2. Kết quả log lịch sử

Bảng/log dưới đây được giữ từ bàn giao trước. Trạng thái mới, phạm vi raw reconciliation và manifest hiện hành xem [audit](Project_Code_Audit_2026-10-22.md); không dùng các dòng log lịch sử để mở rộng phạm vi kiểm chứng mới.

| | Full graph | Sample |
|---|---|---|
| Vertices | 9,073,900 | 194,195 |
| Edges | 6,362,620 | 100,729 |
| PASS checks | 4/4 | 3/3 |

Log: `results/paysim/task1_verification_full.log` (full) 
| `results/paysim/task1_verification_sample.log` (sample)

**Lưu ý kỹ thuật:** Full Parquet đang ở path cũ `data/processed/`. 
Script tự động fallback về path cũ nếu path mới không tồn tại 
(warning `[WARN] Preferred path not found` trong log). Đây là hành vi 
mong muốn, không phải bug. Sample Parquet đọc đúng path mới 
`data/processed/sample/paysim/` — không có warning.

### 1.3. Trích log PASS

[PASS] Vertices contain ['account_type', 'balance', 'id']  
[PASS] Edges contain ['amount', 'dst', 'isFraud', 'src', 'step', 'type']  
[PASS] Vertex count == 9,073,900 (got 9,073,900)  
[PASS] Edge count == 6,362,620 (got 6,362,620)  
[+] Task 1 Completed Successfully. GraphFrame is fully operational.  

### 1.4. Raw-transaction spot-check (`--from-raw`)

Ngoài verification schema + count (so với hardcode), nhóm chạy thêm 
`--from-raw` để đối chiếu 1-1 với **raw CSV gốc**:

| # | Edge (src → dst) | Step | Amount | Kết quả |
|---|------------------|------|--------|---------|
| 1 | C1509309988 → M1643141512 | 1 | 1876.44 | ✅ 1 raw match |
| 2 | C1112456099 → C1225616405 | 1 | 26004.52 | ✅ 1 raw match |
| 3 | C1458091526 → C747464370 | 1 | 323105.08 | ✅ 1 raw match |
| 4 | C201677908 → C451111351 | 1 | 480222.51 | ✅ 1 raw match |
| 5 | C1574873161 → M1591916281 | 1 | 1239.06 | ✅ 1 raw match |

**Phạm vi bằng chứng:** 5 raw spot-checks ở trên PASS; đây không phải đối chiếu toàn bộ Parquet với raw CSV. Chưa thể suy ra mọi dòng đều được bảo toàn chỉ từ 5 ví dụ. Counts/integrity và raw multiset reconciliation phải được ghi riêng theo dataset/run.

Log: `results/paysim/task1_verification_from_raw_sample.log`
**Lưu ý số liệu:** Số ở 1.2 và 1.4 khác nhau do 2 lần chạy độc lập:  
- **1.2** đọc Parquet sample có sẵn (`data/processed/sample/paysim/`)  
- **1.4** induce subgraph ngẫu nhiên ~100k edges **mới** từ raw CSV  
> Hai lượt PASS là bằng chứng cho các kiểm tra đã chạy; spot-check không thay thế đối chiếu đầy đủ.

### 1.5. Insights
- **Quan sát degree trên scope được log ghi nhận:**
  - Max In-Degree = 113 (tài khoản `C1286084959` — hub nhận tiền)
  - Max Out-Degree = 3 (hầu hết users chỉ gửi 1-3 lần)
- Phân bố lệch gợi ý cần quan tâm partition skew; chưa fit power-law hoặc benchmark vertex-cut so với edge-cut. Không kết luận một chiến lược partition là bắt buộc chỉ từ các giá trị degree trên.

### 1.6. Quyết định Mapping (khác biệt so với bảng 4.1 gốc)

#### Balance tie-breaking rule

Đề bài Mục 4.1 ghi rõ cột `balance` lấy từ `oldbalanceOrg`/`oldbalanceDest`. 
Tuy nhiên phần diễn giải của đề lại yêu cầu "giá trị balance gần nhất cho 
mỗi account". Nhóm đã phân tích và chọn **`newbalanceOrig`/`newbalanceDest`** 
thay vì `oldbalance*`, vì:

- `oldbalanceOrg` tại event cuối = balance **TRƯỚC** giao dịch cuối cùng
- `newbalanceOrig` tại event cuối = balance **SAU** giao dịch cuối cùng
- → `newbalance*` phản ánh đúng trạng thái cuối cùng của account

**Quy tắc chính thức:** Cho mỗi account (bao gồm 1,769 tài khoản đóng cả 
2 vai trò sender + receiver), lấy `newbalance` tại `max(step)`. Cài đặt 
bằng `F.max_by("balance", "step")` — một aggregation, không dùng window function. Nếu nhiều event cùng `max(step)`, `max_by` không xác định duy nhất balance nào là cuối trong giờ đó. Do raw step không cung cấp thứ tự trong giờ, đây là balance tại một event cuối kỳ, không phải bằng chứng chính xác trạng thái intrahour. Không dùng vertex balance cuối kỳ làm feature detector theo thời gian.

#### Bổ sung cột vào Edges

Hai cột không có trong bảng 4.1 gốc nhưng được bổ sung cho downstream:

| Cột | Lý do |
|-----|-------|
| `type` | Cần cho Task 3 pivot: 2-hop relay `TRANSFER → CASH_OUT`. PaySim có 0 cycle 3-node (đã verify vét cạn), nên motif được điều chỉnh. |
| `isFraud` | Ground-truth label. Cần để cross-check kết quả Motif/LPA với nhãn gian lận thật. |

#### Step giữ nguyên Integer

Trường `step` giữ nguyên dạng **integer** từ raw làm proxy thời gian mô
phỏng, KHÔNG convert sang datetime. Tránh gây hiểu nhầm về thời gian thực.

## Task 2 — Degree & PageRank (nhãn nhiệm vụ trong PCCV)

Châu Anh triển khai Degree/PageRank; Phương review/final hai dataset theo PCCV. Hiện đã có code và output, không còn trạng thái “chờ”. Root output Task 2 là **sample**, không phải full:

| Dataset | Accounts / transactions | Artifacts |
|---|---:|---|
| PaySim | 194.195 / 100.729 | `results/paysim/{degree_distribution.csv,degree_distribution.png,top10_pagerank.csv,task2_run.json}` |
| IBM HI-Small | 119.043 / 99.869 | Bộ file cùng tên trong `results/ibm_aml/` |

Source: `src/paysim/metrics.py` và adapter `src/ibm_aml/metrics.py`; `resetProbability=0.15`, `maxIter=10`. Đa cạnh được giữ, self-loop đóng góp vào cả in/out degree. Gate kiểm tra degree sum `2E`, đối chiếu PageRank bằng reference độc lập, top-10 và manifest hashes. Degree comparison ở `src/comparison/degree_distribution.py` và `results/comparison/`.

Top-10 được chọn bằng cấu trúc trước khi đối chiếu fraud counts. Top PaySim có incident fraud 0; IBM có hai account nhận lần lượt 2 và 1 fraud transactions trong sample. Đây là hub audit, không phải TP/FP của classifier. Temporal centrality pilot đã có đánh giá riêng, precision còn yếu; xem [audit](Project_Code_Audit_2026-10-22.md). Full Task 2 chưa được nghiệm thu trong lượt này. Không dùng top-10 CSV làm thay thế toàn bộ feature table cho fusion.


## Task 3 — Motif Finding (25đ)

### Mục tiêu và baseline

Khánh triển khai truy vấn GraphFrames trên full PaySim và IBM HI-Small. Ba ID phải khác nhau ở cycle ba đỉnh; khử phép xoay nhưng giữ hai chiều khác nhau và phân biệt đa cạnh với số vòng tài khoản. PaySim baseline có 0 cycle và 30 relay TRANSFER→CASH_OUT >10.000 trong 24 giờ, gồm 2 cặp cùng giờ. Hai cạnh của mọi relay baseline đều có nhãn 0; không gọi 30 ứng viên thành 30 vụ fraud.

IBM audit trên cạnh đã gắn nhãn có 7.473 raw matches, 2.491 tổ hợp giao dịch và 54 directed account cycles (45 bộ tài khoản không xét chiều). Truy vấn ba cạnh USD >10.000 trên toàn graph trả 0. Audit nhãn và detector không biết nhãn là hai mục đích khác nhau.

### Pipeline v2: feature motif và đánh giá có giám sát

Source chính: `src/motif/{config,features,modeling,pipeline}.py`, cùng adapter `src/{paysim,ibm_aml}/motif_finding.py`. Fan-in/out, relay, reciprocal, cycle ba tài khoản và role histories được trích từ quá khứ trong cửa sổ 24/168 giờ. Các dòng cùng timestamp không làm witness cho nhau. Counts được tính bằng expiry-prefix sums; witness star được giải thích bằng truy vấn theo event ID, tránh bounded-window rescans ở hub. FX, self-loop và amount=0 không làm witness dòng tiền nhưng vẫn giữ trong mẫu số. Vòng đối ứng không bị tính nhầm thành relay ba tài khoản; SQL self-join độc lập kiểm tra cách đếm.

So sánh hai cây quyết định cùng cấu hình: transaction-only và motif-assisted. Feature không chứa nhãn, account ID hoặc absolute timestamp; mô hình có giám sát học từ nhãn training. Chuẩn hóa amount theo q90 prefix của từng currency/type. Chọn family và score threshold bằng ba fold mở rộng 40→50%, 50→65%, 65→80%; xem mean/worst/std F1. Sau khi khóa cấu hình mới refit đến 80% và chấm phần còn lại.

Các notebook đã tách theo dataset, import trực tiếp source và giữ toàn bộ output/hình:

- [PaySim](../notebooks/03_khanh_PaySIM_motif.ipynb).
- [IBM HI-Small](../notebooks/03_khanh_IBM_motif.ipynb).

### Kết quả full v2

| Dataset | Test giao dịch / fraud | Mô hình CV chọn | Test TP / FP / FN | Precision | Recall | F1 | F1 transaction-only |
|---|---:|---|---:|---:|---:|---:|---:|
| PaySim | 1.248.736 / 4.250 | motif-assisted, score ≥0,70 | 1.191 / 1.489 / 3.059 | 44,44% | 28,02% | 34,37% | 30,38% |
| IBM | 1.015.564 / 1.797 | motif-assisted, score ≥0,50 | 474 / 4.059 / 1.323 | 10,46% | 26,38% | 14,98% | 15,08% |

PaySim thêm 302 TP và 776 FP so với cùng cây transaction-only; importance nghiêng về receiver history/type/amount. Chưa chứng minh count motif độc lập khỏi role history; cycle vẫn bằng 0. IBM giảm 4.998 FP nhưng mất 411 TP so với transaction-only; F1 giảm nhẹ còn AP chỉ tăng nhẹ. Không kết luận motif cải thiện F1 trên test IBM này. Coverage cycle causal ≤168 giờ của toàn IBM: 304 closing transactions, 92 laundering; reciprocal: 4.455/305. Coverage chồng nhau, khác số vòng tài khoản và không phải chỉ số test của detector.

### Diễn giải và tái lập

TP/FP/FN/TN tính theo giao dịch, không theo tổ hợp motif. Mẫu số gồm tất cả giao dịch test. Báo precision/recall/F1, exact average precision và Wilson 95% CI; CI chưa hiệu chỉnh tương quan giao dịch. Feature importance không chứng minh quan hệ nhân quả. Weighted tree score không phải xác suất fraud đã hiệu chuẩn. Không alert không xác nhận hợp pháp.

Test này đã được phân tích ở phiên bản trước, nên được ghi là **reused internal temporal holdout**, chưa phải benchmark ngoài mẫu mới. Không chọn lại threshold bằng test. Motif được đánh giá bằng ablation thay vì mặc định thêm graph sẽ luôn tốt hơn.

CLI PowerShell và API dùng cùng pipeline; model/amount scales/report/examples/run manifest được xuất vào directory mới nếu gọi `--analysis --output-dir`. Notebook chỉ lưu output nhúng. Loader kiểm tra hash và dùng JVM reader cho các stage Spark ML để chạy được trên Windows Python 3.12/JDK 17. Kết quả full hiện hành lấy từ bảng test trong notebook, không lấy từ synthetic fixture của unit test.


### Tài nguyên khi tái lập motif v2

Chỉ một tác vụ nặng chạy tại một thời điểm; hardware guard bắt buộc giới hạn CPU 10%, tối đa 2 logical CPUs, JVM heap ≤6 GiB và job commit ≤10 GiB trên máy 32 GiB. Có admission và watchdog giữ RAM/commit dự phòng, cùng thu hồi tiến trình con khi kernel chết. Không tăng tài nguyên sau resource stop. GPU chưa được stack Windows native này sử dụng; nhiệt độ CPU không có sensor tin cậy. Xem [quy trình bảo vệ](../.agents/skills/graphguard-powershell/SKILL.md#protect-this-workstation-before-computation) và [skill](../.agents/skills/graphguard-powershell/SKILL.md).


## Task 4 — Community Detection (nhãn nhiệm vụ trong PCCV)

### PaySim và IBM sample — producer chính

Hoàng phụ trách LPA hai dataset; Châu Anh kiểm tra stability/final PaySim, Khánh review/final IBM. Sample producer đã xuất assignment, top-50, **all-community summary** và run manifest:

| Dataset | Accounts | Communities | Phạm vi |
|---|---:|---:|---|
| PaySim | 194.195 | 186.932 | Sample; 153 communities chứa ít nhất một fraud edge theo profile hậu kiểm |
| IBM HI-Small | 119.043 | 86.223 | Sample; amount/count giữ riêng từng currency |

Gate đối chiếu toàn bộ summary với cạnh gốc, không chỉ top-50. PaySim dùng đúng `Customer`/`Merchant`; hai lượt sample cho cùng canonical membership trên 194.195 accounts, 0 thay đổi. LPA label số có thể đổi; khác label ID không tự động là khác partition. Tỷ lệ fraud hậu kiểm không được dùng làm feature test. Rule community pilot chưa đạt detector độc lập, đặc biệt PaySim alert 100% test.

### IBM full — review độc lập


Thuật toán LPA do Hoàng phụ trách; phần của Khánh là review/final theo PCCV đến 07/10. Notebook IBM chạy GraphX LPA `maxIter=5` trên full graph và dùng checker độc lập:

- 518.581/518.581 tài khoản được gán community; 314.829 cộng đồng.
- 853.796 cạnh nội bộ + 4.224.549 cạnh liên cộng đồng = 5.078.345 giao dịch; đối chiếu đủ 5.177 laundering.
- Tổng tiền theo từng `payment_currency`, không cộng nominal amount khác currency; 314.577 nhóm community/currency có giao dịch đi.
- Hai lần chạy sample trên 119.043 tài khoản cho cùng phân hoạch sau canonicalization (0 tài khoản đổi thành viên cụm). Đây là quan sát của hai lần chạy, không bảo đảm LPA luôn deterministic.
- Checker từ chối đủ 6 phản ví dụ: duplicate/missing account, null/fractional label, NaN amount và summary trộn currency.

Output thật và biểu đồ LPA được giữ trong [notebook IBM](../notebooks/03_khanh_IBM_motif.ipynb); toàn notebook có 6 figure nhúng. LPA chưa được dùng làm feature trong detector motif. Kiểm chứng tự động không thay phê duyệt final của Tuệ Minh.
