# Bàn giao checkpoint — 24/10/2026 (UTC+7)

**Yêu cầu mới nhất của user: DỪNG AN TOÀN, commit/push lên main ngay; tiếp tục vào ngày mai.** Chỉ thị này thay yêu cầu không push ban đầu ở phần lịch sử bên dưới. Không tự khởi động lại Spark tối nay.

## Tiến độ và điểm dừng

- Theo số code cells hoàn tất: **23/30 = 76,7%** (IBM15/15 + PaySim8/15). Đây là tỷ lệ cells, không phải tỷ lệ thời gian còn lại; validation/test còn nặng.
- **IBM hoàn tất:** `results/full_system/ibm_aml/run_20261023T165404547138Z`; 15/15 cells, 8 PNGs, 26 source hashes; full artifact + notebook verification PASS. Thời gian4244,9giây, peak commit6,00/8GiB, minimum RAM14,37GiB. Full test1.017.196 rows /1.799 positives, validation-selected full_fusion threshold0,50: TP532/FP5.190/FN1.267/TN1.010.207, P9,30%/R29,57%/F1 = 14,15%/AP5,67%. F1 thấp hơn transaction-only14,29%; không đổi selection theo test.
- **PaySim dừng có chủ đích:** `results/full_system/paysim/run_20261023T180715049802Z`; 8/15 cells. Raw reconciliation, full Degree/PageRank/LPA, baseline và motif features PASS. Đang cell9 `full_system_feature_table`, historical snapshot5/5, cutoff355; PageRank iteration02 đã `_SUCCESS`, chưa xong snapshot5.
- Checkpoints local hoàn chỉnh: `snapshots/snapshot_1.parquet` … `snapshot_4.parquet`; `feature_blocks/block_0.parquet` … `block_4.parquet`. `.work/snapshot_5/pagerank/iteration_02` và weights có `_SUCCESS`. Không dùng thư mục đang ghi thiếu `_SUCCESS` làm completed checkpoint.
- Chưa có common_features PASS, PaySim validation/test/final_predictions/report/latest hoàn tất, full-comparison generation hoặc full project gate mới. **Không đánh dấu toàn bộ DONE FIXED.**
- Đã đóng owned runner/kernel tree; xác nhận0SparkJVM, RAM21,83GiB ngay sau dừng. Runner exit1/kernel-stopped là do operator stop, không OOM/resource stop. Partial outputs được giữ và Notebook gắn notice rõ.
- Full results/models/checkpoints Git-ignore: nằm trên máy này, không đi theo Git push. Code, hai notebooks và tài liệu checkpoint được push; giữ nguyên các thư mục local để ngày mai kiểm tra/tận dụng.

## Chỉ thị CPU cho lượt tiếp theo — user đã cho phép

User yêu cầu dùng CPU khoảng **90%+**, phản đối cap10%/2luồng. Máy thực tế: i7-12800H (14cores/20logicalCPUs), RTX A4500 Laptop GPU. Đo lượt cũ: Spark198,5% của một logical CPU ≈9,9% toàn máy, affinity[0,1].

**Đây là yêu cầu đã được cấp quyền, không hỏi lại quyền tăng CPU.** Hôm nay chỉ dừng/lưu/push; guard code chưa đổi, profile90% chưa được kiểm chứng. Ngày mai không âm thầm chạy lại full với cap10%/2luồng cũ.

