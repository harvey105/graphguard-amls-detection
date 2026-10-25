# Hướng dẫn trình bày từng code cell

Các cell và output đều đã chạy trong original full notebook. Không thực thi lại khi xem. HTML tĩnh giữ code và toàn bộ saved output. Function copy được đối chiếu AST với source snapshot; import còn lại có thể tra src/.

## ibm_aml

[Notebook gốc](IBM_full_system.ipynb) · [Xem code và output offline](IBM_full_system.html)

### Cell 1 — code-environment

**Mục đích:** Xác nhận runtime Windows, dependency pins và bảo vệ bộ nhớ trước tính toán.

**Đọc code:** Khởi động qua session factory có guard; không tạo SparkSession bên ngoài guard.

**Đọc output:** Đọc master/task slots, heap và job cap thực tế. CPU available không đồng nghĩa mọi phase đều CPU-bound.

**Saved output:** 3 blocks; execution_count=1.

### Cell 2 — code-protocol

**Mục đích:** Khai báo trước các đối chứng, tuning budget và temporal protocol.

**Đọc code:** SYSTEM_FAMILY_GROUPS quyết định feature allowlist; mỗi family được train trên cùng prefix.

**Đọc output:** Không lấy metric tốt nhất trên test làm model được chọn; novelty control tách hiệu ứng tài khoản mới.

**Saved output:** 2 blocks; execution_count=2.

### Cell 3 — code-edge-contract

**Mục đích:** Giữ đúng contract giao dịch chung cho mọi nhánh.

**Đọc code:** Kiểm tra amount/time/labels/keys, cast có kiểm soát; hash content không chứa nhãn.

**Đọc output:** Sai dữ liệu thì dừng; không dùng việc cast thành null để che lỗi.

**Kernel được show trong cell:** `normalize_edges` ([source](../src/motif/features.py)).

**Saved output:** 1 blocks; execution_count=3.

### Cell 4 — code-full-index

**Mục đích:** Tạo và persist index một lần; hiển thị scope/counts và lịch train/validation/test thật.

**Đọc code:** Full input là canonical processed data; event_id và timestamp cutoffs được dùng chung.

**Đọc output:** Năm dòng là preview của full input. So sánh full count với unique IDs; timeline cho biết cutoff thực tế.

**Saved output:** 6 blocks; execution_count=4.

### Cell 5 — code-raw-reconciliation

**Mục đích:** Đối chiếu toàn bộ raw mapping với Parquet theo hai chiều, giữ duplicate multiplicity.

**Đọc code:** exceptAll hai chiều kiểm tra mapping; raw/source hashes giữ provenance.

**Đọc output:** Cả raw_minus_parquet và parquet_minus_raw phải bằng0. Số dòng bằng nhau riêng nó chưa chứng minh mapping đúng.

**Saved output:** 3 blocks; execution_count=5.

### Cell 6 — code-pagerank-update

**Mục đích:** Thể hiện phép truyền rank theo hướng giao dịch.

**Đọc code:** Rank nguồn nhân transition weight; tổng incoming và reset term tạo rank vòng mới.

**Đọc output:** Checkpoint/loop được import từ dataframe_pagerank; kernel hiển thị ở đây chạy trong từng iteration.

**Kernel được show trong cell:** `pagerank_update` ([source](../src/paysim/metrics.py)).

**Saved output:** 1 blocks; execution_count=6.

### Cell 7 — code-degree-metrics

**Mục đích:** Tính in/out/total degree từ full physical edges.

**Đọc code:** groupBy đếm multiplicity; left join và fillna giữ isolate.

**Đọc output:** Invariant tổng degree=2E sẽ được kiểm tra trong bước full analytics.

**Kernel được show trong cell:** `account_degree_metrics` ([source](../src/paysim/metrics.py)).

**Saved output:** 1 blocks; execution_count=7.

### Cell 8 — code-full-centrality

**Mục đích:** Chạy PR10/full Degree, export mọi account và biểu diễn phân bố/hubs.

**Đọc code:** Kernels trong hai cell trước được truyền vào backend; assertions kiểm tra mass và coverage.

**Đọc output:** Top10 chỉ là structural hubs từ full graph. Detector chưa được train ở bước này.

**Saved output:** 5 blocks; execution_count=8.

### Cell 9 — code-lpa-update

**Mục đích:** Giải thích cập nhật community labels thay vì chỉ gọi hàm LPA.

**Đọc code:** Join nhãn hàng xóm → cộng phiếu → min(-votes,label) → cập nhật đồng bộ.

**Đọc output:** Tie rule khác GraphX unspecified ties nên không ép partition hai backend giống nhau.

