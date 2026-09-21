# Part A — Graph Theory & Distributed Mechanics Report

> **Barem:** 35/100 điểm. Hạng mục chấm số 1 của đề bài Subject 8: *"Clear mathematical breakdown of PageRank, Vertex Cut partitioning, and GraphFrames internals."*
> **Ngôn ngữ:** tiếng Việt, **giữ nguyên thuật ngữ tiếng Anh**, giải nghĩa tiếng Việt ở lần xuất hiện đầu.
> **Cách dùng file:** mỗi mục 3.1–3.4 là một phần độc lập, do một người phụ trách. Chỉ sửa trong mục của mình để tránh conflict khi merge.

| Mục | Nội dung | Phụ trách | Review | Trạng thái |
|---|---|---|---|---|
| 3.1 | GraphX vs GraphFrames | N1 | N7 | chưa bắt đầu |
| 3.2 | Graph Partitioning: Vertex Cut vs Edge Cut | N7 | N1 | chưa bắt đầu |
| **3.3** | **Dẫn xuất công thức PageRank** | **N3** | **N4** | **draft — bản này** |
| 3.4 | Connected Components vs LPA | N5, N6 | N6 | chưa bắt đầu |

---

## 3.1 — GraphX vs GraphFrames

> Phụ trách **N1**, review **N7**. Chưa bắt đầu.

*Nội dung cần có (theo đề bài):* so sánh biểu diễn graph trong GraphX (`VertexRDD`, `EdgeRDD`) với GraphFrames (hai DataFrame tận dụng Catalyst và Tungsten); nêu đánh đổi và lý do nhóm chọn GraphFrames.

---

## 3.2 — Graph Partitioning: Vertex Cut vs Edge Cut

> Phụ trách **N7**, review **N1**. Chưa bắt đầu.

*Nội dung cần có (theo đề bài):* Spark phân tán graph lớn ra cluster bằng chiến lược Vertex Cut hay Edge Cut để giảm network shuffle; liên hệ với phân phối degree lệch mạnh của PaySim (max in-degree 113, max out-degree 3).

---

## 3.3 — Dẫn xuất công thức PageRank

> Phụ trách **N3**, review **N4**. Bản draft 22/9/2026; lịch final 28/9/2026.
> Trả lời hai yêu cầu của đề bài: *"Derive the iterative PageRank formulation"* và *"Explain how the damping factor (d = 0.85) prevents sink node trapping."*

### Đáp án trực tiếp hai câu hỏi của đề bài

Đề bài Subject 8 hỏi đúng hai việc. Dưới đây là câu trả lời tự chứa; chứng minh ở các mục được dẫn.

**(1) "Derive the iterative PageRank formulation."** Dẫn xuất ở §3.3.1–§3.3.6 theo chuỗi: Random Walk $\Pr[v\to u] = A_{vu}/d_{out}(v)$ → luật xác suất toàn phần → $\mathbf{r}^{(t+1)} = M\mathbf{r}^{(t)}$ → stationary distribution → stochasticity adjustment $S$ → primitivity adjustment $G$ → khai triển thành phần:

$$r^{(t+1)}(u) \;=\; \frac{1-d}{N} \;+\; d\left[\;\sum_{v:\,d_{out}(v)>0} \frac{A_{vu}\,r^{(t)}(v)}{d_{out}(v)} \;+\; \frac{1}{N}\sum_{v\in D} r^{(t)}(v)\right], \qquad d = 0{,}85 .$$

Dạng rút gọn mà đề bài đưa ra, $PR(u) = \frac{1-d}{N} + d\sum_{v\in B(u)} \frac{PR(v)}{L(v)}$, là **trường hợp riêng** khi $D = \varnothing$ và không có parallel edges (§3.3.6.3). PaySim có $\lvert D\rvert = 2\,720\,593$ nên phải dùng dạng đầy đủ.

**(2) "Explain how the damping factor ($d = 0.85$) prevents sink node trapping."** Bốn cơ chế, mỗi cơ chế một bất đẳng thức kiểm chứng được (§3.3.7):

- **(i) Lower bound dương cho mọi node.** $r(u) \ge \frac{1-d}{N} > 0$ với mọi $u$, mọi $t$ — kể cả node không có một in-link nào.
- **(ii) Upper bound cho mọi cụm.** Với mọi tập con **thực sự** $C \subsetneq V$: $\sum_{u\in C} r(u) \le d + (1-d)\frac{\lvert C\rvert}{N} \le 1 - \frac{1-d}{N} < 1$. Không cụm nào — kể cả cụm đóng hoàn toàn — giữ được toàn bộ phân phối. Đây là dạng định lượng của phát biểu: không tập con thực sự nào giữ được toàn bộ phân phối, bất kể cấu trúc của nó.
- **(iii) Ép $G$ primitive.** $G_{uv} \ge \frac{1-d}{N} > 0$ nên $G > 0$; theo Perron–Frobenius tồn tại **duy nhất** $\mathbf{r} > 0$, $\lVert\mathbf{r}\rVert_1 = 1$, và power iteration hội tụ về nó từ **mọi** khởi tạo. $G$ còn là **ánh xạ co** hệ số $d$, cho cận vô điều kiện $\lVert\mathbf{r}^{(t)}-\mathbf{r}^{*}\rVert_1 \le 2d^{\,t}$.
- **(iv) Theo ngôn ngữ random surfer.** Số node walker ghé thăm trong một chặng đi theo link là biến **geometric** tham số $1-d$, kỳ vọng $1/(1-d) \approx 6{,}67$, đuôi $\Pr[T>k] = d^{k}$. Xác suất ở lại **vĩnh viễn** trong bất kỳ cụm nào bằng **0**.

**Bằng chứng số cho đúng cụm từ "sink node trapping":** §3.3.9.2 dựng một sink có self-loop — một **absorbing state** thật. Với $d = 1$ nó hấp thụ **100%** mass ($\mathbf{r}^{*} = (0;0;1)$); với $d = 0{,}85$ nó chỉ giữ $0{,}8575$, còn node đầu chuỗi được giữ đúng ở lower bound $(1-d)/N = 0{,}05$.

**Một vế đề bài không hỏi nhưng PaySim bắt buộc phải nói:** damping **một mình chưa đủ**. Nó chỉ xử lý phần **trapping** (mass bị giữ lại vĩnh viễn), **không** xử lý phần **leakage** (mass thoát khỏi hệ do $d_{out} = 0$). Phần leakage do **stochasticity adjustment** đảm nhiệm, và **thứ tự hai cách giải quyết là bắt buộc** (§3.3.4.3). Hai cách giải quyết thực chất là **một cơ chế nhìn từ hai góc**: cả hai đều teleport về cùng teleportation vector $\mathbf{v} = \frac{1}{N}\mathbf{e}$ (§3.3.7.3).

---

### 3.3.0 — Quy ước ký hiệu

**Quy ước ma trận.** Nhóm dùng **column-stochastic** (mỗi **cột** cộng bằng 1), vector cột $\mathbf{r}$, phương trình $\mathbf{r} = M\mathbf{r}$ — theo giáo trình *Mining of Massive Datasets*. Langville & Meyer dùng **row-stochastic** ($\pi^{T}P = \pi^{T}$), nên **mọi công thức trích từ họ trong mục này đều đã được chuyển vị**.

> **Hệ quả phải nhớ suốt mục:** mọi **outer product** (tích ngoài) mô tả teleportation có **vector đích đứng BÊN TRÁI**: ma trận teleport về $\mathbf{v}$ là $\mathbf{v}\mathbf{e}^{T}$, **không phải** $\mathbf{e}\mathbf{v}^{T}$. Trường hợp đều $\mathbf{v} = \frac1N\mathbf{e}$ che mất khác biệt này vì khi đó hai dạng trùng nhau — đó là lý do lỗi dễ lọt.

**Ký hiệu của nhóm.** $\mathcal{G} = (V,E)$ là **directed multigraph**, $\lvert V\rvert = N$, hướng cạnh là **sender → receiver**.

| Ký hiệu | Nghĩa |
|---|---|
| $A_{vu}$ | số cạnh từ $v$ tới $u$ (đếm theo bội) |
| $d_{out}(v) = \sum_u A_{vu}$ | out-degree, đếm theo bội |
| $D = \{v : d_{out}(v) = 0\}$ | tập **dangling node / sink node** |
| $B(u) = \{v : A_{vu} > 0\}$ | tập **in-neighbour** của $u$ |
| $\mathbf{e}$, $J = \mathbf{e}\mathbf{e}^{T}$ | vector cột toàn 1; ma trận toàn 1 |
| $\mathbf{v}$ | **teleportation vector**, mặc định $\frac1N\mathbf{e}$ |
| $d = 0{,}85$ | **damping factor** |

---

### 3.3.1 — Bước 1: Random walk trên graph

**Random walk** là mô hình sinh của PageRank: điểm số không phải công thức đếm tuỳ tiện mà là **phân phối xác suất dài hạn của vị trí một người đi ngẫu nhiên trên graph**. Brin & Page (1998), §2.1.2 gọi là **random surfer model**:

> "We assume there is a 'random surfer' who is given a web page at random and keeps clicking on links, never hitting 'back' but eventually gets bored and starts on another random page. The probability that the random surfer visits a page is its PageRank."

Hai chi tiết: **"never hitting back"** là giả định mô hình được tuyên bố rõ — quá trình **memoryless**, chỉ phụ thuộc vị trí hiện tại, tức một **Markov chain**; và xác suất thăm một trang **chính là** PageRank, nên PageRank là một **phân phối xác suất trên $V$**.

> **Cảnh báo trích dẫn.** Brin & Page viết tiếp: *"the $d$ damping factor is the probability at each page the 'random surfer' will get bored and request another random page."* Câu này đọc sát chữ **ngược với chính công thức của họ**: với $d = 0{,}85$ trong $PR(A) = (1-d) + d(\cdots)$ thì $d$ là xác suất **đi tiếp theo link**. Nhóm dùng quy ước của GraphFrames, Langville & Meyer và *Mining of Massive Datasets*: $d$ = xác suất follow link, $1-d$ = xác suất teleport.

Đặt $X_t \in V$ là vị trí walker tại bước $t$. Từ node $v$ có $d_{out}(v) > 0$, walker **chọn ngẫu nhiên đều một outgoing edge**:

$$\Pr\!\left[X_{t+1} = u \mid X_t = v\right] \;=\; \frac{A_{vu}}{d_{out}(v)}, \qquad d_{out}(v) > 0 .$$

Với **simple graph** thì $A_{vu} \in \{0,1\}$ và công thức rút về $1/L(v)$ — đúng như đề cương nhóm. Với **multigraph** thì bội số cạnh **có ý nghĩa xác suất thật**: nếu $v$ gửi 3 giao dịch và 2 trong số đó tới $u$, walker đi tới $u$ với xác suất $2/3$ chứ không phải $1/2$.

Công thức trên **chưa định nghĩa gì khi $d_{out}(v) = 0$** — đó là lỗ hổng bộc lộ ở Bước 4.

---

### 3.3.2 — Bước 2: Transition matrix và phép lặp

Định nghĩa $M \in \mathbb{R}^{N\times N}$ theo quy ước column-stochastic:

$$M_{uv} \;=\; \begin{cases} \dfrac{A_{vu}}{d_{out}(v)}, & d_{out}(v) > 0,\\[2ex] 0, & d_{out}(v) = 0 .\end{cases}$$

