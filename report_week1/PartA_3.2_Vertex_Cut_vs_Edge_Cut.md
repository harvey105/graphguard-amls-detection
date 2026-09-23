# Mục 3.2 — Vertex Cut và Edge Cut

## 1. Bài toán phân hoạch graph

Với graph lớn, mục tiêu không chỉ là chia đều số cạnh hoặc số đỉnh. Một phân
hoạch tốt còn phải hạn chế dữ liệu phải truyền qua mạng ở mỗi vòng lặp của
PageRank, Pregel hay message aggregation.

### Edge cut

Edge cut gán mỗi vertex cho một partition và cắt các edge nối hai partition.
Vertex chỉ có một bản chính, nhưng mỗi edge bị cắt làm phát sinh giao tiếp giữa
hai máy khi thuật toán trao đổi trạng thái qua edge đó. Cách này hợp với graph
khá đều; trên graph lệch degree, một hub có thể khiến một partition quá tải và
tạo nhiều edge xuyên partition.

### Vertex cut

Vertex cut gán edge cho partition và cho phép một vertex xuất hiện dưới dạng
replica tại mọi partition chứa edge kề với nó. Một bản master giữ trạng thái
logic; các replica nhận/cộng gộp cập nhật qua routing table. Chi phí được chuyển
từ “số edge bị cắt” sang “số bản sao vertex phải đồng bộ”. Replication factor:

$$
RF = \frac{1}{|V|}\sum_{v\in V}|A(v)|,
$$

với $A(v)$ là tập partition chứa ít nhất một edge kề với $v$. $RF=1$ là không
nhân bản; $RF$ càng lớn thì chi phí đồng bộ vertex càng cao.

## 2. Vì sao GraphX dùng vertex cut

GraphX biểu diễn graph bằng `VertexRDD` và `EdgeRDD`, nhưng về logic phân hoạch
nó gán các edge vào máy và cho vertex trải trên nhiều máy. Routing table cho
biết thuộc tính vertex phải được gửi tới partition nào để dựng triplet hoặc
chạy `aggregateMessages`. Thiết kế này phù hợp với graph thực tế có degree lệch:
thay vì dồn toàn bộ adjacency list của hub vào một partition, các edge của hub
có thể được trải ra và chỉ trạng thái nhỏ của hub bị nhân bản.

Tên `EdgePartition2D` dễ gây hiểu nhầm: đây vẫn là một chiến lược trong kiến
trúc vertex-cut của GraphX. Nó ánh xạ ma trận kề lên lưới 2D và bảo đảm một
vertex không xuất hiện ở quá khoảng $2\sqrt{P}$ partition với $P$ partition.
`RandomVertexCut` và `CanonicalRandomVertexCut` là các lựa chọn khác. GraphX
không tự động hứa rằng một strategy cụ thể luôn tối ưu; graph mới tạo giữ phân
hoạch edge ban đầu cho tới khi gọi `Graph.partitionBy`.

## 3. Liên hệ PaySim

Các số đã được Task 1 ghi nhận:

- $|V|=9.073.900$, $|E|=6.362.620$;
- max in-degree = 113, max out-degree = 3;
- chỉ 1.769 account vừa gửi vừa nhận;
- graph rất sparse và degree bất đối xứng theo vai trò sender/receiver.

Phân phối này ủng hộ cách tiếp cận vertex cut: edge có thể cân bằng giữa các
partition, còn receiver degree cao chỉ cần replica thuộc tính. Tuy nhiên max
in-degree 113 chưa phải “super-hub”, và workflow hiện tại chạy `local[*]` trên
một máy nên không thể dùng thời gian local làm bằng chứng về network shuffle.
Vì vậy kết luận đúng là **vertex cut phù hợp với kiến trúc GraphX và dạng degree
skew của PaySim**, không phải “luôn tối ưu” hay “bắt buộc nhanh hơn edge cut”.
Muốn khẳng định hiệu năng cần benchmark cluster với cùng số partition và đo
replication factor, skew, shuffle read/write, thời gian từng superstep.

## 4. Bảng đối chiếu

| Tiêu chí | Edge cut | Vertex cut (GraphX) |
|---|---|---|
| Đơn vị gán vào partition | Vertex | Edge |
| Thứ bị cắt/nhân bản | Edge xuyên partition | Vertex có edge ở nhiều partition |
| Rủi ro với hub | Nhiều edge xuyên mạng, partition vertex dễ lệch | Hub bị replica nhưng edge dễ cân bằng |
| Trạng thái vertex | Một nơi | Master + replica/routing |
| Phù hợp nhất | Degree khá đều | Degree skew/power-law, graph-parallel message passing |

## 5. Nguồn

- [Apache Spark 3.5 GraphX Programming Guide — Optimized Representation](https://spark.apache.org/docs/3.5.6/graphx-programming-guide.html#optimized-representation)
- [Spark API — EdgePartition2D](https://spark.apache.org/docs/3.5.6/api/java/org/apache/spark/graphx/PartitionStrategy.EdgePartition2D$.html)