**Kernel được show trong cell:** `lpa_update` ([source](../src/paysim/community_detection.py)).

**Saved output:** 1 blocks; execution_count=9.

### Cell 10 — code-full-communities

**Mục đích:** Xuất mọi assignment, community summary và amount theo currency, rồi kiểm tra độc lập.

**Đọc code:** Full assignments và all-summary được đối chiếu SQL; plot/top10 chỉ là view.

**Đọc output:** positive_tx_count là posthoc label audit, không đi vào feature tạo cảnh báo. Internal/cross edges cần cộng về E.

**Saved output:** 4 blocks; execution_count=10.

### Cell 11 — code-cycle-query

**Mục đích:** Cho thấy query 3-cycle và điều kiện ba accounts khác nhau.

**Đọc code:** GraphFrame.find tìm vòng có hướng; chưa kết luận fraud từ topology.

**Đọc output:** Một vòng có thể được trả ở ba rotations; bước collapse xử lý duplicate rotations.

**Kernel được show trong cell:** `find_three_node_cycles` ([source](../src/motif/toy_cycle.py)).

**Saved output:** 1 blocks; execution_count=11.

### Cell 12 — code-motif-baseline

**Mục đích:** Chạy baseline full và so với baseline bàn giao, giữ kết quả bằng0 nếu dữ liệu cho như vậy.

**Đọc code:** Baseline chỉ mô tả các query của đề; không dùng nó làm label cho model.

**Đọc output:** Không có positive trong baseline không có nghĩa toàn dataset không fraud. Đọc causal coverage và benchmark tiếp theo.

**Saved output:** 3 blocks; execution_count=12.

### Cell 13 — code-rolling-history

**Mục đích:** Tính rolling counts bằng activation/expiry và cumulative sums.

**Đọc code:** Giữ timestamp ties; loại keys chỉ xuất hiện một timestamp vì strict-past count của chúng bằng0.

**Đọc output:** Đây là tối ưu phép tính tương đương, không phải cắt sample hoặc bỏ các transaction khỏi evaluation.

**Kernel được show trong cell:** `_sweep_counts` ([source](../src/motif/features.py)).

**Saved output:** 1 blocks; execution_count=13.

### Cell 14 — code-star-relay-history

**Mục đích:** Tính sender/receiver histories và fan/relay candidates theo cửa sổ24/168h.

**Đọc code:** Role events, currency keys và điều kiện type riêng PaySim; gọi expiry-prefix kernel phía trên.

**Đọc output:** Same-partner paths còn được trừ sau đó để A→B→A không bị gọi là relay ba accounts.

**Kernel được show trong cell:** `build_star_features` ([source](../src/motif/features.py)).

**Saved output:** 1 blocks; execution_count=14.

### Cell 15 — code-reciprocal-history

**Mục đích:** Phân biệt reciprocal hai accounts với relay ba accounts.

**Đọc code:** Canonical account pair, hai hướng và strict-past witness window.

**Đọc output:** Witness là event thật; role counts bằng0 có thể là kết quả đúng của cấu trúc dữ liệu.

**Kernel được show trong cell:** `build_reciprocal_features` ([source](../src/motif/features.py)).

**Saved output:** 1 blocks; execution_count=15.

### Cell 16 — code-cycle-topology

**Mục đích:** Tìm account cycle không dùng labels hoặc amounts.

**Đọc code:** Distinct topology trước GraphFrames matching tránh nhân mọi tổ hợp historical transactions.

**Đọc output:** Collapse topology không bỏ multiplicity khi temporal transactions được join lại.

**Kernel được show trong cell:** `find_topological_cycles` ([source](../src/ibm_aml/motif_finding.py)).

**Saved output:** 1 blocks; execution_count=16.

### Cell 17 — code-chronological-cycle

**Mục đích:** Tạo witness cycle hợp lệ tại thời điểm giao dịch đóng vòng.

**Đọc code:** Ba rotations, strict chronology, cùng currency và positive amounts; giữ event IDs thật.

**Đọc output:** Cycle có thật không tự chứng minh money laundering hoặc cùng một khoản tiền đi hết vòng.

**Kernel được show trong cell:** `build_temporal_cycle_features` ([source](../src/ibm_aml/motif_finding.py)).

**Saved output:** 1 blocks; execution_count=17.

### Cell 18 — code-disk-motif-checkpoint

**Mục đích:** Giữ lineage và dữ liệu trung gian trên đĩa dưới heap5GiB.

**Đọc code:** Ghi Parquet rồi đọc lại cắt lineage; tránh MemoryStore.putIteratorAsValues khi nhiều task cùng hoạt động.