Đọc đúng chỉ số: **$M_{uv}$ ở hàng $u$, cột $v$, mô tả luồng xác suất chảy TỪ $v$ SANG $u$.** Cột $v$ chứa toàn bộ phân phối đi ra của node $v$.

**$M$ là substochastic, chưa phải stochastic.** Tổng cột bằng $1$ khi $d_{out}(v) > 0$, nhưng bằng $\mathbf{0}$ khi $v \in D$. *Mining of Massive Datasets* §5.1.4: *"A matrix whose column sums are at most 1 is called substochastic."* Với graph có $D \neq \varnothing$, $M$ **không** stochastic — Langville & Meyer (2006) gọi ma trận thô này là *"very sparse, raw substochastic hyperlink matrix"*.

Gọi $r^{(t)}(u) = \Pr[X_t = u]$. Luật xác suất toàn phần cho $r^{(t+1)}(u) = \sum_v M_{uv} r^{(t)}(v)$, tức

$$\boxed{\;\mathbf{r}^{(t+1)} \;=\; M\,\mathbf{r}^{(t)}\;}$$

Khởi tạo tự nhiên là **uniform distribution** $\mathbf{r}^{(0)} = \frac1N\mathbf{e}$. Lặp phép nhân này chính là **power iteration**.

---

### 3.3.3 — Bước 3: Stationary distribution

**Stationary distribution** của Markov chain là vector xác suất không đổi qua một bước chuyển:

$$\mathbf{r} \;=\; M\mathbf{r}, \qquad \mathbf{r} \ge 0, \qquad \lVert\mathbf{r}\rVert_1 = 1 .$$

Tức $\mathbf{r}$ là **eigenvector** của $M$ ứng **eigenvalue** $\lambda = 1$, chuẩn hoá theo $L_1$. Brin & Page (1998) §2.1.1: *"PageRank … corresponds to the principal eigenvector of the normalized link matrix of the web."*

Viết ra từng thành phần, $\mathbf{r} = M\mathbf{r}$ cho **dạng đệ quy** — đây là "bản chất" của PageRank trước khi có bất kỳ cách giải quyết nào:

$$r(u) \;=\; \sum_{v} M_{uv}\,r(v) \;=\; \sum_{v\in B(u)} rac{A_{vu}\,r(v)}{d_{out}(v)} \qquad\left(	ext{simple graph: } \sum_{v\in B(u)}rac{r(v)}{L(v)}
ight).$$

*(Dangling node không đóng góp gì vì cột của chúng toàn 0 — và chính điều đó là vấn đề ở Bước 4.)*

**PageRank là gì, một câu:** stationary distribution của random walk trên graph — xác suất dài hạn walker đang đứng ở mỗi node.

**Hai mệnh đề phổ, hai giả thiết KHÁC nhau** (thường bị gộp làm một):

**(P1)** Nếu $M$ column-stochastic thì $1$ là eigenvalue của $M$. Vì $\mathbf{e}^{T}M = \mathbf{e}^{T}$ nên $1$ là eigenvalue **trái**; phổ của $M$ và $M^{T}$ trùng nhau nên $1$ cũng là eigenvalue phải. *Mệnh đề này cần đẳng thức, không dùng được cho substochastic.*

**(P2)** Nếu $M$ chỉ substochastic thì $\rho(M) \le 1$. Vì $\lVert M\rVert_1 = \max_v\sum_u M_{uv} \le 1$, nếu $M\mathbf{x} = \lambda\mathbf{x}$ thì $\lvert\lambda\rvert\lVert\mathbf{x}\rVert_1 = \lVert M\mathbf{x}\rVert_1 \le \lVert\mathbf{x}\rVert_1$, suy ra $\lvert\lambda\rvert \le 1$. *Chỉ cần tổng cột $\le 1$.*

> **Lỗi rất phổ biến:** con số $1$ ở (P1) đến từ **tính stochastic**, KHÔNG từ Perron–Frobenius. Perron–Frobenius chỉ nói eigenvalue trội bằng $\rho(\cdot)$.

**Ba câu hỏi còn bỏ ngỏ**, và chúng cần **ba điều kiện khác nhau** — gộp lại là lỗi toán thường gặp nhất trong các bài viết về PageRank:

1. **Tồn tại** — có $\mathbf{r} \ge 0$ nào thoả $\mathbf{r} = M\mathbf{r}$, $\lVert\mathbf{r}\rVert_1 = 1$ không?
2. **Duy nhất** — nếu có thì duy nhất không?
3. **Hội tụ** — dãy $M^{t}\mathbf{r}^{(0)}$ có hội tụ về nó từ **mọi** khởi tạo không?

---

### 3.3.4 — Bước 4: Ba vấn đề của $M$ và cách giải quyết thứ nhất

Một trong hai bước trọng tâm. Có **ba vấn đề khác nhau**, biểu hiện khác nhau, cách giải quyết khác nhau.

#### 3.3.4.1 Vấn đề 1 (substochastic) — dangling node gây leakage

**Sink node** (hay **dangling node**) là node có $d_{out}(v) = 0$: nhận được nhưng không bao giờ gửi. Cột của nó toàn 0. Theo dõi tổng $L_1$ qua một vòng lặp:

$$\lVert\mathbf{r}^{(t+1)}\rVert_1 \;=\; \sum_v r^{(t)}(v)\underbrace{\sum_u M_{uv}}_{=\,1 \text{ nếu } v\notin D,\; =\,0 \text{ nếu } v\in D} \;=\; \lVert\mathbf{r}^{(t)}\rVert_1 \;-\; \sum_{v\in D} r^{(t)}(v).$$

**Mỗi vòng lặp, đúng phần mass nằm trên tập sink bị xoá khỏi hệ thống.** Với graph mà mass liên tục đi vào sink, $\lVert\mathbf{r}^{(t)}\rVert_1 \to 0$: toàn bộ vector tiến về vector không, **không còn thông tin xếp hạng nào**.

*Mining of Massive Datasets* §5.1.4 mô tả đúng hiện tượng: *"importance 'drains out' of the Web, and we get no information about the relative importance of pages."* Và chính **Page et al. (1999)** §2.4 thừa nhận: *"Note that $c < 1$ because there are a number of pages with no forward links and their weight is lost from the system."* — **chính tác giả gốc xác nhận rank leakage do node out-degree 0**, đúng tình huống Merchant của PaySim.

#### 3.3.4.2 Vấn đề 2 và 3 (reducible) — rank sink và nghiệm không duy nhất

> **Đính chính thuật ngữ.** "Rank sink" **lệch nghĩa giữa hai nguồn gốc**. **Page et al. (1999)** §2.4 (nguồn sinh ra thuật ngữ) dùng cho một **loop/cycle không có outedge ra ngoài**: *"this loop will accumulate rank but never distribute any rank … The loop forms a sort of trap which we call a rank sink."* Trong khi **Langville & Meyer (2004)** §5.1.1 lại dùng chữ đó cho **dangling node**.

Hai hiện tượng khác nhau về cơ học:

| | **Sink / dangling node** | **Spider trap / rank sink (nghĩa 1999)** |
|---|---|---|
| Cấu trúc | node lẻ, $d_{out}=0$ | cụm/cycle đóng, có cạnh vào, không có cạnh ra |
| Hiệu ứng lên $\lVert\mathbf{r}\rVert_1$ | **leakage**, tổng $\to 0$ | **giữ nguyên tổng $= 1$**, nhưng dồn hết vào cụm |
| Tính chất ma trận | substochastic | stochastic nhưng **reducible** |
| Cách khắc phục | stochasticity adjustment | teleportation (Bước 5) |

**Nhóm tuyên bố rõ:** trong toàn mục, **"sink node" dùng theo nghĩa dangling node ($d_{out}=0$)** — nghĩa khớp dữ liệu PaySim; khi cần nói cycle tích luỹ mass thì dùng **"spider trap"**.

**Vấn đề 3 — nghiệm không duy nhất.** Ngay cả khi $M$ đã stochastic, nếu ma trận **reducible** và có **từ hai closed class trở lên** thì không gian riêng ứng $\lambda = 1$ có chiều $> 1$: vô số stationary distribution, và dãy lặp hội tụ về cái nào **phụ thuộc khởi tạo**. Một thước đo phụ thuộc điểm khởi tạo thì **không phải là một thước đo**.

> **Phát biểu cho chính xác:** điều kiện gây không duy nhất **không phải** "reducible", mà là **có ít nhất HAI closed class**. Một chain hữu hạn có **đúng một** closed class thì stationary distribution vẫn **duy nhất**, dù reducible.

**Với PaySim, phải tách hai mệnh đề — gộp lại là non sequitur:**

- **Đúng và đo được:** $70{,}00\%$ số node ($6\,351\,538$ (\*)) **không có in-link nào**, nên **graph thô không** strongly connected và **$M$ reducible**.
- **KHÔNG suy ra được:** rằng $S$ cũng reducible. Sau stochasticity adjustment, mỗi node không-in-link nhận cạnh $S_{u,v} = 1/N > 0$ từ **toàn bộ** $2\,720\,593$ dangling node — chúng đi tới được hoàn toàn trong $S$. Phản ví dụ nằm ngay trong bài: ví dụ 1 ở §3.3.9.1 có $C$ không in-link và $T$ dangling, vậy mà $S$ **primitive**.

#### 3.3.4.3 Cách giải quyết thứ nhất: stochasticity adjustment $M \to S$

**Khi walker rơi vào một sink, cho nó teleport ngay tới một node ngẫu nhiên đều.** Định nghĩa **dangling node vector** $\mathbf{a} \in \{0,1\}^{N}$ với $a_v = 1 \iff v \in D$. Khi đó cách giải quyết là một **rank-one update**:

$$\boxed{\;S \;=\; M \;+\; \frac{1}{N}\,\mathbf{e}\,\mathbf{a}^{T}\;}$$

*(Dạng đã chuyển vị của Langville & Meyer (2006) Ch. 4.5; bản gốc row-convention là $S = H + \mathbf{a}(\frac1N\mathbf{e}^{T})$. Tổng quát: $S = M + \mathbf{v}\mathbf{a}^{T}$ — **vector đích $\mathbf{v}$ đứng bên trái**.)*

Kiểm chứng: với $v \in D$ thì cột $v$ của $S$ là $\frac1N\mathbf{e}$, tổng $= 1$; với $v \notin D$ thì $a_v = 0$, cột không đổi. Vậy **$S$ column-stochastic**. Nhưng $S$ **vẫn có thể reducible** — Langville & Meyer (2006) mô tả $S$ là *"sparse, stochastic, most likely reducible matrix"*. Hai vấn đề còn lại chưa được giải quyết.

