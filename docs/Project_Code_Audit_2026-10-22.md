# Full-system presentation và reliability — DONE FIXED

- [x] **DONE FIXED — Hai notebook thuyết trình:** code thuật toán thực thi hiện trực tiếp, sections theo unified pipeline;24/25 definitions AST-matched với Python.
- [x] **DONE FIXED — Full execution:** IBM 35/35 cells và PaySim 36/36; full cardinalities/raw reconciliation/causal features/model exports/case evidence.
- [x] **DONE FIXED — Reliability có số thật:**3 validation folds,5 chronological test periods,95% WilsonP/R, matched ablations, motif coverage, cold-start, model reload và independent temporal metrics. Không gọi softwarePASS là model ổn định cao.
- [x] **DONE FIXED — CPU và bộ nhớ:** full available CPU affinity/quota100%, memory caps5/8 GiB/reserve/mutex/watchdog; motif stages trên đĩa,32 MiB row groups thay object cache gâyOOM. Giữ failed-run history.
- [x] **DONE FIXED — Shared preprocessing / verified reuse:** q90/indexer/truth1 lần mỗi prefix; output inventories/hashes được kiểm tra trước reuse. IBM đã thực tế resume completed phases sau notebook display fix.
- [x] **DONE FIXED — Full comparison + make check:** hai accepted full runs, degree comparison và full native gate PASS/exit0.
- [x] **DONE FIXED — Hướng dẫn code và notebook:** [Code Explainer](Code_Explainer.md) giải thích các chặng, vị trí code cells, source matching và cách đọc kết quả đã chạy.

Chưa push Git. Số liệu / scope hiện tại ở[PartB_Experiments.md](PartB_Experiments.md); lịch sử phía dưới giữ nguyên, không nhận old sample/historical output làm full kết quả mới.

---

## Lịch sử kiểm tra trước lượt nghiệm thu mới

# Checkpoint full-system — 24/10/2026

**STOPPED BY USER / PUSH CHECKPOINT — chưa DONE FIXED toàn bộ full-system mới.** Lịch sử DONE FIXED22/10 bên dưới giữ đúng phạm vi khi đó. Bàn giao đầy đủ và quyền CPU mới: [hướng dẫn code và notebook](Code_Explainer.md).

| Deliverable | Trạng thái thực tế |
|---|---|
| Full Degree/PageRank và LPA cả hai datasets | PASS; toàn bộ accounts/transactions, raw reconciliation và independent summary checks |
| IBM full-system | PASS15/15cells,8PNG,26sourcehashes; artifacts/notebook/model replay/independent Top-K PASS |
| PaySim full-system |8/15cells; dừng cell9/snapshot5 ởPageRank2/10; snapshots1–4 và blocks0–4 đã lưu |
| Comparative models | IBM đủ9families/27CVfits/9frozen tests; PaySim chưa chạy validation/test |
| Full degree-comparison producer | Code đã chuyển sang full;3light tests PASS; generation/verification thật chờ PaySim completed report |
| Full project gate mới | PENDING; không chạy Spark nữa sau user stop |

Tỷ lệ theo cells23/30≈76,7%, không phải phần trăm thời gian. No OOM/resource stop trong các lượt hoàn tất; PaySim bị đóng có chủ đích. Xác nhận0SparkJVM và21,83GiB RAM trống sau stop.

IBM selected full_fusion threshold0,50: test1.017.196/1.799positives, TP532/FP5.190/FN1.267/TN1.010.207, P9,30%/R29,57%/F1 = 14,15%/AP5,67%. F1 thấp hơn baseline14,29%; giữ negative finding. Case3-cycle thật không chứng minh cycle feature gây alert: cycle/relay importance=0 trong cây đã chọn. Không sửa source hashes hoặc metrics để đổi kết luận.

Ngày mai user đã cấp quyền CPU≈90%+; hiện guard vẫn là10% lịch sử. Đổi policy/parallelism và kiểm chứng native trước heavy runs, đồng thời giữ RAM5/8GiB, reserve/mutex/watchdog. Không nâng cap RAM hoặc chạy song song để ép PASS. Source thay đổi phải được xử lý provenance trung thực, có thể cần run mới. Không coi các file local Git-ignore là đã được push.

---

## Audit lịch sử — 22/10/2026

# Kiểm tra code theo PCCV — 22/10/2026

**DONE FIXED — toàn bộ lỗi code trong checklist đã sửa; hai notebook full và gate đầy đủ của `make check` đã chạy PASS trên native Windows.** Kết quả kiểm chứng code không đồng nghĩa detector fraud đã tốt hoặc đã hoàn thành fusion. Các hạn chế hiệu quả được giữ rõ bên dưới.

Git fetch ở đầu audit xác nhận `HEAD == origin/main == 3cfb109ac6918326a2437c84d3dccb8eb637dfb5`. Lượt sửa này chưa commit/push. Hai file docs bị xóa và JSON N4 có sẵn trong working tree được giữ nguyên. Không tạo thêm module `.py` trong lượt sửa; tận dụng source/test/checker đã có từ audit. Theo yêu cầu, không đánh giá comment/review nhóm, slide hoặc phần viết lý thuyết.

## Checklist code