**Đọc output:** Tăng CPU concurrency cần bỏ object cache lớn và giảm Parquet buffers; không tăng heap/job cap.

**Kernel được show trong cell:** `materialize_motif_stage` ([source](../src/motif/features.py)).

**Saved output:** 1 blocks; execution_count=18.

### Cell 19 — code-motif-feature-builder

**Mục đích:** Kết hợp star/reciprocal/cycle features và giữ một row cho mỗi transaction.

**Đọc code:** Trừ same-partner histories, giới hạn cycle gap theo dataset units; fill0 chỉ cho feature không có motif.

**Đọc output:** Các function trong notebook phía trên thực sự được gọi bởi builder, không phải code minh họa rời kết quả.

**Kernel được show trong cell:** `build_motif_features` ([source](../src/motif/features.py)).

**Saved output:** 1 blocks; execution_count=19.

### Cell 20 — code-motif-full-and-coverage

**Mục đích:** Chạy toàn bộ causal motifs và benchmark structural coverage đối với nhãn.

**Đọc code:** Label chỉ join sau construction để đo coverage/enrichment, không điều kiện hóa feature.

**Đọc output:** Coverage không phải precision/recall của model. Các motif overlap nên không cộng các hàng thành tổng.

**Saved output:** 5 blocks; execution_count=20.

### Cell 21 — code-historical-snapshot

**Mục đích:** Tính C/L trên prefix đúng thời điểm.

**Đọc code:** Lọc step≤cutoff, gọi PR/LPA và tính community size/cross fraction từ edges không có label.

**Đọc output:** Không dùng positive_tx_count của full community audit làm feature; chỉ dùng structural statistics.

**Kernel được show trong cell:** `historical_system_snapshot` ([source](../src/motif/pipeline.py)).

**Saved output:** 1 blocks; execution_count=21.

### Cell 22 — code-snapshot-join

**Mục đích:** Join src/dst snapshots mà không dùng numeric community IDs làm feature.

**Đọc code:** Kiểm tra strict timing, seen flags, same-community và fill defaults có kiểm soát.

**Đọc output:** Unknown history không bị gán là fraud; novelty control đo riêng ảnh hưởng này.

**Kernel được show trong cell:** `join_system_snapshot` ([source](../src/motif/pipeline.py)).

**Saved output:** 1 blocks; execution_count=22.

### Cell 23 — code-common-feature-table

**Mục đích:** Materialize một feature table đầy đủ, cùng event index cho9families.

**Đọc code:** Full rows/unique IDs và future-snapshot assertion; completed block checkpoints có hash để resume.

**Đọc output:** Feature bằng0 hoặc account unseen không phải predicted isFraud=0. Chưa có model prediction ở đây.

**Saved output:** 3 blocks; execution_count=23.

### Cell 24 — code-amount-normalization

**Mục đích:** Cho thấy chuẩn hóa theo training q90 và nhóm feature cụ thể của từng family.

**Đọc code:** log1p(amount/train_q90), unknown-group/FX flags và explicit group allowlist.

**Đọc output:** Không cộng nominal amounts khác currency. Full fusion luôn gồm transaction+C+M+L.

**Kernel được show trong cell:** `_prepare_amounts` ([source](../src/motif/modeling.py)), `family_feature_names` ([source](../src/motif/modeling.py)).

**Saved output:** 1 blocks; execution_count=24.

### Cell 25 — code-shared-training-prefix

**Mục đích:** Tách preprocessing fit khỏi9model fits, giảm repeated scans.

**Đọc code:** Chỉ train≤cutoff; fit q90/indexer; truth join; class weights; persist DISK_ONLY.

**Đọc output:** Validation/test tương lai không được dùng fit q90/category vocab hoặc class weights.

**Kernel được show trong cell:** `prepare_training_prefix` ([source](../src/motif/modeling.py)).

**Saved output:** 1 blocks; execution_count=25.

### Cell 26 — code-weighted-tree

**Mục đích:** Cho thấy assembler, classifier và exported pipeline thật.

**Đọc code:** Chọn subset theo family, fit cùng tree architecture trên encoded prefix, gắn indexer đã fit khi export.

**Đọc output:** Các đối chứng cùng preprocessing/budget giúp tránh so sánh lệch population hoặc model capacity.

**Kernel được show trong cell:** `fit_prepared_model` ([source](../src/motif/modeling.py)).

**Saved output:** 1 blocks; execution_count=26.

### Cell 27 — code-score-and-alert

**Mục đích:** Phân biệt risk score, alert và ground truth.

**Đọc code:** Transform bằng model đã fit; so score với threshold; labels chỉ join sau scoring.

