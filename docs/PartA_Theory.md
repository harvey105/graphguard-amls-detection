# 3.3. Derivation of the PageRank Formula

## 3.3.1. Goal

The assignment asks us to derive the iterative PageRank formula from a random walk and explain how the damping factor $d=0.85$ prevents sink node trapping. We distinguish probability lost at a node with no outgoing edge from probability retained in an absorbing state or a closed group of nodes. These require different corrections.

## 3.3.2. From Random Walk to Matrix Form

Let $A_{vu}$ be the number of edges from $v$ to $u$, $d_{\mathrm{out}}(v)=\sum_u A_{vu}$ the out-degree, $N$ the number of nodes, and $D=\{v: d_{\mathrm{out}}(v)=0\}$ the set of dangling nodes (nodes with no outgoing edge). A rank sink, or spider trap, is a closed group in which the walk can continue along edges but cannot leave (Page et al., 1999). An absorbing node with a self-loop is the one-node case. Let $\mathbf{e}$ be the column vector of $N$ ones.

**Step 1. Random walk.** A random walk is a sequence of nodes in which the next node depends only on the current node. In the random surfer model (Brin & Page, 1998), from a node $v$ with $d_{\mathrm{out}}(v)>0$ the walk follows one outgoing edge chosen uniformly:

$$\Pr[v\to u]=\frac{A_{vu}}{d_{\mathrm{out}}(v)}.$$

**Step 2. Transition matrix and power iteration.** The raw matrix $M$ has entries $M_{uv}=\frac{A_{vu}}{d_{\mathrm{out}}(v)}$ if $d_{\mathrm{out}}(v)>0$ and $0$ otherwise. A column with $d_{\mathrm{out}}(v)>0$ is the outgoing distribution of $v$ and sums to 1. The column of a dangling node is zero. Start with a probability vector $\mathbf{r}^{(0)}$, normally $\frac{\mathbf{e}}{N}$. Summing the probability passed to $u$ from each $v$ gives

$$\mathbf{r}^{(t+1)}=M\,\mathbf{r}^{(t)}.$$

Repeating this multiplication is called power iteration. If $D$ is empty, $r^{(t)}(u)$ is the probability of being at $u$ after $t$ steps. Otherwise, the raw update can lose probability and must be repaired before it describes a Markov chain on all $N$ nodes.

**Step 3. Stationary distribution.** For a column-stochastic transition matrix $P$, a stationary distribution satisfies $\mathbf{r}=P\mathbf{r}$, $\mathbf{r}\ge0$ and $\lVert\mathbf{r}\rVert_1=1$. It is a non-negative eigenvector for eigenvalue 1, normalized to sum to 1. Every finite stochastic matrix has a stationary distribution, but uniqueness and convergence require additional conditions. For the raw graph without dangling nodes, take $P=M$ and obtain $r(u)=\sum_{v:\,d_{\mathrm{out}}(v)>0}\frac{A_{vu}r(v)}{d_{\mathrm{out}}(v)}$. PaySim has dangling nodes, so $M$ is not column-stochastic. PageRank will instead be defined using the repaired Google matrix $G$ below.

## 3.3.3. Problems of the Transition Matrix and Their Fixes

**Step 4. Problems of the raw model and the dangling-node repair.**

- *Leakage.* A dangling node has a zero column, so $M$ is substochastic (each column sums to at most 1) and $\lVert\mathbf{r}^{(t+1)}\rVert_1=\lVert\mathbf{r}^{(t)}\rVert_1-\sum_{v\in D}r^{(t)}(v)$. The total probability shrinks because the probability at a dangling node is passed to no node. Page et al. (1999) describe the same effect for pages without outgoing links.
- *Trapping.* In a stochastic walk, probability entering a rank sink cannot leave it. The total over all nodes remains 1, but mass may concentrate in the closed class.
- *Non-uniqueness and oscillation.* A stochastic matrix with multiple closed communicating classes has multiple stationary distributions. If the iterates converge, their limit can depend on the start vector. Periodic classes can also cause oscillation, even when the stationary distribution is unique. Irreducibility ensures a unique stationary distribution for a finite chain; aperiodicity additionally ensures convergence from every initial probability vector.

**Stochasticity adjustment.** Let $a_v=1$ if $v\in D$ and $0$ otherwise. Replace each zero column by the uniform distribution (Langville & Meyer, 2006):

$$S=M+\frac{1}{N}\mathbf{e}\,\mathbf{a}^{T}.$$

$S$ is column-stochastic, so leakage is removed: at a dangling node, the next node is chosen uniformly from all $N$ nodes. This correction does not by itself guarantee uniqueness or convergence on every graph.

**Step 5. Teleportation and primitivity adjustment.** With probability $d$, use $S$: follow a uniformly chosen outgoing edge when one exists, or choose a node uniformly at a dangling node. With probability $1-d$, choose a node uniformly regardless of the edges. This latter choice is teleportation. The Google matrix is