- [x] **DONE FIXED — PaySim account types và exporter.** `src/paysim/community_detection.py` dùng `Customer`/`Merchant`, bắt invariant tổng hai loại bằng số thành viên; stream assignments, xuất top 50 và toàn bộ summary. Native fixture kiểm tra type counts, parallel edges/self-loop, fraud counts và cấm `toPandas()` khi export: PASS. CSV root mới đã qua đối chiếu toàn bộ summaries.
- [x] **DONE FIXED — IBM exporter theo currency, không collect toàn bộ assignment.** `src/ibm_aml/community_detection.py` dùng streaming writer chung; giữ all-summary và bảng amount/count theo `payment_currency`. Native fixture đa tiền tệ và chặn `toPandas()`: PASS. CSV root mới đã thay bộ cũ và qua đối chiếu độc lập.
- [x] **DONE FIXED — Task 1 fail thật và đóng Spark.** `src/paysim/graph_analysis.py` raise khi schema, cardinality, key, value hoặc raw spot-check sai; `finally` giải phóng frame/đóng session. Native negative tests và chạy entry point trên sample: PASS, có `results/paysim/task1_run.json`; artifact gate kiểm tra hash và scope/counts của manifest.
- [x] **DONE FIXED — Stability so phân hoạch theo thành viên.** PaySim tái sử dụng `compare_partition_frames`, bỏ kết luận ổn định vô điều kiện và ghi comparison vào manifest. Native phản ví dụ cùng size nhưng khác thành viên, cùng partition nhưng đổi label: PASS. Hai lượt sample thật có cùng partition, kết quả được ghi trong manifest.
- [x] **DONE FIXED — Task 2 CLI, scope và manifest.** PaySim/IBM dùng chung implementation, nhận sample/full/input/output, cutoff và export feature tùy chọn. Degree sum phải bằng `2E`, aggregate trước plot, limit top 10 trước pandas, stream CSV lớn. Hai entry point sample, independent PageRank reference và manifest: PASS. Full chưa chạy lại; không coi sample là kết quả full.
- [x] **DONE FIXED — Visualization collect sau aggregate/limit.** `src/paysim/visualize.py` aggregate degree trong Spark, limit PageRank trước pandas; top_n giới hạn 1–100. Source syntax và rà soát đường collect: PASS; PNG Task 2 hai sample đã tạo bằng producer mới. Không chạy full visualization để ép xác nhận.
- [x] **DONE FIXED — Protocol đánh giá riêng centrality/community.** API snapshot trong hai module PaySim chỉ dùng topology quá khứ, dùng được cho cả dataset. `src/common/project_audit.py` chọn family/quantile trên hai validation folds, refit snapshot rồi giữ nguyên rule trên test tương lai; thêm novelty baseline và ABSTAIN khi không có validation TP. Native tests chứng minh không dùng cạnh tương lai/ground truth và kiểm tra end-to-end export/manifest trên fixture tổng hợp: PASS. Test nhẹ kiểm tra giải phóng cache khi split sai, giữ rule đã chọn và chấp nhận nhãn nhị phân dạng `1.0/0.0`: PASS. Kết quả 4 experiment thật đã ghi ở phần runtime; hiệu quả các rule đơn biến còn yếu.
- [x] **DONE FIXED — Gate fail closed và bảo vệ tài nguyên.** `scripts/check_project.ps1` có preflight nhẹ, `-Refresh` chạy producer/test/4 experiment lần lượt; từ chối thư mục experiment đã có dữ liệu trước khi chạy nặng. Artifact checker đối chiếu toàn summary, currency, manifest, account snapshot và confusion counts. Profile sample heap 4 GiB dùng hard job cap **7 GiB**, giữ nguyên reserve khoảng 8 GiB, CPU 10%, tối đa 2 logical CPUs, mutex và watchdog; profile full ít bộ nhớ 5/8 GiB đã được kiểm chứng; reserve và CPU cap giữ nguyên. Policy tests và kiểm tra OS Job Object thật: PASS. **Toàn gate PASS, exit code 0.**
- [x] **DONE FIXED — Xóa `notebooks/04_project_verification.ipynb`, cập nhật README.** Dùng CLI và JSON hiện có để kiểm chứng; không thêm notebook thay thế, không thay output/hashes lịch sử của hai notebook Khánh để giả lập một lần chạy mới.

## Checklist runtime — DONE FIXED

- [x] **DONE FIXED — LPA PaySim root và stability.** Producer mới đã xuất assignments, top 50, toàn bộ **186.932** summaries và manifest. Hai lượt stability cùng partition trên **194.195** tài khoản, **0** canonical membership changes. Có **153** cộng đồng chứa fraud. Gate đối chiếu toàn bộ summary và account types với sample gốc.
- [x] **DONE FIXED — IBM LPA sample root.** Xuất assignments, top 50, toàn bộ **86.223** summaries, amount/count theo từng currency và manifest. Gate kiểm tra membership, internal/cross edges, fraud counts, bank diversity và mixed-currency contract.
- [x] **DONE FIXED — 4 temporal experiments thật.** PaySim/IBM × centrality/community có validation, test predictions, account snapshot, metrics, AP, intervals, ví dụ TP/FP/FN, PNG và manifest. Gate kiểm tra hash input/source/output, chọn lại rule từ validation và tính lại confusion counts từ từng prediction. Evidence: các experiment được tạo bởi lệnh kiểm chứng; lượt trước sửa baseline tie được lưu riêng. Không chạy lại experiment khi chỉ thay session factory, vì source/thuật toán đã ghi trong manifest không đổi và toàn bộ hashes vẫn PASS.
- [x] **DONE FIXED — hai notebook full chạy tuần tự với heap 5 GiB / hard job cap 8 GiB.** IBM **15/15** code cells, PaySim **12/12**; mỗi notebook **6 PNG, 22 source hashes** khớp. Verifier kiểm tra execution counts, output, metrics và provenance. IBM có full raw–Parquet multiset reconciliation, motif, ML holdout, full LPA/checker và sample stability. Cả hai notebook lưu output mới thật, không sửa giả metadata.
- [x] **DONE FIXED — full gate `make check`, exit code 0.** Chạy đúng entry point PowerShell bên dưới với native `.venv` Python **3.12.10**, JDK **17.0.20.1**, Spark **3.5.1**, GraphFrames **0.12.2**. Gate nhẹ **44/44 tests PASS**, artifact **26 PASS / 0 FAIL / 0 BLOCKED**, rồi tất cả native/Spark suites, IBM ETL full và rerun motif full hai dataset đều PASS. Không thay source Python sau execution.
- [x] **DONE FIXED — dừng và dọn workload.** Không còn Spark JVM hoặc notebook kernel sau gate. Đã dọn đúng bốn Spark scratch directories của gate bị Windows giữ JAR lúc `Spark.stop()`; sau JVM exit xóa thành công. Không OOM/resource stop trong các lượt hoàn tất. Đo cuối: **21,83 GiB RAM trống / 18,98 GiB commit headroom**.

```powershell
# Entry point giống target make check; không cần cài GNU Make
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\check_project.ps1 -MaxHeap 5g
```