**Đọc output:** risk_score không phải calibrated probability; isFraud là truth, alert là prediction.

**Kernel được show trong cell:** `score_transactions` ([source](../src/motif/modeling.py)), `frozen_prediction` ([source](../src/motif/modeling.py)).

**Saved output:** 1 blocks; execution_count=27.

### Cell 28 — code-exact-metrics

**Mục đích:** Hiển thị cách tính benchmark từ score histogram, gồm score ties.

**Đọc code:** TP/FP theo frozen threshold; cumulative grouped scores tạo precision/recall và exact AP.

**Đọc output:** Accuracy dễ bị majority class che lấp; đọc P/R/F1/AP, số alerts và prevalence thay vì chỉ accuracy.

**Kernel được show trong cell:** `metrics_at_threshold` ([source](../src/motif/modeling.py)), `precision_recall_curve` ([source](../src/motif/modeling.py)).

**Saved output:** 1 blocks; execution_count=28.

### Cell 29 — code-walk-forward

**Mục đích:** Thực thi vòng lặp train/validation và đóng băng lựa chọn trước test.

**Đọc code:** Prefix preprocess một lần,9trees; mọi thresholds trên validation; SHA ghi frozen rules.

**Đọc output:** Đọc worst/std cùng mean. Không đổi family/ngưỡng sau khi đã xem test, kể cả full fusion không tốt hơn baseline.

**Kernel được show trong cell:** `full_system_validation` ([source](../src/motif/pipeline.py)).

**Saved output:** 4 blocks; execution_count=29.

### Cell 30 — code-frozen-test

**Mục đích:** Xuất prediction và benchmark cuối; kiểm tra coverage/reload.

**Đọc code:** full_system_test dùng các training/scoring/alert kernels đã hiện phía trên; rule vẫn kiểm SHA trước từng family.

**Đọc output:** Đọc TP/FP/FN và alert rate trước khi kết luận. Selected_on_validation đánh dấu lựa chọn hợp lệ, không chọn theo bảng test.

**Saved output:** 5 blocks; execution_count=30.

### Cell 31 — code-benchmark-results

**Mục đích:** Đọc kết quả với graphs, ngân sách review và baseline cùng mẫu số.

**Đọc code:** Biểu đồ ablation/PR/confusion; exact Top-K và chênh lệch selected-baseline.

**Đọc output:** Giá trị âm vẫn giữ nguyên. Một model ít alerts hơn có thể tăng precision nhưng giảm recall.

**Saved output:** 6 blocks; execution_count=31.

### Cell 32 — code-temporal-reliability

**Mục đích:** Đo stability thực tế và phơi bày giới hạn của reliability claim.

**Đọc code:** Chia test theo time quantiles, giữ timestamp ties, cùng rule cho mọi period; không train lại.

**Đọc output:** Có thể xảy ra F1=0 ở một period hoặc feature importance=0. Phải giải thích bằng support và contribution, không ép kết quả khác0.

**Kernel được show trong cell:** `temporal_test_context` ([source](../src/motif/pipeline.py)).

**Saved output:** 10 blocks; execution_count=32.

### Cell 33 — code-case-evidence

**Mục đích:** Giải thích một cảnh báo và cả thất bại của detector bằng giao dịch thật.

**Đọc code:** TP/FP/FN lấy từ frozen predictions; evidence truy xuất event IDs thực.

**Đọc output:** Ground truth chỉ dùng audit sau prediction. Witness xác nhận cấu trúc/thời gian, chưa chứng minh cùng một khoản tiền hoặc nguyên nhân dự đoán.

**Saved output:** 9 blocks; execution_count=33.

### Cell 34 — code-independent-acceptance

**Mục đích:** Nghiệm thu artifact bằng phép kiểm tra độc lập rồi xuất runtime benchmark.

**Đọc code:** Recompute confusion/AP từ saved predictions; hash index/source/input; không chỉ tin training report.

**Đọc output:** PASS không có nghĩa đạt precision/recall ngoài thực tế. Các số CPU là đo theo phase, có bước I/O/serial.

**Saved output:** 3 blocks; execution_count=34.

### Cell 35 — code-close-session

**Mục đích:** Giải phóng kernel-owned Spark sau khi hoàn tất và lưu thông số tài nguyên.

**Đọc code:** Đóng session có kiểm soát; không chạy notebook thứ hai trước khi runner này kết thúc.

**Đọc output:** Đối chiếu peak commit/available RAM với guard budget; đây không phải kiểm định phần cứng hoặc nhiệt độ.

**Saved output:** 1 blocks; execution_count=35.

## paysim

[Notebook gốc](PaySIM_full_system.ipynb) · [Xem code và output offline](PaySIM_full_system.html)