1. Trước heavy work: thay CPU policy/affinity và Spark parallelism bằng high-throughput profile khoảng90% (mục tiêu90%+ theo user), có CPU ceiling hữu hạn và native tests xác nhận. Kiểm tra các điểm ép2luồng trong `hardware_guard.py`, `spark_session.py`, `windows_runtime.py`, `NotebookSession.start`, `AnalysisConfig` và scripts. Phân bố trên physical cores hợp lý, đo throughput thật; các bước serial/I/O có thể không sử dụng90% liên tục.
2. **Giữ bảo vệ RAM/commit:** heap5GiB, job8GiB, host reserve khoảng8GiB; mutex một heavy workload và watchdog vẫn bắt buộc. Cấp quyền CPU cao không cấp quyền bỏ guard, tăng RAM cap để ép PASS hay chạy nhiều notebooks/Spark đồng thời. Tune partitions/spill theo số task đang chạy để không đổi tốc độ lấy OOM.
3. Tối ưu code theo prefix: dùng chung q90 scales/category preprocessing/truth join giữa9families; giảm scan/ghi lặp. Thiết kế resume có xác minh source/input/config và completed outputs; runner hiện **chưa hỗ trợ tự resume**. Không giả vờ chỉ mở notebook là chạy tiếp iteration02.
4. GPU hiện chưa được pipeline dùng. Đánh giá backend hỗ trợ đúng native Windows/Spark stack trước khi tuyên bố tăng tốc; không tự chuyển WSL hoặc cài driver để né giới hạn.
5. Giữ protocol9families/3folds/frozen thresholds/full rows. Thay resource/helper source có thể làm source hashes cũ không còn current: kiểm tra provenance và chạy run mới khi cần; không gán hash mới cho output cũ. IBM run đã hoàn tất vẫn là evidence lịch sử thật, không đổi số cho đẹp.
6. Hoàn tất PaySim snapshots/common table →27validation fits →9frozen refit/test →model replay/artifact/notebook checks. Tạo full comparison bằng `python -m src.comparison.degree_distribution`, rồi native full gate `scripts/check_project.ps1`. Cập nhật README/PartB/audit bằng số thật và DONE FIXED chỉ khi PASS đủ.

ETA đã nói trước (~2giờ PaySim +10–15phút gate nếu RunAll từ đầu) là **profile10% cũ**. Với CPU90%, đo lại trước khi chốt ETA; không hứa tốc độ tăng tuyến tính9lần. IBM có thể cần run mới nếu nâng profile làm thay source/contract verification.

## Kiểm tra trước checkpoint push

- Native Windows `pip check`: PASS; **48/48 pure/unit tests PASS**,1,272giây; không khởi động JVM.
- IBM notebook recheck PASS:15cells/8figures/9models/26sourcehashes. PaySim giữ trạng thái partial/operator-stop, không sửa thành completed.
- Git fetch xác nhận `HEAD == origin/main` tại `a1e0a64d56eb50e8f3e701e39dcbdc4faff6013d` trước checkpoint commit; không có merge conflict. Native Git `diff --check` PASS (CRLF hợp lệ của Windows được giữ, không chỉnh byte artifacts cho đẹp diff).
- Logs local: `results/project_check/prepush_units_2026-10-24.log`, `IBM_full_system.log`, `PaySIM_full_system_partial.log`.

## Files thay đổi trong checkpoint

- [.gitignore](.gitignore): loại full results/models khỏi Git.
- [AGENTS.md](AGENTS.md): lưu stop/resume và quyền CPU90%+ cho lượt tiếp theo.
- [README.md](README.md): objective, cả nhóm, full architecture/protocol và trạng thái chưa nghiệm thu đủ.
- [agent_job.md](agent_job.md): điểm dừng, kết quả thật, phần còn thiếu và việc ngày mai.
- [docs/PartB_Comparison.md](docs/PartB_Comparison.md), [docs/PartB_Experiments.md](docs/PartB_Experiments.md), [docs/Project_Code_Audit_2026-10-22.md](docs/Project_Code_Audit_2026-10-22.md): scope/history/checkpoint trung thực.
- [notebooks/IBM_full_system.ipynb](notebooks/IBM_full_system.ipynb): full pipeline đã chạy15/15 và graphs/metrics/witness.
- [notebooks/PaySIM_full_system.ipynb](notebooks/PaySIM_full_system.ipynb): full pipeline code, output8/15 và notice dừng.
- [src/motif/config.py](src/motif/config.py), [modeling.py](src/motif/modeling.py), [pipeline.py](src/motif/pipeline.py), [presentation.py](src/motif/presentation.py):9families, shared index, causal snapshots, frozen evaluation/export/replay và views.
- [src/paysim/metrics.py](src/paysim/metrics.py), [community_detection.py](src/paysim/community_detection.py): full defaults và disk-checkpoint PageRank/LPA backends.
- [src/ibm_aml/community_detection.py](src/ibm_aml/community_detection.py), [verify_communities.py](src/ibm_aml/verify_communities.py): full backend/scope và verifier empty-column fix.
- [src/common/project_audit.py](src/common/project_audit.py): full rows/artifacts/notebook/metrics acceptance.
- [src/comparison/degree_distribution.py](src/comparison/degree_distribution.py): full comparison từ accepted aggregate CSVs, không Spark mới.
- [scripts/run_n4_notebook.py](scripts/run_n4_notebook.py), [check_project.ps1](scripts/check_project.ps1), [check_task4.ps1](scripts/check_task4.ps1): checkpoint outputs, full gate và resource profile.
- [tests/test_project_audit.py](tests/test_project_audit.py): independent oracles, full pipeline fixture và negative comparison tests. Không thêm module .py mới.