$$G=d\,S+(1-d)\frac{1}{N} J,\qquad J=\mathbf{e}\mathbf{e}^{T}.$$

Both corrections use the same uniform destination distribution. The overall probability of choosing a node uniformly is 1 at a dangling node and $1-d$ elsewhere. Adding teleportation directly to the raw $M$ is insufficient: a dangling column of $dM+\frac{1-d}{N}J$ sums to $1-d$, rather than 1. For a probability vector with dangling mass $m_D$, that update has total $1-dm_D$. By contrast, $G$ is stochastic and, for $0<d<1$, every entry is positive. It is therefore irreducible and aperiodic, and its power iteration converges to a unique stationary distribution (Langville & Meyer, 2004). A matrix is primitive if some power of it has all entries positive; $G$ already has this property at its first power.

## 3.3.4. The Final Iterative Formula

**Step 6.** Writing $\mathbf{r}^{(t+1)}=G\mathbf{r}^{(t)}$ per component and using $\sum_v r^{(t)}(v)=1$:

$$r^{(t+1)}(u)=\frac{1-d}{N}+d\left[\sum_{v:\,d_{\mathrm{out}}(v)>0}\frac{A_{vu}\,r^{(t)}(v)}{d_{\mathrm{out}}(v)}+\frac{1}{N}\sum_{v\in D}r^{(t)}(v)\right],\quad d=0.85.$$

Summing over $u$ gives $(1-d)+d=1$, so the total is 1 at every iteration. At convergence, replace both iterates by $r^*$ to obtain the stationary PageRank equation. Brin and Page (1998) write an unscaled restart term $(1-d)$ and omit an explicit dangling term. Under the convention $\mathrm{PR}=Nr$, dividing that equation by $N$ gives the normalized *simplified* formula. The dangling-mass term above is a separate correction, not a consequence of rescaling. When $D=\varnothing$ and there are no parallel edges, the formula reduces to the assignment's expression $r(u)=\frac{1-d}{N}+d\sum_{v\to u}\frac{r(v)}{d_{\mathrm{out}}(v)}$.

## 3.3.5. How the Damping Factor Prevents Sink Node Trapping

### 3.3.5.1. What happens without teleportation

Without damping-based teleportation ($d=1$), distinguish the raw update $\mathbf{r}^{(t+1)}=M\mathbf{r}^{(t)}$ from the dangling-repaired update $\mathbf{r}^{(t+1)}=S\mathbf{r}^{(t)}$. They behave differently at a dangling node.

1. **A dangling node under $M$.** Its zero column passes no probability onward. The total decreases by the mass currently at dangling nodes; it need not decrease strictly at every step. If every node can reach a dangling node, the finite raw walk eventually loses all its mass and the vector tends to $\mathbf{0}$. For edges $A\to B$, $B\to T$ with $T$ dangling and a uniform start, the totals at $t=0,1,2,3$ are $1,\ \frac{2}{3},\ \frac{1}{3},\ 0$. This is leakage, not absorption. Under $S$, the mass at $T$ is instead redistributed uniformly, so the total remains 1.
2. **An absorbing node with a self-loop.** In a stochastic walk without teleportation, probability that reaches this node never leaves. It receives 100% in the limit if it is the only closed communicating class, as in Section 3.3.6. If other closed classes exist, the mass may be split between them according to the starting distribution and the probabilities of reaching each class.
3. **A closed group (a rank sink or spider trap).** Once the walk enters the group, it cannot leave along an edge. The group absorbs all mass only if every initial trajectory reaches it with probability 1. A periodic group can cause the individual node scores to oscillate, so a limit need not exist.

The raw model can therefore lose all probability, concentrate it in one or more closed classes, or fail to converge. The dangling-node correction repairs leakage. Damping-based teleportation allows escape from closed classes and removes periodicity and dependence on the initial distribution.

### 3.3.5.2. Why teleportation breaks the trap

Teleportation adds $\frac{1-d}{N}$ to the update of every node, whatever the edges look like. At each iteration a fraction $1-d=0.15$ of the total probability is redistributed uniformly over all $N$ nodes, so a trap $C$ passes 15% of the probability it holds to teleportation, and teleportation returns only $\frac{|C|}{N}$ of that to the trap. Every node, including a node with no in-link, receives at least $\frac{0.15}{N}$ per iteration. This gives three consequences.