### Cell 1 — code-environment

**Mục đích:** Xác nhận runtime Windows, dependency pins và bảo vệ bộ nhớ trước tính toán.

**Đọc code:** Khởi động qua session factory có guard; không tạo SparkSession bên ngoài guard.

**Đọc output:** Đọc master/task slots, heap và job cap thực tế. CPU available không đồng nghĩa mọi phase đều CPU-bound.

**Saved output:** 3 blocks; execution_count=1.

### Cell 2 — code-protocol

**Mục đích:** Khai báo trước các đối chứng, tuning budget và temporal protocol.

**Đọc code:** SYSTEM_FAMILY_GROUPS quyết định feature allowlist; mỗi family được train trên cùng prefix.

**Đọc output:** Không lấy metric tốt nhất trên test làm model được chọn; novelty control tách hiệu ứng tài khoản mới.

**Saved output:** 2 blocks; execution_count=2.

### Cell 3 — code-edge-contract

**Mục đích:** Giữ đúng contract giao dịch chung cho mọi nhánh.

**Đọc code:** Kiểm tra amount/time/labels/keys, cast có kiểm soát; hash content không chứa nhãn.

**Đọc output:** Sai dữ liệu thì dừng; không dùng việc cast thành null để che lỗi.

**Kernel được show trong cell:** `normalize_edges` ([source](../src/motif/features.py)).

**Saved output:** 1 blocks; execution_count=3.

### Cell 4 — code-full-index

**Mục đích:** Tạo và persist index một lần; hiển thị scope/counts và lịch train/validation/test thật.

**Đọc code:** Full input là canonical processed data; event_id và timestamp cutoffs được dùng chung.

**Đọc output:** Năm dòng là preview của full input. So sánh full count với unique IDs; timeline cho biết cutoff thực tế.

**Saved output:** 6 blocks; execution_count=4.

### Cell 5 — code-raw-reconciliation

**Mục đích:** Đối chiếu toàn bộ raw mapping với Parquet theo hai chiều, giữ duplicate multiplicity.

**Đọc code:** exceptAll hai chiều kiểm tra mapping; raw/source hashes giữ provenance.

**Đọc output:** Cả raw_minus_parquet và parquet_minus_raw phải bằng0. Số dòng bằng nhau riêng nó chưa chứng minh mapping đúng.

**Saved output:** 3 blocks; execution_count=5.

### Cell 6 — code-pagerank-update

**Mục đích:** Thể hiện phép truyền rank theo hướng giao dịch.

**Đọc code:** Rank nguồn nhân transition weight; tổng incoming và reset term tạo rank vòng mới.

**Đọc output:** Checkpoint/loop được import từ dataframe_pagerank; kernel hiển thị ở đây chạy trong từng iteration.

**Kernel được show trong cell:** `pagerank_update` ([source](../src/paysim/metrics.py)).

**Saved output:** 1 blocks; execution_count=6.

### Cell 7 — code-degree-metrics

**Mục đích:** Tính in/out/total degree từ full physical edges.

**Đọc code:** groupBy đếm multiplicity; left join và fillna giữ isolate.

**Đọc output:** Invariant tổng degree=2E sẽ được kiểm tra trong bước full analytics.

**Kernel được show trong cell:** `account_degree_metrics` ([source](../src/paysim/metrics.py)).

**Saved output:** 1 blocks; execution_count=7.

### Cell 8 — code-full-centrality

**Mục đích:** Chạy PR10/full Degree, export mọi account và biểu diễn phân bố/hubs.

**Đọc code:** Kernels trong hai cell trước được truyền vào backend; assertions kiểm tra mass và coverage.

**Đọc output:** Top10 chỉ là structural hubs từ full graph. Detector chưa được train ở bước này.

**Saved output:** 6 blocks; execution_count=8.

### Cell 9 — code-lpa-update

**Mục đích:** Giải thích cập nhật community labels thay vì chỉ gọi hàm LPA.

**Đọc code:** Join nhãn hàng xóm → cộng phiếu → min(-votes,label) → cập nhật đồng bộ.

**Đọc output:** Tie rule khác GraphX unspecified ties nên không ép partition hai backend giống nhau.

**Kernel được show trong cell:** `lpa_update` ([source](../src/paysim/community_detection.py)).

**Saved output:** 1 blocks; execution_count=9.

### Cell 10 — code-full-communities

**Mục đích:** Xuất mọi assignment, community summary và amount theo currency, rồi kiểm tra độc lập.

**Đọc code:** Full assignments và all-summary được đối chiếu SQL; plot/top10 chỉ là view.