> **THỨ TỰ HAI PHÉP SỬA LÀ BẮT BUỘC — chỗ dễ sai nhất của khung 6 bước.**
>
> Nếu áp teleportation **trực tiếp** lên $M$ thô còn cột 0, tức $G' = dM + (1-d)\frac1N J$, thì $G' > 0$ (vẫn primitive) **nhưng KHÔNG còn column-stochastic**: cột của một dangling node cộng lại chỉ bằng $1-d = 0{,}15$.
>
> Vì $G' > 0$ nên irreducible, và với ma trận không âm irreducible thì $\min_v\sum_u G'_{uv} \le \rho(G') \le \max_v\sum_u G'_{uv}$, **đẳng thức chỉ khi mọi tổng cột bằng nhau**. Ở đây tổng cột nhận cả $1$ lẫn $0{,}15$, nên $\rho(G') < 1$ **ngặt**. Hệ quả: $1$ **không** là eigenvalue, $\mathbf{x} = G'\mathbf{x}$ chỉ có nghiệm $\mathbf{x} = \mathbf{0}$, và $\mathbf{r}^{(t)} \to \mathbf{0}$ từ **mọi** khởi tạo. **Toàn bộ thông tin xếp hạng biến mất.**
>
> **Phải làm $S$ stochastic TRƯỚC, rồi mới teleport.** Câu "thêm teleportation là đủ để vừa stochastic vừa primitive" là **sai**.

#### 3.3.4.4 Đối chiếu lịch sử — trung thực về nguồn

- **Page et al. (1999)** §2.7 xử lý dangling link bằng cách **loại bỏ rồi thêm lại**: *"we simply remove them from the system until all the PageRanks are calculated."*
- **Dạng rank-one $S = M + \frac1N\mathbf{e}\mathbf{a}^{T}$ và tên gọi "stochasticity adjustment" là của Langville & Meyer (2006)**, không phải của Brin & Page.

> **Ba điều KHÔNG được viết:** (1) "Brin & Page (1998) đề xuất xử lý dangling link" — bản 1998 **không chứa** hai chữ "sink" lẫn "dangling" ở bất kỳ đâu. (2) "Số hạng $\frac1N\sum_{v\in D}r(v)$ là theo Page et al. (1999)" — họ **xoá** dangling node chứ không phân phối lại. (3) Không ghi tên bản 1999 là "Brin et al." — thứ tự tác giả là **Page** đứng đầu.

Langville & Meyer (2004) §5.1 **phê phán trực tiếp** cách xoá dangling node, và lời phê phán ánh xạ chính xác sang PaySim:

> "we are certain that the removal of dangling nodes is not a fair procedure. Some dangling nodes should receive high PageRank … Simply removing the dangling nodes biases the PageRank vector unjustly."

Merchant của PaySim đóng đúng vai đó: out-degree $= 0$ tuyệt đối, trong khi lớp Merchant hấp thụ $2\,151\,495$ giao dịch `PAYMENT` — $33{,}81\%$ tổng số cạnh. Xoá chúng đi là xoá mất đúng những hub mà Task 2 đi tìm.

---

### 3.3.5 — Bước 5: Teleportation, Google matrix và điều kiện hội tụ

Bước trọng tâm thứ hai. Mục tiêu: từ $S$ (stochastic nhưng có thể reducible) dựng một ma trận mà power iteration **chắc chắn** hội tụ về **một** nghiệm **duy nhất** từ **mọi** khởi tạo.

#### 3.3.5.1 Primitivity adjustment $S \to G$

Thêm hành vi thứ hai: ở **mỗi bước**, với xác suất $1-d$, walker **bỏ qua cấu trúc link** và nhảy tới một node ngẫu nhiên đều. Đó là **teleportation**.

$$\boxed{\;G \;=\; d\,S \;+\; (1-d)\,\frac{1}{N}\,J\;}, \qquad J = \mathbf{e}\mathbf{e}^{T},\qquad 0 < d < 1 .$$

$G$ gọi là **Google matrix**, với $G_{uv} = d\,S_{uv} + \frac{1-d}{N}$. Dạng tổng quát: $G = dS + (1-d)\mathbf{v}\mathbf{e}^{T}$. Chọn $\mathbf{v}$ tập trung vào một node cho **personalized PageRank** — chính là tham số `sourceId` của GraphFrames.

> **Ràng buộc $0 < d < 1$ là CHẶT.** Tại $d = 1$ ta có $G = S$: vẫn stochastic nhưng *"most likely reducible"*, khi đó có thể **dao động vĩnh viễn** (closed class tuần hoàn), **toàn bộ mass bị hấp thụ vào một absorbing state**, hoặc **nghiệm không duy nhất**. Ở đầu kia, $d \to 0$ làm $\mathbf{r} \to \frac1N\mathbf{e}$, mất hết sức phân biệt. **Toàn bộ tác dụng của damping nằm ở chỗ $1-d > 0$.**

#### 3.3.5.2 Bốn tính chất của $G$

**(1) Column-stochastic.** $G$ là **tổ hợp lồi** của hai ma trận column-stochastic với trọng số $d$ và $1-d$: $\sum_u G_{uv} = d\cdot 1 + (1-d)\cdot 1 = 1$. Do đó theo (P1), $\rho(G) = 1$ và $1$ là eigenvalue.

**(2) Irreducible.** Vì $G_{uv} > 0$ với **mọi** cặp, mọi node đi tới được mọi node trong đúng một bước — vấn đề 3 được giải quyết.

**(3) Aperiodic.** **Period** của state $u$ là $\gcd\{n\ge 1 : (G^n)_{uu} > 0\}$. Ở đây $G_{uu} \ge \frac{1-d}{N} > 0$ nên $\gcd = 1$.

> **Mâu thuẫn biểu kiến phải xử lý dứt điểm.** Nhóm đo được PaySim có **self-loop $= 0$**. Điều đó đúng cho $M$ và $S$ (đường chéo bằng 0), nhưng **sai hoàn toàn cho $G$**: chính teleportation tạo ra self-loop nhân tạo $G_{uu} \ge (1-d)/N > 0$, và đó mới là nguồn gốc tính aperiodic. Viết "PaySim không có self-loop" rồi vẫn dùng lập luận aperiodicity là **mâu thuẫn logic**.

**(4) Primitive.** Theo **tiêu chuẩn Frobenius** (*"$A \ge 0$ is primitive if and only if $A^{m} > 0$ for some $m > 0$"*), vì $G_{uv} \ge \frac{1-d}{N} > 0$ nên $G > 0$ và tiêu chuẩn thoả với $m = 1$.

Quan hệ: **primitive $\iff$ irreducible + aperiodic**. (4) bao hàm (2) và (3); tách ra để thấy **tính chất nào giải quyết vấn đề nào**.

#### 3.3.5.3 Perron–Frobenius — phát biểu chính xác

Phải phân biệt **hai** bản của định lý:

**Bản cho ma trận IRREDUCIBLE.** Nếu $A \ge 0$ irreducible thì (i) $\rho(A)$ là eigenvalue và $\rho(A) > 0$; (ii) tồn tại eigenvector **dương** ứng $\rho(A)$; (iii) $\rho(A)$ là eigenvalue **đơn**; **(iv) NHƯNG** các eigenvalue khác **vẫn có thể** nằm trên **spectral circle**.

**Bản cho ma trận PRIMITIVE.** Thêm giả thiết primitive thì (i)–(iii) giữ nguyên **và (iv')** $\lvert\lambda\rvert < \rho(A)$ **ngặt** với mọi $\lambda \neq \rho(A)$.

Khác biệt ở (iv)/(iv') chính là toàn bộ vấn đề: **irreducible thôi chưa loại được tính tuần hoàn.** Áp dụng cho $G$ (vì $G > 0$) kết hợp tính column-stochastic:

$$\boxed{\;\exists!\; \mathbf{r} > 0,\; \lVert\mathbf{r}\rVert_1 = 1: \; G\mathbf{r} = \mathbf{r}, \quad \text{và } \lvert\lambda\rvert < 1 \text{ với mọi } \lambda \neq 1.\;}$$

> $\rho(G) = 1$ đến từ **stochasticity**; tính **đơn** và bất đẳng thức ngặt $\lvert\lambda_2\rvert < 1$ đến từ **primitivity**.

**Tồn tại/duy nhất KHÁC hội tụ** — đây là điểm quan trọng về độ chặt toán học. Chain hữu hạn **irreducible** đã đủ cho **tồn tại + duy nhất**; cần thêm **aperiodic** mới có **hội tụ từ mọi khởi tạo**. Langville & Meyer (2004) chia vai trò rất rõ: *"The irreducibility … guarantees the existence of the unique stationary distribution vector … Convergence of the PageRank power method is governed by the primitivity."*

**Phản ví dụ chứng minh irreducible KHÔNG đủ:** $P = \begin{pmatrix}0&1\\1&0\end{pmatrix}$ có $\operatorname{spec}(P) = \{1,-1\}$. Chain này **irreducible hoàn toàn**, stationary distribution $(1/2,1/2)$ **tồn tại và duy nhất**, nhưng khởi tạo $(1,0)$ cho dãy $(1,0)\to(0,1)\to(1,0)\to\cdots$ **dao động vĩnh viễn**. Nguyên nhân: period $= 2$, và eigenvalue $-1$ nằm trên đường tròn đơn vị — đúng trường hợp (iv) mà bản irreducible **không** loại được.

#### 3.3.5.4 Tốc độ hội tụ

**(A) $G$ là ánh xạ co hệ số $d$ — chứng minh hai dòng, KHÔNG cần giả thiết nào.** Lấy $\mathbf{x},\mathbf{y}$ **cùng tổng**, đặt $\mathbf{z} = \mathbf{x}-\mathbf{y}$ thì $\mathbf{e}^{T}\mathbf{z} = 0$, nên số hạng teleportation **triệt tiêu**: $G\mathbf{z} = dS\mathbf{z}$. Vì $S$ column-stochastic nên $\lVert S\mathbf{z}\rVert_1 \le \lVert\mathbf{z}\rVert_1$, do đó $\lVert G\mathbf{x}-G\mathbf{y}\rVert_1 \le d\lVert\mathbf{x}-\mathbf{y}\rVert_1$. Lặp $t$ lần với $\lVert\mathbf{r}^{(0)}-\mathbf{r}^{*}\rVert_1 \le 2$:

$$\boxed{\;\lVert\mathbf{r}^{(t)} - \mathbf{r}^{*}\rVert_1 \;\le\; 2\,d^{\,t}\;}$$

Đây là cận **tuyệt đối, vô điều kiện**, không cần Perron–Frobenius, không cần giả thiết chéo hoá được — và nó cũng cho ngay tồn tại + duy nhất + hội tụ qua nguyên lý ánh xạ co. Con số dùng cho Task 2: $\lVert\mathbf{r}^{(10)}-\mathbf{r}^{*}\rVert_1 \le 2\times 0{,}85^{10} = 0{,}394$.

**(B) Tốc độ tiệm cận.** Nếu $G$ chéo hoá được, khai triển $\mathbf{r}^{(0)} = \sum_i c_i\mathbf{x}_i$ cho $G^{t}\mathbf{r}^{(0)} = c_1\mathbf{r}^{*} + O(\lvert\lambda_2\rvert^{t})$ — sai số tắt theo cấp số nhân với công bội $\lvert\lambda_2\rvert$. **Định lý phổ của Google matrix:** nếu $\operatorname{spec}(S) = \{1,\lambda_2,\dots\}$ thì $\operatorname{spec}(G) = \{1, d\lambda_2, \dots\}$, hệ quả

$$\boxed{\;\lvert\lambda_2(G)\rvert \;\le\; d \;=\; 0{,}85\;}$$

> **Quy công cho đúng người:** **cận** $\lvert\lambda_2(G)\rvert \le d$ là **Haveliwala & Kamvar (2003), Theorem 1**; **đẳng thức từng eigenvalue** $\operatorname{spec}(G) = \{1, d\lambda_2,\dots\}$ là **Langville & Meyer (2004), Theorem 5.1**. Không được gán đẳng thức phổ cho Haveliwala & Kamvar. Và bất đẳng thức này **không** phải của Page et al. (1999) — bản 1999 §4 chỉ lập luận về expander graph và rapid mixing.

> **Không được khẳng định $\lvert\lambda_2(G)\rvert = 0{,}85$ cho PaySim nếu chưa kiểm.** Sau khi vá dangling, $S$ của PaySim có thể **đã** primitive. Phát biểu luôn đúng: *"$\lvert\lambda_2(G)\rvert \le d = 0{,}85$, nên sai số giảm không chậm hơn $0{,}85^{t}$"* — cận (A) cho điều này vô điều kiện.

**Số vòng lặp cần** (Langville & Meyer 2004, §5.1.1), với $t \approx \log_{10}\varepsilon/\log_{10}d$ và $\log_{10}0{,}85 = -0{,}07058$:

| tolerance $\varepsilon$ | giá trị chính xác | làm tròn LÊN | L&M ghi |
|---|---|---|---|
| $10^{-6}$ | $85{,}009$ | $86$ | *"roughly 85 iterations"* |
| $10^{-8}$ | $113{,}345$ | $114$ | *"about 114 iterations"* |
| $10^{-10}$ | $141{,}681$ | $142$ | *"about 142 iterations"* |

Ngược lại với $t = 10$: $0{,}85^{10} = 0{,}1969$, tức $\tau \approx 0{,}71$ — **sau 10 vòng chưa được một chữ số thập phân chính xác**. Đối chiếu: Langville & Meyer (2006) viết *"$.85^{50} \approx .000296$, which implies that at the 50th iteration one can expect roughly 2-3 places of accuracy"*; Page et al. (1999) §4 báo cáo *"converges to a reasonable tolerance in roughly 52 iterations"* trên 322 triệu link. **Đây là luận cứ định lượng cho cảnh báo (2) ở §3.3.12.**

---

### 3.3.6 — Bước 6: Công thức cuối

#### 3.3.6.1 Dẫn ra dạng thành phần

Viết $\mathbf{r} = G\mathbf{r}$ ra từng thành phần với $G = dS + (1-d)\frac1N J$ và $S = M + \frac1N\mathbf{e}\mathbf{a}^{T}$, rồi dùng $\sum_v r(v) = 1$ cho số hạng teleportation:

$$r(u) \;=\; \underbrace{\frac{1-d}{N}}_{\text{teleportation}} \;+\; d\Bigg[\underbrace{\sum_{v:\,d_{out}(v)>0} \frac{A_{vu}\,r(v)}{d_{out}(v)}}_{\text{link-following}} \;+\; \underbrace{\frac{1}{N}\sum_{v\in D} r(v)}_{\text{dangling-mass redistribution}}\Bigg].$$

Ở dạng lặp — **đây là công thức cuối của Mục 3.3**:

$$\boxed{\;r^{(t+1)}(u) \;=\; \frac{1-d}{N} \;+\; d\left[\;\sum_{v:\,d_{out}(v)>0} \frac{A_{vu}\,r^{(t)}(v)}{d_{out}(v)} \;+\; \frac{1}{N}\sum_{v\in D} r^{(t)}(v)\right], \qquad d = 0{,}85\;}$$

> **Bổ sung một bước còn thiếu trong lập luận.** Bước rút gọn số hạng teleportation dùng $\lVert\mathbf{r}^{(t)}\rVert_1 = 1$. Với **dạng LẶP**, đẳng thức đó phải đúng ở **mọi** $t$, và điều này hợp lệ theo **quy nạp**: cơ sở là $\lVert\mathbf{r}^{(0)}\rVert_1 = 1$, bước quy nạp chính là chứng minh ở §3.3.6.2. Lập luận **không** vòng tròn, nhưng thiếu câu này thì trông như vòng tròn.

Số hạng thứ ba là công thức hoá của **Langville & Meyer (2004), §5.1 equation (1)**, trong đó tích vô hướng $\mathbf{x}^{(k-1)T}\mathbf{a}$ **chính là** tổng dangling mass.

#### 3.3.6.2 Chứng minh bảo toàn tổng

$$\begin{aligned}
\sum_u r^{(t+1)}(u) &\;=\; (1-d) + d\left[\sum_{v\notin D} r^{(t)}(v)\underbrace{\sum_u \frac{A_{vu}}{d_{out}(v)}}_{=\,1} + \underbrace{\sum_u \frac{1}{N}}_{=\,1}\sum_{v\in D} r^{(t)}(v)\right]\\
&\;=\; (1-d) + d\left[\sum_{v\notin D} r^{(t)}(v) + \sum_{v\in D} r^{(t)}(v)\right] \;=\; (1-d) + d \;=\; 1 .\qquad\blacksquare
\end{aligned}$$

**Tổng được bảo toàn bằng đúng 1 ở mọi vòng.** Nếu **bỏ** số hạng dangling thì

$$\sum_u \tilde{r}^{(t+1)}(u) \;=\; 1 - d\sum_{v\in D} r^{(t)}(v) \;<\; 1 .$$

> **Đừng ngoại suy sai.** Công thức chỉ nói tổng **nhỏ hơn 1**; nó **KHÔNG** nói tổng tụt dần về 0. Phép lặp rút gọn $\tilde{\mathbf{r}}^{(t+1)} = \frac{1-d}{N}\mathbf{e} + dM\tilde{\mathbf{r}}^{(t)}$ là một **affine iteration** với $\rho(dM) \le d < 1$, nên nó **hội tụ về một điểm bất động DƯƠNG duy nhất** và tổng **ổn định ở một hằng số $< 1$**. Số liệu ở §3.3.9.1.

#### 3.3.6.3 Dạng rút gọn của đề bài là trường hợp riêng

Đề bài yêu cầu dẫn ra $PR(u) = \frac{1-d}{N} + d\sum_{v\in B(u)}\frac{PR(v)}{L(v)}$. Dạng này thu được từ dạng đầy đủ bằng **đúng hai giả thiết**:

1. **$D = \varnothing$** — không có dangling node. Khi đó số hạng $\frac1N\sum_{v\in D}r(v)$ biến mất (tổng rỗng bằng 0).
2. **Không có parallel edges** — $A_{vu} \in \{0,1\}$, nên tổng link rút về $\sum_{v\in B(u)}\frac{r(v)}{L(v)}$.

**PaySim vi phạm ÍT NHẤT giả thiết thứ nhất, và hai giả thiết KHÔNG ngang hàng:**

- **Giả thiết 1 bị vi phạm chắc chắn, quy mô lớn:** $\lvert D\rvert = 2\,720\,593$ (\*), tức $29{,}98\%$ graph. Riêng toàn bộ Merchant có out-degree $= 0$ tuyệt đối, hấp thụ $2\,151\,495$ giao dịch `PAYMENT` ($33{,}81\%$ tổng cạnh). Số đo trực tiếp.
- **Giả thiết 2 chỉ có thể bị vi phạm ở quy mô không đáng kể.** **Max out-degree $= 3$ KHÔNG suy ra sự tồn tại của parallel edges** — ba cạnh đó có thể tới ba đích phân biệt. Trần chặt: số cạnh dôi ra nhiều nhất là $6\,362\,620 - 6\,353\,307 = 9\,313$ (\*), tức $0{,}146\%$ tổng cạnh.

> **Không xếp hai cái này ngang hàng bằng câu "PaySim vi phạm cả hai giả thiết".** Một cái vi phạm ở $29{,}98\%$ số node; cái kia **nếu** vi phạm thì tối đa $0{,}146\%$ số cạnh.

> **Kết luận của Mục 3.3:** dạng rút gọn chỉ hợp lệ trên graph không có sink node và không có parallel edges. **Trên PaySim, dạng rút gọn cho một vector KHÔNG PHẢI phân phối xác suất** — tổng hội tụ về một hằng số $< 1$ — nên Mục 3.3 **dùng dạng đầy đủ**.
>
> **Ba lý do ĐÚNG để dùng dạng đầy đủ:** (1) giữ $\lVert\mathbf{r}^{(t)}\rVert_1 = 1$ ở mọi vòng nên **residual có nghĩa làm tiêu chí dừng**; (2) giá trị đọc được **trực tiếp là xác suất**; (3) ở `maxIter` hữu hạn nhỏ, hai dãy lặp **không** trùng nhau kể cả sau chuẩn hoá — sự trùng nhau chỉ xảy ra **tại fixed point** (§3.3.6.4).

#### 3.3.6.4 Mệnh đề tỉ lệ — cái mất đi là CHUẨN HOÁ, không phải THỨ HẠNG

> **Mệnh đề.** Gọi $\mathbf{r}$ là nghiệm dừng dạng **đầy đủ**, $\tilde{\mathbf{r}}$ là nghiệm dừng dạng **rút gọn**. Khi đó với **mọi** graph: $\mathbf{r} \parallel \tilde{\mathbf{r}}$ và $\mathbf{r} = \tilde{\mathbf{r}}/\lVert\tilde{\mathbf{r}}\rVert_1$.

**Chứng minh.** $M$ substochastic nên theo (P2), $\rho(dM) \le d < 1$, do đó $(I-dM)$ khả nghịch. Dạng rút gọn cho $\tilde{\mathbf{r}} = \frac{1-d}{N}(I-dM)^{-1}\mathbf{e}$. Dạng đầy đủ cho $(I-dM)\mathbf{r} = \frac{\kappa}{N}\mathbf{e}$ với $\kappa = (1-d) + d\sum_{v\in D}r(v) > 0$, tức $\mathbf{r} = \frac{\kappa}{N}(I-dM)^{-1}\mathbf{e}$. Hai vector cùng là bội vô hướng **dương** của cùng một vector, nên **luôn cùng phương**. $\blacksquare$

**Ba hệ quả dùng trực tiếp:**

- **(H1)** Tại fixed point, **thứ hạng hai dạng TRÙNG KHÍT**. Task 2 chỉ cần top-10 hub — một bài toán **thứ hạng** — nên thiếu số hạng dangling **không** làm hỏng kết quả ở điểm dừng. Cái hỏng là **giá trị tuyệt đối**.
- **(H2)** Đây là chứng minh sạch cho khẳng định "rescale một lần ở cuối tương đương tái-phân-phối mỗi vòng, **tại** fixed point" (§3.3.11).
- **(H3)** Tương đương **chỉ đúng tại fixed point**. Ở `maxIter` hữu hạn nhỏ hai dãy khác nhau. *(Ngoại lệ: nếu $M$ **nilpotent** bậc $K \le$ `maxIter` thì cả hai đã đứng yên đúng tại fixed point.)*

**Khai triển Neumann.** Vì $\rho(dM) < 1$, $(I-dM)^{-1} = \sum_{k\ge0}(dM)^k$, do đó

$$\tilde{\mathbf{r}} \;=\; \frac{1-d}{N}\sum_{k\ge 0} d^{k}\,M^{k}\,\mathbf{e}.$$

**Đọc bằng lời:** *PageRank của $u$ là tổng có chiết khấu của **mọi** đường đi theo link kết thúc tại $u$, đường đi độ dài $k$ mang trọng số $d^{k}$.* Đây là **chứng minh đại số cho cơ chế (iv) ở §3.3.7** — trọng số $d^k$ chính là xác suất walker chưa teleport sau $k$ bước. Và **nếu $M$ nilpotent bậc $K$ thì chuỗi HỮU HẠN**, phép lặp rút gọn cho **chính xác** điểm bất động sau đúng $K$ vòng.

---

### 3.3.7 — Damping factor chống sink node trapping như thế nào

Đề bài viết nguyên văn: *"Explain how the damping factor ($d = 0.85$) prevents sink node trapping."*

#### 3.3.7.1 Bốn cơ chế, mỗi cơ chế một công thức

**(i) Lower bound dương — không node nào bị rút về 0.** Mọi số hạng trong ngoặc của công thức cuối đều không âm, nên

$$\boxed{\;r^{(t+1)}(u) \;\ge\; \frac{1-d}{N} \;=\; \frac{0{,}15}{N} \;>\; 0 \qquad \forall u \in V,\; \forall t\;}$$

Đúng **kể cả** với node không có một in-link nào — trên PaySim là $6\,351\,538$ node (\*), $70{,}00\%$ graph. Hệ quả cho Task 2: **mọi tài khoản đều có điểm dương để xếp hạng**. Lower bound này **chặt**: ví dụ 2 ở §3.3.9.2 có $r(A) = 0{,}05$ **đúng bằng** $(1-d)/N$.

**(ii) Upper bound cho mọi cụm — không cụm nào giữ được toàn bộ phân phối.** Cộng $\mathbf{r} = G\mathbf{r}$ trên $u \in C$:

$$\sum_{u\in C} r(u) \;=\; d\sum_{v} r(v)\underbrace{\sum_{u\in C} S_{uv}}_{\le\,1} \;+\; (1-d)\frac{\lvert C\rvert}{N},$$

nên với mọi tập con **thực sự** $C \subsetneq V$ (khi đó $\lvert C\rvert \le N-1$):

$$\boxed{\;\sum_{u\in C} r(u) \;\le\; d \;+\; (1-d)\frac{\lvert C\rvert}{N} \;\le\; 1 - \frac{1-d}{N} \;<\; 1\;}$$

*(Với $C = V$ thì $d + (1-d) = 1$ — đạt dấu bằng, đúng như phải thế. Viết "$<1$ với mọi $C \subseteq V$" là sai ở đúng một điểm biên, và người review sẽ bắt.)*

**Ý nghĩa:** dù $C$ là một **absorbing class** đóng hoàn toàn dưới $S$ — mọi mass vào rồi không bao giờ ra — nó **vẫn** không giữ quá $d + (1-d)\lvert C\rvert/N$. Phần bù luôn giữ được ít nhất $(1-d)\lvert V\setminus C\rvert/N > 0$. **Đây chính là dạng định lượng của tính chất chống trapping.**

**(iii) Ép $G$ primitive, biến phép lặp thành ánh xạ co.** $G > 0$ nên vừa irreducible vừa aperiodic; Perron–Frobenius cho $\mathbf{r}^{*} > 0$ duy nhất và hội tụ từ mọi khởi tạo; cận co cho $\lVert\mathbf{r}^{(t)}-\mathbf{r}^{*}\rVert_1 \le 2d^{\,t} \to 0$, **không cần giả thiết gì về graph**. Không có damping ($d = 1$) thì hệ số co bằng 1 và lập luận không còn hiệu lực.

**(iv) Theo ngôn ngữ random surfer — thời gian kẹt hữu hạn với xác suất 1.** Gọi $T$ = số node walker ghé thăm trong một chặng đi theo link, tính cả node xuất phát. $T$ là biến **geometric** trên $\{1,2,\dots\}$ tham số $1-d$:

$$\Pr[T = k] = d^{\,k-1}(1-d),\qquad \mathbb{E}[T] = \frac{1}{1-d} \approx 6{,}67,\qquad \Pr[T > k] = 0{,}85^{k}.$$

Đuôi tắt theo cấp số nhân, nên **xác suất walker ở lại vĩnh viễn trong bất kỳ cụm nào bằng 0**.

> **Dùng đúng thuật ngữ xác suất:** $1/(1-d) \approx 6{,}67$ là **KỲ VỌNG**, không phải **cận trên**. Biến geometric **không bị chặn trên**. Viết "thời gian kẹt bị chặn trên bởi 6,67" là sai.

Molloy et al. (2016) diễn giải damping theo ngôn ngữ tài chính, dùng được trực tiếp cho PaySim: *"In financial transactions, the damping factor can be used to model an account saving."* Tức $1-d$ là xác suất một đồng tiền **dừng lại và được giữ** thay vì tiếp tục lưu thông.

#### 3.3.7.2 Ba kịch bản khi KHÔNG có damping

Chữ "trapping" che ba cấu hình khác nhau:

- **(a) Sink không self-loop ($d_{out}=0$) — mass RÒ RỈ khỏi hệ.** Cột sink toàn 0 nên mass đang nằm trên sink **biến mất khỏi vector**; tổng giảm đơn điệu về 0. → **Ví dụ 1, §3.3.9.1.**
- **(b) Sink CÓ self-loop — một absorbing state thật, mass bị GIỮ LẠI chứ không leakage.** Ma trận vẫn stochastic (tổng luôn $=1$), nhưng sink hút **toàn bộ** mass; mọi node khác về 0. Đây là cấu hình khớp **sát chữ nhất** với cụm từ của đề bài. → **Ví dụ 2, §3.3.9.2.**
- **(c) Cụm đóng nhiều node (spider trap) — tổng vẫn bằng 1 nhưng dồn hết vào cụm**, và nếu cụm tuần hoàn thì dãy lặp còn **không hội tụ**.

Damping xử lý cả ba theo đúng một cách: cộng $\frac{1-d}{N} > 0$ vào **mọi** phần tử ma trận, phá mọi cấu trúc đóng và mọi chu kỳ cùng lúc.

#### 3.3.7.3 Sắc thái bắt buộc: damping xử lý trapping, không xử lý leakage

> Damping factor **một mình không** giải quyết được sink node. Nó chữa phần **trapping** (cơ chế ii, iii). Phần **leakage** — mass thoát **ra khỏi hệ** do out-degree $= 0$ — phải chữa bằng **stochasticity adjustment**, tương ứng số hạng $\frac{d}{N}\sum_{v\in D}r^{(t)}(v)$. Cả hai bắt buộc, và **phải đúng thứ tự** (§3.3.4.3).

**Câu hoà giải giữa cách đề bài đóng khung và cách mục này phân tích.** Đề bài nói tới **một** cơ chế; mục này phân tích **hai** cách giải quyết. Không mâu thuẫn, vì cả hai dùng **CÙNG một teleportation vector** $\mathbf{v} = \frac1N\mathbf{e}$:

| | Điều kiện kích hoạt | Xác suất teleport | Giải quyết vấn đề nào |
|---|---|---|---|
| **stochasticity adjustment** | khi đang đứng **ở một sink** | $1$ (chắc chắn) | **leakage** — mass thoát khỏi hệ |
| **primitivity adjustment** (damping) | ở **mọi** node, mọi bước | $1-d = 0{,}15$ | **trapping** — mass bị giữ lại vĩnh viễn trong cụm |

Nhìn theo bảng này thì chỉ có **một** cơ chế duy nhất — *teleport về $\mathbf{v}$* — với hai luật kích hoạt. Đó là lý do Google matrix gộp được cả hai vào một công thức rank-one duy nhất.

---

### 3.3.8 — Vì sao $d = 0{,}85$

**Trung thực về những gì nguồn KHÔNG nói.** Toàn bộ những gì **Brin & Page (1998)** §2.1.1 nói về giá trị của $d$ là **một câu**:

> "The parameter $d$ is a damping factor which can be set between 0 and 1. We usually set $d$ to 0.85."

**Không có** thực nghiệm dò giá trị, **không có** bảng so sánh, **không có** phân tích hội tụ theo $d$. **Page et al. (1999)** thậm chí **không viết con số 0.85** ở đâu trong thân bài; tương đương gần nhất là §6: *"an $E$ vector that is uniform over all web pages with $\lVert E\rVert_1 = 0.15$"*.

> **Không được viết "các tác giả chọn $d = 0{,}85$ sau khi thực nghiệm".** Cách viết đúng: *"0,85 là giá trị mặc định do chính tác giả công bố và được cộng đồng chấp nhận như quy ước, không kèm chứng minh tối ưu."* Cũng không viết "Google hiện vẫn dùng $d = 0{,}85$" — Langville & Meyer (2006) viết thận trọng *"at last report, this is still the value used by Google"*, thông tin tính đến 2006.

**Đánh đổi.**

- **$d$ lớn (gần 1):** bám cấu trúc link thật hơn, đường đi dài được cân nặng hơn (theo chuỗi Neumann). **Nhưng** hệ số co $d \to 1$ và $\lvert\lambda_2(G)\rvert \to 1$: hội tụ chậm dần, chi phí tăng vọt; **và** vector PageRank trở nên **nhạy cảm** với thay đổi nhỏ của graph.
- **$d$ nhỏ:** hội tụ nhanh, ổn định số tốt. **Nhưng** mass được rải đều bất kể cấu trúc; ở cực hạn $d \to 0$, $\mathbf{r}\to\frac1N\mathbf{e}$ — **mọi node điểm bằng nhau, mất hết sức phân biệt**.

Số liệu là **Table 5.1 của Langville & Meyer (2006)**, *"Effect of $\alpha$ on expected number of power iterations"* ở tolerance $10^{-10}$:

| $d$ | 0,50 | 0,75 | 0,80 | **0,85** | 0,90 | 0,95 | 0,99 | 0,999 |
|---|---|---|---|---|---|---|---|---|
| số vòng lặp | 34 | 81 | 104 | **142** | 219 | 449 | 2.292 | 23.015 |

**Đọc thành mệnh đề định lượng.** Hàm $t(d) = -\tau/\log_{10}d$ **trơn và lồi**, **không có điểm gãy** tại $0{,}85$. Câu đúng: chi phí lặp **tăng đơn điệu và tăng tốc khi $d\to1$** — $+54\%$ khi lên $0{,}90$, gấp $3{,}16$ lần khi lên $0{,}95$, gấp $162$ lần khi lên $0{,}999$. $0{,}85$ là **giá trị mặc định do tác giả công bố**; các con số cho thấy **cái giá phải trả** nếu đẩy $d$ cao hơn, chứ không chứng minh $0{,}85$ là tối ưu.

Boldi, Santini & Vigna (2005) còn cho thấy — *"contradicting the common beliefs"* — trên graph thực, $d$ gần 1 **không** cho ranking có ý nghĩa hơn.

**Quy đổi sang tham số Task 2:** `resetProbability` $= 1-d = 0{,}15 \iff d = 0{,}85$.

> **`resetProbability = 0.15` KHÔNG có nghĩa "15% giao dịch là fraud".** Nó là xác suất teleport của random surfer, thuần tuý tham số mô hình.

---

### 3.3.9 — Hai ví dụ tính tay

Hai ví dụ chứng minh hai mệnh đề khác nhau; mọi con số đã được dựng lại độc lập bằng số học phân số chính xác.

#### 3.3.9.1 Ví dụ 1 — vì sao cần số hạng dangling

**Thiết lập.** $V = \{A,B,C,T\}$, 5 cạnh: $A\to B$, $A\to T$, $B\to T$, $C\to A$, $C\to B$.

| Node | $d_{out}$ | $B(u)$ | in-degree |
|---|---|---|---|
| $A$ | 2 | $\{C\}$ | 1 |
| $B$ | 1 | $\{A,C\}$ | 2 |
| $C$ | **2** | $\varnothing$ | **0** |
| $T$ | **0** | $\{A,B\}$ | 2 |

$T$ là **sink node**, $D = \{T\}$ — **toy model** của Merchant trong PaySim. $C$ **không có in-link nào** — toy model của $70{,}00\%$ tài khoản PaySim. Tham số: $N = 4$, $d = 0{,}85$, $\frac{1-d}{N} = 0{,}0375$, khởi tạo uniform $\mathbf{r}^{(0)} = (0{,}25;0{,}25;0{,}25;0{,}25)$.

$$M = \begin{pmatrix} 0&0&\tfrac12&0\\ \tfrac12&0&\tfrac12&0\\ 0&0&0&0\\ \tfrac12&1&0&0\end{pmatrix} \text{ tổng cột } (1,1,1,\mathbf{0}) \Rightarrow \text{substochastic}, \qquad S = \begin{pmatrix} 0&0&\tfrac12&\tfrac14\\ \tfrac12&0&\tfrac12&\tfrac14\\ 0&0&0&\tfrac14\\ \tfrac12&1&0&\tfrac14\end{pmatrix} \Rightarrow \text{stochastic.}\checkmark$$

**$S$ là PRIMITIVE, không chỉ irreducible.** Self-loop nhân tạo $S_{TT} = \frac14 > 0$ làm $S$ vừa irreducible vừa aperiodic. Kiểm bằng tiêu chuẩn Frobenius: **$S^{3} > 0$ theo từng phần tử** (phần tử nhỏ nhất bằng $0{,}0625$; $S^{2}$ còn đúng 2 phần tử bằng 0, nên $k = 3$ là số mũ nhỏ nhất).

> **Đây cũng là phản ví dụ cho suy luận ở §3.3.4.2.** Ở đây $C$ không in-link và $T$ dangling, vậy mà sau stochasticity adjustment $S$ lại **primitive**. Nghĩa là: "có node không in-link" **không** suy ra "$S$ reducible" — suy luận đó chỉ đúng cho $M$.

**Vòng lặp 1, dạng ĐẦY ĐỦ.** Dangling mass $= r^{(0)}(T) = 0{,}25$; số hạng phân phối lại $= 0{,}25/4 = 0{,}0625$ (giống nhau cho mọi node). Luồng link: $A\leftarrow 0{,}125$; $B\leftarrow 0{,}25$; $C\leftarrow 0$; $T\leftarrow 0{,}375$. Áp $r^{(1)}(u) = 0{,}0375 + 0{,}85[\text{link} + 0{,}0625]$:

| | $r^{(1)}(A)$ | $r^{(1)}(B)$ | $r^{(1)}(C)$ | $r^{(1)}(T)$ | **tổng** |
|---|---|---|---|---|---|
| **đầy đủ** | $0{,}196875$ | $0{,}303125$ | $0{,}090625$ | $0{,}409375$ | **$1{,}000000$** ✓ |
| **rút gọn** | $0{,}143750$ | $0{,}250000$ | $0{,}037500$ | $0{,}356250$ | **$0{,}787500$** ✗ |

**Ngay vòng đầu tiên, dạng rút gọn đã hụt $0{,}2125 = d \times 0{,}25$** — đúng bằng $d\times$(mass trên tập sink), khớp công thức §3.3.6.2.

**Chạy tới điểm dừng.** Dạng đầy đủ hội tụ về $\mathbf{r}^{*} = (0{,}182991;\,0{,}260762;\,0{,}128415;\,0{,}427833)$, tổng $= 1$. Dạng rút gọn hội tụ về $\tilde{\mathbf{r}}^{*} = (0{,}053437;\,0{,}076148;\,0{,}037500;\,0{,}124937)$, tổng **ổn định ở $0{,}292023$** — **không** tụt về 0, đúng như cảnh báo ở §3.3.6.2. Chuẩn hoá $\tilde{\mathbf{r}}^{*}/0{,}292023$ cho **đúng** $\mathbf{r}^{*}$ — **xác nhận bằng số Mệnh đề tỉ lệ §3.3.6.4.**

**Kiểm chứng tính nilpotent:** $M^{4} = 0$ trong khi $M^{3} \neq 0$, nên chuỗi Neumann hữu hạn và dãy rút gọn đứng yên **chính xác** từ $t = 4$.

#### 3.3.9.2 Ví dụ 2 — bằng chứng số cho đúng cụm từ "sink node trapping"

**Vì sao cần ví dụ này.** Đề bài hỏi đích danh *"how the damping factor prevents **sink node trapping**"*. Cấu hình khớp **sát chữ** nhất — **một node sink GIỮ LẠI mass thay vì để xảy ra leakage, tức một absorbing state** — là cấu hình dưới đây.

**Thiết lập.** $V = \{A,B,T\}$, 3 cạnh: $A\to B$, $B\to T$, $T\to T$ (self-loop). Mọi node có $d_{out} = 1$, nên **$D = \varnothing$** và $S = M$ — **mọi hiệu ứng quan sát được là thuần tuý do damping**.

$$M = S = \begin{pmatrix} 0&0&0\\ 1&0&0\\ 0&1&1\end{pmatrix}, \qquad \text{tổng cột }(1,1,1)\Rightarrow\text{column-stochastic.}\checkmark$$

$\{T\}$ là một closed class một phần tử — một **absorbing state** thật. $S$ reducible, $\operatorname{spec}(S) = \{1;0;0\}$. *(Closed class ở đây **aperiodic** nên $\lvert\lambda_2(S)\rvert = 0 < 1$ và dãy lặp **có** hội tụ — đúng trường hợp §3.3.5.4 cảnh báo: "reducible" **không** kéo theo $\lvert\lambda_2\rvert = 1$.)*

**Với $d = 1$:** $\mathbf{r}^{*} = (0;\,0;\,\mathbf{1})$. Tổng **vẫn bằng 1** — đây **không** phải leakage. Nhưng $r(A) = r(B) = \mathbf{0}$: **hai phần ba số node biến mất hoàn toàn khỏi bảng xếp hạng.** Đây chính xác là "sink node trapping" theo nghĩa đen.

**Với $d = 0{,}85$** ($\frac{1-d}{N} = 0{,}05$), từ khởi tạo uniform:

| $t$ | $r(A)$ | $r(B)$ | $r(T)$ | tổng |
|---|---|---|---|---|
| 0 | $0{,}333333$ | $0{,}333333$ | $0{,}333333$ | $1{,}000000$ |
| 1 | $\mathbf{0{,}050000}$ | $0{,}333333$ | $0{,}616667$ | $1{,}000000$ ✓ |
| 2 | $\mathbf{0{,}050000}$ | $\mathbf{0{,}092500}$ | $\mathbf{0{,}857500}$ | $1{,}000000$ ✓ |
| 3 | $\mathbf{0{,}050000}$ | $\mathbf{0{,}092500}$ | $\mathbf{0{,}857500}$ | $1{,}000000$ ✓ |

Dãy **đứng yên chính xác từ $t = 2$** vì $\operatorname{spec}(G) = \{1;0;0\}$. Nghiệm dừng dạng phân số chính xác:

$$\mathbf{r}^{*} \;=\; \left(\tfrac{1}{20};\ \tfrac{37}{400};\ \tfrac{343}{400}\right) \;=\; (0{,}0500;\ 0{,}0925;\ 0{,}8575), \qquad \lVert\mathbf{r}^{*}\rVert_1 = 1 .$$

*(Kiểm tay: $r(A) = \frac{1-d}{N} = 0{,}05$ vì $A$ không in-link; $r(B) = 0{,}05 + 0{,}85\times0{,}05 = 0{,}0925$; kiểm ngược $r(T) = 0{,}05 + 0{,}85\times(0{,}0925+0{,}8575) = 0{,}8575$ ✓.)*

**Đặt cạnh nhau — đây là câu trả lời số cho đề bài:**

| | $d = 1$ | $d = 0{,}85$ | Cơ chế |
|---|---|---|---|
| $r(A)$ — node đầu chuỗi, không in-link | $\mathbf{0}$ | $\mathbf{0{,}0500} = \frac{1-d}{N}$ — **đúng lower bound** | (i) |
| $r(B)$ | $\mathbf{0}$ | $\mathbf{0{,}0925} > 0$ | (i) |
| $r(T)$ — absorbing state | $\mathbf{1{,}0000}$ — hấp thụ toàn bộ | $\mathbf{0{,}8575} \le d + \frac{1-d}{N} = 0{,}90$ — **dưới upper bound** | (ii), $C = \{T\}$ |
| Số node có điểm $> 0$ | **1 / 3** | **3 / 3** | (i) |

> **Đọc kết quả.** Damping **không** xoá bỏ sự thật rằng $T$ là node quan trọng nhất — nó vẫn đứng đầu với $0{,}8575$. Cái damping làm là **chặn không cho $T$ chiếm 100%** và **giữ cho mọi node khác có điểm dương để xếp hạng**. Đó chính là nội dung của "prevents sink node trapping": không phải loại bỏ hub, mà là không để một node hay một cụm nào hấp thụ toàn bộ phân phối.
>
> Sắc thái cuối: ở đây $d = 1$ **vẫn hội tụ** (vì closed class aperiodic), nên vấn đề ở đây **không** phải "không hội tụ" mà là "hội tụ về một nghiệm vô dụng".

---

### 3.3.10 — Liên hệ dataset PaySim của nhóm

Số **đo trực tiếp** in đậm; số **dẫn xuất** đánh dấu **(\*)** kèm phép tính.

| Đại lượng | Giá trị |
|---|---|
| Tổng vertices $N$ | **9.073.900** |
| Tổng edges $\lvert E\rvert$ | **6.362.620** |
| Tài khoản **có gửi** (out-degree $\ge 1$) | **6.353.307** (70,02%) |
| Tài khoản **có nhận** (in-degree $\ge 1$) | **2.722.362** (30,00%) |
| Tài khoản đóng cả hai vai (**dual-role**) | **1.769** (0,0195%) |
| Self-loop | **0** (kiểm vét cạn) |
| 3-node cycle $A\to B\to C\to A$ | **0** (kiểm vét cạn) |
| Max in-degree | **113** (tài khoản `C1286084959`, một tài khoản `C`) |
| Max out-degree | **3** |
| Giao dịch `PAYMENT` kiểu C→M | **2.151.495** (33,81% tổng cạnh) |
| Cạnh có nhãn `isFraud` | **8.213** (0,129%) — `isFlaggedFraud` bắt **16**, recall **0,19%** |
| **Sink node** ($d_{out} = 0$) | 2.720.593 (\*) $= 9\,073\,900 - 6\,353\,307$, tức 29,98% |
| Node **không có in-link** | 6.351.538 (\*) $= 9\,073\,900 - 2\,722\,362$, tức 70,00% |
| Cận trên số cạnh parallel | 9.313 (\*) $= 6\,362\,620 - 6\,353\,307$, tức 0,146% |

> **Lưu ý nhãn số liệu.** Hai con số $6\,353\,307$ và $2\,722\,362$ phải đọc là **"có gửi" / "có nhận"** (inclusive), **không** phải "chỉ gửi" / "chỉ nhận": $6\,353\,307 + 2\,722\,362 = 9\,075\,669 > N$, dư đúng $1\,769$ — bằng đúng số dual-role. Theo nguyên lý bù trừ, $6\,353\,307 + 2\,722\,362 - 1\,769 = 9\,073\,900$ **khớp chính xác**.

#### PaySim minh hoạ trực tiếp cho Bước 4 và Bước 5

**(a) Tập dangling rất lớn và có cấu trúc rõ ràng.** $\lvert D\rvert = 2\,720\,593$ (\*) — gần **30% graph**. **Toàn bộ Merchant** (tiền tố `M`) có **out-degree $= 0$ tuyệt đối**: đây là sink node thật trong chính dataset, không phải ví dụ giả định.

> **Không viết "tập sink chính là tập Merchant".** Merchant **chắc chắn** là sink, nhưng tập sink **rộng hơn** — nó gồm cả những tài khoản `C` chỉ nhận.

**(b) Lượng mass đi vào $D$ mỗi vòng là rất lớn.** Riêng $2\,151\,495$ giao dịch `PAYMENT` C→M chiếm $33{,}81\%$ tổng cạnh, và $100\%$ số cạnh đó trỏ vào node có $d_{out} = 0$.

> **Đây là CẬN DƯỚI, không phải giá trị điểm.** Tập sink rộng hơn tập Merchant, nên tỷ lệ cạnh trỏ vào tập sink phải **LỚN HƠN** $33{,}81\%$.

**(c) Vai trò của teleportation trên PaySim là BẢO ĐẢM, không phải CỨU VÃN.** Như đã tách ở §3.3.4.2: $M$ reducible là đã chứng minh, nhưng $S$ có thể **đã** primitive. Teleportation bảo đảm tính duy nhất và hội tụ **không phụ thuộc** vào việc $S$ có primitive hay không — ta **không cần** biết câu trả lời để dùng được kết quả. Câu "vì 70% node không in-link nên $\mathbf{r} = S\mathbf{r}$ không duy nhất" là **non sequitur** và phải bỏ.

**(d) Graph rất shallow (nông).** Chỉ $1\,769/9\,073\,900$ node ($0{,}0195\%$) đóng cả hai vai; max out-degree $= 3$; self-loop $= 0$. Cấu trúc gần một **shallow DAG**, rất khác web graph mà PageRank được thiết kế cho. Max in-degree chỉ $113$ và node giữ kỷ lục là một tài khoản `C` — **không có node đơn lẻ nào là siêu-hub**. Nhưng lớp Merchant hấp thụ $2\,151\,495$ cạnh nên phải có **ít nhất $19\,040$ Merchant** (\*). **Kết luận: ảnh hưởng của tập sink đến từ SỐ LƯỢNG node sink, không từ in-degree của từng node.**

#### Hai kết quả cấu trúc riêng cho PaySim

*(Phân tích riêng của nhóm, không phải trích dẫn.)*

> **Bổ đề chu trình.** Mọi **chu trình có hướng** của graph PaySim đều nằm **trọn vẹn** trong đồ thị con cảm sinh trên $1\,769$ node dual-role.
>
> **Chứng minh.** Lấy chu trình $v_0\to v_1\to\cdots\to v_0$. Mỗi đỉnh $v_i$ có ít nhất một cạnh vào (từ $v_{i-1}$) và một cạnh ra (tới $v_{i+1}$), nên là node dual-role. $\blacksquare$

**Ba hệ quả:** (1) câu hỏi "PaySim có spider trap không" **quy về một lệnh SCC trên đúng $1\,769$ đỉnh** — vài giây, thay vì quét $6{,}36$ triệu cạnh; (2) nếu acyclic thì $M$ **nilpotent**, chuỗi Neumann hữu hạn, và phép lặp rút gọn cho **nghiệm đúng** sau $K$ vòng; (3) mọi node trung gian của một đường đi đều phải là dual-role, nên đường đi dài nhất **bị chặn trên bởi $1\,770$ cạnh**.

> **Mệnh đề (dạng gần-đóng).** Đặt $\beta = \frac{1-d}{N} + \frac{d}{N}\sum_{v\in D}r(v)$ (phần phi-link, giống nhau cho mọi node) và $w(u) = \sum_{v:d_{out}(v)>0}\frac{A_{vu}}{d_{out}(v)}$ (**weighted in-degree**). Nếu **mọi** in-neighbour của $u$ là "người gửi thuần" (in-degree $= 0$) thì tại nghiệm dừng
> $$r(u) \;=\; \beta\,\bigl(1 + d\,w(u)\bigr).$$
>
> **Chứng minh.** Người gửi thuần $v$ không có in-link nên $r(v) = \beta$ chính xác. Thay vào công thức cuối: $r(u) = \beta + d\beta\sum_{v\in B(u)}\frac{A_{vu}}{d_{out}(v)} = \beta(1 + d\,w(u))$. $\blacksquare$

**Đúng CHÍNH XÁC cho ít nhất $99{,}94\%$ node PaySim:** một node chỉ **không** thoả khi có ít nhất một in-neighbour dual-role; mỗi node dual-role có out-degree $\le 3$ nên gửi tới nhiều nhất 3 đích, vậy số node bị loại nhiều nhất là $3\times1\,769 = 5\,307$ (\*), tức $(9\,073\,900-5\,307)/9\,073\,900 = \mathbf{99{,}94\%}$.

**Hai hệ quả định lượng:** (1) PageRank là hàm **affine đơn điệu tăng** của weighted in-degree, nên **top-10 PageRank $=$ top-10 weighted in-degree** cho $\ge 99{,}94\%$ graph; (2) vì $w(u) \le \text{indeg}(u) \le 113$, ta có $r(u)/\beta = 1 + d\,w(u) \le 1 + 0{,}85\times113 = \mathbf{97{,}05}$ — node cao điểm nhất chỉ hơn baseline **nhiều nhất $\approx 97$ lần**, một dự đoán Task 2 đo được.

---

### 3.3.11 — Từ lý thuyết tới GraphFrames

`resetProbability = 0.15` $\iff d = 0{,}85$. GraphFrames `pageRank(resetProbability, maxIter)` dùng **backend GraphX** (`aggregateMessages`), và từ v0.12.x dùng bản **vendored** trong `org.apache.spark.graphframes.graphx`.

**Quy ước scale.** Mã nguồn v0.12.2 áp một hệ số chuẩn hoá tất định ở cuối, nên tổng cột `pagerank` $= N$ (hoặc $= 1$ với personalized), **không** phải $1{,}0$. Theo Mệnh đề §3.3.6.4, rescale-một-lần-ở-cuối **tương đương** tái-phân-phối-mỗi-vòng **tại fixed point** — đó là chứng minh sạch cho việc kết quả GraphFrames dùng được.

> **Một chỗ sai trong chính tài liệu chính thức:** scaladoc của cả GraphX lẫn GraphFrames ghi *"pages that have no inlinks will have a PageRank of alpha"*. Câu này có từ **trước** bản vá SPARK-18847 và **chỉ còn đúng khi graph không có sink**. **Không được viết "node không có in-link sẽ có pagerank = 0,15".**

> **Ràng buộc API:** GraphFrames ghi *"You cannot specify maxIter() and tol() at the same time."* Task 2 dùng `maxIter`, nên **không** có tiêu chí dừng theo tolerance; muốn đo residual phải chạy nhiều lần với `maxIter` tăng dần.

#### Sáu dự đoán kiểm chứng được cho Task 2

| # | Truy vấn | Dự đoán |
|---|---|---|
| 1 | `result.vertices.agg(sum("pagerank"))` | $\approx 9\,073\,900$ (tức $N$), **không** phải $1{,}0$ |
| 2 | Cột `weight` của edges | $= 1/d_{out}(\text{src})$, chỉ nhận $\{1{,}0;\,0{,}5;\,0{,}333\}$; $\ge 99{,}85\%$ cạnh có `weight` $= 1{,}0$ (\*) |
| 3 | `edges.groupBy("src","dst").count().filter("count > 1").count()` | nhỏ, $\le 9\,313$ (\*); nếu $= 0$ thì PaySim là simple graph |
| 4 | `N - g.outDegrees.count()` và `N - g.inDegrees.count()` | đúng $2\,720\,593$ và $6\,351\,538$ |
| 5 | **SCC trên đồ thị con $1\,769$ node dual-role** | **acyclic** — đóng **bốn** chỗ cùng lúc |
| 6 | `result.vertices.orderBy(desc("pagerank")).limit(10)` | node đứng đầu là **`C1286084959`**, **không** phải một Merchant |

**Dự đoán 5 đáng giá nhất.** Theo Bổ đề chu trình, mọi chu trình nằm trong $1\,769$ đỉnh đó, nên một lệnh SCC trả lời dứt điểm bốn câu hỏi bài đang phải phát biểu có điều kiện: (i) PaySim có spider trap không; (ii) $\rho(M) < 1$ có đúng không; (iii) $M$ có nilpotent không và bậc bao nhiêu; (iv) `maxIter = 10` là xấp xỉ hay nghiệm đúng.

#### `maxIter = 10`: lập luận ba chiều

- **Chiều phản đối:** $0{,}85^{10} = 0{,}1969$, cận co chỉ bảo đảm $\lVert\mathbf{r}^{(10)}-\mathbf{r}^{*}\rVert_1 \le 0{,}394$. Langville & Meyer ước lượng $86$ vòng cho $\varepsilon = 10^{-6}$; Page et al. báo cáo $\approx 52$ vòng. Cả hai **lớn hơn 10 rất nhiều**.
- **Chiều ủng hộ 1:** thứ hạng hội tụ nhanh hơn giá trị — Haveliwala (1999), *"As few as 10 iterations produced a good approximate ordering"*. *(Trích dẫn **gián tiếp** qua Langville & Meyer, nên là luận cứ hỗ trợ.)*
- **Chiều ủng hộ 2, MẠNH NHẤT và tự chứa:** nếu dự đoán 5 xác nhận acyclic thì $M$ **nilpotent** bậc $K$, chuỗi Neumann hữu hạn, và $\tilde{\mathbf{r}}^{(t)} = \tilde{\mathbf{r}}^{*}$ với **mọi** $t \ge K$ — **không xấp xỉ, không phụ thuộc khởi tạo**. Nếu thêm $K \le 10$ thì `maxIter = 10` **KHÔNG phải xấp xỉ mà là NGHIỆM ĐÚNG**. Ví dụ 1 ở §3.3.9.1 là trường hợp đã kiểm được của chính lập luận này: $M^{4} = 0$ và dãy rút gọn đứng yên chính xác từ $t = 4$.

> **Phát biểu đúng, để không tự mâu thuẫn:** `maxIter = 10` là **chính đáng cho mục tiêu lấy TOP-10 HUB** — một bài toán **thứ hạng**. Nhưng **chừng nào dự đoán 5 chưa chạy**, **không được công bố giá trị PageRank như số đã hội tụ**. Hai điều này không mâu thuẫn vì nói về **hai đại lượng khác nhau**.

---

### 3.3.12 — Caveat: đọc kết quả PageRank cho đúng

Mục này bắt buộc phải có vì Task 2 sẽ dẫn lại.

**(1) PageRank cao $\neq$ gian lận.** Cảnh báo quan trọng nhất, và literature **không thống nhất về dấu**:

- **Molloy et al. (2016)** — PageRank trên transaction graph ngân hàng thật (ABN AMRO, *"hundreds of millions of transactions"*, có nhãn fraud thật) — giả thiết **ngược lại**: *"Our hypothesis is that accounts with a high PageRank are **less** likely to be fraudulent."* Họ dùng PageRank để **giảm false positive**.
- **Fronzetti Colladon & Remondi (2017)** — mạng 559 node của một công ty factoring Ý, đo bằng **closeness centrality** (không phải PageRank) — tìm thấy actor rủi ro cao nằm **ở ngoại vi**. *(Quy mô và thước đo khác hẳn PaySim; đây là phản chứng **định tính**, không phải kết quả chuyển giao trực tiếp.)*

**Lập luận cấu trúc mạnh nhất, dùng làm câu chốt:** PageRank chấm điểm mỗi **vertex**, trong khi `isFraud` là nhãn trên mỗi **edge**. Molloy et al. nói thẳng: *"One can view SNA as focused on identifying anomalous/special nodes while fraud detection finds anomalous edges."* Đây là **sai khác về đối tượng đo**, không chỉ là vấn đề độ chính xác. **Top-10 hub là danh sách nút trung tâm của mạng, không phải danh sách nghi vấn.**

Ánh xạ sang PaySim: vì thứ hạng PageRank gần như trùng thứ hạng weighted in-degree (§3.3.10), node đứng đầu bảng nhiều khả năng là `C1286084959` — một tài khoản **Customer** — chứ không phải một Merchant. Đây là **dự đoán 6** ở §3.3.11.

> **Nhưng phải nêu cả vế thứ hai.** Luật ngưỡng tĩnh `isFlaggedFraud` (`amount > 200.000`) chỉ bắt **16/8.213** cạnh gian lận — **recall $0{,}19\%$**. Một luật cục bộ trên thuộc tính đơn lẻ gần như không phát hiện được gì. PageRank **không** thay thế nó một-đổi-một (nó chấm **vertex** còn `isFraud` gán nhãn **edge**), nhưng cho một chiều thông tin **CẤU TRÚC** mà mọi luật ngưỡng theo hàng đều không có. Đây là lý do chính đáng để nhóm dùng graph analytics.

**(2) `maxIter = 10` không đồng nghĩa "đã hội tụ".** Ngôn ngữ đúng: *"PageRank sau 10 vòng lặp"*, không phải *"PageRank hội tụ"* — trừ khi dự đoán 5 ở §3.3.11 xác nhận $M$ nilpotent bậc $\le 10$. Luận cứ định lượng ở §3.3.5.4: cận co chỉ bảo đảm $\lVert\mathbf{r}^{(10)}-\mathbf{r}^{*}\rVert_1 \le 0{,}394$.

---

### 3.3.13 — Tóm tắt

| Bước | Nội dung | Kết quả |
|---|---|---|
| 1 | Random walk / random surfer model | $\Pr[v\to u] = A_{vu}/d_{out}(v)$ |
| 2 | Transition matrix column-stochastic | $\mathbf{r}^{(t+1)} = M\mathbf{r}^{(t)}$; $M$ **substochastic**, với PaySim thì **không** stochastic |
| 3 | Stationary distribution | $\mathbf{r} = M\mathbf{r}$, eigenvector ứng $\lambda = 1$ — **với giả thiết $M$ stochastic**, mà PaySim **không thoả** |
| 4 | Ba vấn đề + stochasticity adjustment | $S = M + \frac1N\mathbf{e}\mathbf{a}^{T}$ — stochastic, nhưng có thể reducible |
| 5 | Teleportation + primitivity adjustment | $G = dS + (1-d)\frac1N J$ — $G > 0$, primitive; Perron–Frobenius cho $\mathbf{r}$ dương duy nhất; ánh xạ co nên $\lVert\mathbf{r}^{(t)}-\mathbf{r}^{*}\rVert_1 \le 2d^{t}$; $\lvert\lambda_2(G)\rvert \le d$ |
| 6 | Công thức cuối | $r^{(t+1)}(u) = \frac{1-d}{N} + d\left[\sum_{v:d_{out}(v)>0}\frac{A_{vu}r^{(t)}(v)}{d_{out}(v)} + \frac1N\sum_{v\in D}r^{(t)}(v)\right]$ |

**Bốn đóng góp của mục này ngoài việc phát biểu công thức:**

1. Chỉ ra **dạng rút gọn của đề bài là trường hợp riêng** ($D = \varnothing$, không parallel edges), và **PaySim vi phạm giả thiết mang tính quyết định** — $\lvert D\rvert = 2\,720\,593$ (\*), gần 30% graph — kèm chứng minh số ở §3.3.9.1.
2. Tách bạch **hai cách giải quyết** cho **hai vấn đề** khác nhau, chỉ ra **thứ tự là bắt buộc**, rồi **hoà giải** chúng thành một cơ chế duy nhất qua cùng một teleportation vector (§3.3.7.3) — trả lời câu hỏi của đề bài bằng **bốn bất đẳng thức kiểm chứng được** và **hai ví dụ tính tay**, trong đó ví dụ 2 là bằng chứng số cho **đúng chữ "sink node trapping"**.
3. **Mệnh đề tỉ lệ** $\mathbf{r} \parallel \tilde{\mathbf{r}}$ (§3.3.6.4) và **khai triển Neumann**: hai dạng cho cùng nghiệm dừng sau chuẩn hoá với **mọi** graph. Hệ quả: **sai về SCALE không đồng nghĩa sai về THỨ HẠNG** — lý do `maxIter = 10` **vẫn** cho top-10 hub dùng được, và cũng là lý do **không được công bố GIÁ TRỊ PageRank**.
4. **Hai kết quả cấu trúc riêng cho PaySim** (§3.3.10) rút từ con số $1\,769$ dual-role: **Bổ đề chu trình** (thu câu hỏi spider trap về một lệnh SCC vài giây) và **dạng gần-đóng** $r(u) = \beta(1 + d\,w(u))$ đúng cho $\ge 99{,}94\%$ node, kéo theo cận $r(u)/\beta \le 97{,}05$ , và hệ quả là **top-10 PageRank trùng top-10 weighted in-degree** cho phần áp đảo graph.

---

### 3.3.14 — Tài liệu tham khảo

1. **Brin, S. & Page, L.** (1998). *The Anatomy of a Large-Scale Hypertextual Web Search Engine.* WWW7 / Computer Networks and ISDN Systems 30(1–7), 107–117.
   *Nguồn cho:* random surfer model (§2.1.2); *"We usually set $d$ to 0.85"* (§2.1.1); *"principal eigenvector of the normalized link matrix"* (§2.1.1); quy ước $PR(A) = (1-d) + d(\cdots)$ không chia $N$.

2. **Page, L., Brin, S., Motwani, R. & Winograd, T.** (1999). *The PageRank Citation Ranking: Bringing Order to the Web.* Stanford InfoLab Technical Report 1999-66. http://ilpubs.stanford.edu:8090/422/
   *Nguồn cho:* định nghĩa **rank sink** (§2.4); *"their weight is lost from the system"* (§2.4); xử lý dangling link bằng loại-bỏ-rồi-thêm-lại (§2.7); $\lVert E\rVert_1 = 0.15$ (§6); $\approx 52$ vòng lặp trên 322 triệu link (§4); ký hiệu $B_u$, $F_u$, $N_u = \lvert F_u\rvert$.

3. **Langville, A. N. & Meyer, C. D.** (2004). *Deeper Inside PageRank.* Internet Mathematics 1(3), 335–380.
   *Nguồn cho:* stochasticity/primitivity adjustment; phê phán việc xoá dangling node (§5.1); phân vai irreducibility (tồn tại/duy nhất) vs primitivity (hội tụ) (§5.1.1); Theorem 5.1 (đẳng thức phổ); bảng số vòng lặp (§5.1.1); Haveliwala (1999) dẫn lại.

4. **Langville, A. N. & Meyer, C. D.** (2006). *Google's PageRank and Beyond: The Science of Search Engine Rankings.* Princeton University Press.
   *Nguồn cho:* $S = H + \mathbf{a}(\frac1n\mathbf{e}^{T})$ và $G = \alpha S + (1-\alpha)\frac1n\mathbf{e}\mathbf{e}^{T}$ (Ch. 4.5); sáu hệ quả của primitivity adjustment; Table 5.1 (ảnh hưởng của $\alpha$ tới số vòng lặp); *"$.85^{50} \approx .000296$"*; *"at last report, this is still the value used by Google"*.

5. **Haveliwala, T. H. & Kamvar, S. D.** (2003). *The Second Eigenvalue of the Google Matrix.* Stanford University Technical Report.
   *Nguồn cho:* Theorem 1 ($\lvert\lambda_2\rvert \le c$); Theorem 2 (điều kiện đủ để đạt đẳng thức).

6. **Meyer, C. D.** (2000). *Matrix Analysis and Applied Linear Algebra.* SIAM.
   *Nguồn cho:* Perron–Frobenius (bản irreducible và bản primitive); tiêu chuẩn Frobenius *"$A \ge 0$ is primitive iff $A^{m} > 0$ for some $m > 0$"*.

7. **Leskovec, J., Rajaraman, A. & Ullman, J. D.** *Mining of Massive Datasets*, Ch. 5 "Link Analysis". Cambridge University Press.
   *Nguồn cho:* định nghĩa substochastic (§5.1.4); *"importance 'drains out' of the Web"*; quy ước column-stochastic.

8. **Boldi, P., Santini, M. & Vigna, S.** (2005). *PageRank as a Function of the Damping Factor.* WWW '05, 557–566.
   *Nguồn cho:* *"contradicting the common beliefs"*; quan hệ giữa vòng lặp thứ $k$ của power method và đa thức Maclaurin bậc $k$.

9. **Molloy, I. et al.** (2016). *Graph Analytics for Real-Time Scoring of Cross-Channel Transactional Fraud.* Financial Cryptography and Data Security (FC 2016), LNCS 9603.
   *Nguồn cho:* giả thiết PageRank cao $\Rightarrow$ **ít** khả năng gian lận hơn; *"the damping factor can be used to model an account saving"*; *"SNA … identifying anomalous/special nodes while fraud detection finds anomalous edges"*; Table 2 (Average ZER, AUC).

10. **Fronzetti Colladon, A. & Remondi, E.** (2017). *Using social network analysis to prevent money laundering.* Expert Systems with Applications 67, 49–58.
    *Nguồn cho:* mạng 559 node / 33.670 link; *"the most dangerous social actors … are more peripheral in the transactions network"*; thước đo là closeness centrality.

11. **Lopez-Rojas, E. A., Elmir, A. & Axelsson, S.** (2016). *PaySim: A Financial Mobile Money Simulator for Fraud Detection.* EMSS 2016.
    *Nguồn cho:* mô tả simulator. **Cảnh báo:** bài này **không chứa fraudulent agent** (Conclusions ghi đó là future work) và dataset mô tả là PS41840 (~23 triệu bản ghi), **khác** file 6.362.620 dòng nhóm dùng. **Không trích bài này làm nguồn cho định nghĩa `isFraud` hay con số 8.213.**

12. **Apache Software Foundation.** *SPARK-18847: "PageRank gives incorrect results for graphs with sinks".* Apache JIRA (Fix Version 2.2.0), PR apache/spark#16483.
    *Nguồn cho:* *"Sink vertices … should evenly distribute their rank to the entire graph but in the current implementation it is just lost"*; việc chuẩn hoá ở cuối *"gives the same result as doing it after every iteration but without the extra overhead"*.

13. **GraphFrames project** (2025). *PageRank.scala*, GraphFrames v0.12.2 (bản GraphX **vendored** trong `org.apache.spark.graphframes.graphx`).
    *Nguồn cho:* scaladoc *"alpha is the random reset probability (typically 0.15)"*; *"pages that have no inlinks will have a PageRank of alpha"*; ràng buộc *"You cannot specify maxIter() and tol() at the same time."*; khởi tạo mọi đỉnh $= 1{,}0$; trọng số cạnh `1.0 / e.srcAttr`; hàm `normalizeRankSum`.


---

## 3.4 — Connected Components vs LPA

> Phụ trách **N5** (lý thuyết) và **N6** (kiểm chứng), review **N6**. Chưa bắt đầu.

*Nội dung cần có (theo đề bài):* phân biệt Connected Components (reachability chính xác) với Label Propagation Algorithm (community detection dựa trên đồng thuận lân cận); nêu vì sao đề bài nhắc cả hai.
