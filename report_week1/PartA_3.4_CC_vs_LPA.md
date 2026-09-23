# Mục 3.4 — Connected Components và Label Propagation

## 1. Connected Components trả lời câu hỏi gì?

Trên transaction graph có hướng, GraphFrames `connectedComponents()` tìm weakly
connected components: bỏ hướng edge rồi gom mỗi tập vertex cực đại mà mọi cặp
đều có đường đi vô hướng. Đây là bài toán reachability chính xác. Quan hệ “có
đường đi vô hướng” là phản xạ, đối xứng và bắc cầu, nên các component tạo thành
một phân hoạch duy nhất của tập vertex.

Một edge cầu là đủ gộp hai vùng rất dày thành cùng component. Vì vậy CC cho biết
phạm vi kết nối và các đảo cô lập, nhưng không tự chứng minh một nhóm là
community gắn kết. Với câu hỏi chu trình có hướng phải dùng strongly connected
components (SCC), không được suy diễn từ weak CC.

## 2. LPA trả lời câu hỏi gì?

Label Propagation Algorithm (LPA) là community detection không giám sát trong
ngữ cảnh project. Khởi tạo mỗi vertex bằng một label riêng:

$$\ell_u^{(0)} = u.$$

Ở vòng $t+1$, vertex nhận label xuất hiện nhiều nhất trong các message từ hàng
xóm:

$$
\ell_u^{(t+1)} \in \operatorname*{arg\,max}_{c}
\sum_{v\in N(u)}\mathbf{1}[\ell_v^{(t)}=c].
$$

Hai vertex mang cùng label cuối cùng được xem là cùng community. Đây là đồng
thuận cục bộ, không phải reachability và không tối ưu trực tiếp modularity hay
một objective AML.

### Tie, hội tụ và non-determinism

Trong LPA cổ điển, tie giữa các label cực đại có thể được phá ngẫu nhiên. Khi
chạy phân tán, thứ tự message/partition và cách implementation xử lý tie cũng có
thể làm label ID hoặc cả phân hoạch đổi giữa các lần chạy. Do đó:

- không so stability bằng giá trị label thô; label chỉ là định danh;
- chuẩn hóa community theo tập thành viên hoặc dùng metric như ARI/NMI;
- chạy lặp lại nhiều lần trước khi diễn giải một community là ổn định.

LPA không có bảo đảm hội tụ hữu hạn cho mọi graph; vertex biên có thể dao động,
và cũng có thể xảy ra nghiệm tầm thường khi gần như mọi vertex nhận cùng label.
GraphFrames API nhận `maxIter`; với kế hoạch project, `maxIter=5` nghĩa là chặn
chi phí ở năm superstep, không phải tuyên bố đã đạt fixed point. Độ phức tạp
mỗi vòng gần $O(|V|+|E|)$, tổng gần $O(k(|V|+|E|))$ cho $k$ vòng.

## 3. Vì sao đề bài cần cả hai?

| Câu hỏi | Connected Components | LPA |
|---|---|---|
| Hai account có thuộc cùng vùng liên thông? | Có, chính xác | Không phải mục tiêu |
| Một bridge có gộp hai nhóm? | Có | Có thể có hoặc không; không có bảo đảm |
| Tìm nhóm đồng thuận cục bộ | Không | Có |
| Kết quả duy nhất theo graph | Phân hoạch component là duy nhất | Có thể không ổn định |
| Điều kiện chạy project | Checkpoint cho GraphFrames CC mặc định | `maxIter=5`; checkpoint định kỳ/runtime |
| Diễn giải AML | Baseline topology | Candidate communities, không phải bằng chứng laundering |

CC là baseline cấu trúc: nó giúp phát hiện liệu LPA chỉ đang chia nhỏ một giant
component hay đang phản ánh các vùng tách biệt vốn đã có. LPA bổ sung khái niệm
đồng thuận/mật độ cục bộ. Hai kết quả cần profile bằng size, internal edge share,
amount, transaction type và fraud label; không dùng một ngưỡng 80–90% không có
calibration để tự động kết luận “red flag”.

## 4. Lưu ý GraphFrames

GraphFrames cho biết LPA có thể dao động hoặc sụp về một community duy nhất và
khuyến nghị thử `maxIter` hợp lý. Kết quả trả về được persist nên phải `unpersist`
sau khi dùng. Với implementation DataFrame, checkpoint định kỳ ngăn logical plan
tăng quá sâu; persistent checkpoint cần `SparkContext.setCheckpointDir(...)`.
Repo đã tập trung cấu hình này trong `src/common/spark_session.py`.

## 5. Nguồn

- [GraphFrames — Community Detection / LPA](https://graphframes.io/04-user-guide/06-graph-clustering.html)
- [GraphFrames — Connected Components](https://graphframes.io/04-user-guide/05-traversals.html#connected-components)
- [Raghavan, Albert & Kumara (2007), DOI 10.1103/PhysRevE.76.036106](https://link.aps.org/doi/10.1103/PhysRevE.76.036106)