**Đọc output:** positive_tx_count là posthoc label audit, không đi vào feature tạo cảnh báo. Internal/cross edges cần cộng về E.

**Saved output:** 5 blocks; execution_count=10.

### Cell 11 — code-cycle-query

**Mục đích:** Cho thấy query 3-cycle và điều kiện ba accounts khác nhau.

**Đọc code:** GraphFrame.find tìm vòng có hướng; chưa kết luận fraud từ topology.

**Đọc output:** Một vòng có thể được trả ở ba rotations; bước collapse xử lý duplicate rotations.

**Kernel được show trong cell:** `find_three_node_cycles` ([source](../src/motif/toy_cycle.py)).

**Saved output:** 1 blocks; execution_count=11.

### Cell 12 — code-relay-query

**Mục đích:** Trình bày query relay theo type/amount/time của PaySim.

**Đọc code:** Tách TRANSFER và CASH_OUT, distinct accounts và giới hạn gap.

**Đọc output:** Baseline query và strict-past detector có ranh giới khác nhau; same-hour matches phải báo mơ hồ.

**Kernel được show trong cell:** `find_relays` ([source](../src/paysim/motif_finding.py)).

**Saved output:** 1 blocks; execution_count=12.

### Cell 13 — code-motif-baseline

**Mục đích:** Chạy baseline full và so với baseline bàn giao, giữ kết quả bằng0 nếu dữ liệu cho như vậy.

**Đọc code:** Baseline chỉ mô tả các query của đề; không dùng nó làm label cho model.

**Đọc output:** Không có positive trong baseline không có nghĩa toàn dataset không fraud. Đọc causal coverage và benchmark tiếp theo.

**Saved output:** 3 blocks; execution_count=13.

### Cell 14 — code-rolling-history

**Mục đích:** Tính rolling counts bằng activation/expiry và cumulative sums.

**Đọc code:** Giữ timestamp ties; loại keys chỉ xuất hiện một timestamp vì strict-past count của chúng bằng0.

**Đọc output:** Đây là tối ưu phép tính tương đương, không phải cắt sample hoặc bỏ các transaction khỏi evaluation.

**Kernel được show trong cell:** `_sweep_counts` ([source](../src/motif/features.py)).

**Saved output:** 1 blocks; execution_count=14.

### Cell 15 — code-star-relay-history

**Mục đích:** Tính sender/receiver histories và fan/relay candidates theo cửa sổ24/168h.

**Đọc code:** Role events, currency keys và điều kiện type riêng PaySim; gọi expiry-prefix kernel phía trên.

**Đọc output:** Same-partner paths còn được trừ sau đó để A→B→A không bị gọi là relay ba accounts.

**Kernel được show trong cell:** `build_star_features` ([source](../src/motif/features.py)).

**Saved output:** 1 blocks; execution_count=15.

### Cell 16 — code-reciprocal-history

**Mục đích:** Phân biệt reciprocal hai accounts với relay ba accounts.

**Đọc code:** Canonical account pair, hai hướng và strict-past witness window.

**Đọc output:** Witness là event thật; role counts bằng0 có thể là kết quả đúng của cấu trúc dữ liệu.

**Kernel được show trong cell:** `build_reciprocal_features` ([source](../src/motif/features.py)).

**Saved output:** 1 blocks; execution_count=16.

### Cell 17 — code-cycle-topology

**Mục đích:** Tìm account cycle không dùng labels hoặc amounts.

**Đọc code:** Distinct topology trước GraphFrames matching tránh nhân mọi tổ hợp historical transactions.

**Đọc output:** Collapse topology không bỏ multiplicity khi temporal transactions được join lại.

**Kernel được show trong cell:** `find_topological_cycles` ([source](../src/ibm_aml/motif_finding.py)).

**Saved output:** 1 blocks; execution_count=17.

### Cell 18 — code-chronological-cycle

**Mục đích:** Tạo witness cycle hợp lệ tại thời điểm giao dịch đóng vòng.

**Đọc code:** Ba rotations, strict chronology, cùng currency và positive amounts; giữ event IDs thật.

**Đọc output:** Cycle có thật không tự chứng minh money laundering hoặc cùng một khoản tiền đi hết vòng.

**Kernel được show trong cell:** `build_temporal_cycle_features` ([source](../src/ibm_aml/motif_finding.py)).

**Saved output:** 1 blocks; execution_count=18.

### Cell 19 — code-disk-motif-checkpoint

**Mục đích:** Giữ lineage và dữ liệu trung gian trên đĩa dưới heap5GiB.

**Đọc code:** Ghi Parquet rồi đọc lại cắt lineage; tránh MemoryStore.putIteratorAsValues khi nhiều task cùng hoạt động.

