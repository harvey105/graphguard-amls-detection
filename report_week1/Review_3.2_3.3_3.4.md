# Biên bản review lý thuyết tuần 1

## Mục 3.2 — reviewer N1

Kết quả: **ACCEPT sau chỉnh sửa trong bản final**.

- Đã phân biệt đúng edge cut (gán vertex) và vertex cut (gán edge, replica
  vertex).
- Đã thêm replication factor và routing-table cost.
- Đã chặn overclaim “vertex cut bắt buộc tối ưu”: dữ liệu PaySim có skew nhưng
  max in-degree chỉ 113, còn runtime local không đo được network shuffle.
- Đã làm rõ `EdgePartition2D` vẫn thuộc kiến trúc vertex-cut của GraphX và
  default graph construction không tự chọn một strategy tối ưu cho workload.

## Mục 3.3 — reviewer N4

Kết quả: **ACCEPT với một minor fix đã áp dụng**.

Checklist toán:

- Chuỗi sáu bước random walk → Markov transition → stationary distribution →
  sửa dangling column → damping/teleportation → component formula là nhất quán.
- Dạng đầy đủ giữ dangling-mass redistribution; dạng ngắn chỉ là trường hợp
  riêng. Phần này cần thiết vì PaySim có nhiều out-degree-zero vertex.
- Đã tách đúng leakage ở dangling node khỏi trapping ở closed class/spider trap.
- Đã tách ba mệnh đề tồn tại, duy nhất và hội tụ; không dùng “reducible” như điều
  kiện đủ cho nghiệm không duy nhất.
- Đã giữ caveat `PageRank cao ≠ fraud`.

Minor fix: công thức tại §3.3.3 chứa ký tự form-feed/tab do `\frac` và `\text`
bị escape sai. Đã thay bằng LaTeX hợp lệ và quét lại file để chắc chắn không
còn control character.

## Mục 3.4 — reviewer N6

Kết quả: **REWORK bản note nháp, ACCEPT bản final trong `report_week1`**.

Các điểm đã sửa so với `docs/CC_vs_LPA_Note.md`:

- LPA trong project là unsupervised, không gọi chung là “bán giám sát”.
- $O(|V|+|E|)$ là gần đúng cho một vòng; tổng $k$ vòng là
  $O(k(|V|+|E|))$.
- Không hứa LPA luôn tách hoàn hảo hai cụm chỉ vì có một bridge.
- Tách tie-breaking cổ điển khỏi tính không ổn định của implementation phân
  tán; không khẳng định GraphFrames chọn uniform-random nếu chưa chứng minh từ
  đúng version source.
- Phân biệt điều kiện fixed-point lý thuyết với hành vi API chặn bằng `maxIter`.
- Bỏ ngưỡng “internal share 80–90% = red flag” vì chưa có calibration/source.
- Bổ sung nguy cơ trivial one-community solution, stability runs, checkpoint và
  `unpersist`.