báo cáo JSON được tạo bởi project gate là báo cáo **artifact preflight**, không phải log mọi bước runtime. Full Task 3 transcript ở transcript được tạo khi chạy Task 3 gate; rerun manifests nằm trong manifests được tạo khi chạy lại hai Task 3 producers. Các experiment/check logs là evidence cục bộ, một số bị Git-ignore.

## Bằng chứng và phạm vi

| Kiểm tra trong gate cuối | Kết quả |
|---|---|
| Dependencies + unit tests nhẹ | `pip check` PASS; **44/44**, 3,864 giây |
| Artifact preflight độc lập | **26/26 PASS**, peak working set **414,8 MiB / 512 MiB**, 1 logical CPU, không Spark |
| Native OS guard | **6/6**, 7,080 giây; kiểm tra Job Object thật, cap 7/8 GiB, CPU/affinity, lock và descendant cleanup |
| Native thuật toán chung | **9/9**, 121,577 giây; PageRank reference, Task 1 negative/cleanup, exporters, stability, past-only snapshots, frozen protocol |
| Guard + notebook checkpoint/provenance trong Task 3 gate | **15/15**, 7,283 giây; có test lặp với preflight/native guard, không cộng thành test độc lập mới |
| Motif CSV / evidence / visualization tests | **18/18**, 0,190 giây |
| Motif cơ bản / calibration / v2 | **5/5**, 19,511 giây; **7/7**, 37,502 giây; **8/8**, 88,293 giây |
| IBM ETL full | PASS: **518.581 vertices / 5.078.345 edges / 5.177 fraud labels**; schema, aliases, nulls, endpoint, bank IDs, cardinality, self-loops, currency/time invariants |
| IBM motif full rerun | CSV khớp từng dòng; **54 directed cycles / 2.491 transaction combinations / 45 unordered triples**; USD >10.000 query vẫn **0**, đúng dữ liệu |
| PaySim motif full rerun | CSV khớp; **0 cycle / 30 relay**, gồm **2** cặp cùng giờ chưa biết thứ tự thực |
| Task 1 PaySim | Sample entry point và manifest PASS: **194.195 vertices / 100.729 edges**; không chạy lại raw ETL PaySim toàn bộ |
| Task 2 hai dataset | **Sample** entry points, degree CSV/PNG, independent PageRank reference, top-10 fraud annotations và manifests PASS; không trình bày sample thành kết quả full |

Full PaySim footer có **9.073.900 vertices / 6.362.620 edges**. Gate chỉ đọc footer cho con số này, không dùng nó để tuyên bố đã chạy full raw–Parquet reconciliation PaySim. Full IBM reconciliation đã chạy thực tế trong notebook. Chưa chạy lại toàn bộ producer Task 2 trên full dataset; đây không phải yêu cầu sửa lỗi exporter/sample handoff trong checklist.

## Tối ưu bộ nhớ và hardware protection — DONE FIXED

Profile cũ 6 GiB heap / 10 GiB job từng bị admission từ chối trước Java vì commit headroom sát ngưỡng **17,946 GiB**. Người dùng yêu cầu tối ưu theo RAM hiện có: chuyển hai notebook và gate sang **5 GiB heap / 8 GiB hard job cap**, admission còn khoảng **15,946 GiB**. Đây là giảm ngân sách allocation thực; **không giảm reserve khoảng 8 GiB**, không nâng CPU cap **10%**, không thêm worker quá **2**, không bỏ mutex/watchdog.

`GRAPHGUARD_MAX_HEAP` trong session factory chỉ hạ request: 6g→5g, 4g vẫn 4g; ceiling lớn không tăng request, input sai bị chặn trước JVM. Profile nhỏ không nâng được cap trong kernel đang chạy. Unit tests vẫn kiểm tra policy full 6g/10 GiB; native tests truy vấn OS cap thật 7/8 GiB. Guard không bị bypass.

