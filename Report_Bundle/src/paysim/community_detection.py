"""Task 4 - Community Detection (PaySim).

Input:
    data/processed/sample/paysim/
Output:
    results/paysim/communities.csv
    results/paysim/community_summary.csv

Mục tiêu kỹ thuật:
    1. Cấu hình setCheckpointDir bắt buộc để tránh StackOverflowError do lineage sâu.
    2. Chạy GraphFrames labelPropagation(maxIter=5).
    3. Thống kê phân bố cộng đồng (kích thước, top hubs, tỷ lệ C/M).
    4. Nâng nhãn và đối chiếu fraud: đo lường giao dịch nội bộ vs liên cộng đồng,
       tỷ lệ giao dịch gian lận (isFraud == 1) trong từng cụm.
    5. Hỗ trợ đánh giá tính ổn định (Stability Check qua nhiều lần chạy).
"""

import argparse
import sys
from pathlib import Path

from graphframes import GraphFrame
from pyspark.sql import functions as F

# Đảm bảo đường dẫn gốc dự án có trong sys.path
PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.common.spark_session import get_graph_session
from src.common.run_evidence import REPO_ROOT, write_run_evidence


# ============================================================
# Cấu hình đường dẫn mặc định
# ============================================================

DEFAULT_INPUT_DIR = Path("data/processed/paysim")
DEFAULT_OUTPUT_DIR = Path("results/paysim/full")
DEFAULT_CHECKPOINT_DIR = Path("checkpoints/paysim_lpa")

COMMUNITIES_FILENAME = "communities.csv"
COMMUNITY_SUMMARY_FILENAME = "community_summary.csv"


# ============================================================
# 1. Tải Đồ thị (Graph Loading)
# ============================================================

def load_graph(spark, input_dir: Path) -> GraphFrame:
    """Đọc dữ liệu Vertices và Edges Parquet từ Task 1 để tạo GraphFrame."""
    vertices_path = input_dir / "vertices.parquet"
    edges_path = input_dir / "edges.parquet"

    if not vertices_path.exists() or not edges_path.exists():
        raise FileNotFoundError(
            f"Không tìm thấy Parquet tại {input_dir}. "
            "Vui lòng chạy Task 1 ETL trước khi thực hiện Task 4."
        )

    vertices = spark.read.parquet(str(vertices_path))
    edges = spark.read.parquet(str(edges_path))

    print("\n=== [Task 4] Nạp Đồ thị PaySim ===")
    print(f"  Thư mục dữ liệu: {input_dir}")
    print(f"  Số đỉnh (Vertices): {vertices.count():,}")
    print(f"  Số cạnh (Edges):    {edges.count():,}")

    return GraphFrame(vertices, edges)


# ============================================================
# 2. Thuật toán LPA & Quản lý Checkpoint
# ============================================================

def run_lpa(graph: GraphFrame, spark, max_iter: int = 5, checkpoint_dir: Path = DEFAULT_CHECKPOINT_DIR, *, backend="graphx"):
    """
    Thực thi Label Propagation Algorithm (LPA).
    
    Lưu ý kỹ thuật quan trọng:
        PySpark GraphFrames thực hiện LPA lặp qua RDD/DataFrame. Nếu không setCheckpointDir,
        lineage graph sẽ phình to theo từng iteration và gây StackOverflowError trên JVM.
    """
    if backend == "dataframe":
        import uuid
        return dataframe_lpa(graph.vertices, graph.edges.select("src", "dst"), checkpoint_dir / ("sql_"+uuid.uuid4().hex), max_iter)
    if backend != "graphx":
        raise ValueError("Unknown LPA backend")
    if max_iter <= 0:
        raise ValueError("max_iter must be positive")
    checkpoint_dir.mkdir(parents=True, exist_ok=True)
    spark.sparkContext.setCheckpointDir(str(checkpoint_dir.resolve()))

    print(f"\n[*] Đang thực thi LPA (maxIter={max_iter}) với checkpoint tại: {checkpoint_dir} ...")
    topology = GraphFrame(graph.vertices.select("id"), graph.edges.select("src", "dst"))
    labels = topology.labelPropagation(maxIter=max_iter)
    lpa_result = graph.vertices.join(labels.select("id", "label"), "id")

    # Cache kết quả để phục vụ nhiều phép tính downstream mà không phải chạy lại LPA
    lpa_result.cache()
    total_labeled = lpa_result.count()
    labels.unpersist()
    print(f"[+] LPA hoàn tất. Tổng số đỉnh đã gán nhãn community: {total_labeled:,}")

    return lpa_result