---
## Yêu cầu và nhật ký triển khai trước checkpoint

đầu tiên công việc bạn là hãy hoàn thành 1 pipeline full thống nhất, có dependancy kết nối tốt hết cả 2 datasets, sau đó Để đáp ứng đúng yêu cầu của bạn những bên kiến trúc nào trong hệ thống còn dùng samples thì chuyển sang dùng full data, còn cần:

1. Chạy và nghiệm thu Degree/PageRank full cho cả PaySim và IBM.
2. Có LPA full và bộ output đầy đủ cho cả hai, đặc biệt PaySim; IBM cần đưa kết quả full vào luồng bàn giao chung.
3. Khi kết hợp, tạo feature từ cùng full input, transaction index và lịch thời gian. Không ghép kết quả sample với motif full.  rồi đến bước Phương án kết hợp tôi đề xuất:

1. Tạo feature table chung theo giao dịch, cùng input, transaction index và tập đánh giá; không ghép trực tiếp các CSV hiện tại.
2. Tính feature đúng thời điểm, kể cả training rows. Không dùng snapshot cuối training cho những giao dịch xảy ra trước snapshot đó.
3. So sánh công bằng transaction-only, từng nhóm feature, full fusion và bỏ từng nhóm khỏi fusion.
4. Chọn model/ngưỡng trên validation rồi khóa, báo AP, precision/recall/F1, alert rate và kết quả theo ngân sách review. Đây là hướng phù hợp với đánh giá transaction classification theo thời gian trong AMLworld (https://arxiv.org/html/2306.16424v3).
5. Xuất prediction và chứng cứ kiểm toán được: score, alert, thời điểm snapshot, TP/FP/FN và witness. Test hiện tại phải tiếp tục ghi là reused internal holdout.đén khi  mà bạn thấy là nó hợp lí và  bạn hài lòng rồi thì sau khi các code .py files được update chuẩn chỉnh rồi, tôi muốn bạn add vào notebooks\PaySIM_full_system.ipynb với notebooks\IBM_full_system.ipynb respective pipeline dataset match với tên nó, hãy add vào đo full pipeline mà chúng ta code ra trong các py và sử dụng để gom lại vào các notebook đó như một system pipeline chuẩn, chạy full mà nếu có thắc mắc hay vấn đề gì thì có thể đọc và check lại code chính ở trong file py, đặc biệt ở mỗi code cells sẽ có from src import đúng function chúng ta cần để nếu vấn đề ở code cell nào thì chúng ta make cheeck được trong file py đó luôn tiện lợi
---
## Kế hoạch thực hiện ban đầu — full system (khi đó chưa cho phép push)

Quy tắc: native Windows Python 3.12/JDK17; một workload nặng; heap tối đa 5 GiB / job cap 8 GiB, reserve/CPU/mutex/watchdog giữ nguyên. Không tự retry sau OOM/pressure stop. Không lấy sample làm nghiệm thu full.

- [x] P1 — Freeze config: cùng full input, index tạo một lần, 3 validation folds (40→50,50→65,65→80), snapshot boundaries 20/40/50/65/80%; test >80 reused internal holdout. 8 factorial model families (mọi tổ hợp 3 nhóm) + 1 novelty control = 9 families, cùng cây/seed/budget; chọn F1 validation, báo AP và review budgets 0.1/0.5/1% test.
- [x] P2 — Backend DataFrame có disk checkpoint cho PageRank10/reset.15 và LPA5, tránh materialize GraphX 9 triệu vertices trong heap. PR kiểm tra reference + GraphX trên fixture; LPA explicit deterministic min-label tie, undirected messages/parallel/self-loops/isolate semantics. Ghi rõ backend, không nhận hai implementation LPA cho cùng partition một cách mặc định.
- [ ] P3 — Full Task 1 integrity và Task 2/4 exports hai dataset: all-account metrics, assignments, all-summary/currency, top views/graphs, manifests và full-row invariants. Output dưới results/full_system/<dataset>/, không ghi đè sample cũ.
- [ ] P4 — Common indexed transactions + causal motif features + lagged snapshots cho TRAIN lẫn validation/test; join checks không mất/trùng dòng, unknown flags, no labels vào feature.
- [ ] P5 — Walk-forward/ablation/frozen thresholds; final fit/test predictions/model reload; baseline novelty, budgets/tie policy, confusion/AP/CI/examples/witness/PR and ablation graphs.
- [x] P6 — Tiny native oracles/end-to-end/negative tests trên files test sẵn có; guard native trước full. Source frozen trước execution, failure báo thật.
- [ ] P7 — Hai full-system notebooks: Markdown rõ scope/units/config; mỗi cell import đúng hàm ở module gốc, không chép hàm dài; output/graphs thật; chạy tuần tự và checkpoint từng cell.
- [ ] P8 — Verify full outputs, model replay, source/input/output hashes, notebook run status; cập nhật README/audit bằng số thật; báo phần hoàn tất/chưa đạt. Tuyệt đối không push Git.

Bảng tham số được định trước; không thay sau khi xem test để làm đẹp điểm. Decision-tree weighted score không gọi là calibrated probability. IBM laundering và PaySim fraud báo riêng.

### Bổ sung protocol trước benchmark full

Giữ 8 factorial combinations và thêm 1 matched-tree baseline `transaction_novelty` (chỉ transaction + src/dst seen flags), tổng 9 families / 27 validation fits. Lý do: tách hiệu ứng cold-start khỏi centrality/community, không suy lợi ích graph chỉ vì unknown accounts. Thay đổi khai báo trước mọi full run; không dựa vào metric test full mới. Raw reconciliation full hai dataset bắt buộc trước nghiệm thu; PaySim balance cùng giờ không có thứ tự được ghi là giới hạn, không là feature.

### Trạng thái trước chạy full

- 45/45 pure/unit tests PASS; 16/16 policy/native guard/checkpoint tests PASS trước Spark.
- 4/4 NativeFullSystemTests PASS (238,857 giây) trên Windows: PR/reference+GraphX, LPA/oracle, snapshot joins/unknown/ground truth rejection, end-to-end 9 models + exported model replay + artifact tamper rejection. Đây là fixture, chưa phải full benchmark.
- Đã sửa trong fixture: Python-worker tạo dữ liệu chuyển sang SQL JVM; numeric verifier hỗ trợ danh sách cột rỗng; snapshot_as_of thống nhất long giữa block chưa có history và các block sau. Không OOM/pressure stop trong các lượt này.
- Source chuẩn bị freeze; chạy IBM_full_system rồi PaySIM_full_system tuần tự bằng runner cell-timeout 7200s, vẫn heap/job/CPU caps cũ. Không commit/push.

### IBM full đang chạy — source đã freeze

Runner: `notebooks/IBM_full_system.ipynb`, run directory `results/full_system/ibm_aml/run_20261023T161113752907Z`.

- Index đầy đủ 5.078.345 physical transactions, duy nhất từng event ID; snapshot cutoffs thực tế lưu trong system_state/report.
- Raw reconciliation full vertices + edges PASS, hai chiều multiset đều 0 (155,925 giây).
- Full Degree/PageRank PASS: 518.581 accounts; degree sum 10.156.690; rank sum ≈518.581 (44,68 giây).
- Full LPA/all-summary/currency PASS: 314.722 communities; 852.930 internal + 4.225.415 cross = 5.078.345 edges; đủ 5.177 positives (92,699 giây). Backend min-hash-label tie khác GraphX nên không ép số community trùng bản cũ.
- Peak job commit đến bước này 3,86/8 GiB; minimum available RAM 15,93 GiB; host CPU max 27,0%. Đang chạy motif features. Chưa có kết quả full ML test; chưa chạy PaySim.
- Không sửa source Python/runner trong lúc full notebook chạy để bảo toàn executed hashes. Chỉ ghi tiến độ vào tài liệu.

### IBM run 1 — dừng có kiểm soát để sửa hiển thị

Common features đủ 5.078.345 rows/unique IDs, future-snapshot violations = 0 (978,543 giây). Peak commit 6,04/8 GiB; minimum available RAM 13,78 GiB. PNG được lưu nhưng chưa nhúng vào notebook vì Agg backend; đã dừng đúng runner/kernel tree, xác nhận không còn Java/kernel trước sửa. Đây không phải OOM/pressure stop. Run này là partial, không publish latest và không nghiệm thu. Sửa explicit IPython PNG display, smoke-test notebook rồi chạy lại trong thư mục run mới; không thay ngưỡng hay model theo test.

### Chuẩn hóa tên đường dẫn provenance (không thay hash)

Manifest Windows dùng backslash, metadata template ban đầu dùng slash. PaySim template được đổi key đường dẫn trước execution để khớp native manifest. IBM đang chạy với template slash: sau runner hoàn tất sẽ đối chiếu từng actual SHA-256 rồi chỉ đổi tên key sang cùng native path; không thay hash values, code digest, source bytes hoặc metrics. Đây là alias-path normalization, không tái tạo execution evidence.

### IBM full-system — hoàn tất, chưa push

Run `run_20261023T165404547138Z`: notebook 15/15 code cells, 8 embedded PNGs, 26 distinct source hashes; independent artifacts + notebook verification PASS. Full feature rows/unique IDs = 5.078.345; future snapshot violations = 0. Validation chọn full_fusion threshold 0,50; test chung 1.017.196 rows / 1.799 positives, TP532 / FP5.190 / FN1.267 / TN1.010.207, P9,30% / R29,57% / F1 14,15% / AP5,67%. F1 thấp hơn baseline14,29%, AP nhỉnh hơn baseline5,39%; không đổi lựa chọn bằng test. Selected-model replay toàn test PASS.

9 final families có cùng training 4.061.149 rows / 3.378 positives và cùng q90 amount scales. Independent Python heap streaming kiểm tra selected Top-K: K1.018→95TP; K5.086→496TP; K10.172→775TP, khớp CSV. Case graph là 3-cycle thực, ba cạnh Saudi Riyal đều mang nhãn laundering1. Metadata chỉ chuẩn hóa tên key path sau đối chiếu samefile + unchanged SHA; executed code digest giữ nguyên. Không còn Java trước chuyển dataset; RAM22,20GiB / commit20,84GiB, guard vẫn tự admission trước PaySim.

### PaySim full analytics — PASS, benchmark ML còn chờ

Run `run_20261023T180715049802Z`: full vertices9.073.900 / edges6.362.620 / fraud8.213; integrity và raw edges + vertex IDs/types multiset reconciliation PASS (150,826 giây). PageRank/Degree PASS (330,473 giây), sum degree12.725.240 và rank sum≈9.073.900. LPA5 cùng toàn bộ summaries/currency/account types PASS: 5,433,491 communities, 0 internal + 6,362,620 cross edges. Không dùng sample. Còn causal features/snapshots, validation/test và full gate.

### Chuyển nốt cross-dataset comparison sang full

`src/comparison/degree_distribution.py` mặc định đọc accepted full degree CSVs + report/index hashes, kiểm tra đủ accounts và degree sum2E rồi xuất full PMF/CSV/PNG/manifest. Không scan raw hay khởi động Spark lần nữa. `--sample` giữ dev mode rõ ràng. Full gate kiểm tra comparison manifest/CSV/hashes, `-Refresh` tạo lại comparison sau hai notebooks. 3 native light negative/invariant tests PASS (1,435 giây); phần generation/verification thật chờ PaySim hoàn tất. Đây là producer độc lập, có source hash riêng; không là feature/model dependency. Đã kiểm tra lại 26 benchmark source hashes không đổi. Không thêm module .py.
