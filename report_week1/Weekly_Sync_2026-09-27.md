# Biên bản kỹ thuật sync tuần 1 — 27/09/2026

> Đây là biên bản kỹ thuật được lập từ trạng thái repository. Không ghi tên
> người tham dự hoặc phê duyệt vì chưa có dữ liệu cuộc họp; nhóm cần xác nhận
> phần attendance khi sync thật.

## Deliverable đã chốt

- Task 1 PaySim, Spark session dùng chung, N4 toy motif, LPA research note và
  refactor `src/` đã tồn tại trước lượt hoàn thiện này; không làm lại.
- Mục 3.2 Vertex Cut vs Edge Cut: final + review.
- Mục 3.3 PageRank: review toán, sửa lỗi control character trong LaTeX.
- Mục 3.4 CC vs LPA: final + review; bỏ các overclaim của note nháp.
- PaySim community feasibility: kết luận chưa đủ bằng chứng về community rõ.
- IBM AML research/schema mapping và full ETL: code, manifest, log, Parquet
  round-trip (trạng thái số liệu lấy từ manifest sau run).

## Quyết định kỹ thuật

1. IBM account ID là `bank::account`; không dùng account string đơn lẻ.
2. IBM canonical `amount` dùng `Amount Received` và giữ paid-side fields để
   không quy đổi currency ngầm.
3. CC là reachability baseline; LPA là candidate community, không phải AML
   verdict.
4. Không tuyên bố vertex cut luôn nhanh hơn; cần benchmark cluster để kết luận
   hiệu năng.
5. Không dùng WSL run làm bằng chứng. PASS chỉ lấy từ Windows Python 3.12 +
   JDK 17.
6. Không triển khai các module Task 2–4 được xếp sang tuần 2.

## Rủi ro và handoff tuần 2

- LPA PaySim có nguy cơ nhóm star/degree-low thành community không ổn định; cần
  2–3 stability runs.
- GraphFrames iterative algorithms cần checkpoint và output phải `unpersist`.
- IBM amount có hai currency; mọi so sánh amount cross-currency cần FX policy
  rõ ràng.
- Raw CSV và full Parquet tiếp tục nằm ngoài Git vì size/license.