# ============================================================
# 3. Phân tích Thống kê Cộng đồng (Community Profiling)
# ============================================================

def analyze_communities(lpa_vertices, graph: GraphFrame, top_n: int = 15):
    """
    Khai phá thuộc tính và cấu trúc của các cộng đồng:
      - Phân bổ kích thước (size distribution)
      - Thành phần loại tài khoản (Customer 'C' vs Merchant 'M')
      - Giao dịch nội bộ (Intra-community) vs Giao dịch liên cụm (Inter-community)
      - Phân bổ nhãn gian lận (isFraud enrichment)
    """
    print("\n=== [Task 4] Phân tích Thống kê Cộng đồng ===")

    # A. Thống kê cơ bản về kích thước cộng đồng
    community_sizes = (
        lpa_vertices
        .groupBy("label")
        .agg(
            F.count("*").alias("member_count"),
            F.sum(F.when(F.col("account_type") == "Customer", 1).otherwise(0)).alias("customer_count"),
            F.sum(F.when(F.col("account_type") == "Merchant", 1).otherwise(0)).alias("merchant_count"),
            F.round(F.avg("balance"), 2).alias("avg_balance"),
            F.round(F.max("balance"), 2).alias("max_balance"),
        )
        .orderBy(F.desc("member_count"), F.asc("label"))
    )

    total_communities = community_sizes.count()
    if total_communities == 0:
        raise ValueError("Cannot analyze an empty graph")
    if community_sizes.where(F.col("customer_count") + F.col("merchant_count") != F.col("member_count")).limit(1).count():
        raise ValueError("PaySim account_type must be Customer or Merchant")
    singleton_count = community_sizes.filter(F.col("member_count") == 1).count()
    multi_member_count = total_communities - singleton_count

    print(f"  Tổng số cộng đồng phát hiện: {total_communities:,}")
    print(f"  Số cộng đồng đơn lẻ (Singletons - size=1): {singleton_count:,} ({singleton_count / total_communities * 100:.1f}%)")
    print(f"  Số cộng đồng có từ 2 thành viên trở lên:  {multi_member_count:,} ({multi_member_count / total_communities * 100:.1f}%)")

    # B. Gán nhãn community vào Edges để phân tích dòng tiền nội bộ vs ngoại bộ
    edges = graph.edges
    v_labels = lpa_vertices.select(F.col("id"), F.col("label"))

    edges_with_labels = (
        edges
        .join(v_labels.withColumnRenamed("id", "src").withColumnRenamed("label", "src_label"), on="src", how="inner")
        .join(v_labels.withColumnRenamed("id", "dst").withColumnRenamed("label", "dst_label"), on="dst", how="inner")
    )

    total_edges = edges_with_labels.count()
    if total_edges == 0:
        raise ValueError("Cannot analyze a graph without transactions")
    internal_edges = edges_with_labels.filter(F.col("src_label") == F.col("dst_label"))
    internal_count = internal_edges.count()
    cross_count = total_edges - internal_count

    print(f"\n  Phân tích ranh giới dòng tiền:")
    print(f"    Giao dịch nội bộ (Intra-community): {internal_count:,} ({internal_count / total_edges * 100:.1f}%)")
    print(f"    Giao dịch liên cụm (Inter-community): {cross_count:,} ({cross_count / total_edges * 100:.1f}%)")

    # C. Đánh giá gian lận theo từng cộng đồng
    fraud_stats = (
        edges_with_labels
        .groupBy("src_label")
        .agg(
            F.count("*").alias("total_tx_count"),
            F.sum("amount").alias("total_tx_amount"),
            F.sum("isFraud").alias("fraud_tx_count"),
            F.sum(F.when(F.col("src_label") == F.col("dst_label"), 1).otherwise(0)).alias("internal_tx_count"),
            F.sum(F.when((F.col("src_label") == F.col("dst_label")) & (F.col("isFraud") == 1), 1).otherwise(0)).alias("internal_fraud_count"),
        )
        .withColumnRenamed("src_label", "label")
    )

    # D. Tổng hợp bảng Summary cho Top Communities
    summary_df = (
        community_sizes
        .join(fraud_stats, on="label", how="left")
        .na.fill(0, subset=["total_tx_count", "fraud_tx_count", "internal_tx_count", "internal_fraud_count", "total_tx_amount"])
        .withColumn("fraud_rate", F.round(F.col("fraud_tx_count") / F.when(F.col("total_tx_count") == 0, 1).otherwise(F.col("total_tx_count")), 4))
        .orderBy(F.desc("member_count"), F.asc("label"))
    )

    print(f"\n=== Top {top_n} Cộng đồng lớn nhất theo số lượng tài khoản ===")
    summary_df.show(top_n, truncate=False)

    # Lọc kiểm tra cộng đồng có chứa gian lận
    fraud_hotspots = summary_df.filter(F.col("fraud_tx_count") > 0).orderBy(F.desc("fraud_tx_count"))
    fraud_community_count = fraud_hotspots.count()
    print(f"\n  Số lượng cộng đồng có chứa giao dịch gian lận: {fraud_community_count:,}")
    if fraud_community_count > 0:
        print("  Top 5 cộng đồng tập trung nhiều giao dịch gian lận nhất:")
        fraud_hotspots.show(5, truncate=False)

    return community_sizes, summary_df