Cache trung gian được giải phóng đồng bộ bằng `unpersist(blocking=True)` giữa các phase, fold, baseline và review. [Spark 3.5.1 local checkpoint](https://github.com/apache/spark/blob/v3.5.1/core/src/main/scala/org/apache/spark/rdd/LocalRDDCheckpointData.scala) dùng `MEMORY_AND_DISK`, cho phép spill xuống đĩa. Không cắt dữ liệu, giảm folds, sửa feature/ngưỡng hoặc đổi protocol để chạy được. Skill và PowerShell gate đã cập nhật profile này. Không dùng GPU vì backend hiện tại chưa hỗ trợ/kiểm chứng offload.

| Workload, chạy tuần tự | Heap / job cap GiB | Peak job commit GiB | RAM trống thấp nhất GiB | Host CPU cao nhất quan sát |
|---|---:|---:|---:|---:|
| Notebook IBM full, 1.851,0 giây | 5 / 8 | **5,97** | **13,49** | 62,1% |
| Notebook PaySim full, 1.175,1 giây | 5 / 8 | **5,87** | **14,58** | 41,6% |
| PaySim LPA root/stability refresh | 4 / 7 | 3,61 | 18,19 | 33,1% |
| IBM LPA root refresh | 4 / 7 | 3,47 | 18,45 | 29,4% |
| IBM baseline full trong gate | 5 / 8 | 2,91 | 19,33 | theo manifest |
| PaySim baseline full trong gate | 5 / 8 | 3,63 | 17,77 | theo manifest |

Host CPU là tổng toàn máy, khác giới hạn **job CPU 10%**. Không có cảm biến nhiệt đáng tin cậy; đây là bằng chứng về giới hạn và lần chạy, không phải bảo đảm chống lỗi nguồn/tản nhiệt/phần cứng. Nếu có resource stop/OOM hoặc tiếng lạ/tắt máy, dừng điều tra, không tự retry.

## Fraud results: giữ kết quả thật và giới hạn diễn giải

### Motif notebook full, reused internal temporal holdout

Metrics tái lập hoàn toàn sau tối ưu bộ nhớ. Test không dùng để chọn lại threshold.

| Dataset / family | Threshold | TP | FP | FN | TN | Precision | Recall | F1 | Average precision |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| PaySim transaction-only | 0,70 | 889 | 713 | 3.361 | 1.243.773 | 55,49% | 20,92% | 30,38% | 0,124546 |
| PaySim motif-assisted | 0,70 | **1.191** | 1.489 | 3.059 | 1.242.997 | **44,44%** | **28,02%** | **34,37%** | 0,207101 |
| IBM transaction-only | 0,50 | 885 | 9.057 | 912 | 1.004.710 | 8,90% | 49,25% | 15,08% | 0,056023 |
| IBM motif-assisted | 0,50 | **474** | 4.059 | 1.323 | 1.009.708 | **10,46%** | **26,38%** | **14,98%** | 0,056472 |

PaySim motif-assisted cải thiện F1/AP nhưng không có cycle; lợi ích graph context chưa chứng minh count motif có đóng góp độc lập. IBM giảm FP nhưng giảm recall và F1 nhẹ; không kết luận cả hai dataset cải thiện mạnh. Nhãn thật `isFraud` không bị thay bằng dự đoán.

### Rule centrality/community, internal sample holdout

Chọn rule trên hai validation folds, khóa trên test; có novelty baseline và ABSTAIN. PaySim test **20.034 giao dịch / 71 fraud**, IBM **19.962 / 27**.

| Nhánh | Rule | TP | FP | FN | Precision | Recall | F1 | Alert rate |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| PaySim centrality | PageRank thấp, q=0,10 | 68 | 18.674 | 3 | 0,363% | 95,77% | 0,723% | 93,55% |
| PaySim community | Cross fraction thấp, q=0,10 | 71 | 19.963 | 0 | 0,354% | 100% | 0,706% | 100% |
| IBM centrality | PageRank cao, q=0,99 | 1 | 910 | 26 | 0,110% | 3,70% | 0,213% | 4,56% |
| IBM community | Community lớn, q=0,95 | 1 | 1.433 | 26 | 0,070% | 3,70% | 0,137% | 7,18% |

**Các rule đơn biến này không đạt làm detector fraud độc lập.** PaySim community cảnh báo tất cả; recall 100% không phải thành công. Rule IBM chọn trên validation kém novelty baseline ở test; không chọn lại rule theo test để che kết quả. Ít nhất một endpoint chưa có trong snapshot ở **100% PaySim test / 66,25% IBM test**. Scope sample thưa hạn chế lịch sử, nhưng chưa tách riêng ảnh hưởng lấy mẫu với cấu trúc phát sinh tài khoản vốn có; cần kiểm chứng cùng scope trước khi kết luận nguyên nhân. Không so điểm trực tiếp pilot sample với notebook motif full.

Sample có **153 PaySim / 89 IBM fraud edges**. Top PageRank được chọn trước khi đối chiếu nhãn: IBM có hai tài khoản nhận lần lượt 2 và 1 fraud transactions; PaySim top 10 có incident fraud counts bằng 0, được gate đối chiếu đúng cạnh gốc. Đây là mô tả, không phải confusion matrix của classifier.

**Kết luận bàn giao:** checklist lỗi code và các gate đã DONE FIXED. Có API features lịch sử, baseline và evidence để làm bước kết hợp tiếp theo; chưa có bằng chứng PageRank/LPA riêng đạt 9/10 về hiệu quả fraud. Chưa triển khai fusion theo yêu cầu của người dùng. Khi kết hợp phải thống nhất input scope/cutoff/transaction index; không join `event_id` cục bộ từ các run độc lập.

## Review ngày 23/10 — Điểm chất lượng và phương án tích hợp

<a id="review-ngay-2310--diem-chat-luong-va-phuong-an-tich-hop"></a>

### 1. Cách chấm và phạm vi

Đây là điểm review kỹ thuật tham khảo, không phải điểm chính thức của giảng viên. Chấm theo workstream được PCCV giao; không chấm cá nhân từ số dòng code, số commit hoặc Status của CSV. Công việc review/final và report không bắt buộc tạo module riêng.

Code xét correctness khoảng 40%, testing/reproducibility 25%, cấu trúc/maintainability 20%, tài nguyên/scope 15%. Output xét đúng yêu cầu, phạm vi kiểm chứng, truy xuất nguồn và diễn giải. **Output analytics đúng không đồng nghĩa hiệu quả detector cao.** Các số điểm là đánh giá reviewer, không phải metric của dataset hoặc một phép quy đổi F1→điểm.

| Workstream / thành viên theo PCCV | Code /10 | Output đúng nhiệm vụ /10 | Bằng chứng và điểm còn thiếu |
|---|---:|---:|---|
| Hạ tầng/common — Thảo, phối hợp lead | 8,9 | 8,5 | Native Windows/JDK17, shared session, guard/cleanup được test; evidence vẫn cần dựng lại trên clone/máy khác |
| Task 1 / ETL — Thảo, Tuệ Minh; Khánh QA IBM | 8,5 | 8,5 | Schema/count/key/label tests, full IBM raw reconciliation; PaySim full raw multiset chưa chạy lại; balance cùng max(step) có tie chưa xác định intrahour |
| Task 2 — Châu Anh; Phương review/final | 8,6 | 8,0 | Degree/PageRank đúng tham số, reference/manifest PASS; root outputs còn sample; pilot standalone precision yếu |
| Task 3 — Khánh; Phương/Hoàng review/final | 8,8 | 8,5 | Full motif query và multiplicity/time/currency checks; temporal experiments/witness/ablation; test cũ đã xem, graph context chưa tách hết khỏi motif count |
| Task 4 — Hoàng; Châu Anh/Khánh support/final | 8,7 | 8,0 | Types/currency/all-summary và membership stability đúng; full IBM review; full PaySim nghiệm thu tương ứng chưa có; LPA không phải classifier |
| Comparison — Phương, cùng các nhánh/report | 8,0 | 7,5 | Degree PMF được kiểm tra trên sample; tổng hợp Task 1–4; chưa có benchmark fusion cùng population |
| **Trung bình tham khảo các workstream trên** | **8,6** | **8,2** | Trung bình reviewer, không cộng deadline/review lặp thành điểm mới |
| Detector kết hợp ba nhánh | **Chưa chấm** | **Chưa có output** | Chưa triển khai, không dùng PASS của component gate để chấm điểm hệ thống chưa tồn tại |

Các điểm trên thuộc code/kết quả analytics. Hiệu quả fraud/AML đọc từ confusion matrices thật: motif-assisted PaySim precision/recall/F1 **44,44/28,02/34,37%**, IBM **10,46/26,38/14,98%**. Pilot centrality/community chỉ **0,07–0,36% precision**, PaySim community alert toàn bộ test. Chưa có căn cứ cho điểm 9/10 về hiệu quả phát hiện laundering hoặc tuyên bố fusion tốt hơn.

### 2. Kết luận ba nhánh đã chuẩn ở mức nào?

- **Degree/PageRank:** dùng được như thuật toán cấu trúc và API historical snapshot. Top-10 root là bảng mô tả sample, không phải account feature table full hoặc danh sách fraud. Top-10 selection không dùng nhãn; annotation chỉ hậu kiểm.
- **3-cycle/relay:** query baseline và causal motif features đã có tests độc lập và full outputs. 54 IBM cycles là audit có dùng nhãn, không được đưa vào detector dưới dạng kết quả phát hiện mù. Detector phải dùng feature không nhận nhãn trong `src/motif/features.py`.
- **LPA/community:** partition, exporter, member types và currency summaries đã được kiểm tra; `snapshot_features` cung cấp đặc trưng không nhãn. Community label không phải class fraud; `fraud_rate` và amount/fraud summaries trên toàn dataset không được đưa ngược vào training/test.
- **Phần chưa chuẩn để ghép ngay:** root Task 2/4 là sample, motif notebook là full; pilot component dùng hai validation folds, motif dùng ba folds; snapshot pilot cố định cả khoảng test. Các run có `event_id` cục bộ. Vì vậy chưa có một common evaluation population hoặc final fusion score.

### 3. Objective và đơn vị đánh giá cuối

Giữ **PaySim core** đúng phạm vi môn học; dùng **IBM HI-Small cho đánh giá laundering trực tiếp**. Mỗi dataset có model/threshold/metrics riêng. Đơn vị chính là transaction/edge với nhãn gốc. PaySim fraud và IBM laundering không được gom làm một nhãn để báo một F1 chung. Account/community risk chỉ là đầu ra xếp hạng điều tra nếu chưa định nghĩa ground truth account/ring phù hợp.

Mục tiêu có thể nghiệm thu: “Dùng ngữ cảnh centrality, temporal motifs và community để xếp hạng/cảnh báo giao dịch; đo xem các nhóm feature có cải thiện phát hiện nhãn laundering so với transaction-only hay không, tại khối lượng cảnh báo đã khai báo.” Không hứa cả ba nhóm sẽ luôn cải thiện hoặc mọi cycle đều illicit.

### 4. Thiết kế tích hợp đề xuất, chưa code/chạy fusion

**A. Common table và identity.** Tạo normalized transaction table và index đúng một lần trên input fingerprint cố định. Giữ đủ duplicate rows; reuse cùng `event_id` trong toàn run. Không dùng fingerprint nội dung làm unique key nếu duplicate có thể trùng. Feature joins phải unique theo event ID, không đổi số dòng hoặc bỏ cold-start/unflagged/FX/self-loop khỏi mẫu số test.

**B. Point-in-time features trên cả train, validation, test.** Motif dùng strict-past history/witness đúng như hiện tại. Degree/PageRank/LPA lấy snapshot trước block đang chấm. Cần snapshot cho **training rows**, không lấy snapshot tại cuối training rồi gán cho những transaction xảy ra trước snapshot đó. Đó là nhìn tương lai trong training dù không dùng nhãn.

Một lịch khởi đầu tiết kiệm để thẩm định là các boundary theo thời gian 20%, 40%, 50%, 65%, 80%, giữ timestamp ties; tạo snapshot trước block kế tiếp. Block đầu không có lịch sử thì features mặc định/cờ unseen, không gán fraud. Đây là **đề xuất lịch**, chưa là thông số được nghiệm thu. Benchmark fixture/sample và memory trước; có thể chọn lịch theo ngày nghiệp vụ nếu phù hợp. Không chạy PageRank/LPA cho mỗi transaction hoặc mỗi timestamp thô trên laptop. Giữ lag/as-of của centrality/community và strict-past semantics của motif rõ trong export; mọi ablation dùng cùng feature availability.

Snapshot có thể cập nhật bằng giao dịch đã quan sát của block trước, kể cả khi đó là khoảng validation/test, nhưng tuyệt đối không dùng nhãn của các khoảng đó để tính feature. Refit/tuning model chỉ dùng đúng prefix training của fold. FX không đổi amount sang cùng đơn vị nếu chưa có tỷ giá; normalize scales trên training theo currency/type.

**C. Reuse module hiện có.** Điều phối chung trong `src/motif/pipeline.py`; gọi `src/motif/features.py`, `src/paysim/metrics.py::snapshot_features` và `src/paysim/community_detection.py::snapshot_features`. Hai API topology/history dùng được qua dataset adapter. Bổ sung feature allowlist/model input trong `src/motif/modeling.py`/`config.py`, không tạo ba bản pipeline sao chép hoặc thêm module chỉ để nối CSV. Các snapshot được cache/spill theo từng cutoff rồi giải phóng; chỉ một workload nặng.

**D. Mô hình và ablation.** Bắt đầu bằng cùng family cây nhỏ đang có; training/weights/scales từ prefix, cùng seed và tuning budget. So sánh: transaction-only; +centrality; +motif; +community; full fusion; full trừ lần lượt centrality/motif/community. Thêm so sánh role-history với motif-counts nếu cần khẳng định riêng giá trị motif. Không sử dụng các con số risk_score từ những model/run khác nhau để cộng 1/3 thủ công. Không mặc định đổi sang GNN/GPU hoặc mở hyperparameter grid lớn.

Cần thêm cờ src/dst seen, số đối tác/degree/PR nguồn–đích, motif counts theo cửa sổ, size/cross-fraction cộng đồng và cùng/khác nhóm khi cả hai đã thấy. Không đưa label ID số học, account ID, fraud_rate hậu kiểm, balance cuối kỳ, `Patterns.txt` hoặc isFraud lồng trong struct vào model. Unseen là điều kiện thiếu lịch sử, không phải ground truth fraud.

**E. Chọn và khóa operating point.** Dùng cùng walk-forward boundaries cho mọi family; fit model chỉ trên prefix, tune family/threshold trên validation. Báo cả mean/worst fold và số positives. Chọn một metric chính trước test: AP để đánh giá ranking, kèm precision/recall/F1 của operating point đã chọn và ngân sách review cố định. Nếu đề yêu cầu F1 thì giữ F1 làm selection criterion, đồng thời vẫn báo AP và alert load. Không chọn lại criterion vì test của một model đẹp hơn.

Ngân sách review có thể là K hoặc tỷ lệ alert định trước; cần nêu tie policy. Top-K và threshold alert là hai operating policies khác nhau khi nhiều giao dịch cùng score. Xuất cả số alert thực tế. Precision@K/Recall@K, false positives/1.000 transactions, AP/PR curve, TP/FP/FN/TN và novelty baseline giúp tránh việc “recall cao vì alert gần tất cả”. Score weighted tree chưa phải calibrated probability. Cần calibration riêng trên validation nếu muốn gọi score là xác suất.

**F. Holdout và kiểm toán.** Các full test hiện có đã được xem: dùng được làm reused internal holdout khi báo đúng giới hạn, không được gọi “untouched” chỉ vì đổi seed hoặc chia lại. Nếu cần kết luận tổng quát hóa mới, phải có batch/dataset tương thích chưa dùng; không tải thêm biến thể lớn hoặc chạy nhiều seed tự động trong lượt review này. CI binomial hiện có chưa xử lý phụ thuộc tài khoản/thời gian; có thể bổ sung uncertainty theo block ngày khi có đủ blocks, ghi hạn chế khi không đủ.

Prediction table tối thiểu: dataset/input/run ID, event ID, event time, feature/snapshot as-of, risk score, alert, threshold/policy, unknown flags và witness/reason references. Truth join ở bước đánh giá; report có paired metrics/ablation, alert-budget chart, PR curve và các ví dụ TP/FP/FN. Không suy từ một vài TP có cycle rằng toàn bộ độ tăng F1 do cycle.

### 5. Checklist nghiệm thu fusion trước khi gọi kết quả cuối

- [ ] **COMMON INPUT:** cùng input fingerprint, transaction index, split boundaries, labels và test denominators ở mọi ablation.
- [ ] **POINT-IN-TIME:** thêm/sửa cạnh tương lai không đổi feature của transaction quá khứ; snapshot as-of < quyết định, bao gồm training rows; same-time không giả thứ tự.
- [ ] **NO LABEL LEAKAGE:** thay nhãn validation/test không đổi features, fit/scales hay lựa chọn threshold; nhãn thật vẫn giữ nguyên ở evaluator.
- [ ] **JOINS/COUNTS:** không duplicate/lost rows qua join; giữ cold-start và các transaction không có motif; confusion sums đúng N và P.
- [ ] **REFERENCE:** tiny oracle cho degree/PR, motif witnesses, community membership; export model reload tái tạo prediction; checksum không bị sửa.
- [ ] **BASELINES/ABLATIONS:** đủ transaction-only, từng nhánh, full/drop-group; cùng population/model budget; báo cold-start subgroup, novelty và false alerts.
- [ ] **RESULTS:** thresholds chọn validation, manifest lưu config và input/source/output hashes; test reuse được khai báo; không đòi metric phải tăng để test PASS.
- [ ] **OPERATING QUALITY:** có tiêu chí alert load/precision/recall do nhóm xác định trước; không đạt thì báo chất lượng chưa đạt, tách khỏi software PASS.
- [ ] **HARDWARE:** profile được guard admit, chạy tuần tự, không bypass reserve/CPU/job cap, dừng điều tra nếu OOM/pressure stop.

Đây là checklist **chưa hoàn tất**, không bị đánh dấu DONE FIXED cùng những lỗi component đã sửa. Các test hiện tại là nền cho integration, chưa tự chứng minh tất cả tiêu chí fusion trên đã đạt.

### 6. Sửa tài liệu trong lượt review này

README chuyển sang objective toàn nhóm, core/bonus/nhãn đúng, kiến trúc Task 1–4 và fusion phân biệt trạng thái; có đủ bảy thành viên/ownership theo CSV, scope sample/full, kết quả thật và runbook. Hardware giữ một mục ngắn cuối tài liệu, chi tiết ở skill/audit.

Part B đã điền Task 2, bổ sung Task 4 sample của cả nhóm, mở Comparison khỏi chỉ motif. Đã bỏ suy luận “5 raw spot-checks chứng minh toàn ETL 100%”, “power-law/vertex-cut bắt buộc” khi chưa có fit/benchmark. File Part A hiện chỉ chứa derivation 3.3; CC/LPA ở note riêng. Chưa xác nhận bản hoàn chỉnh 3.1/3.2 trong repo; không chấm thiếu thuật toán vì nhiệm vụ lý thuyết này, nhưng phải đưa bản report tương ứng vào bàn giao nếu barem yêu cầu. Đã ghi rõ `max_by(balance, step)` chưa xác định thứ tự intrahour khi nhiều event cùng max(step); vertex balance cuối kỳ không dùng trong detector. Không thay status CSV hoặc tự nhận đã duyệt thay reviewer.

Nguồn định hướng: [IBM AMLworld](https://arxiv.org/html/2306.16424v3#A4) về temporal graph features; [Saito & Rehmsmeier](https://journals.plos.org/plosone/article?id=10.1371/journal.pone.0118432) về precision–recall trong dữ liệu lệch lớp; [GraphFrames motif API](https://graphframes.io/04-user-guide/04-motif-finding.html) và [LPA](https://graphframes.io/04-user-guide/06-graph-clustering.html). Thiết kế/rubric ở trên là đề xuất review của repo, không phải score benchmark lấy từ các bài báo.

### 7. Make check mới ngày 23/10

- **PASS, exit 0:** `powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\check_project.ps1 -MaxHeap 5g`.
- `pip check` PASS; **44/44 tests nhẹ (2,599 giây)**; artifact **26/26 PASS**, không FAIL/BLOCKED.
- Native guard **6/6 (7,043 giây)**; native algorithm **9/9 (140,367 giây)**; Task 3 guard/checkpoint **15/15 (7,234 giây)**; artifact/evidence suites **18/18 (0,203 giây)**; motif cơ bản **5/5 (18,529 giây)**, calibration **7/7 (35,138 giây)**, v2 **8/8 (81,016 giây)**. Một số suite lặp test, không cộng thành số test độc lập.
- IBM ETL full invariants PASS; IBM full motif và PaySim full motif rerun khớp toàn bộ CSV bàn giao, manifests/evidence PASS.
- Chỉ một workload nặng, cùng guard; không có OOM/resource stop. Hai notebook full không chạy lại trong lượt tài liệu này vì Python source không đổi; gate xác nhận saved execution/source hashes/metrics vẫn khớp. Execution đầy đủ của notebooks là ngày 22/10 đã ghi ở trên.
- Kết quả này nghiệm thu component correctness và evidence hiện có. **Chưa nghiệm thu detector fusion** hoặc các ô checklist fusion chưa được thực hiện.

## Audit ban đầu — lưu đối chiếu, không phải trạng thái hiện tại

## Đối chiếu các nhiệm vụ code của thành viên

| Người / nhóm nhiệm vụ trong CSV | Source thực tế | Kết luận từ code và phép kiểm tra |
|---|---|---|
| Tuệ Minh — Task 1 PaySim, final/check repo | `src/paysim/graph_analysis.py` | Có GraphFrame construction, schema/count/probes và raw spot-check. Sample integrity và full footer counts đúng; module vẫn có nhánh chỉ in FAIL rồi kết thúc thành công. |
| Thảo — session, tổ chức source, ETL PaySim/IBM, Parquet, integrity | `src/common/{spark_session,windows_runtime,graph_utils}.py`, `src/paysim/{etl_mapping,export_parquet}.py`, `src/ibm_aml/etl.py` | Đã có code và full/sample input. Sample được đối chiếu schema/key/amount/label/time và endpoint đầy đủ. Full row integrity/raw reconciliation không được chạy lại trong lượt nhẹ này; có bằng chứng IBM ETL ở notebook đã lưu. |
| Châu Anh — Task 2 PaySim và IBM | `src/paysim/metrics.py`, `src/ibm_aml/metrics.py` | Có degree, distribution, PageRank reset=0.15/maxIter=10, top 10 và PNG. Hai CSV top 10 khớp reference độc lập trên sample. Entry point hiện hard-code sample; thiếu CLI chọn input/output và run manifest cho Task 2. |
| Khánh — toy, Task 3 PaySim/IBM, kiểm chứng ETL và Task 4 IBM | `src/motif/*.py`, `src/{paysim,ibm_aml}/motif_finding.py`, hai notebook `03_khanh_*` | CSV motif hợp lệ. Hai notebook đã lưu đủ 12/15 cell, mỗi file 6 hình, source hashes và confusion metrics nhất quán. Lượt này kiểm tra bằng chứng đã lưu, không chạy lại full detector. |
| Hoàng — Task 4 PaySim và IBM; Châu Anh — kiểm tra stability PaySim | `src/{paysim,ibm_aml}/community_detection.py`, `src/ibm_aml/verify_communities.py` | Có LPA maxIter=5 và checkpoint. **PaySim sai type counts và stability chưa kiểm tra thành viên cụm. IBM code exporter hiện có sửa currency, nhưng CSV root bàn giao vẫn cũ.** |
| Phương — final Task 2/3, comparison | Module Task 2/3 ở trên, `src/comparison/degree_distribution.py` | Degree comparison CSV khớp cả hai sample. Motif comparison đã có source/output tương ứng. CSV giao nhiệm vụ comparison chủ yếu là tổng hợp kết quả, không bắt buộc một module thuật toán mang tên Phương. |
| Tuấn Anh, Tuệ Minh — report/integration | Các entry point trong `scripts/`, `Makefile` | Không yêu cầu mỗi người một file thuật toán riêng. Chưa có một gate cũ bao phủ toàn project; lượt này bổ sung artifact gate và notebook chung. Không đánh giá nội dung comment/báo cáo theo yêu cầu của người dùng. |

## Các vấn đề cần sửa

### P1 — LPA PaySim đếm sai loại tài khoản

[community_detection.py:119](../src/paysim/community_detection.py#L119) và dòng kế tiếp so `account_type == "C"/"M"`, trong khi [ETL](../src/paysim/etl_mapping.py#L53) tạo `Customer`/`Merchant`.

`results/paysim/communities.csv` có 160.262 Customer và 33.933 Merchant. Summary top 50 có tổng 211 thành viên nhưng cả hai cột loại tài khoản cộng lại bằng 0. Đối chiếu từng community phát hiện 50 trường sai; ví dụ label `6997` có 6 Customer, CSV lưu 0. Đây là lỗi code và đã xuất hiện trong artifact, không phải một kết quả fraud bằng 0 hợp lý.

Cần sửa mapping loại account và xuất lại summary; giữ invariant `customer_count + merchant_count == member_count` đối với contract PaySim hiện tại.

### P1 — Kết quả cộng đồng IBM root chưa theo exporter hiện hành

`results/ibm_aml/community_summary.csv` vẫn chứa `total_tx_amount` không kèm currency; input sample có 15 payment currencies. Gate từ chối tổng nominal amount không có đơn vị rõ ràng.

[Exporter hiện tại](../src/ibm_aml/community_detection.py#L211) đã có all-community summary và `community_amounts_by_currency.csv`, nhưng hai file này chưa có ở thư mục kết quả root đang bàn giao. Cần xuất lại và thay đồng bộ bộ artifact root bằng code hiện hành. Không nên sửa detector motif hoặc viết lại IBM LPA chỉ để xử lý file xuất cũ này. Các run kiểm chứng riêng trong thư mục ignored hoặc bảng LPA trong notebook không tự cập nhật CSV root.

### P1 — Task 1 PaySim có thể báo thành công sau một kiểm tra FAIL

[graph_analysis.py:210](../src/paysim/graph_analysis.py#L210) và các nhánh count/schema chỉ in kết quả boolean; không gom các điều kiện để raise/exit nonzero. Cuối hàm của phiên bản được audit khi đó vẫn in `Task 1 Completed Successfully`. Vì vậy entry point này chưa phải một test gate đáng tin cậy khi dữ liệu sai nhưng vẫn đủ schema để các probe chạy.

Cần biến vi phạm schema/count/referential integrity/raw matching thành lỗi thực sự và đảm bảo Spark được đóng trong `finally`. Footer counts và sample hiện tại đúng không loại bỏ lỗi điều khiển này.

### P2 — Stability PaySim chưa chứng minh ổn định phân hoạch

[check_lpa_stability](../src/paysim/community_detection.py#L196) lưu số cộng đồng và top-5 sizes, rồi in kết luận ổn định vô điều kiện ở dòng 240. Hai phân hoạch `{A,B}/{C,D}` và `{A,C}/{B,D}` có cùng số/size nhưng khác thành viên.

Cần so assignment theo thành viên sau canonicalization, đồng thời báo khác biệt quan sát được. Có thể dùng hướng so sánh đã có trong `src/ibm_aml/verify_communities.py`; không so trực tiếp numeric label giữa hai lần chạy.

### P2 — Phạm vi sample/full và khả năng xuất dữ liệu lớn

- Hai `metrics.py` dùng cố định `data/processed/sample/...`; kết quả PageRank đã đối chiếu là sample, không chứng minh top 10 trên toàn dataset. Task 2 chưa có run manifest liên kết input/code/output.
- PaySim chỉ xuất summary top 50; chưa có export summary của mọi cộng đồng để đối chiếu tổng toàn graph. IBM đã có code export này nhưng bộ kết quả root chưa được cập nhật.
- [PaySim export assignments](../src/paysim/community_detection.py#L256) collect toàn bộ assignment bằng `toPandas()`. [Visualization](../src/paysim/visualize.py#L26) cũng có đường collect toàn bộ degrees/PageRank trước khi giới hạn. Không chạy thử trên full 9 triệu tài khoản để ép PASS; cần aggregate/limit trước collect và stream assignment ra đĩa. Hardware guard/maxResultSize vẫn giữ nguyên.
- Chưa có một lệnh chạy lại ETL → Task 2 → motif → LPA với cùng input scope và manifest ở mọi nhánh. Artifact gate mới giúp phát hiện dữ liệu bàn giao sai; nó không thay toàn bộ integration runtime test.

## Kiến trúc có thiếu thuật toán bắt buộc không?

Đã có các nhánh lõi `raw → ETL/Parquet → GraphFrame → degree/PageRank, motif, LPA`. Việc cần hoàn thiện tập trung vào invariants, scope, artifact consistency và kiểm chứng tích hợp. PCCV không bắt buộc một classifier hợp nhất PageRank + motif + LPA; pipeline motif nâng cấp hiện cũng chưa dùng PR/LPA làm feature.

Connected Components được CSV ghi là mở rộng tự chọn sau quyết định GO/NO-GO. Không có bằng chứng GO trong CSV hiện tại, nên chưa coi thiếu module CC là lỗi bắt buộc. Số fraud bằng 0 của một truy vấn hoặc một top-50 community table không tự chứng minh bug; phải kiểm tra mẫu số, scope và nhãn thực tế.

## Kết quả chạy kiểm chứng lần này

Trên Windows `.venv` Python 3.12.10:

- `pip check`: PASS.
- 34 unit test nhẹ, gồm các phản ví dụ cho type counts, currency, duplicate assignment, PageRank/self-loop/parallel-edge/reference và HTML metrics: PASS.
- Artifact gate: **13 PASS, 2 FAIL, 2 WARN**, exit code **1**. Hai FAIL là kết quả cộng đồng PaySim và IBM nêu trên. Hai WARN là thiếu all-community/currency exports ở thư mục root.
- Sample PaySim: 194.195 vertices, 100.729 edges, 0 dangling endpoints. Sample IBM: 119.043 vertices, 99.869 edges, 0 dangling endpoints.
- Full footer counts: PaySim 9.073.900 / 6.362.620; IBM 518.581 / 5.078.345. Chỉ kiểm tra cardinality ở footer, chưa quét lại full row integrity.
- Top 10 PageRank và degree comparison khớp reference độc lập trên hai sample. Reference giữ parallel edges/self-loops và normalization theo [source Spark 3.5.1](https://github.com/apache/spark/blob/v3.5.1/graphx/src/main/scala/org/apache/spark/graphx/lib/PageRank.scala), không dùng điều kiện sai `PageRank <= 1`.
- Hai notebook motif có output/source hash và TP/FP/FN/TN nhất quán; không chạy lại detector. IBM giữ lịch sử hai phiên đã ghi rõ trong notebook.
- Notebook kiểm chứng toàn project ở thời điểm audit đã chạy đủ 5/5 cell trên Windows, không lỗi cell, có biểu đồ và giữ nguyên kết luận project FAIL. File `04_project_verification.ipynb` đã được xóa trong lượt sửa theo yêu cầu người dùng.

Máy chưa có GNU Make cho Windows trong PATH; đã chạy đúng PowerShell entry point được `make check` gọi:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\check_project.ps1
```

`make check` mới chạy bounded artifact gate trước; chỉ khi PASS mới gọi lại gate Task 3 nguyên gốc, giữ các kiểm chứng cũ. `make check-artifacts` hoặc `-ArtifactsOnly` chỉ chạy phần nhẹ. Lần này hai FAIL làm lệnh dừng trước Spark. Các lượt Spark có thể gọi riêng ở `make check-task3`, `make check-task4` và `make check-task4-full`, phải chạy lần lượt. Trong lượt audit này không khởi động JVM/Spark: RAM trống khoảng 17,5–17,7 GiB thấp hơn admission xấp xỉ 17,95 GiB của profile bảo vệ; không tăng tài nguyên hay bỏ guard để chạy tiếp.

Checker CLI dùng 1 logical CPU, peak working set quan sát 384,9 MiB trong lần gate cuối; ngân sách RSS 512 MiB được kiểm tra theo batch. Notebook ghi số đo riêng trong output cuối. Đây là tác vụ kiểm chứng nhẹ; không phải một lần full Spark/LPA mới.

JSON chi tiết được lưu local tại báo cáo JSON được tạo bởi project gate. Source kiểm chứng: `src/common/project_audit.py`; entry point: `scripts/check_project.ps1`; negative tests: `tests/test_project_audit.py`. Các sửa đổi lần này chưa được commit/push; source thuật toán và CSV của thành viên được giữ nguyên để nhóm thấy rõ lỗi cần xử lý.