**Đọc output:** Tăng CPU concurrency cần bỏ object cache lớn và giảm Parquet buffers; không tăng heap/job cap.

**Kernel được show trong cell:** `materialize_motif_stage` ([source](../src/motif/features.py)).

**Saved output:** 1 blocks; execution_count=19.

### Cell 20 — code-motif-feature-builder

**Mục đích:** Kết hợp star/reciprocal/cycle features và giữ một row cho mỗi transaction.

**Đọc code:** Trừ same-partner histories, giới hạn cycle gap theo dataset units; fill0 chỉ cho feature không có motif.

**Đọc output:** Các function trong notebook phía trên thực sự được gọi bởi builder, không phải code minh họa rời kết quả.

**Kernel được show trong cell:** `build_motif_features` ([source](../src/motif/features.py)).

**Saved output:** 1 blocks; execution_count=20.

### Cell 21 — code-motif-full-and-coverage

**Mục đích:** Chạy toàn bộ causal motifs và benchmark structural coverage đối với nhãn.

**Đọc code:** Label chỉ join sau construction để đo coverage/enrichment, không điều kiện hóa feature.

**Đọc output:** Coverage không phải precision/recall của model. Các motif overlap nên không cộng các hàng thành tổng.

**Saved output:** 6 blocks; execution_count=21.

### Cell 22 — code-historical-snapshot

**Mục đích:** Tính C/L trên prefix đúng thời điểm.

**Đọc code:** Lọc step≤cutoff, gọi PR/LPA và tính community size/cross fraction từ edges không có label.

**Đọc output:** Không dùng positive_tx_count của full community audit làm feature; chỉ dùng structural statistics.

**Kernel được show trong cell:** `historical_system_snapshot` ([source](../src/motif/pipeline.py)).

**Saved output:** 1 blocks; execution_count=22.

### Cell 23 — code-snapshot-join

**Mục đích:** Join src/dst snapshots mà không dùng numeric community IDs làm feature.

**Đọc code:** Kiểm tra strict timing, seen flags, same-community và fill defaults có kiểm soát.

**Đọc output:** Unknown history không bị gán là fraud; novelty control đo riêng ảnh hưởng này.

**Kernel được show trong cell:** `join_system_snapshot` ([source](../src/motif/pipeline.py)).

**Saved output:** 1 blocks; execution_count=23.

### Cell 24 — code-common-feature-table

**Mục đích:** Materialize một feature table đầy đủ, cùng event index cho9families.

**Đọc code:** Full rows/unique IDs và future-snapshot assertion; completed block checkpoints có hash để resume.

**Đọc output:** Feature bằng0 hoặc account unseen không phải predicted isFraud=0. Chưa có model prediction ở đây.

**Saved output:** 4 blocks; execution_count=24.

### Cell 25 — code-amount-normalization

**Mục đích:** Cho thấy chuẩn hóa theo training q90 và nhóm feature cụ thể của từng family.

**Đọc code:** log1p(amount/train_q90), unknown-group/FX flags và explicit group allowlist.

**Đọc output:** Không cộng nominal amounts khác currency. Full fusion luôn gồm transaction+C+M+L.

**Kernel được show trong cell:** `_prepare_amounts` ([source](../src/motif/modeling.py)), `family_feature_names` ([source](../src/motif/modeling.py)).

**Saved output:** 1 blocks; execution_count=25.

### Cell 26 — code-shared-training-prefix

**Mục đích:** Tách preprocessing fit khỏi9model fits, giảm repeated scans.

**Đọc code:** Chỉ train≤cutoff; fit q90/indexer; truth join; class weights; persist DISK_ONLY.

**Đọc output:** Validation/test tương lai không được dùng fit q90/category vocab hoặc class weights.

**Kernel được show trong cell:** `prepare_training_prefix` ([source](../src/motif/modeling.py)).

**Saved output:** 1 blocks; execution_count=26.

### Cell 27 — code-weighted-tree

**Mục đích:** Cho thấy assembler, classifier và exported pipeline thật.

**Đọc code:** Chọn subset theo family, fit cùng tree architecture trên encoded prefix, gắn indexer đã fit khi export.

**Đọc output:** Các đối chứng cùng preprocessing/budget giúp tránh so sánh lệch population hoặc model capacity.

**Kernel được show trong cell:** `fit_prepared_model` ([source](../src/motif/modeling.py)).

**Saved output:** 1 blocks; execution_count=27.

### Cell 28 — code-score-and-alert

**Mục đích:** Phân biệt risk score, alert và ground truth.

