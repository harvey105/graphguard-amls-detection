# GRIMOIRE — GraphGuard: Distributed Graph Analytics with GraphX & GraphFrames

> **Mục đích:** Đọc từ đầu dù chưa biết graph, Spark hay thuật toán. Sau mỗi phần, bạn phải trả lời được: *nó là gì, objective của nó là gì, công thức hoạt động ra sao, và nó được dùng ở bước nào của project*. Tên thuật ngữ tiếng Anh được giữ nguyên; phần tiếng Việt giải thích nghĩa và cách dùng. Công thức mô tả mô hình toán học; kết quả cụ thể của thư viện có thể phụ thuộc phiên bản và cách triển khai.
>
**Thứ tự ưu tiên:** [Đề gốc](graphX_subject.md) quy định nội dung phải nộp → [bản kiến trúc nhóm](BIG_Data_Group6.md) là đề xuất thực hiện → [bảng phân công](BDA%20-%20PCCV%20-%20Trang%20t%C3%ADnh1.csv) là lịch và trách nhiệm → code hiện có là trạng thái triển khai. Không lấy một câu trong proposal làm yêu cầu của thầy nếu đề gốc không nói vậy.

## Mục lục / đường học

1. [Đọc hiểu đề trong 5 phút](#1-đọc-hiểu-đề-trong-5-phút)
2. [Từ giao dịch thành graph](#2-từ-giao-dịch-thành-graph)
3. [Spark, GraphX, GraphFrames và phân tán](#3-spark-graphx-graphframes-và-phân-tán)
4. [Graph partitioning: Edge Cut và Vertex Cut](#4-graph-partitioning-edge-cut-và-vertex-cut)
5. [PaySim và ETL: xây graph đúng nghĩa](#5-paysim-và-etl-xây-graph-đúng-nghĩa)
6. [Degree và degree distribution](#6-degree-và-degree-distribution)
7. [PageRank: từ random walk đến công thức đầy đủ](#7-pagerank-từ-random-walk-đến-công-thức-đầy-đủ)
8. [Motif Finding: tìm chu trình giao dịch](#8-motif-finding-tìm-chu-trình-giao-dịch)
9. [Connected Components, SCC và LPA](#9-connected-components-scc-và-lpa)
10. [Diễn giải, kiểm chứng và đánh giá](#10-diễn-giải-kiểm-chứng-và-đánh-giá)
11. [Bản đồ công việc, sản phẩm nộp và câu hỏi phản biện](#11-bản-đồ-công-việc-sản-phẩm-nộp-và-câu-hỏi-phản-biện)
12. [Glossary và nguồn học](#12-glossary-và-nguồn-học)

---

## 1. Đọc hiểu đề trong 5 phút

### 1.1 Bài toán thực sự là gì?

Một hàng trong bảng giao dịch nói *ai chuyển tiền cho ai, bao nhiêu, lúc nào*. Muốn nhìn **cấu trúc của nhiều giao dịch liên quan**, ta nối các hàng thành một graph. Một account là **vertex**; một transaction là **directed edge**. Ví dụ:

```text
Account A --$12,000--> Account B --$11,800--> Account C
    ^                                          |
    +-----------------$11,500------------------+
```

Từng hàng riêng lẻ không cho thấy vòng `A → B → C → A`; graph cho phép hỏi trực tiếp liệu mẫu đó có tồn tại. Mục tiêu kỹ thuật của bài là **xây và phân tích graph phân tán**, sau đó giải thích các cấu trúc có thể đáng điều tra trong bối cảnh tài chính. Đây **không phải** yêu cầu huấn luyện một classifier hoặc chứng minh một account rửa tiền. Tên project có chữ AML, nhưng dataset PaySim gắn nhãn **fraud** của kịch bản mobile money; fraud label không tự động là nhãn **money laundering**. [Nguồn PaySim](https://www.kaggle.com/datasets/ealaxi/paysim1/data).

### 1.2 Hệ thống tạo ra những gì?

```text
Raw transactions (PaySim CSV)
    ↓ ETL: kiểm tra schema, chuẩn hóa, tạo account duy nhất
vertices(id, account_type, balance) + edges(src, dst, amount, step, type, isFraud)
    ↓ GraphFrame(vertices, edges)
    ├─ Degree → account gửi/nhận nhiều giao dịch
    ├─ PageRank → account nhận "tầm ảnh hưởng" từ mạng
    ├─ Motif Finding → mẫu A→B→C→A và các mẫu khác
    └─ LPA / Connected Components → cộng đồng / thành phần liên thông
    ↓ Kiểm tra chứng cứ, giải thích nghiệp vụ, giới hạn kết luận
```

### 1.3 Từng yêu cầu bắt buộc nằm ở đâu?

| Trong đề gốc | Objective | Sản phẩm cần thấy |
|---|---|---|
| **Part A**, 35 điểm: GraphX vs GraphFrames, partitioning, PageRank, CC vs LPA | Chứng minh hiểu cơ chế | Báo cáo có định nghĩa, công thức, ví dụ, trade-off |
| **Task 1** | Tạo graph từ giao dịch | `graph_analysis.py`, Vertices/Edges DataFrame, `GraphFrame`, kiểm tra schema và số lượng |
| **Task 2** | Tính topology và xếp hạng account | In-Degree, Out-Degree, degree distribution; PageRank `resetProbability=0.15`, `maxIter=10`, top 10 |
| **Task 3** | Tìm mẫu giao dịch vòng | `graph.find` cho `A→B→C→A`, filter cả ba `amount > 10000`, kết quả và diễn giải |
| **Task 4** | Phân cộng đồng | Chạy LPA, tìm và giải thích cộng đồng đáng chú ý; đối chiếu Connected Components ở Part A |

Rubric Part B: Graph Construction & Metrics 15 điểm; PageRank & Motif Search 25 điểm; Community Detection & Insights 25 điểm. **Degree nằm trong Task 2 nhưng rubric không nói chính xác thuộc bucket 15 hay 25 điểm.** Làm đầy đủ dù cách chấm chưa rõ. Task 4 ghi “Community Detection & Connected Components”, còn phần pipeline nhấn mạnh chạy LPA; vì vậy đưa CC vào đối chiếu thực nghiệm nếu đủ điều kiện để giảm rủi ro bỏ sót rubric. [Xem đề gốc](graphX_subject.md).

### 1.4 Ba câu phân biệt để không lạc đề

| Câu hỏi | Công cụ | Ý nghĩa kết quả |
|---|---|---|
| “Account nào có nhiều giao dịch?” | Degree | Số cạnh sát account đó |
| “Account nào được những account quan trọng chuyển tới?” | PageRank | Điểm ảnh hưởng cấu trúc theo hướng cạnh |
| “Có đúng cấu trúc A→B→C→A?” | Motif Finding | Những bộ account/transaction khớp mẫu |
| “Account nào cùng vùng liên thông?” | Connected Components | Có một đường đi **nếu bỏ hướng** giữa chúng |
| “Graph có thể tách thành những community nào?” | LPA | Nhãn community do đồng thuận lân cận sau số vòng lặp hữu hạn |

---

## 2. Từ giao dịch thành graph

### 2.1 Khái niệm cơ bản

Một graph có hướng là $G=(V,E)$: $V$ là tập **vertices** (đỉnh), $E$ là tập **directed edges** (cạnh có hướng). Ở project, $u\in V$ là một account; $e=(u,v,\text{amount},\text{step},\ldots)\in E$ là một giao dịch từ account $u$ sang $v$. **Objective:** biến dữ liệu hàng thành quan hệ có thể truy vấn theo đường đi và cấu trúc. Hướng `src → dst` nghĩa là **người gửi → người nhận**; đảo hướng sẽ đổi toàn bộ ý nghĩa của In-Degree và PageRank.

`GraphFrames` dùng **property graph**: vertex và edge có thêm thuộc tính. `account_type`, `balance` là vertex attributes; `amount`, `step`, `type`, `isFraud` là edge attributes. Có thể tồn tại nhiều giao dịch giữa cùng cặp account: đó là **multigraph / parallel edges**. Không được `.distinct()` các cạnh theo `(src,dst)` nếu muốn giữ số giao dịch và giá trị từng lần. Self-loop là cạnh $u\to u$; một self-loop góp 1 In-Degree và 1 Out-Degree. [GraphX property graph](https://spark.apache.org/docs/3.5.7/graphx-programming-guide.html#the-property-graph), [GraphFrames tạo graph](https://graphframes.io/04-user-guide/01-creating-graphframes.html).

**Mini example:** giao dịch `A→B`, `B→C`, `C→A`, `D→B`. Khi đó $|V|=4$, $|E|=4$; `B` có In-Degree 2, `A` Out-Degree 1; `A,B,C` tạo một directed 3-cycle. `D` nối với cả ba khi bỏ hướng, dù `D` không thuộc cycle.

### 2.2 “Connected” có hai nghĩa quan trọng

- **Path có hướng** $u\leadsto v$: đi từ $u$ đến $v$ theo chiều mũi tên. Trong `A→B→C`, A đến C được; C đến A thì không.
- **Weakly connected**: bỏ hướng cạnh rồi hỏi có đường đi không. `A→B→C` đều cùng weak component.
- **Strongly connected**: mọi cặp trong nhóm đều đi tới nhau theo chiều cạnh. `A→B→C→A` tạo strongly connected component; thêm `D→B` thì D chỉ weakly connected với nhóm.

**Objective trong project:** CC giúp thấy nhóm account có liên hệ giao dịch dù một account chỉ gửi hoặc chỉ nhận; SCC hoặc cycle mới trực tiếp nói về khả năng tiền đi vòng theo chiều giao dịch. GraphFrames có API riêng cho CC và SCC. [GraphFrames connectivity](https://graphframes.io/04-user-guide/05-traversals.html).

### 2.3 Graph là phép nhìn, không là chứng cứ phạm tội

Một cycle có thể là giao dịch hợp pháp giữa nhiều account; một hub có thể là merchant hoặc đại lý thanh toán; một community có thể chỉ là khách hàng chung. Một kết quả topology là **candidate for investigation**. Muốn kết luận mạnh hơn cần thêm thời gian, số tiền, loại giao dịch, nhãn hoặc chứng cứ nghiệp vụ. Điểm này phải xuất hiện trong phần Insights.

---

## 3. Spark, GraphX, GraphFrames và phân tán

### 3.1 Vì sao Spark?

**Apache Spark** chia dữ liệu và công việc thành các **partitions** rồi chạy trên các **executors**; **driver** dựng kế hoạch và nhận kết quả nhỏ. Có thể dùng Spark trên một máy `local[*]` để phát triển, nhưng điều đó **không chứng minh benchmark trên cluster nhiều máy**. Một file 6,36 triệu giao dịch là quy mô lớn cho máy cá nhân và hữu ích để thực hành distributed APIs; câu “billions of edges” trong đề là bối cảnh chung, không phải kích thước PaySim. [Spark overview](https://spark.apache.org/docs/3.5.1/cluster-overview.html).

| Từ | Nghĩa đơn giản | Liên hệ project |
|---|---|---|
| `SparkSession` | Điểm vào PySpark | Tạo trong `src/graph_analysis.py` trước khi đọc Parquet |
| `DataFrame` | Bảng phân tán có tên và kiểu cột | `vertices_df`, `edges_df` |
| `RDD` | Tập bản ghi phân tán ở mức thấp | Cấu trúc gốc của GraphX |
| `partition` | Một mảnh dữ liệu được xử lý song song | Cạnh và vertex phân phối qua workers |
| `transformation` | Mô tả phép biến đổi, thường lazy | `select`, `filter`, `join`, `groupBy` |
| `action` | Kích hoạt thực thi | `count`, `show`, `collect` |
| `shuffle` | Trao đổi dữ liệu giữa partitions | `groupBy`, join theo khóa không cùng partition |
| `cache/persist` | Giữ kết quả để tái sử dụng | Hữu ích khi nhiều thuật toán đọc cùng graph, cần đủ RAM/disk |
| `checkpoint` | Cắt chuỗi phụ thuộc tính toán | Thuật toán lặp/CC; không đồng nghĩa `cache` |
| `Parquet` | Định dạng cột có schema, nén | Input đã ETL cho Task 2–4 |

Spark đánh giá lazy: viết `df.filter(...)` chỉ tạo **logical plan**; `df.count()` mới khởi chạy job. `df.explain()` cho thấy plan để chẩn đoán join/shuffle. `collect()` kéo toàn bộ dữ liệu về driver và có thể hết bộ nhớ; dùng `show`, `limit`, `write` trên graph lớn. [Spark SQL/DataFrames](https://spark.apache.org/docs/3.5.1/sql-programming-guide.html), [Spark performance tuning](https://spark.apache.org/docs/3.5.1/sql-performance-tuning.html).

### 3.2 GraphX vs GraphFrames — trả lời Part A

| Tiêu chí | GraphX | GraphFrames |
|---|---|---|
| Biểu diễn | `Graph[VD, ED]` trên `VertexRDD` và `EdgeRDD` | `GraphFrame(vertices, edges)` trên hai `DataFrame` |
| ID/thuộc tính | `VertexId` kiểu `Long`, thuộc tính kiểu `VD/ED` | Cột `id`, `src`, `dst`; thuộc tính là các cột DataFrame |
| Ngôn ngữ dùng trực tiếp | Chủ yếu Scala/Java GraphX API | Scala, Java, Python API |
| Biểu đạt query | Graph operators, message passing | DataFrame `select/filter/join/groupBy`, Motif DSL, graph algorithms |
| Tối ưu hóa | Cấu trúc và partition routing riêng của GraphX | Phép toán **DataFrame-native** hưởng Catalyst, AQE, định dạng Tungsten; thuật toán bọc GraphX vẫn có backend GraphX |
| Project | Giải thích kiến trúc và Vertex Cut | Dùng để code tất cả Task 1–4 |

**Catalyst** là optimizer của Spark SQL: phân tích schema và biến đổi query plan để chọn cách chạy. **Tungsten** là các kỹ thuật biểu diễn dữ liệu và thực thi hiệu quả của Spark SQL. **AQE** là Adaptive Query Execution: điều chỉnh một số quyết định khi runtime thấy kích thước dữ liệu thực. Chúng giúp phép join/aggregate trên DataFrame, nhưng không có bảo đảm rằng GraphFrames luôn nhanh hơn GraphX trong mọi workload. GraphFrames có cả thuật toán DataFrame-native và wrapper qua GraphX; cụ thể tài liệu GraphFrames nêu **PageRank `maxIter` dùng GraphX aggregateMessages**. Bản proposal viết “GraphFrames không có Pregel API” là sai đối với tài liệu hiện hành: GraphFrames có Pregel API. Bản proposal cũng khẳng định “GraphFrames dùng Vertex Cut mặc định” quá rộng: các phép DataFrame-native phụ thuộc Spark SQL partition/shuffle; GraphX dùng Vertex Cut khi biểu diễn graph, nhưng GraphX giữ phân vùng edge đầu vào lúc khởi tạo nếu chưa gọi `partitionBy`. [GraphFrames architecture](https://graphframes.io/01-about/02-architecture.html), [GraphFrames Pregel](https://graphframes.io/04-user-guide/10-pregel.html), [GraphX optimized representation](https://spark.apache.org/docs/3.5.7/graphx-programming-guide.html#optimized-representation).

**Cách trả lời ngắn khi thầy hỏi:** “GraphFrames là API property graph trên hai DataFrame. Motif và nhiều thao tác biểu diễn thành relational joins nên Spark SQL tối ưu được. Một số thuật toán, ví dụ PageRank hiện tại, vẫn dùng GraphX ở backend; vì thế kiến trúc thực tế là hybrid.”

### 3.3 Tại sao dùng `GraphFrame(vertices, edges)` thay vì một bảng?

Một bảng giao dịch đủ để đọc từng hàng, nhưng truy vấn nhiều bước cần self-join lặp lại. GraphFrames cung cấp **ngôn ngữ graph** cho query và algorithm có sẵn. Ví dụ tìm `A→B→C→A` tương đương ba bản sao bảng edge join theo `e1.dst=e2.src`, `e2.dst=e3.src`, `e3.dst=e1.src`; GraphFrames diễn đạt bằng một motif string. **Objective:** viết logic rõ và tận dụng engine phân tán, nhưng chi phí join vẫn tồn tại. [Motif finding](https://graphframes.io/04-user-guide/04-motif-finding.html).

---

## 4. Graph partitioning: Edge Cut và Vertex Cut

### 4.1 Bài toán phân vùng

Nếu graph không vừa một worker, phải chia nó thành $P$ partitions. Mục tiêu là giảm **communication cost** và **memory/storage cost**, đồng thời cân bằng tải. Trong thuật toán lặp, thông tin phải đi giữa các đỉnh kề nhau; nếu chúng ở các máy khác nhau, phải truyền qua mạng. **Network shuffle** là việc dữ liệu trao đổi/được phân phối lại; chi phí của nó thường đáng kể. [GraphX guide](https://spark.apache.org/docs/3.5.7/graphx-programming-guide.html#optimized-representation).

### 4.2 Edge Cut: chia vertices

Chọn ánh xạ $p_V:V\to\{1,\ldots,P\}$, mỗi vertex có một partition chủ. Cạnh $(u,v)$ là **cut edge** nếu $p_V(u)\ne p_V(v)$. Một chỉ số đơn giản:

$$C_{\text{edge-cut}}=\sum_{(u,v)\in E}\mathbf{1}[p_V(u)\ne p_V(v)].$$

**Objective:** ít cut edges thì ít giao tiếp qua ranh giới partitions cho các tác vụ truyền thông tin theo cạnh. Ví dụ một hub $H$ nối với 1.000 account rải đều trên bốn máy: nếu H chỉ ở một máy, nhiều cạnh đi qua ranh giới; máy chứa H cũng dễ quá tải.

### 4.3 Vertex Cut: chia edges

Chọn ánh xạ $p_E:E\to\{1,\ldots,P\}$; mỗi edge ở một partition. Vertex $v$ có thể có bản sao ở các partition chứa edge kề nó. Gọi $R(v)$ là tập partitions có bản sao của $v$; **replication factor** trung bình:

$$RF=\frac{1}{|V|}\sum_{v\in V}|R(v)|;\qquad RF\ge 1\text{ đối với vertex có edge.}$$

**Objective:** phân bổ nhiều cạnh của hub sang nhiều worker để chia tải; phải đồng bộ vertex state giữa các bản sao. Với 1.000 cạnh của H trên bốn partitions, H có thể xuất hiện bốn lần thay vì giữ mọi cạnh ở một nơi. GraphX có các `PartitionStrategy` như `RandomVertexCut`, `EdgePartition1D`, `EdgePartition2D`; chiến lược nào tốt hơn tùy graph và workload. [GraphX guide](https://spark.apache.org/docs/3.5.7/graphx-programming-guide.html#optimized-representation), [PartitionStrategy API](https://spark.apache.org/docs/3.5.7/api/java/org/apache/spark/graphx/PartitionStrategy.html).

### 4.4 Kết nối với project và giới hạn suy luận

PaySim handoff báo Max In-Degree 113, Max Out-Degree 3 trên bản đầy đủ. Đây là **kết quả nhóm báo cáo** trong [handoff](person2_handoff.md), chưa được kiểm chứng lại ở workspace hiện tại do thiếu raw/full graph. Nó gợi ý tải không đều ở account nhận nhiều tiền; *chưa đủ* để khẳng định phân phối degree tuân power law hoặc Vertex Cut chắc chắn tối ưu. Muốn phát biểu thực nghiệm, đo histogram/quantiles degree, partition sizes, runtime/shuffle và memory trên cùng workload. `spark.sql.shuffle.partitions=8` trong code là số partitions cho một số shuffle DataFrame, **không** có nghĩa ta đã cấu hình `GraphX.partitionBy(RandomVertexCut)`.

**Câu trả lời Part A:** Edge Cut gán vertices cho partitions và cắt các cạnh liên máy; Vertex Cut gán edges cho partitions và nhân bản vertices. Chúng đánh đổi communication, replication và cân bằng tải. GraphX chủ đích dùng biểu diễn Vertex Cut; GraphFrames ở tầng DataFrame có kế hoạch thực thi Spark SQL, còn backend GraphX có cơ chế riêng.

---

## 5. PaySim và ETL: xây graph đúng nghĩa

### 5.1 Dataset và ý nghĩa nghiệp vụ

**PaySim** là dữ liệu tổng hợp từ bộ mô phỏng mobile money. `step` từ 1 đến 744, mỗi step là **một giờ mô phỏng**, không phải ngày giờ lịch thực. `isFraud=1` đánh dấu hành vi fraud được cấy trong mô phỏng, chủ yếu chiếm đoạt account, `TRANSFER` rồi `CASH_OUT`. `isFlaggedFraud` là nhãn cờ theo rule riêng; không được xem là nhãn ground truth tương đương `isFraud`. `amount` là đơn vị tiền tệ của bộ dữ liệu; đề dùng threshold `10000`, **không có bằng chứng đó là 10.000 USD**. Tên cột `nameOrig`/`nameDest` là ID account. Merchant bắt đầu bằng `M`, Customer thường bắt đầu bằng `C`; thông tin balance của Merchant ở phía nhận không đầy đủ theo data card. [PaySim data card](https://www.kaggle.com/datasets/ealaxi/paysim1/data).

| Cột raw | Nghĩa | Dùng ở project |
|---|---|---|
| `step` | giờ mô phỏng | Thứ tự thời gian trong edge; không gán datetime giả |
| `type` | `TRANSFER`, `CASH_OUT`, `PAYMENT`, `CASH_IN`, `DEBIT` | Phân biệt mẫu giao dịch |
| `amount` | số tiền | Filter motif, thống kê tổng tiền |
| `nameOrig`, `nameDest` | account gửi, nhận | `src`, `dst` và tập vertex |
| `oldbalanceOrg`, `newbalanceOrig` | số dư bên gửi trước/sau | Cân nhắc tạo vertex snapshot; dễ bị leakage |
| `oldbalanceDest`, `newbalanceDest` | số dư bên nhận trước/sau | Tương tự; Merchant có thể thiếu thông tin thực |
| `isFraud` | nhãn fraud của transaction | Đối chiếu kết quả, không dùng làm điều kiện tìm mẫu nếu muốn đánh giá độc lập |
| `isFlaggedFraud` | cờ rule của simulator | Có thể phân tích thêm, không phải nhãn fraud chuẩn |

**Cảnh báo leakage:** data card PaySim nói các balance columns không nên dùng để làm fraud detection vì giao dịch fraud có thể bị hủy, tạo dấu vết sau sự kiện. Đề yêu cầu cột vertex `balance`, nên vẫn có thể tạo để đáp ứng schema, nhưng **không đưa nó vào scoring/đánh giá fraud như feature hợp lệ mà không kiểm tra leakage và semantics**. Một “balance của account” cũng thay đổi theo thời gian; gom một account nhiều sự kiện thành một số duy nhất là **snapshot/summary**, không phải số dư bất biến. [PaySim data card](https://www.kaggle.com/datasets/ealaxi/paysim1/data).

### 5.2 ETL = Extract, Transform, Load

**Extract:** đọc CSV với schema kiểm soát kiểu, kiểm tra row count và null. **Transform:** tạo `vertices` bằng hợp nhất `nameOrig` và `nameDest`, gán loại account, chọn chính sách balance; tạo `edges` bằng đổi tên cột và giữ một hàng cho mỗi transaction. **Load:** lưu Parquet, đọc lại và tạo GraphFrame. Objective của ETL là mọi thuật toán nhận cùng một graph đáng tin cậy.

Định nghĩa toán học:

$$V=\operatorname{distinct}\big(\{\text{nameOrig}_i\}_i\cup\{\text{nameDest}_i\}_i\big),\quad
E=\{(\text{nameOrig}_i,\text{nameDest}_i,\text{amount}_i,\text{step}_i,\ldots)\}_{i=1}^{m}.$$

Nếu không lọc raw và giữ mọi giao dịch, $|E|=m$. `src` và `dst` phải nằm trong `V`; `id` không null và không trùng. Cùng cặp `(src,dst)` có thể xuất hiện nhiều lần, vì đó là nhiều transaction.

| Yêu cầu đề | Proposal ban đầu | Code hiện có | Cách diễn giải đúng |
|---|---|---|---|
| Vertex `id` | Gộp sender/receiver | `groupBy("id")` trên union hai vai | Đúng mục tiêu account duy nhất |
| `account_type` | Tiền tố C/M | `Customer` / `Merchant` / `Unknown` | Phân loại theo quy ước PaySim, kiểm tra giá trị lạ |
| Vertex `balance` | Gợi ý `oldbalance*` gần nhất | `F.max_by(newbalance*, step)` | Đây là **số dư sau sự kiện ở step lớn nhất** theo policy nhóm; khác proposal, phải viết rõ |
| Edge thời gian | `timestamp` | `step` nguyên int | Dùng `step` là proxy giờ mô phỏng, giải thích trong báo cáo |
| Edge bổ sung | Không yêu cầu `type`, `isFraud` | Có cả hai | Hữu ích cho diễn giải và đối chiếu nhãn |

Xem triển khai: [ETL mapping](src/utils/etl_mapping.py), [graph construction](src/graph_analysis.py), [handoff](person2_handoff.md).

**Chỗ cần xem kỹ:** `F.max_by(balance, step)` không giải quyết trường hợp account có **nhiều sự kiện trong cùng một `step`** theo thứ tự xác định; PaySim chỉ có độ phân giải giờ. Nếu hai dòng cùng step có balance khác nhau, kết quả tie có thể không ổn định. `max_by` cũng có thể chọn giá trị balance không đại diện cho Merchant. Nêu chính sách tie rõ, kiểm tra số account bị tie, và nếu cần thêm event order đáng tin cậy từ nguồn; không tự bịa thứ tự khi raw không có. Đừng gọi balance này là “số dư cuối cùng chắc chắn đúng” nếu chưa xác thực.

### 5.3 Tình trạng dữ liệu trong workspace này

Tại lúc viết Grimoire, repo có `data/processed/sample/{vertices,edges}.parquet`; không có `data/raw/` hay full `data/processed/{vertices,edges}.parquet` trong workspace. [Handoff](person2_handoff.md) báo **full:** 9.073.900 vertices, 6.362.620 edges, 8.213 fraud edges; **sample:** 193.143 vertices, 100.111 edges, 153 fraud edges. Các số full là **số nhóm ghi lại**, không phải kết quả tôi vừa chạy lại từ raw. Sample là graph được lấy mẫu theo edges rồi giữ các vertices liên quan; nó có thể mất cycle, đường đi và community. Không dùng “không tìm thấy trên sample” để kết luận “không có trên full”.

### 5.4 Kiểm tra chất lượng dữ liệu trước mọi thuật toán

| Check | Công thức/điều kiện | Vì sao |
|---|---|---|
| Unique vertex ID | $\operatorname{count}(V)=\operatorname{countDistinct}(id)$ | GraphFrame cần mỗi account một vertex |
| Không null key | `id`, `src`, `dst` đều khác null | Null làm hỏng join |
| Referential integrity | $\{src\}\cup\{dst\}\subseteq\{id\}$ | Không có dangling edges |
| Edge count | $|E|=\text{raw rows}$ nếu không lọc | Không mất transaction |
| Kiểu cột | `amount` numeric, `step` integer | Filter/sắp xếp đúng nghĩa |
| Time range | `step` trong miền dữ liệu | Tránh timestamp hiểu sai |
| Balance policy | Một bản ghi/ID, tie được ghi nhận | Snapshot tái lập được |

Nếu `left_anti` join từ edges sang vertices cho `src`/`dst` trả 0 hàng, referential integrity đạt. Việc `edge_count == raw_count` **chưa chứng minh mapping đúng**, vì đổi nhầm `src`/`dst` vẫn giữ nguyên số hàng. Cần đối chiếu vài transaction thật theo cả `nameOrig`, `nameDest`, `amount`, `step`.

### 5.5 Tạo graph với project này

```python
from graphframes import GraphFrame
from src.graph_analysis import create_graph_spark_session

# Tạo SparkSession với Maven coordinate tương thích trong code project.
spark = create_graph_spark_session()
v = spark.read.parquet("data/processed/sample/vertices.parquet")
e = spark.read.parquet("data/processed/sample/edges.parquet")
g = GraphFrame(v, e)
print(g.vertices.count(), g.edges.count())
```

`graphframes-py` là Python package; GraphFrames còn cần JVM jar tương ứng Spark/Scala. Xem [GraphFrames installation](https://graphframes.io/02-quick-start/01-installation.html) và hàm cấu hình đang dùng ở [graph_analysis.py](src/graph_analysis.py). Đừng đoán phiên bản từ trí nhớ. `requirements.txt` hiện ghi cả `graphframes==0.6` và `graphframes-py==0.12.2`; cần kiểm tra/xử lý xung đột package trước khi chạy môi trường mới, nhưng Grimoire này không tự sửa dependency của nhóm.

---

## 6. Degree và degree distribution

### 6.1 Định nghĩa và công thức

Với account $u$:

$$d_{\text{in}}(u)=|\{(v,u)\in E\}|,\qquad d_{\text{out}}(u)=|\{(u,v)\in E\}|,\qquad d(u)=d_{\text{in}}(u)+d_{\text{out}}(u).$$

Trong **multigraph**, mỗi transaction góp một lần; hai transaction cùng sender/receiver tăng count lên 2. **Degree distribution** là phân bố bậc trên toàn graph. Chẳng hạn $n_k=|\{u:d(u)=k\}|$ và $P(k)=n_k/|V|$. Có thể tính riêng $P_{in}(k)$ và $P_{out}(k)$. Đồ thị histogram là số account theo bậc; thêm quantiles $p50,p90,p99$ và max để nhìn độ lệch. **Objective:** xác định hubs và mô tả topology trước khi chạy thuật toán tốn kém. [GraphFrames centrality metrics](https://graphframes.io/04-user-guide/03-centralities.html).

```python
from pyspark.sql import functions as F

in_df = g.inDegrees
out_df = g.outDegrees
degree_df = g.degrees
distribution = degree_df.groupBy("degree").agg(F.count("*").alias("accounts"))
distribution.orderBy("degree").show()
```

**Lưu ý API:** Python API reference hiện khai báo `inDegrees`, `outDegrees`, `degrees` là **properties** (dùng không có `()`). Trang User Guide lại minh họa với `()`; nếu thấy khác biệt, ưu tiên kiểm tra `type(g.inDegrees)` và API của đúng package đã cài. [Python API reference](https://graphframes.io/api/python/graphframes.html).

Các bảng degree thường **không chứa vertex bậc bằng 0** ở loại bậc tương ứng. Nếu muốn mọi account, bắt đầu từ `g.vertices.select("id")`, left join In/Out-Degree rồi `fillna(0)`. Trong graph dựng chỉ từ endpoint giao dịch, mọi vertex có ít nhất một cạnh tổng thể, nhưng vẫn có thể In-Degree hoặc Out-Degree bằng 0.

**Ví dụ:** `A→X`, `B→X`, `C→X`: X có In-Degree 3, Out-Degree 0. X là điểm tập trung tiền theo chiều gửi→nhận; chưa có bằng chứng fraud. “Degree distribution theo power law” cần ước lượng/kiểm định phù hợp; chỉ nhìn max lớn hơn median không đủ để khẳng định.

---

## 7. PageRank: từ random walk đến công thức đầy đủ

### 7.1 Objective và trực giác

**PageRank** chấm một vertex cao nếu nó được nhiều vertex khác trỏ tới, đặc biệt nếu các vertex gửi tới đó cũng quan trọng. Với hướng `src=sender → dst=receiver`, điểm cao thường gắn với account **nhận** từ nguồn có điểm cao. Nó không đo trực tiếp số tiền, tốc độ giao dịch hay fraud. Trong Task 2, yêu cầu là `resetProbability=0.15`, `maxIter=10`, lấy top 10 account. [GraphFrames PageRank API](https://graphframes.io/04-user-guide/03-centralities.html#pagerank), [bài gốc Brin & Page](https://research.google/pubs/the-anatomy-of-a-large-scale-hypertextual-web-search-engine/).

### 7.2 Bước 1: random walk trên directed graph

Giả sử có $N=|V|$ accounts và người đi ngẫu nhiên đang ở $v$. Nếu $v$ có $d_{out}(v)>0$, chọn đều một outgoing edge để sang account nhận. Đây là **Markov chain**: xác suất bước tiếp theo chỉ phụ thuộc vị trí hiện tại, không cần nhớ toàn bộ đường đã đi. Đặt $A_{vu}$ bằng **số cạnh** từ $v$ đến $u$. Khi có parallel edges, xác suất chuyển từ $v$ sang $u$ là:

$$P_{uv}=\frac{A_{vu}}{d_{out}(v)},\qquad d_{out}(v)=\sum_x A_{vx}.$$

Ở đây $P$ là ma trận *cột*: cột $v$ là phân bố nơi đi tiếp từ $v$. Nếu $r^{(t)}_v$ là xác suất ở $v$ sau $t$ bước, thì $r^{(t+1)}=Pr^{(t)}$ khi không có sink. **Objective của random walk:** chuyển cấu trúc cạnh thành một thước đo xác suất về khả năng ghé thăm account.

### 7.3 Bước 2: sink/dangling node và teleportation

**Sink / dangling node** là vertex có Out-Degree 0. Nếu để cột $P_{\cdot v}$ toàn 0, tổng xác suất bị mất; thêm mỗi bước một hằng số $(1-d)/N$ mà **không** xử lý mass này thì công thức không còn là phân bố xác suất chuẩn hóa. Cách chuẩn trong mô hình random surfer: tại sink, chọn một vertex bất kỳ theo phân bố $q$; trong bài này $q_u=1/N$. Đặt

$$S_{uv}=\begin{cases}A_{vu}/d_{out}(v),&d_{out}(v)>0,\\1/N,&d_{out}(v)=0.\end{cases}$$

Mọi cột của $S$ cộng lại bằng 1. Gọi $d=0.85$ là **damping factor**: với xác suất $d$ đi theo cạnh hoặc rời sink theo $S$; với xác suất $1-d=0.15$ **teleport** ngẫu nhiên đều. Ma trận cuối:

$$T=dS+(1-d)q\mathbf{1}^{\mathsf T},\qquad q=(1/N,\ldots,1/N)^{\mathsf T}.$$

$T_{uv}>0$ với mọi $u,v$ vì $1-d>0$: random walk có thể đến mọi account và không mắc vào vòng kín hoặc sink vĩnh viễn. Theo tính chất của ma trận stochastic dương, tồn tại **stationary distribution** duy nhất $\pi$ và power iteration hội tụ tới nó. Stationary distribution nghĩa là $T\pi=\pi$, $\sum_u\pi_u=1$, $\pi_u\ge0$; nó là eigenvector của $T$ với eigenvalue 1.

### 7.4 Bước 3: công thức scalar dùng trong báo cáo

Gọi $M(u)$ là **multiset các incoming edges** tới $u$ và $D=\{v:d_{out}(v)=0\}$. Khi teleport đều:

$$\boxed{\displaystyle
PR^{(t+1)}(u)=\frac{1-d}{N}
+d\left[\sum_{v:d_{out}(v)>0}\frac{A_{vu}\,PR^{(t)}(v)}{d_{out}(v)}
+\frac{1}{N}\sum_{v\in D}PR^{(t)}(v)\right]}
$$

Khởi tạo thường $PR^{(0)}(u)=1/N$. Nếu **không có sink** và không có parallel edges, công thức rút gọn thành biểu thức trong đề:

$$PR(u)=\frac{1-d}{N}+d\sum_{v\in M(u)}\frac{PR(v)}{L(v)},\qquad L(v)=d_{out}(v).$$

Đề gốc định dạng công thức bị mất dấu ngoặc/phân số; đây là bản viết rõ. Dạng rút gọn **không đầy đủ khi có sink**, trong khi PaySim có thể có rất nhiều receiver không gửi tiếp. Vì vậy khi giảng cơ chế chống sink, phải nêu **phân phối lại dangling mass**, không chỉ nói teleport một cách mơ hồ. `d=0.85` tương ứng `resetProbability=0.15`. $PR^{(10)}$ là kết quả sau mười vòng lặp; không mặc định bằng nghiệm hội tụ $\pi$.

### 7.5 Ví dụ tính tay để nhớ

Graph ba account: `A→B`, `B→C`, `C` là sink. $N=3$, $d=0.85$, $PR^{(0)}=(1/3,1/3,1/3)$. Sink mass $=PR^{(0)}(C)=1/3$. Teleport base mỗi account $0.15/3=0.05$; dangling share mỗi account $0.85(1/3)/3\approx0.09444$. Do đó:

$$PR^{(1)}(A)=0.05+0.09444\approx0.14444,$$
$$PR^{(1)}(B)=0.05+0.85(1/3)+0.09444\approx0.42778,$$
$$PR^{(1)}(C)=0.05+0.85(1/3)+0.09444\approx0.42778.$$

Tổng $=1$. Nếu quên dangling share, tổng chỉ còn $0.71667$; đó là dấu hiệu công thức xác suất sai. Ý nghĩa: C có điểm cao vì B gửi đến C; không có outgoing edge không làm điểm bị kẹt vĩnh viễn vì sink mass quay lại toàn graph.

### 7.6 Dùng PageRank trong project

```python
from pyspark.sql import functions as F

ranked_graph = g.pageRank(resetProbability=0.15, maxIter=10)
top10 = ranked_graph.vertices.select("id", "pagerank").orderBy(F.desc("pagerank")).limit(10)
top10.show(truncate=False)
```

GraphFrames `pageRank` trả về **GraphFrame**, điểm trong `ranked_graph.vertices.pagerank`; API hiện tại có backend GraphX cho nhánh `maxIter`. Công thức ở trên là **mô hình xác suất chuẩn hóa để hiểu PageRank**; implementation có thể dùng scale/quy ước xử lý sink riêng. Vì vậy so sánh **thứ hạng** trong cùng run và kiểm tra tài liệu/giá trị đầu ra, đừng mặc định tổng cột `pagerank` bằng 1. Để so sánh score giữa các graph/sample, phải chuẩn hóa và xác minh cùng implementation. [GraphFrames PageRank](https://graphframes.io/04-user-guide/03-centralities.html#pagerank), [GraphFrames internals](https://graphframes.io/01-about/02-architecture.html).

**Diễn giải top 10:** join với account_type, In/Out-Degree, tổng incoming amount, transaction types và fraud edges liên quan. “Điểm cao” là tín hiệu ưu tiên xem xét, **không** là phát hiện rửa tiền. Tài khoản Merchant nhận nhiều PAYMENT có thể hợp pháp. PageRank mặc định xem mọi edge như một link, không tự dùng `amount` làm weight; nếu muốn amount weighted PageRank, đó là mở rộng khác, phải định nghĩa công thức và cách chạy riêng.

---

## 8. Motif Finding: tìm chu trình giao dịch

### 8.1 Định nghĩa, objective và phép join

**Motif** là một mẫu cấu trúc nhỏ. **Motif Finding** trả về các bộ vertex/edge khớp mẫu. Task 3 bắt buộc tìm **directed 3-cycle**: $a\to b$, $b\to c$, $c\to a$. Toán học, tập kết quả là:

$$\mathcal{C}_3=\{(a,b,c,e_1,e_2,e_3):e_1=(a,b),e_2=(b,c),e_3=(c,a),\ a,b,c\text{ phân biệt},\ \operatorname{amount}(e_i)>10000\ \forall i\}.$$

**Objective:** phát hiện giao dịch khép kín có thể liên quan layering hoặc quay vòng tiền để điều tra. Bản thân cycle không chứng minh dòng tiền thực sự đi theo chuỗi thời gian: phải kiểm tra $step(e_1)<step(e_2)<step(e_3)$ nếu muốn nói giao dịch diễn ra liên tiếp. Nếu nhiều transaction trong cùng giờ, PaySim không cho thứ tự phút/giây. Có thể thêm điều kiện số tiền tương đối gần nhau, ví dụ $|amount(e_1)-amount(e_2)|/amount(e_1)<\epsilon$, nhưng phải nói rõ đây là heuristic bổ sung và giải thích epsilon.

Phép tìm tương đương ba edge self-joins, nên fan-out cao có thể tạo rất nhiều candidates trước khi lọc. Đẩy filter `amount > 10000` lên edges trước khi tạo GraphFrame cho truy vấn thử có thể giảm input, nhưng giữ một bản graph gốc để báo cáo đúng số edge tổng thể. [GraphFrames Motif guide](https://graphframes.io/04-user-guide/04-motif-finding.html).

### 8.2 Query đúng đề và hậu xử lý đúng nghĩa

```python
from pyspark.sql import functions as F

cycles = (
    g.find("(a)-[e1]->(b); (b)-[e2]->(c); (c)-[e3]->(a)")
     .filter("e1.amount > 10000 AND e2.amount > 10000 AND e3.amount > 10000")
     .filter("a.id <> b.id AND b.id <> c.id AND c.id <> a.id")
)

# Nếu phân tích tuần tự thực sự, thêm: .filter("e1.step < e2.step AND e2.step < e3.step")
cycles.select("a.id", "b.id", "c.id", "e1.amount", "e2.amount", "e3.amount").show(10, False)
```

`a`, `b`, `c` là **struct vertex**, `e1`… là **struct edge**, nên `e1.amount`, `a.id` truy cập thuộc tính bên trong. Một cycle `A→B→C→A` có thể xuất hiện ba lần do **rotation** `(A,B,C)`, `(B,C,A)`, `(C,A,B)`; với parallel edges còn có nhiều bộ giao dịch khác nhau trên cùng ba account. Nếu báo cáo “số chu trình duy nhất”, phải định nghĩa đơn vị đếm: **bộ transaction** hay **bộ ba account**. Với account triplet, tạo khóa canonical rotation (ví dụ ID nhỏ nhất làm điểm bắt đầu) rồi distinct; đừng đếm raw motif rows như số fraud rings. [Motif guide](https://graphframes.io/04-user-guide/04-motif-finding.html).

### 8.3 Điểm nghẽn dataset: 0 cycle trong PaySim theo handoff

[Handoff hiện tại](person2_handoff.md) khẳng định đã kiểm tra full 6.362.620 giao dịch và tìm thấy **0 directed 3-cycles**. Workspace này không chứa raw/full graph để tôi tái lập kết quả. Vì vậy đưa vào báo cáo theo đúng dạng: “Theo kết quả kiểm tra full dataset của nhóm, query directed 3-cycle cho 0 kết quả; cần đính kèm code/log tái lập.” Nếu full graph thực sự có **0 cycle trước khi lọc amount**, hạ threshold từ `10000` không thể sinh cycle: filter chỉ loại bớt, không tạo đường mới. Đây là lỗi logic trong gợi ý “tinh chỉnh threshold để có cycle”.

**Cách hoàn thành Task 3 mà vẫn đúng đề:**

1. Chạy và lưu chính xác query 3-cycle của đề trên **full graph**; ghi `count=0` nếu đúng. Xác minh cả structural cycle không lọc amount và cycle đã lọc.
2. Chạy query trên graph đồ chơi `A→B→C→A` để chứng minh code/motif syntax đúng; không trộn kết quả toy với PaySim.
3. Giải thích PaySim mô phỏng fraud kiểu `TRANSFER → CASH_OUT`, vì thế motif vòng không phản ánh kịch bản chính trong data card.
4. Báo cáo **phân tích bổ sung** trên PaySim bằng 2-hop relay; nếu muốn minh họa cycle thật trên dataset khác, dùng AMLSim và ghi rõ tên dataset, mapping, phạm vi và nguồn.

Đề yêu cầu cyclic transaction detection; **2-hop relay không thay thế vòng 3-node**. Nếu giảng viên yêu cầu bắt buộc *có* cycle từ dữ liệu thật, nhóm cần chọn dataset có cycle và vẫn chạy query gốc. Dữ liệu AMLSim khác schema và nhãn, cần ETL/kiểm chứng lại. [Đề gốc](graphX_subject.md), [PaySim data card](https://www.kaggle.com/datasets/ealaxi/paysim1/data), [bài về AMLSim](https://arxiv.org/abs/2306.16424).

### 8.4 Mẫu thay thế bổ sung: 2-hop relay

```python
relays = (
    g.find("(a)-[e1]->(b); (b)-[e2]->(c)")
     .filter("e1.type = 'TRANSFER' AND e2.type = 'CASH_OUT'")
     .filter("e1.amount > 10000 AND e2.amount > 10000")
     .filter("a.id <> b.id AND b.id <> c.id AND a.id <> c.id")
     .filter("e1.step <= e2.step")  # <= vì cùng giờ không có thứ tự nhỏ hơn
)
```

Một 2-hop relay chỉ nói *cùng account B nhận TRANSFER rồi thực hiện CASH_OUT*. Nếu nhiều giao dịch cùng giờ, thứ tự chính xác chưa biết; nếu không kiểm tra amount gần nhau và thời gian ngắn, khó nói chính những đồng tiền ấy được rút. `type` trên edge hiện có là điều kiện cần cho query này. **Objective:** chọn motif phù hợp hơn với cơ chế fraud PaySim nhưng giữ minh bạch rằng đây là phân tích bổ sung.

---

## 9. Connected Components, SCC và LPA

### 9.1 Connected Components (CC): reachability chính xác

**Connected Components** chia graph thành các nhóm tối đại sao cho, khi **bỏ hướng cạnh**, mọi cặp vertex trong một nhóm có đường đi. Viết quan hệ $u\sim v$ nếu có undirected path $u=v_0,\dots,v_k=v$. Quan hệ này có tính phản xạ, đối xứng, bắc cầu; mỗi lớp tương đương là một component. Kết quả API là `id, component`. **Objective trong project:** biết những account nào thuộc cùng vùng giao dịch, phát hiện component cô lập hoặc component khổng lồ cần phân tích tiếp. [GraphFrames CC](https://graphframes.io/04-user-guide/05-traversals.html#connected-components).

```python
spark.sparkContext.setCheckpointDir("checkpoints")
cc = g.connectedComponents()
cc.groupBy("component").count().orderBy(F.desc("count")).show()
```

GraphFrames CC DataFrame-native thường cần checkpoint directory để cắt lineage. Output là DataFrame đã persist trong một số API; unpersist khi xong để tránh giữ tài nguyên. `component` chỉ là ID của nhóm, **không phải risk score**. Nếu một bridge account nối hai nhóm bằng chỉ một transaction, CC có thể gộp chúng thành một component lớn. CC không đo “tight knit”; hai account ở cùng CC có thể cách nhau nhiều hops. Tài liệu hiện tại có `two_phase` mặc định cho CC và có lựa chọn khác; API và chi tiết backend có thể đổi theo phiên bản. [GraphFrames CC guide](https://graphframes.io/04-user-guide/05-traversals.html#connected-components).

### 9.2 SCC: khi hướng giao dịch quan trọng

**Strongly Connected Component** là tập tối đại mà mọi $u,v$ đều có $u\leadsto v$ và $v\leadsto u$ theo hướng cạnh. Dùng SCC để phân biệt một vùng có khả năng quay vòng tiền theo directed paths với một vùng chỉ nối một chiều. Nhưng SCC lớn không bảo đảm có **3-cycle**, và 3-cycle là một mẫu riêng. GraphFrames có `stronglyConnectedComponents(maxIter=...)`. Đây là kiến thức bổ trợ cho việc giải thích cycle, không thay thế LPA trong Task 4. [GraphFrames SCC](https://graphframes.io/04-user-guide/05-traversals.html#strongly-connected-components).

### 9.3 Label Propagation Algorithm (LPA): community heuristic

LPA khởi tạo cho mỗi vertex một label riêng: $\ell_u^{(0)}=u$. Mỗi vòng, vertex nhận labels từ neighbors rồi nhận label xuất hiện nhiều nhất:

$$\ell_u^{(t+1)}\in\operatorname*{arg\,max}_{c}\sum_{v\in N(u)}\mathbf{1}[\ell_v^{(t)}=c].$$

$N(u)$ là tập/multiset neighbors theo định nghĩa truyền thông điệp của implementation; trong graph giao dịch có hướng, cần đọc API để hiểu nó xử lý chiều cạnh nào, thay vì tự suy rằng `LPA` tìm luồng tiền theo hướng. Khi hòa phiếu, tie-breaking và lịch cập nhật ảnh hưởng kết quả. Một community là tập vertices có cùng label ở cuối số vòng lặp, **không bảo đảm** đó là clique, vùng dày đặc, độc lập hay fraud ring. GraphFrames mô tả LPA là rẻ tính toán nhưng **không bảo đảm hội tụ** và có thể đưa toàn graph vào một label. [GraphFrames LPA](https://graphframes.io/04-user-guide/06-graph-clustering.html#label-propagation-lpa), [bài báo LPA gốc](https://link.aps.org/doi/10.1103/PhysRevE.76.036106).

**So sánh bằng ví dụ:** hai tam giác nhiều cạnh nối nhau bằng một bridge. CC cho **một** component vì bridge tạo đường đi. LPA có thể cho **hai** labels nếu đồng thuận nội bộ thắng liên kết cầu; cũng có thể gộp chúng tùy graph và số vòng lặp. Một đường thẳng dài cũng có thể thành một CC lớn nhưng không “tightly knit”.

```python
communities = g.labelPropagation(maxIter=5)
sizes = communities.groupBy("label").count().orderBy(F.desc("count"))
sizes.show()
```

`maxIter=5` là số vòng lặp giới hạn, **không phải lời hứa thuật toán đã hội tụ**. Python API GraphFrames hiện ghi `labelPropagation(..., algorithm="graphx")` là mặc định; có thể chọn `algorithm="graphframes"` cho backend DataFrame. Vì thế cảnh báo trong handoff rằng *mọi* LPA bắt buộc phải cấu hình checkpoint để tránh `StackOverflowError` là quá tuyệt đối: checkpoint quan trọng với DataFrame iterative implementation, còn nhu cầu cụ thể phụ thuộc backend và phiên bản. Proposal gọi LPA “non-deterministic vì thứ tự cập nhật ngẫu nhiên” cũng giải thích quá chắc: tính không ổn định có thể từ tie, partition/order, implementation và số vòng lặp; không nên khẳng định chính xác nguyên nhân nếu chưa kiểm tra. Chạy nhiều lần cùng phiên bản/config/dữ liệu để đánh giá ổn định. So sánh **cặp account cùng label** hoặc community sizes thay vì so trực tiếp số ID label, vì ID có thể khác dù partition tương đương. [Python API reference](https://graphframes.io/api/python/graphframes.html).

### 9.4 Từ community đến “tightly knit” cần đo thêm

Để nói một community $C$ chặt, phải đo cạnh **bên trong** và cạnh **ra ngoài**. Với $n_C=|C|$, $m_C=|\{(u,v)\in E:u,v\in C\}|$, có thể dùng directed density:

$$\rho(C)=\frac{m_C}{n_C(n_C-1)}\qquad(n_C>1,\text{ nếu simple directed graph, không self-loop}).$$

Với multigraph PaySim, $m_C$ có thể vượt $n_C(n_C-1)$ vì parallel transactions; lúc đó $\rho$ trên **số giao dịch** không còn là density trong $[0,1]$. Nếu muốn density chuẩn, trước tiên distinct cặp `(src,dst)`; nếu muốn intensity, giữ $m_C$ và gọi là “transactions per possible directed pair”. Một chỉ số khác:

$$\text{internal share}(C)=\frac{m_C}{m_C+m_{\text{out}}},$$

với $m_{out}$ là số edge từ trong C ra ngoài C (có thể tính thêm incoming external). Cần báo cả `n_C`, `m_C`, total amount, loại giao dịch, median/time span và số fraud edges. Một cộng đồng nhiều account nhưng chỉ có vài giao dịch không thể gọi là fraud ring hoạt động chặt.

### 9.5 Đối chiếu CC, LPA, Motif

| Công cụ | Câu hỏi | Cần thêm gì để gắn với fraud? |
|---|---|---|
| CC | Account nào nằm cùng vùng đường đi không hướng? | Kích thước, tỷ lệ fraud, bridge, edge types |
| SCC | Account nào có đường đi hai chiều theo hướng? | Cycle cụ thể, thời gian, amounts |
| LPA | Heuristic chia cộng đồng theo neighbors | Density, internal share, stability, fraud enrichment |
| Motif | Những account/edge nào khớp pattern cụ thể? | Temporal order, amount consistency, nhãn/điều tra |

**Objective Task 4:** lấy LPA labels, tìm một community có bằng chứng cấu trúc đáng chú ý, xem nó có overlap với motif/relay nào không, và diễn giải với giới hạn. Nếu các community chủ yếu là star quanh merchant hoặc singletons, đó cũng là kết quả cần báo, không tự gắn “fraud ring”.

---

## 10. Diễn giải, kiểm chứng và đánh giá

### 10.1 Một finding tốt gồm những gì?

Ví dụ viết về một account/cụm:

> “Account X có In-Degree 82, nhận 82 giao dịch từ 79 account, PageRank thuộc top 10 trên full graph. Trong 82 giao dịch có 74 `PAYMENT`, 0 `isFraud=1`. Điều này phù hợp với vai trò merchant/hub; dữ liệu hiện tại không đủ để gọi X là fraud.”

Hoặc:

> “Hai giao dịch `A→B` (`TRANSFER`, step 211, amount 15.000) và `B→C` (`CASH_OUT`, step 212, amount 14.900) khớp relay motif. Chúng cách 1 giờ mô phỏng và số tiền lệch 100. Đây là candidate kiểm tra thêm; graph không chứng minh cùng đơn vị tiền được chuyển tiếp.”

Mỗi finding nên có **ID hoặc ID ẩn danh nhất quán**, edge sequence, timestamps, amounts, type, kết quả thuật toán, lý do quan tâm, và giới hạn. Với PaySim, không gọi `step=211` là ngày/giờ ngoài đời.

### 10.2 Đánh giá bằng `isFraud` sao cho không tự đánh lừa

`isFraud` là **transaction-level** label. PageRank, CC, LPA cho **account/community-level** outputs, nên phải định nghĩa phép nâng nhãn trước khi tính metrics. Ví dụ:

$$y_{account}(u)=\mathbf{1}[\exists e\text{ kề }u: isFraud(e)=1],$$

hoặc $y_{community}(C)=\mathbf{1}[\exists e\text{ nội bộ C fraud}]$. Cả hai có nhược điểm: một account/cluster có một fraud edge không làm tất cả giao dịch liên quan thành fraud. Vì thế trong báo cáo, ưu tiên ghi **số edge fraud / số edge đã flag**, precision và recall ở đúng cấp edge nếu motif tạo candidate edges:

$$\mathrm{precision}=\frac{TP}{TP+FP},\qquad \mathrm{recall}=\frac{TP}{TP+FN}.$$

Trong đó $TP$ là flagged edges có `isFraud=1`, $FP$ là flagged edges `isFraud=0`, $FN$ là fraud edges không được flag. Nếu mẫu motif trên PaySim cho 0 candidate, precision có mẫu số 0, **không ghi là 0 hoặc 100%**; ghi “không xác định vì không có predicted positive”. Một motif có thể hữu ích cho AML nhưng `isFraud` của PaySim là fraud kịch bản khác; precision thấp không tự chứng minh motif AML vô ích.

**Leakage:** không dùng `isFraud` để lọc graph trước khi tìm pattern rồi lại tuyên bố pattern phát hiện fraud. Nếu dùng nhãn để mô tả, ghi rõ đó là **post hoc validation**. Đừng dùng `newbalance*` làm predictor fraud khi data card cảnh báo dấu vết sau giao dịch.

### 10.3 Thử nghiệm mẫu vs full và khả năng tái lập

| Cách chạy | Mục tiêu | Không được suy ra |
|---|---|---|
| Toy graph 3–5 vertices | Chứng minh công thức/query/API đúng | Hiệu quả trên PaySim |
| Parquet sample ~100k edges | Gỡ lỗi pipeline nhanh | Không có cycle/community trên full |
| Full PaySim | Kết quả chính của report | Kết quả cho dữ liệu ngân hàng thật |
| AMLSim hoặc dataset khác | Minh họa AML motifs nếu cần | Rằng PaySim đã có motif ấy |

Lưu lại dataset path/version, số vertices/edges, câu query, threshold, `maxIter`, Spark/GraphFrames versions, tài nguyên chạy, ngày thực thi, log count. Cùng một graph có thể thay đổi LPA labels theo run; report cần ghi cả sự ổn định. Với PageRank 10 vòng, không dùng từ “đã hội tụ” nếu chưa kiểm tra sai số $\|r^{(t+1)}-r^{(t)}\|_1$ hoặc so với nhiều vòng hơn. Với graph rất lớn, `count()`/motif self-join/CC/LPA là các job đắt; dùng sample để phát triển rồi chạy full có kiểm soát. [Spark tuning](https://spark.apache.org/docs/3.5.1/sql-performance-tuning.html), [GraphFrames LPA guide](https://graphframes.io/04-user-guide/06-graph-clustering.html#label-propagation-lpa).

### 10.4 Những câu dễ nói sai và câu thay thế chính xác

| Câu dễ nói sai | Câu nên nói |
|---|---|
| “PageRank cao = rửa tiền.” | “PageRank cao chỉ là account có vị trí nhận ảnh hưởng cao theo graph hướng sender→receiver.” |
| “LPA cho fraud rings chính xác.” | “LPA đưa community candidates; cần đo độ chặt và đối chiếu chứng cứ.” |
| “CC là community detection.” | “CC trả weak reachability; một bridge có thể gộp nhiều community.” |
| “Hạ threshold sẽ tìm được 3-cycle.” | “Chỉ đúng nếu đã có structural cycle; filter không thể tạo cycle.” |
| “PaySim là AML ground truth.” | “PaySim có fraud labels của mô phỏng mobile money; không có nhãn money laundering chuẩn cho mỗi ring.” |
| “GraphFrames luôn dùng Vertex Cut.” | “GraphX có biểu diễn Vertex Cut; GraphFrames DataFrame-native dùng Spark SQL execution/partitioning, và vài thuật toán bọc GraphX.” |
| “Bất kỳ GraphFrame algorithm nào cũng được Catalyst tối ưu hết.” | “Các thao tác DataFrame hưởng Catalyst; PageRank `maxIter` hiện dùng GraphX backend.” |
| “`step` là timestamp ngày thực.” | “`step` là giờ mô phỏng, chỉ thể hiện thứ tự thời gian thô.” |
| “Full graph có 0 cycle vì sample có 0.” | “Muốn khẳng định phải chạy structural 3-cycle trên full graph.” |

---

## 11. Bản đồ công việc, sản phẩm nộp và câu hỏi phản biện

### 11.1 Ai đang làm gì, cần hiểu gì, bàn giao gì?

Bảng này tóm tắt [phân công gốc](BDA%20-%20PCCV%20-%20Trang%20t%C3%ADnh1.csv); “Người 1–7” là ký hiệu của nhóm, không suy đoán danh tính bạn.

| Người | Trách nhiệm chính | Đầu vào | Bàn giao và người cần nhận |
|---|---|---|---|
| **1 — Lead** | Setup/tích hợp, GraphX vs GraphFrames, đồng làm Task 1, report/demo | Đề và ETL của 2 | `GraphFrame` chạy, code tích hợp và báo cáo; phối hợp 2,7 |
| **2 — Data Engineering** | Khảo sát PaySim/AMLSim, ETL vertices/edges, Parquet, kiểm tra chất lượng | Raw dataset | Parquet + mapping + counts; bàn giao 1 rồi mở cho 3–6 |
| **3 — Metrics/PageRank** | Degree distribution, PageRank top 10, đạo hàm công thức | Graph từ 1/2 | Bảng/plot metrics + giải thích; 4 review |
| **4 — Motif Finding** | Query 3-cycle, threshold, diễn giải; xử lý trường hợp 0 cycle | Graph từ 1/2, `type`, `step` | Count 3-cycle full + query toy + mẫu bổ sung nếu cần; 3 review |
| **5 — LPA** | Chạy LPA, so sánh CC vs LPA, diễn giải communities | Graph từ 1/2 | Community table + một case có chứng cứ; 6 review |
| **6 — Community hỗ trợ** | Kiểm tra LPA stability, CC đối chiếu nếu khả thi | Output của 5 | Stability note + CC comparison; 5 review |
| **7 — Partitioning/report** | Vertex Cut vs Edge Cut, ghép Part A/B, slide/demo | Outputs của 1–6 | Report nhất quán, bảng rubric, demo; 1 review |

**Dependency chính:** Task 2–4 cần cùng phiên bản vertices/edges từ Task 1. Nếu 2 đổi mapping balance, step hay `type`, báo ngay cho 1,3,4,5,6. `src/graph_analysis.py`, `src/utils/etl_mapping.py` đang có; `src/metrics.py`, `src/motif_finding.py`, `src/community_detection.py` được đề xuất trong handoff nhưng chưa thấy ở workspace lúc viết. Bảng phân công chia 6 tuần: tuần 1 foundation; tuần 2 Task 1; tuần 3 Task 2 + khởi đầu Task 3; tuần 4 Task 3–4; tuần 5 hoàn thiện; tuần 6 report/demo.

### 11.2 Checklist báo cáo theo rubric

**Part A — 35 điểm:**

- Vẽ graph nhỏ, định nghĩa $V,E$, directed multigraph.
- Bảng GraphX vs GraphFrames, giải thích Catalyst/Tungsten và backend GraphX của PageRank.
- Edge Cut vs Vertex Cut có $C_{edge-cut}$ và $RF$, trade-off, liên hệ hub PaySim nhưng không khẳng định tối ưu khi chưa benchmark.
- PageRank từ transition matrix đến stationary distribution, xử lý dangling mass, $d=0.85$, ý nghĩa 10 iterations.
- CC weak reachability vs LPA community heuristic; thêm SCC để phân biệt đường đi có hướng.

**Part B — 65 điểm:**

- Task 1: data card, ETL mapping, schema, QA counts/integrity, graph initialization.
- Task 2: In/Out-Degree, degree distribution, PageRank top 10 và lý giải business.
- Task 3: query 3-cycle đúng đề, structural/filtered counts, ví dụ toy; nếu 0 trên full, giải thích và làm mẫu bổ sung trên PaySim hoặc dataset khác được ghi rõ.
- Task 4: LPA labels và sizes, case cụ thể với độ chặt/edge types/fraud labels; CC đối chiếu nếu chạy được.
- Cuối cùng: limitations của synthetic data, time proxy, sample bias, thuật toán heuristic, risk interpretation.

### 11.3 Câu hỏi phản biện thường gặp

**“Tại sao graph hữu ích hơn bảng?”** Vì cần truy vấn nhiều bước, reachability và cộng đồng; bảng vẫn là nơi lưu trữ thực tế trong DataFrame, graph là phép nhìn và API phân tích.

**“PageRank khác In-Degree thế nào?”** In-Degree đếm số giao dịch vào; PageRank cộng đóng góp có trọng số theo *điểm của người gửi* và chia theo Out-Degree của họ, có teleport/dangling handling.

**“Tại sao resetProbability là 0.15?”** Nó bằng $1-d$ với $d=0.85$ trong random surfer. Dùng đúng tham số đề; không có nghĩa 15% giao dịch fraud.

**“Tại sao CC và LPA cho số nhóm khác?”** CC gom theo tồn tại path không hướng; LPA dùng majority labels sau hữu hạn iterations. Một bridge có thể nối hai cụm chặt vào cùng CC.

**“PaySim 0 cycle thì Task 3 thế nào?”** Chạy query đúng đề, lưu count và log trên full, kiểm thử toy chứng minh code, giải thích dataset mismatch, báo 2-hop relay là phân tích bổ sung; muốn có cycle thật thì dùng dataset phù hợp và nêu rõ chuyển dataset.

**“Tại sao sample và full khác PageRank/LPA?”** Lấy mẫu edges đổi cả degree, paths, sinks và community boundaries; đây là những đại lượng phụ thuộc toàn mạng.

**“Có thật là project chạy phân tán?”** Spark DataFrame/GraphFrames là distributed APIs; code đang `.master("local[*]")` chạy song song trên một máy. Muốn claim scaling liên máy phải chạy trên cluster và đo thời gian/resource.

---

## 12. Glossary và nguồn học

### 12.1 Glossary Anh → giải nghĩa bằng tiếng Việt

| English term | Giải nghĩa ngắn | Objective trong project |
|---|---|---|
| Account | Tài khoản/thực thể giao dịch | Một vertex |
| AML (Anti-Money Laundering) | Phòng chống rửa tiền | Bối cảnh diễn giải, không là ground truth của PaySim |
| Big Data | Dữ liệu/quan hệ đủ lớn hoặc phức tạp để cần xử lý phân tán | Lý do dùng Spark; cần nêu kích thước thật |
| Catalyst | Optimizer query của Spark SQL | Tối ưu các thao tác DataFrame |
| Community | Nhóm vertices liên kết nội bộ theo một tiêu chí | Candidate groups của LPA |
| Connected Component | Thành phần liên thông yếu khi bỏ hướng | Nhóm account có path nào đó |
| Damping factor | Xác suất đi theo link trong random surfer | $d=0.85$ của PageRank |
| DataFrame | Bảng phân tán có schema | Vertices và edges của GraphFrames |
| Degree / In-Degree / Out-Degree | Số cạnh tổng / vào / ra | Mô tả account hubs |
| Directed cycle | Đường đi theo hướng quay lại vertex đầu | Motif Task 3 |
| Edge / vertex | Cạnh giao dịch / đỉnh account | Đơn vị graph |
| Edge Cut / Vertex Cut | Phân vùng chia vertex / chia edge | Phân tích chi phí phân tán Part A |
| ETL | Extract, Transform, Load | CSV → Parquet graph |
| Ground truth | Nhãn kiểm chứng do dataset cung cấp | `isFraud` ở cấp transaction |
| Hub | Vertex nhiều kết nối hoặc điểm cao theo metric | Ưu tiên xem xét, chưa là fraud |
| Label Propagation Algorithm (LPA) | Thuật toán chọn nhãn phổ biến từ neighbors | Task 4 community candidates |
| Markov chain | Quá trình ngẫu nhiên mà bước kế tiếp chỉ phụ thuộc trạng thái hiện tại | Nền tảng mô hình PageRank |
| Motif Finding | Tìm mẫu cấu trúc graph | Task 3 cycle/relay |
| PageRank | Điểm ảnh hưởng theo random walk | Task 2 top 10 |
| Partition | Mảnh dữ liệu/công việc của Spark | Chạy song song |
| Parquet | Định dạng file cột, hỗ trợ schema/nén | Lưu graph sau ETL |
| Reset probability | Xác suất teleport | `0.15 = 1-d` |
| Shuffle | Dữ liệu chuyển/repartition giữa partitions | Chi phí join/groupBy/thuật toán |
| Sink / dangling node | Vertex không có outgoing edge | Cần phân phối lại mass trong PageRank |
| Strongly Connected Component (SCC) | Nhóm có paths hai chiều theo hướng | Phân biệt vòng với weak connectivity |
| Timestamp proxy | Đại diện thời gian không phải datetime thực | PaySim `step` |
| Tungsten | Các tối ưu thực thi/biểu diễn của Spark SQL | Phép toán DataFrame hiệu quả |

### 12.2 Nguồn gốc nên học theo thứ tự

1. **Đề và tài liệu nhóm:** [graphX_subject.md](graphX_subject.md) → [BIG_Data_Group6.md](BIG_Data_Group6.md) → [bảng phân công](BDA%20-%20PCCV%20-%20Trang%20t%C3%ADnh1.csv) → [Person 2 handoff](person2_handoff.md). Đọc đề trước để biết cái gì bắt buộc.
2. **Khởi đầu Spark:** [Spark SQL, DataFrames and Datasets Guide (Spark 3.5.1)](https://spark.apache.org/docs/3.5.1/sql-programming-guide.html); [Cluster Mode Overview](https://spark.apache.org/docs/3.5.1/cluster-overview.html). Học DataFrame, lazy execution, partitions và actions.
3. **GraphFrames chính thức:** [Quick Start](https://graphframes.io/02-quick-start/02-quick-start.html), [Installation](https://graphframes.io/02-quick-start/01-installation.html), [Internals](https://graphframes.io/01-about/02-architecture.html), [Python API](https://graphframes.io/api/python/graphframes.html). Học GraphFrame trước khi chạy thuật toán.
4. **Part A GraphX và partitioning:** [Spark GraphX Programming Guide](https://spark.apache.org/docs/3.5.7/graphx-programming-guide.html), nhất là Property Graph, Vertex/Edge RDDs, Optimized Representation; [GraphFrames About](https://graphframes.io/01-about/01-index.html). Chú ý version trong repo là PySpark 3.5.1 còn guide GraphX liên kết là nhánh 3.5.x gần tương thích về khái niệm.
5. **PageRank:** [GraphFrames Centrality Metrics](https://graphframes.io/04-user-guide/03-centralities.html), [Brin & Page original paper](https://research.google/pubs/the-anatomy-of-a-large-scale-hypertextual-web-search-engine/). Dùng phần 7 ở đây để đi từ random walk đến công thức có sink.
6. **Motif:** [GraphFrames Motif Finding](https://graphframes.io/04-user-guide/04-motif-finding.html) và [Motif Tutorial](https://graphframes.io/03-tutorials/02-motif-tutorial.html). Chạy toy graph trước.
7. **CC/SCC/LPA:** [GraphFrames Traversals and Connectivity](https://graphframes.io/04-user-guide/05-traversals.html), [Community Detection](https://graphframes.io/04-user-guide/06-graph-clustering.html), [Raghavan et al. 2007 LPA](https://link.aps.org/doi/10.1103/PhysRevE.76.036106).
8. **Dataset:** [PaySim data card của tác giả](https://www.kaggle.com/datasets/ealaxi/paysim1/data); nếu đổi dataset, [AMLSim paper](https://arxiv.org/abs/2306.16424). Đọc data card để không lẫn fraud và AML, nhãn và `step`.

### 12.3 Nếu chỉ có một buổi để bắt đầu

Đọc mục 1 → mục 2 → mục 5.1–5.4 → chạy `python src/graph_analysis.py --sample` trong môi trường đúng package → chọn mục của người được giao trong bảng 11.1 → đọc mục thuật toán đó và tài liệu gốc tương ứng. Sau khi hiểu riêng phần mình, đọc mục 10 để không kết luận quá mức. Đến lúc viết báo cáo, dùng checklist 11.2 và trích nguồn chính thức nêu trên.

---

*Tài liệu này giải thích yêu cầu, mô hình toán, code hiện có và các giới hạn đã biết. Các số thống kê full PaySim và tuyên bố 0 cycle được gắn rõ là theo handoff của nhóm vì raw/full graph không có trong workspace lúc soạn; cần đưa log chạy full vào báo cáo chính thức.*
