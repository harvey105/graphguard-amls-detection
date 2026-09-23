# Đánh giá sơ bộ cấu trúc community của PaySim

## Kết luận

**Chưa có bằng chứng để nói PaySim có community structure rõ.** Dữ liệu có thể
cho LPA tạo ra label groups, nhưng topology đã đo giống graph giao dịch rất
sparse, nông và bất đối xứng hơn là các cụm dày có vòng lặp. Đây là đánh giá
feasibility tuần 1, không thay cho stability experiment của Task 4 tuần 2.

## Bằng chứng đã có từ Task 1

- 9.073.900 vertices và 6.362.620 transaction edges.
- Chỉ 1.769 vertices vừa xuất hiện ở vai trò sender vừa ở vai trò receiver,
  tương đương khoảng 0,0195% vertices.
- Max out-degree = 3, max in-degree = 113.
- Full PaySim không có 3-node directed cycle theo kiểm tra motif đã lưu.
- Dùng raw transaction edges làm tử số cho thấy mức cực sparse
  $6.362.620/(9.073.900\times9.073.899)\approx7,73\times10^{-8}$; đây là tỷ lệ
  transaction trên cặp có thể, không phải simple-graph density vì có parallel
  edges.

Các con số trên không chứng minh “không có community”, nhưng bác bỏ nhận định
rằng 1.769 bridge account tự động tạo “cụm kết nối chặt rất rõ”. Một bridge có
thể nối các star/relay nhỏ mà không tạo internal density cao.

## Rủi ro khi chạy LPA

- Các star quanh receiver có thể nhận cùng label dù không phải ring/cộng đồng
  AML theo nghĩa nghiệp vụ.
- Nhiều vertex degree thấp làm tie phổ biến và partition dễ không ổn định.
- Có thể thu được nhiều community rất nhỏ hoặc một nghiệm tầm thường lớn.
- Label không phải fraud prediction; phải profile `isFraud`, transaction type,
  amount và internal/external edge share.

## Tiêu chí quyết định ở Task 4

Chạy LPA 2–3 lần với cùng `maxIter=5`, rồi so phân hoạch sau khi bỏ phụ thuộc vào
label ID. Báo cáo size distribution, tỷ lệ singleton/small groups, largest-group
share, internal edge share và label stability. Chỉ khi các nhóm ổn định và có
internal connectivity cao hơn baseline mới được mô tả là community rõ.
