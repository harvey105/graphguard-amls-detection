# Pipeline, phương pháp và tham số thực chạy

## Mạch xử lý

Raw riêng dataset → ETL full vertices/edges → integrity + raw reconciliation + một transaction index → full descriptive Degree/PageRank, LPA, motif baseline. Song song, lịch sử giao dịch → snapshots C/L + strict-past M → một common feature row/transaction → 3-fold walk-forward/9 families → freeze family/ngưỡng → refit prefix≤80% → test sau cutoff → PR/AP, review budgets, evidence, reliability và kiểm tra độc lập.

Full descriptive analytics để mô tả graph. Predictive C/L lấy snapshot trước giao dịch, M chỉ lấy quá khứ; không đưa full-future graph vào features của test.

## Các nhóm feature và 9 cấu hình

T: type/currency index, amount chuẩn hóa theo currency/type, unseen_amount_group, FX flag. C: degree/PageRank và cờ endpoint đã có trong prefix. M: history 24h/168h, fan-in/fan-out, relay, reciprocal, chronological 3-cycle và thông tin cycle. L: community size/cross fraction/outgoing transactions, same-community và endpoints-seen. Không đưa label, account ID hay community numeric ID làm feature.

| family | T | C | M | L | novelty_only | meaning |
| --- | --- | --- | --- | --- | --- | --- |
| transaction_only | 1 | 0 | 0 | 0 | 0 | Baseline thuộc tính giao dịch |
| transaction_novelty | 1 | 0 | 0 | 0 | 1 | T + cờ tài khoản đã thấy; đối chứng cold start |
| transaction_centrality | 1 | 1 | 0 | 0 | 0 | T + Degree/PageRank |
| motif_assisted | 1 | 0 | 1 | 0 | 0 | T + motif/history |
| transaction_community | 1 | 0 | 0 | 1 | 0 | T + community context |
| full_fusion | 1 | 1 | 1 | 1 | 0 | Đủ ba nhóm đồ thị |
| without_centrality | 1 | 0 | 1 | 1 | 0 | T + motif + communities |
| without_motifs | 1 | 1 | 0 | 1 | 0 | T + centrality + communities |
| without_community | 1 | 1 | 1 | 0 | 0 | T + centrality + motif |

Tên feature chính xác theo dataset/family/index nằm ở [exact_feature_allowlists.csv](tables/exact_feature_allowlists.csv). Các family chia sẻ cùng preprocessing prefix để so sánh có kiểm soát.

## Graph analytics

- Total degree = inDegree + outDegree, tính theo physical transactions, giữ giao dịch trùng thật; self-loop đóng góp hai vào total degree. Tổng degree = 2E.
- PageRank: 10 vòng, reset probability 0.15; triển khai fixed-iteration theo GraphX, sau cùng normalize tổng rank bằng V. Không chèn dangling redistribution giữa các vòng. Đây không phải score fraud trực tiếp.
- LPA: 5 vòng đồng bộ, messages hai chiều có trọng số theo số physical edges; tie bằng min signed xxhash64 seed label, có kiểm tra collision. Label là partition ID, không phải nhãn gian lận. Không diễn giải internal-edge=0 là mọi giao dịch đều fraud.
- Motif history: windows 24 và 168 giờ; chỉ prior event s<t và không quá H. Các giao dịch cùng timestamp không được coi là history của nhau. Cycle cần ba tài khoản phân biệt, thứ tự thời gian hợp lệ; baseline label-audit không được đưa vào inference.

## Chia thời gian và chống leakage

Snapshot ở quantiles gần 20/40/50/65/80%; giữ nguyên ties timestamp nên số rows không nhất thiết đúng tỷ lệ tròn. Cutoff thực trong portable_summary.json và [full_time_blocks.csv](tables/full_time_blocks.csv).

1. Train ≤40%, validate (40%,50%].
2. Train ≤50%, validate (50%,65%].
3. Train ≤65%, validate (65%,80%].
4. Freeze family + threshold dựa validation; refit train ≤80%, test >80% cutoff.

C/L của warm-up trước snapshot đầu không có history và dùng giá trị 0 + cờ unseen; motif vẫn dùng quá khứ hợp lệ. Mỗi giao dịch chỉ có một feature row/event_id, không deduplicate physical raw transactions. [evaluation_splits.csv](tables/evaluation_splits.csv) ghi counts và timestamp thật cho từng fold.

## Fitted classifier và optimizer

Weighted DecisionTreeClassifier: maxDepth=5, minInstancesPerNode=50, maxBins=64, seed=2026. Positive weight = sqrt((Ntrain−Ptrain)/Ptrain), chỉ tính trên training prefix. StringIndexer alphabetAsc, handleInvalid=keep. Chuẩn hóa amount dùng q90 của positive amount trong mỗi currency/type trên training prefix; công thức chính xác xem [_prepare_amounts](src/motif/modeling.py). Không dùng threshold tiền USD chung cho mọi currency.

Ngưỡng candidate: 0.001, 0.005, 0.01, 0.02, 0.05, 0.1, 0.2, 0.3, 0.5, 0.7, 0.9, 0.99. Chọn theo mean validation F1; tie: worst-fold F1, ít FP, family đơn giản hơn, threshold cao hơn. Mỗi family có threshold riêng được freeze. Final winner không chọn lại bằng test. Mỗi dataset: 4 lần fit preprocessing prefix, 27 cây validation + 9 cây refit = 36 cây.

Thông số từng trained tree và q90 nằm trong datasets/<dataset>/model_details/<family>/, bao gồm toàn bộ nodes, leaf rules, categorical vocabulary, exact feature order, positive weight và training support. Đây là đọc model đã lưu, không fit lại.

## Chỉ số

Precision=TP/(TP+FP); Recall=TP/(TP+FN); F1=2TP/(2TP+FP+FN). AP tính exact theo các mức score rời rạc, giữ score ties; không dùng ROC-AUC hoặc accuracy để thay kết luận về dữ liệu cực lệch nhãn. PR CSV chứa cumulative precision/recall, transactions và positives theo mỗi score bin.

Review budget f∈{0.001,0.005,0.01}: K=ceil(f×Ntest), order risk DESC,event_key ASC,event_id ASC. Không gọi AP là accuracy; score weighted leaf không phải xác suất đã calibrate. Wilson 95% cho precision/recall; test chia 5 khoảng thời gian để quan sát biến thiên.

## Nguồn thực thi

Hai run dùng Windows Python 3.12.10, Spark 3.5.1, JDK 17.0.20.1, local[20], heap5GiB/job8GiB; seed và các config gốc lưu nguyên bản trong provenance. Source snapshot trong bundle khớp SHA-256 thực chạy. Revision thực thi lưu trong original run.json; revision đóng gói riêng trong manifest, không gắn lịch sử chạy vào revision mới.
