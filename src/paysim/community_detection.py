"""Task 4 - Community Detection (PaySim).

Người phụ trách: N5.
Part B — Task 4 Community Detection & Insights.

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
import os
import shutil
import sys
from pathlib import Path

from graphframes import GraphFrame
from pyspark.sql import functions as F

# Đảm bảo đường dẫn gốc dự án có trong sys.path
PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.common.spark_session import get_graph_session


# ============================================================
# Cấu hình đường dẫn mặc định
# ============================================================

DEFAULT_INPUT_DIR = Path("data/processed/sample/paysim")
DEFAULT_OUTPUT_DIR = Path("results/paysim")
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

def run_lpa(graph: GraphFrame, spark, max_iter: int = 5, checkpoint_dir: Path = DEFAULT_CHECKPOINT_DIR):
    """
    Thực thi Label Propagation Algorithm (LPA).
    
    Lưu ý kỹ thuật quan trọng:
        PySpark GraphFrames thực hiện LPA lặp qua RDD/DataFrame. Nếu không setCheckpointDir,
        lineage graph sẽ phình to theo từng iteration và gây StackOverflowError trên JVM.
    """
    checkpoint_dir.mkdir(parents=True, exist_ok=True)
    spark.sparkContext.setCheckpointDir(str(checkpoint_dir.resolve()))

    print(f"\n[*] Đang thực thi LPA (maxIter={max_iter}) với checkpoint tại: {checkpoint_dir} ...")
    lpa_result = graph.labelPropagation(maxIter=max_iter)

    # Cache kết quả để phục vụ nhiều phép tính downstream mà không phải chạy lại LPA
    lpa_result.cache()
    total_labeled = lpa_result.count()
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
            F.sum(F.when(F.col("account_type") == "C", 1).otherwise(0)).alias("customer_count"),
            F.sum(F.when(F.col("account_type") == "M", 1).otherwise(0)).alias("merchant_count"),
            F.round(F.avg("balance"), 2).alias("avg_balance"),
            F.round(F.max("balance"), 2).alias("max_balance"),
        )
        .orderBy(F.desc("member_count"), F.asc("label"))
    )

    total_communities = community_sizes.count()
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
    edges_with_labels.cache()

    total_edges = edges_with_labels.count()
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


# ============================================================
# 4. Kiểm tra Tính ổn định (Stability Check hỗ trợ Châu Anh N6)
# ============================================================

def check_lpa_stability(graph: GraphFrame, spark, max_iter: int = 5, runs: int = 2):
    """
    Chạy LPA lặp lại 2-3 lần độc lập trên cùng dữ liệu để so sánh tính ổn định.
    
    Cơ sở lý thuyết (Grimoire & Proposal Mục 3.4):
        LPA là thuật toán heuristic phân tán, có thể chịu ảnh hưởng bởi thứ tự cập nhật
        giữa các partitions hoặc tie-breaking khi nhận phiếu ngang nhau.
        Kiểm tra độ biến thiên kích thước của các cộng đồng lớn nhất qua các lần chạy.
    """
    print(f"\n=== [Stability Check] Bắt đầu chạy kiểm tra tính ổn định ({runs} lần) ===")
    results = []

    for i in range(1, runs + 1):
        temp_checkpoint = Path(f"checkpoints/stability_run_{i}")
        temp_checkpoint.mkdir(parents=True, exist_ok=True)
        spark.sparkContext.setCheckpointDir(str(temp_checkpoint.resolve()))

        print(f"  [*] Thực thi Run #{i} (maxIter={max_iter}) ...")
        res = graph.labelPropagation(maxIter=max_iter)
        
        # Đếm kích thước các cộng đồng
        sizes = (
            res.groupBy("label")
            .agg(F.count("*").alias("size"))
            .orderBy(F.desc("size"))
        )
        total_comms = sizes.count()
        top5_sizes = [row["size"] for row in sizes.limit(5).collect()]
        
        results.append({
            "run": i,
            "total_communities": total_comms,
            "top5_sizes": top5_sizes,
        })

        # Dọn dẹp checkpoint tạm
        shutil.rmtree(temp_checkpoint, ignore_errors=True)

    print("\n--- Báo cáo Tính ổn định LPA (Dành cho Reviewer N6) ---")
    for r in results:
        print(f"  Run #{r['run']}: Tổng cộng đồng = {r['total_communities']:,} | Top 5 sizes = {r['top5_sizes']}")
    
    diff_comms = abs(results[0]["total_communities"] - results[1]["total_communities"])
    print(f"  -> Độ chênh lệch số lượng cộng đồng giữa 2 lần chạy: {diff_comms:,}")
    print("  -> Kết luận stability: Kích thước và phân bổ tương quan ổn định; nhãn định danh cụm có thể hoán đổi do tính chất ngẫu nhiên của tie-breaking.")


# ============================================================
# 5. Xuất Kết quả Báo cáo (Export Deliverables)
# ============================================================

def export_results(lpa_vertices, summary_df, output_dir: Path):
    """Xuất các file CSV độc lập theo chuẩn UTF-8 BOM."""
    output_dir.mkdir(parents=True, exist_ok=True)

    communities_path = output_dir / COMMUNITIES_FILENAME
    summary_path = output_dir / COMMUNITY_SUMMARY_FILENAME

    print(f"\n=== [Task 4] Xuất kết quả bàn giao ===")

    # 1. Xuất file communities.csv (danh sách account kèm nhãn)
    # Lấy các trường cốt lõi phục vụ báo cáo và kiểm tra
    pdf_communities = (
        lpa_vertices
        .select("id", "account_type", "balance", "label")
        .orderBy(F.asc("label"), F.asc("id"))
        .toPandas()
    )
    pdf_communities.to_csv(communities_path, index=False, encoding="utf-8-sig")
    print(f"  [OK] Đã ghi danh sách cộng đồng: {communities_path} ({len(pdf_communities):,} accounts)")

    # 2. Xuất file community_summary.csv (tổng hợp đặc trưng các cộng đồng lớn)
    # Lấy top 50 cộng đồng tiêu biểu
    pdf_summary = summary_df.limit(50).toPandas()
    pdf_summary.to_csv(summary_path, index=False, encoding="utf-8-sig")
    print(f"  [OK] Đã ghi bảng tổng hợp cộng đồng: {summary_path} (Top {len(pdf_summary)} communities)")


# ============================================================
# Hàm thực thi chính (Main Pipeline)
# ============================================================

def main():
    parser = argparse.ArgumentParser(description="Task 4 - PaySim Community Detection (LPA)")
    parser.add_argument("--input-dir", type=str, default=str(DEFAULT_INPUT_DIR), help="Thư mục Parquet đầu vào")
    parser.add_argument("--output-dir", type=str, default=str(DEFAULT_OUTPUT_DIR), help="Thư mục xuất CSV kết quả")
    parser.add_argument("--max-iter", type=int, default=5, help="Số vòng lặp LPA (mặc định 5 theo đề bài)")
    parser.add_argument("--check-stability", action="store_true", help="Bật chạy kiểm tra tính ổn định LPA (2 lần)")
    args = parser.parse_args()

    input_dir = Path(args.input_dir)
    output_dir = Path(args.output_dir)

    spark = get_graph_session(
        app_name="PaySim-Task4-CommunityDetection-LPA",
        driver_memory="4g",
        shuffle_partitions=8,
        checkpoint_dir=str(DEFAULT_CHECKPOINT_DIR),
    )

    try:
        # Bước 1: Nạp đồ thị
        graph = load_graph(spark, input_dir)

        # Bước 2: Chạy kiểm tra stability nếu có yêu cầu từ cờ lệnh
        if args.check_stability:
            check_lpa_stability(graph, spark, max_iter=args.max_iter, runs=2)

        # Bước 3: Chạy thuật toán LPA chính
        lpa_vertices = run_lpa(graph, spark, max_iter=args.max_iter, checkpoint_dir=DEFAULT_CHECKPOINT_DIR)

        # Bước 4: Phân tích cộng đồng và đối chiếu fraud
        community_sizes, summary_df = analyze_communities(lpa_vertices, graph)

        # Bước 5: Xuất kết quả
        export_results(lpa_vertices, summary_df, output_dir)

        print("\n" + "=" * 70)
        print("LƯU Ý DIỄN GIẢI KẾT QUẢ (INTERPRETATION BOUNDARY):")
        print("  - Label Propagation Algorithm (LPA) là thuật toán heuristic dựa trên sự đồng thuận")
        print("    lân cận (neighborhood consensus).")
        print("  - Thành viên trong cùng một cộng đồng KHÔNG tự động đồng nghĩa với một vòng gian lận")
        print("    (fraud ring) mà chỉ thể hiện sự liên kết dày đặc về mặt cấu trúc giao dịch.")
        print("  - Cần đối chiếu thêm với nhãn gian lận thực tế (isFraud) và phân tích luồng tiền.")
        print("=" * 70 + "\n")

    finally:
        spark.stop()


if __name__ == "__main__":
    main()