# ==============================================
# 4. Kiểm tra Tính ổn định (Stability Check)
# ==============================================

def check_lpa_stability(graph: GraphFrame, spark, max_iter: int = 5, runs: int = 2,
                        checkpoint_dir: Path = DEFAULT_CHECKPOINT_DIR / "stability", backend="graphx"):
    """Compare actual account membership, allowing arbitrary numeric label IDs."""
    from src.ibm_aml.verify_communities import compare_partition_frames

    if not 2 <= runs <= 3:
        raise ValueError("Stability requires two or three sequential runs")
    first = None
    comparisons = []
    try:
        for index in range(runs):
            current = run_lpa(graph, spark, max_iter, checkpoint_dir / str(index + 1), backend=backend)
            if first is None:
                first = current
                continue
            try:
                comparisons.append({"run": index + 1, **compare_partition_frames(current, first)})
            finally:
                current.unpersist()
        print("Observed membership comparisons:", comparisons)
        return comparisons
    finally:
        if first is not None:
            first.unpersist()


# ============================================================
# 5. Xuất Kết quả Báo cáo (Export Deliverables)
# ============================================================

def export_results(lpa_vertices, summary_df, output_dir: Path):
    """Keep the display view and every community; never collect all accounts."""
    from src.common.graph_utils import write_spark_csv

    output_dir.mkdir(parents=True, exist_ok=True)
    assignments = lpa_vertices.select("id", "account_type", "balance", "label").repartition(64).sortWithinPartitions("id")
    write_spark_csv(assignments, output_dir / COMMUNITIES_FILENAME)
    write_spark_csv(summary_df.orderBy(F.desc("member_count"), "label").limit(50),
                    output_dir / COMMUNITY_SUMMARY_FILENAME)
    write_spark_csv(summary_df.repartition(32), output_dir / "community_summary_all.csv")


# ============================================================
# Hàm thực thi chính (Main Pipeline)
# ============================================================

