# TỔNG HỢP KIẾN THỨC: CONNECTED COMPONENTS (CC) VÀ LABEL PROPAGATION ALGORITHM (LPA)
> **Tài liệu học tập & Báo cáo kỹ thuật — Part A & Task 4 (GraphGuard Project)**

---

## 1. TỔNG QUAN VÀ ĐẶT VẤN ĐỀ

Trong phân tích đồ thị giao dịch tài chính (Financial Transaction Networks), các đối tượng gian lận hoặc tội phạm rửa tiền (AML) thường không hoạt động riêng lẻ mà phối hợp theo tổ chức, băng nhóm (fraud rings / syndicates), sử dụng nhiều tài khoản trung gian (mule accounts) để phân tán và luân chuyển dòng tiền.

Để phát hiện các cấu trúc này, chúng ta sử dụng hai hướng tiếp cận phân cụm đồ thị:
1. **Phân tích khả năng tiếp cận (Reachability Analysis - Connected Components):** Xác định các "vùng liên thông" độc lập trên mạng lưới mà giữa các đỉnh có đường đi tới nhau.
2. **Phát hiện cộng đồng (Community Detection - Label Propagation Algorithm):** Phát hiện các nhóm tài khoản có mật độ giao dịch nội bộ dày đặc, gắn kết chặt chẽ với nhau vượt trội so với liên kết ra bên ngoài.

---

## 2. CONNECTED COMPONENTS (CC) & STRONGLY CONNECTED COMPONENTS (SCC)

### 2.1. Định nghĩa