**Đọc code:** Transform bằng model đã fit; so score với threshold; labels chỉ join sau scoring.

**Đọc output:** risk_score không phải calibrated probability; isFraud là truth, alert là prediction.

**Kernel được show trong cell:** `score_transactions` ([source](../src/motif/modeling.py)), `frozen_prediction` ([source](../src/motif/modeling.py)).

**Saved output:** 1 blocks; execution_count=28.

### Cell 29 — code-exact-metrics

**Mục đích:** Hiển thị cách tính benchmark từ score histogram, gồm score ties.

**Đọc code:** TP/FP theo frozen threshold; cumulative grouped scores tạo precision/recall và exact AP.

**Đọc output:** Accuracy dễ bị majority class che lấp; đọc P/R/F1/AP, số alerts và prevalence thay vì chỉ accuracy.

**Kernel được show trong cell:** `metrics_at_threshold` ([source](../src/motif/modeling.py)), `precision_recall_curve` ([source](../src/motif/modeling.py)).

**Saved output:** 1 blocks; execution_count=29.

### Cell 30 — code-walk-forward

**Mục đích:** Thực thi vòng lặp train/validation và đóng băng lựa chọn trước test.

**Đọc code:** Prefix preprocess một lần,9trees; mọi thresholds trên validation; SHA ghi frozen rules.

**Đọc output:** Đọc worst/std cùng mean. Không đổi family/ngưỡng sau khi đã xem test, kể cả full fusion không tốt hơn baseline.

**Kernel được show trong cell:** `full_system_validation` ([source](../src/motif/pipeline.py)).

**Saved output:** 5 blocks; execution_count=30.

### Cell 31 — code-frozen-test

**Mục đích:** Xuất prediction và benchmark cuối; kiểm tra coverage/reload.

**Đọc code:** full_system_test dùng các training/scoring/alert kernels đã hiện phía trên; rule vẫn kiểm SHA trước từng family.

**Đọc output:** Đọc TP/FP/FN và alert rate trước khi kết luận. Selected_on_validation đánh dấu lựa chọn hợp lệ, không chọn theo bảng test.

**Saved output:** 5 blocks; execution_count=31.

### Cell 32 — code-benchmark-results

**Mục đích:** Đọc kết quả với graphs, ngân sách review và baseline cùng mẫu số.

**Đọc code:** Biểu đồ ablation/PR/confusion; exact Top-K và chênh lệch selected-baseline.

**Đọc output:** Giá trị âm vẫn giữ nguyên. Một model ít alerts hơn có thể tăng precision nhưng giảm recall.

**Saved output:** 6 blocks; execution_count=32.

### Cell 33 — code-temporal-reliability

**Mục đích:** Đo stability thực tế và phơi bày giới hạn của reliability claim.

**Đọc code:** Chia test theo time quantiles, giữ timestamp ties, cùng rule cho mọi period; không train lại.

**Đọc output:** Có thể xảy ra F1=0 ở một period hoặc feature importance=0. Phải giải thích bằng support và contribution, không ép kết quả khác0.

**Kernel được show trong cell:** `temporal_test_context` ([source](../src/motif/pipeline.py)).

**Saved output:** 10 blocks; execution_count=33.

### Cell 34 — code-case-evidence

**Mục đích:** Giải thích một cảnh báo và cả thất bại của detector bằng giao dịch thật.

**Đọc code:** TP/FP/FN lấy từ frozen predictions; evidence truy xuất event IDs thực.

**Đọc output:** Ground truth chỉ dùng audit sau prediction. Witness xác nhận cấu trúc/thời gian, chưa chứng minh cùng một khoản tiền hoặc nguyên nhân dự đoán.

**Saved output:** 8 blocks; execution_count=34.

### Cell 35 — code-independent-acceptance

**Mục đích:** Nghiệm thu artifact bằng phép kiểm tra độc lập rồi xuất runtime benchmark.

**Đọc code:** Recompute confusion/AP từ saved predictions; hash index/source/input; không chỉ tin training report.

**Đọc output:** PASS không có nghĩa đạt precision/recall ngoài thực tế. Các số CPU là đo theo phase, có bước I/O/serial.

**Saved output:** 3 blocks; execution_count=35.

### Cell 36 — code-close-session

**Mục đích:** Giải phóng kernel-owned Spark sau khi hoàn tất và lưu thông số tài nguyên.

**Đọc code:** Đóng session có kiểm soát; không chạy notebook thứ hai trước khi runner này kết thúc.

**Đọc output:** Đối chiếu peak commit/available RAM với guard budget; đây không phải kiểm định phần cứng hoặc nhiệt độ.

**Saved output:** 1 blocks; execution_count=36.