def snapshot_features(edges, as_of_step, spark, checkpoint_dir):
    """Structural LPA features from history only; no fraud rates enter inference."""
    from src.motif.evaluation import require_unlabelled
    require_unlabelled(edges)
    past = edges.where(F.col("step") <= as_of_step).select("src", "dst")
    ids = past.select(F.col("src").alias("id")).union(past.select(F.col("dst").alias("id"))).distinct()
    labels = run_lpa(GraphFrame(ids, past), spark, max_iter=5, checkpoint_dir=checkpoint_dir)
    try:
        sizes = labels.groupBy("label").agg(F.count("*").alias("community_size"),
                                             F.min("id").alias("community_anchor"))
        source = labels.select(F.col("id").alias("src"), F.col("label").alias("source_community"))
        dest = labels.select(F.col("id").alias("dst"), F.col("label").alias("dest_community"))
        interactions = past.join(source, "src").join(dest, "dst")
        stats = interactions.groupBy("source_community").agg(
            F.count("*").alias("community_out_transactions"),
            F.avg((F.col("source_community") != F.col("dest_community")).cast("double")).alias("community_cross_fraction")
        ).withColumnRenamed("source_community", "label")
        result = labels.join(sizes, "label").join(stats, "label", "left").fillna(
            0, subset=["community_out_transactions", "community_cross_fraction"])
        return result.select("id", "community_anchor", "community_size", "community_out_transactions",
                             "community_cross_fraction").withColumn("as_of_step", F.lit(int(as_of_step))).localCheckpoint(eager=True)
    finally:
        labels.unpersist()


def main():
    parser = argparse.ArgumentParser(description="Task 4 - PaySim Community Detection (LPA)")
    parser.add_argument("--input-dir", type=str, default=str(DEFAULT_INPUT_DIR), help="Thư mục Parquet đầu vào")
    parser.add_argument("--output-dir", type=str, default=str(DEFAULT_OUTPUT_DIR), help="Thư mục xuất CSV kết quả")
    parser.add_argument("--max-iter", type=int, default=5, help="Số vòng lặp LPA (mặc định 5 theo đề bài)")
    parser.add_argument("--check-stability", action="store_true", help="Bật chạy kiểm tra tính ổn định LPA (2 lần)")
    args = parser.parse_args()

    input_dir = Path(args.input_dir).resolve()
    output_dir = Path(args.output_dir).resolve()
    if args.max_iter <= 0:
        parser.error("--max-iter must be positive")

    spark = get_graph_session(
        app_name="PaySim-Task4-CommunityDetection-LPA",
        driver_memory="4g" if "sample" in input_dir.parts else "5g",
        shuffle_partitions=8,
        checkpoint_dir=str(DEFAULT_CHECKPOINT_DIR),
    )

    owned = []
    try:
        # Bước 1: Nạp đồ thị
        graph = load_graph(spark, input_dir)

        stability = []
        # Bước 2: Chạy kiểm tra stability nếu có yêu cầu từ cờ lệnh
        if args.check_stability:
            stability = check_lpa_stability(graph, spark, max_iter=args.max_iter, runs=2, backend="graphx" if "sample" in input_dir.parts else "dataframe")

        # Bước 3: Chạy thuật toán LPA chính
        lpa_vertices = run_lpa(graph, spark, max_iter=args.max_iter, checkpoint_dir=DEFAULT_CHECKPOINT_DIR, backend="graphx" if "sample" in input_dir.parts else "dataframe")
        owned.append(lpa_vertices)

        # Bước 4: Phân tích cộng đồng và đối chiếu fraud
        community_sizes, summary_df = analyze_communities(lpa_vertices, graph)
        summary_df = summary_df.cache()
        owned.append(summary_df)

        # Bước 5: Xuất kết quả
        export_results(lpa_vertices, summary_df, output_dir)
        write_run_evidence(output_dir / "task4_run.json", spark, task="Task 4 PaySim LPA execution",
            inputs=[input_dir], outputs=[output_dir / name for name in
                (COMMUNITIES_FILENAME, COMMUNITY_SUMMARY_FILENAME, "community_summary_all.csv")],
            sources=[Path(__file__), REPO_ROOT / "src/common/graph_utils.py",
                REPO_ROOT / "src/common/spark_session.py", REPO_ROOT / "src/ibm_aml/verify_communities.py"],
            parameters={"max_iter": args.max_iter, "backend": "graphx" if "sample" in input_dir.parts else "dataframe_min_hash_label", "scope": str(input_dir),
                        "stability": stability}, metrics={"assigned_vertices": lpa_vertices.count(),
                        "communities": summary_df.count(), "fraud_audit_posthoc": [row.asDict() for row in
                            summary_df.where("fraud_tx_count>0").orderBy(F.desc("fraud_tx_count"), "label")
                            .select("label", "member_count", "total_tx_count", "fraud_tx_count", "fraud_rate").limit(5).collect()]})

        print("\n" + "=" * 70)
        print("LƯU Ý DIỄN GIẢI KẾT QUẢ (INTERPRETATION BOUNDARY):")
        print("  - Label Propagation Algorithm (LPA) là thuật toán heuristic dựa trên sự đồng thuận")
        print("    lân cận (neighborhood consensus).")
        print("  - Thành viên trong cùng một cộng đồng KHÔNG tự động đồng nghĩa với một vòng gian lận")
        print("    (fraud ring) mà chỉ thể hiện sự liên kết dày đặc về mặt cấu trúc giao dịch.")
        print("  - Cần đối chiếu thêm với nhãn gian lận thực tế (isFraud) và phân tích luồng tiền.")
        print("=" * 70 + "\n")

    finally:
        for frame in owned:
            frame.unpersist()
        spark.stop()