#### a. Connected Components (CC - Thành phần liên thông yếu / vô hướng)
* Cho đồ thị có hướng $G = (V, E)$, Connected Components được định nghĩa bằng cách **bỏ qua chiều mũi tên của các cạnh** (xem đồ thị như một đồ thị vô hướng $G_{undirected} = (V, E')$).
* Một **Connected Component** là một tập con các đỉnh $V_i \subseteq V$ cực đại (maximal subset) sao cho giữa hai đỉnh bất kỳ trong $V_i$ đều tồn tại một đường đi (undirected path).
* Toàn bộ đồ thị sẽ được phân hoạch (partition) thành các thành phần liên thông rời rạc nhau: không có bất kỳ cạnh nào kết nối giữa hai component khác nhau.

#### b. Strongly Connected Components (SCC - Thành phần liên thông mạnh)
* Đối với đồ thị có hướng, **Strongly Connected Component (SCC)** là tập con các đỉnh $V_j \subseteq V$ cực đại sao cho với mọi cặp đỉnh $u, v \in V_j$, đều tồn tại cả đường đi có hướng từ $u$ đến $v$ ($u \leadsto v$) **và** đường đi có hướng từ $v$ đến $u$ ($v \leadsto u$).
* **Ý nghĩa:** SCC đảm bảo dòng tiền có thể tuần hoàn khép kín giữa các thành viên.

---

### 2.2. Cơ sở toán học của Connected Components

Xét quan hệ hai ngôi $\sim$ trên tập đỉnh $V$:
$$u \sim v \iff \text{Tồn tại đường đi vô hướng nối giữa } u \text{ và } v \text{ trong } G$$

Quan hệ $\sim$ là một **quan hệ tương đương** (Equivalence Relation) vì thỏa mãn 3 tính chất:
1. **Phản xạ (Reflexive):** $u \sim u$ (tự nó luôn nối với chính nó qua đường đi rỗng).
2. **Đối xứng (Symmetric):** Nếu $u \sim v$ thì $v \sim u$ (vì không xét chiều mũi tên).
3. **Bắc cầu (Transitive):** Nếu $u \sim v$ và $v \sim w$ thì $u \sim w$.

Do đó, các Connected Components chính là các **lớp tương đương (Equivalence Classes)** của quan hệ $\sim$:
$$[u] = \{v \in V \mid u \sim v\}$$

Tập đỉnh $V$ được phân rã hoàn toàn thành các lớp rời nhau:
$$V = \bigcup_{i=1}^k C_i \quad \text{với } C_i \cap C_j = \emptyset \ (\forall i \ne j)$$

---

### 2.3. Ví dụ minh họa CC & Giới hạn "Chiếc cầu nối" (The Bridge Problem)

Xét mạng lưới gồm 6 tài khoản:
* Cụm 1: Tam giác $A - B - C$ (giao dịch qua lại nhiều lần).
* Cụm 2: Tam giác $D - E - F$ (giao dịch qua lại nhiều lần).
* Giữa 2 cụm chỉ có đúng **một giao dịch duy nhất** nối từ $C$ sang $D$ (Cạnh cầu nối - Bridge edge).

```text
    A --- B               D --- E
     \   /                 \   /
       C --------(Cầu)------> D
       
   [ Băng nhóm 1 ]        [ Băng nhóm 2 ]
```

* **Kết quả CC:** Vì bỏ qua hướng và chỉ xét có đường đi hay không, đường đi $A - B - C - D - E - F$ kết nối toàn bộ hệ thống. Thuật toán CC sẽ gom tất cả 6 đỉnh vào **DUY NHẤT 1 Component**: $\{A, B, C, D, E, F\}$.
* **Hạn chế lớn nhất của CC:** Chỉ một giao dịch ngẫu nhiên hoặc tài khoản trung gian nhỏ đóng vai trò cầu nối (bridge) cũng đủ làm cho CC **gộp các cụm độc lập thành một component khổng lồ**. Do đó, CC **không thể đo được mức độ gắn kết khăng khít (tightly-knit)** của các thành viên.

---

## 3. LABEL PROPAGATION ALGORITHM (LPA)

### 3.1. Định nghĩa

**Label Propagation Algorithm (LPA)** là thuật toán phát hiện cộng đồng bán giám sát/không giám sát (Raghavan et al., 2007) hoạt động dựa trên cơ chế **truyền thông điệp (message passing) và bỏ phiếu đa số cục bộ (local majority voting)**. 

* **Ý tưởng cốt lõi:** Một cá nhân có xu hướng gia nhập hoặc thuộc về cộng đồng mà đa số bạn bè/đối tác của người đó đang thuộc về ("Gần mực thì đen").
* Thuật toán có chi phí tính toán tuyến tính $O(|V| + |E|)$, cực kỳ phù hợp để chạy phân tán trên quy mô Big Data (Apache Spark).

---

### 3.2. Cơ sở toán học của LPA

Giả sử mạng lưới đồ thị $G = (V, E)$, với $N(u)$ là tập hợp các đỉnh láng giềng kề với $u$.

#### Bước 1: Khởi tạo (Initialization at $t = 0$)
Mỗi đỉnh $u \in V$ được gán một nhãn ban đầu duy nhất mang chính ID của nó:
$$\ell_u^{(0)} = u, \quad \forall u \in V$$

#### Bước 2: Cập nhật nhãn lặp (Iterative Label Update at step $t+1$)
Tại mỗi vòng lặp $t+1$, mỗi đỉnh $u$ khảo sát nhãn hiện tại của tất cả các láng giềng $v \in N(u)$, và chọn **nhãn xuất hiện nhiều nhất (đa số áp đảo)**:

$$\ell_u^{(t+1)} = \operatorname*{arg\,max}_{c} \sum_{v \in N(u)} \mathbf{1}\left[\ell_v^{(t)} = c\right]$$

* Trong đó $\mathbf{1}[\cdot]$ là hàm chỉ thị (indicator function):
$$\mathbf{1}[\text{điều kiện}] = \begin{cases} 1 & \text{nếu điều kiện đúng} \\ 0 & \text{nếu điều kiện sai} \end{cases}$$
* **Quy tắc giải quyết hòa phiếu (Tie-breaking Rule):** Nếu có từ hai nhãn trở lên cùng đạt số phiếu tối đa, một nhãn sẽ được chọn ngẫu nhiên đồng đều (uniformly at random).

#### Bước 3: Điều kiện dừng (Termination Condition)
Thuật toán dừng khi:
1. Đạt trạng thái cân bằng (hội tụ): Không có đỉnh nào thay đổi nhãn sau một vòng lặp ($\ell_u^{(t+1)} = \ell_u^{(t)}, \forall u \in V$).
2. Hoặc đạt số vòng lặp tối đa được chỉ định trước: $t = \text{maxIter}$ (trong project quy định `maxIter = 5`).

---

### 3.3. Ví dụ từng bước: Cách LPA giải quyết "Chiếc cầu nối"

Sử dụng lại đồ thị 6 đỉnh ở phần 2.3: Tam giác $A-B-C$ nối với Tam giác $D-E-F$ qua cạnh cầu $C-D$.

```text
    A --- B               D --- E
     \   /                 \   /
       C ------------------- D
```

* **Vòng 0 ($t = 0$):** Mỗi đỉnh mang nhãn của chính mình:
  $\ell_A = 1, \ell_B = 2, \ell_C = 3, \ell_D = 4, \ell_E = 5, \ell_F = 6$.
* **Vòng 1 ($t = 1$):** Các đỉnh cập nhật theo láng giềng:
  * Đỉnh $A$ có láng giềng là $\{B, C\}$ (nhãn 2, 3) $\to$ chọn ngẫu nhiên 1 trong 2.
  * Giả sử cụm $\{A, B, C\}$ bắt đầu thống nhất về nhãn $1$.
  * Giả sử cụm $\{D, E, F\}$ bắt đầu thống nhất về nhãn $4$.
* **Vòng 2 trở đi ($t \ge 2$): Đỉnh cầu nối $C$ bầu cử ra sao?**
  * Láng giềng của $C$ gồm: $A$ (nhãn 1), $B$ (nhãn 1), và $D$ (nhãn 4).
  * Kiểm phiếu tại $C$:
    * Nhãn $1$: Có 2 phiếu (từ $A$ và $B$).
    * Nhãn $4$: Chỉ có 1 phiếu (từ $D$).
  * $\to$ **Nhãn 1 thắng áp đảo ($2 > 1$)**! Đỉnh $C$ giữ nguyên nhãn 1.
  * Tương tự tại đỉnh $D$: Nhãn $4$ thắng áp đảo ($2 > 1$) trước nhãn $1$ từ $C$.

👉 **Kết quả cuối cùng của LPA:**
* **Cộng đồng 1:** $\{A, B, C\}$ mang nhãn $1$.
* **Cộng đồng 2:** $\{D, E, F\}$ mang nhãn $4$.

Nhờ cơ chế bỏ phiếu đa số, **LPA không bị đánh lừa bởi cạnh cầu nối duy nhất**, tách biệt hoàn hảo 2 cụm giao dịch nội bộ dày đặc!

---

## 4. TIÊU CHÍ ĐÁNH GIÁ ĐỘ GẮN KẾT CỘNG ĐỒNG (TIGHTLY-KNIT METRICS)

Để trả lời câu hỏi phản biện của giảng viên: *"Làm sao chứng minh một cộng đồng tìm được từ LPA thực sự gắn kết chặt chẽ (tightly knit) chứ không phải ngẫu nhiên?"*, ta sử dụng 2 thước đo định lượng:

### 4.1. Mật độ giao dịch nội bộ (Internal Directed Density - $\rho(C)$)
Với một cộng đồng $C$ gồm $n_C = |C|$ tài khoản và $m_C$ giao dịch nội bộ giữa các thành viên trong $C$:

$$\rho(C) = \frac{m_C}{n_C(n_C - 1)}$$

* $n_C(n_C - 1)$ là số cặp giao dịch có hướng tối đa có thể tồn tại giữa $n_C$ đỉnh.
* $\rho(C) \in [0, 1]$ đối với đồ thị đơn (simple graph). Giá trị $\rho(C)$ càng tiến gần 1 chứng tỏ cộng đồng giao dịch nội bộ càng dày đặc.
* *Lưu ý trong PaySim (Multigraph):* Nếu có nhiều giao dịch lặp lại giữa cùng một cặp tài khoản, $m_C$ có thể lớn hơn $n_C(n_C - 1)$. Khi đó ta tính trên số cặp đỉnh duy nhất đã giao dịch (distinct pairs) hoặc diễn giải là "cường độ giao dịch trung bình trên mỗi cặp".

### 4.2. Tỷ trọng giao dịch nội bộ (Internal Edge Share)

$$\text{Internal Share}(C) = \frac{m_C}{m_C + m_{out}}$$

* $m_C$: Số giao dịch diễn ra giữa các thành viên bên trong cộng đồng $C$.
* $m_{out}$: Số giao dịch từ thành viên trong $C$ chuyển tiền ra cho tài khoản bên ngoài.
* **Ý nghĩa thực tế AML:** Nếu $\text{Internal Share} \ge 80\% - 90\%$, đây là tín hiệu báo động đỏ về một **nhóm khép kín (closed financial ring)**, dòng tiền chủ yếu luân chuyển nội bộ mà không phân tán ra nền kinh tế.

---

## 5. BẢNG SO SÁNH TOÀN DIỆN: CC VS SCC VS LPA

| Tiêu chí so sánh | Connected Components (CC) | Strongly Connected (SCC) | Label Propagation Algorithm (LPA) |
|---|---|---|---|
| **Mục tiêu kỹ thuật** | Tìm tập đỉnh cực đại có đường đi tới nhau khi **bỏ qua hướng**. | Tìm tập đỉnh cực đại có đường đi **hai chiều theo đúng hướng**. | Tìm các cụm đỉnh có **mật độ liên kết nội bộ dày đặc**. |
| **Xử lý chiều cạnh** | Vô hướng (Undirected). | Có hướng (Directed). | Thực thi theo cơ chế láng giềng kề của engine. |
| **Độ nhạy với Cầu nối (Bridge)** | **Rất kém:** Một cạnh đơn lẻ có thể gộp 2 nhóm lớn thành 1 component. | Tốt: Chỉ gộp nếu cạnh cầu nối có đường quay ngược lại. | **Rất tốt:** Bỏ phiếu đa số dập tắt ảnh hưởng của cạnh cầu nối đơn lẻ. |
| **Tính tất định (Determinism)** | **Tất định (Deterministic):** Cùng đồ thị luôn ra 1 kết quả phân rã duy nhất. | **Tất định (Deterministic):** Luôn ra 1 kết quả duy nhất. | **Bất định (Non-deterministic):** Hòa phiếu chọn ngẫu nhiên có thể đổi nhãn cụm. |
| **Đảm bảo hội tụ** | Luôn hội tụ (sau khi duyệt hết các thành phần). | Luôn hội tụ. | **Không đảm bảo hội tụ**; thường chặn bằng `maxIter`. |
| **Độ phức tạp tính toán** | $O(|V| + |E|)$. | $O(|V| + |E|)$ (thuật toán Tarjan/Kosaraju). | $O(k \cdot (|V| + |E|))$ với $k$ là số vòng lặp. |
| **Vai trò trong Project** | Thống kê cấu trúc vĩ mô, phát hiện các cụm cô lập. | Bổ trợ nghiên cứu khả năng tuần hoàn dòng tiền. | **Nhiệm vụ chính Task 4:** Gom cụm các băng nhóm giao dịch nghi vấn. |