1. **Positive lower bound.** Let $\mathbf{r}^{(0)}$ be any probability vector. For the limit and for every iterate with $t\ge1$, all terms are non-negative, so $r(u)\ge\frac{1-d}{N}=\frac{0.15}{N}>0$. Hence for any proper subset $C$ of the nodes, $\sum_{u\in C}r(u)\le 1-\frac{(N-|C|)(1-d)}{N}<1$. The total score of a rank sink is always below 1. Equivalently, $\sum_{u\in C}r(u)\le d+(1-d)\frac{|C|}{N}$. In the example of Section 3.3.6 the sink is $C=\{T\}$ with $|C|=1$ and $N=3$, so the bound is $0.85+0.05=0.90$, and the measured score is $0.8575$.
2. **Unique limit.** $G_{uv}\ge\frac{1-d}{N}>0$, so $G$ is positive and column-stochastic. Perron–Frobenius therefore gives a unique positive stationary vector summing to 1, and power iteration converges to it from every initial probability vector (Langville & Meyer, 2004). For probability vectors $x,y$, $\lVert Gx-Gy\rVert_1\le d\lVert x-y\rVert_1$, because $S$ is stochastic and the uniform terms cancel. Consequently, $\lVert\mathbf{r}^{(t)}-\mathbf{r}^*\rVert_1\le2d^t$. At $d=1$ this contraction argument fails.
3. **Finite segments.** Let $T$ count the nodes visited during one segment of edge-following, including its initial node and ending before the next uniform restart. Without a forced restart at a dangling node, $\Pr[T>k]=d^k$ and $\mathbb{E}[T]=\frac{1}{1-d}\approx6.67$. If forced dangling-node restarts are also counted, they can only shorten the segment: $\Pr[T>k]\le d^k$ and $\mathbb{E}[T]\le6.67$. Thus an edge-following segment is finite with probability 1; 6.67 is an expected length, not a maximum length.

Damping does not remove the sink or its high score. It stops the sink from taking 100% and gives every other node a positive score. Damping fixes trapping and non-uniqueness. The dangling term fixes leakage. Any $0<d<1$ works. The value 0.85 is the published default (Brin & Page, 1998), not a proven optimum.

## 3.3.6. Worked Example: A Three-Node Sink

Edges: $A\to B$, $B\to T$, $T\to T$. Once the walk reaches $T$ it cannot leave, so $T$ is an absorbing state and $\{T\}$ is a rank sink. $T$ is not dangling: every node has out-degree 1, so $D=\varnothing$. The two columns differ only in $d$.

| | $d=1$ | $d=0.85$ |
|---|---|---|
| $r(A)$ | $0$ | $0.0500=\frac{1-d}{N}$ |
| $r(B)$ | $0$ | $0.0925$ |
| $r(T)$ | $1.0000$ | $0.8575$ |
| Nodes with score $>0$ | 1 of 3 | 3 of 3 |

At $d=1$ the sum is still 1 and the iteration converges to $\mathbf{r}^*=(0,0,1)$: it distinguishes the absorbing node but cannot distinguish $A$ from $B$. With $d=0.85$ and a uniform start, the iteration reaches the vector in the table after 2 iterations. $T$ still has the highest score, but $r(T)<1$ and every other node has a positive score.

The iteration, starting from $r^{(0)}=(\frac{1}{3},\frac{1}{3},\frac{1}{3})$, shows how the trap forms and how damping stops it:

| $d$ | $t$ | $r(A)$ | $r(B)$ | $r(T)$ | Sum |
|---|---|---|---|---|---|
| 1 | 0 | 0.3333 | 0.3333 | 0.3333 | 1 |
| 1 | 1 | 0.0000 | 0.3333 | 0.6667 | 1 |
| 1 | 2 | 0.0000 | 0.0000 | 1.0000 | 1 |
| 1 | 3 | 0.0000 | 0.0000 | 1.0000 | 1 |
| 0.85 | 0 | 0.3333 | 0.3333 | 0.3333 | 1 |
| 0.85 | 1 | 0.0500 | 0.3333 | 0.6167 | 1 |
| 0.85 | 2 | 0.0500 | 0.0925 | 0.8575 | 1 |
| 0.85 | 3 | 0.0500 | 0.0925 | 0.8575 | 1 |

At $d=1$, $A$ has no in-link, so $r(A)$ becomes 0 after one iteration. $B$ passes all its probability to $T$ and receives none once $r(A)=0$, so $r(B)$ becomes 0 after two. $T$ passes its probability to itself, so $r(T)$ reaches 1. At $d=0.85$, the uniform restart contributes $0.05$ to each node per iteration. Thus $r(A)=0.05$ from the first iteration, $r(B)=0.05+0.85\times0.05=0.0925$ from the second, and $r(T)=1-r(A)-r(B)=0.8575$. This proves directly that the vector is stationary from $t=2$.

## References

Brin, S., & Page, L. (1998). The anatomy of a large-scale hypertextual web search engine. *Computer Networks and ISDN Systems, 30*(1–7), 107–117. https://doi.org/10.1016/S0169-7552(98)00110-X

Langville, A. N., & Meyer, C. D. (2004). Deeper inside PageRank. *Internet Mathematics, 1*(3), 335–380. https://doi.org/10.1080/15427951.2004.10129091

Langville, A. N., & Meyer, C. D. (2006). *Google's PageRank and beyond: The science of search engine rankings*. Princeton University Press. 

Page, L., Brin, S., Motwani, R., & Winograd, T. (1999). *The PageRank citation ranking: Bringing order to the web* (Technical Report No. 1999-66). Stanford InfoLab. http://ilpubs.stanford.edu:8090/422/