def lpa_update(links, labels):
    """Synchronous weighted neighbor voting; deterministic minimum-label tie."""
    messages = links.join(labels.select(
        F.col("id").alias("neighbor"), F.col("label").alias("neighbor_label")), "neighbor")
    votes = messages.groupBy("id", "neighbor_label").agg(F.sum("multiplicity").alias("votes"))
    # Lexicographic min(-votes, label) = most votes, then smallest label.
    winner = votes.groupBy("id").agg(F.min(F.struct(
        (-F.col("votes")).alias("negative_votes"),
        F.col("neighbor_label").alias("label"))).alias("winner"))
    winner = winner.select("id", F.col("winner.label").alias("new_label"))
    # Isolates receive no message and keep their current label.
    return labels.join(winner, "id", "left").select(
        "id", F.coalesce("new_label", "label").alias("label"))


def dataframe_lpa(vertices, edges, checkpoint_dir, max_iter=5, *, update=None):
    """SQL modal-neighbor LPA; deterministic minimum-label tie handling.

    Messages travel both directions per physical transaction, including two
    messages for a self-loop. Isolates retain their label. Unlike GraphX's
    unspecified tie winner, this backend explicitly chooses the smallest label.
    Numeric labels are run-local partition IDs and never model features.
    """
    from src.motif.evaluation import require_unlabelled
    require_unlabelled(edges)
    if max_iter <= 0:
        raise ValueError("LPA needs positive iterations")
    root = Path(checkpoint_dir)
    root.mkdir(parents=True, exist_ok=True)
    spark = vertices.sparkSession
    links = (edges.select(F.col("src").alias("id"), F.col("dst").alias("neighbor"))
        .unionByName(edges.select(F.col("dst").alias("id"), F.col("src").alias("neighbor")))
        .groupBy("id", "neighbor").agg(F.count("*").alias("multiplicity")))
    links.write.parquet(str(root / "links"))
    links = spark.read.parquet(str(root / "links"))
    initial = vertices.select("id").withColumn("label", F.xxhash64("id"))
    # Stable seed labels make min-label tie decisions independent of partition order.
    # Check actual collision freedom rather than assuming a hash is a unique ID.
    if initial.groupBy("label").count().where("count>1").limit(1).count():
        raise ValueError("Initial LPA hash labels collide; refuse ambiguous partition")
    initial.write.parquet(str(root / "iteration_00"))
    labels = spark.read.parquet(str(root / "iteration_00"))
    for index in range(max_iter):
        updated = (update or lpa_update)(links, labels)
        path = root / f"iteration_{index+1:02d}"
        updated.write.parquet(str(path))
        labels = spark.read.parquet(str(path))
        print(f"[SYSTEM] LPA iteration {index+1}/{max_iter} persisted", flush=True)
        import shutil
        shutil.rmtree(root / f"iteration_{index:02d}", ignore_errors=True)
    return vertices.join(labels, "id")

if __name__ == "__main__":
    main()
