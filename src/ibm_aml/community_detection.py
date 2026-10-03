"""Task 4 - Community Detection (IBM AML HI-Small).

Người phụ trách: N5 & N3/N4 .
Part B — Task 4 IBM AML Community Detection (Mục tiêu mở rộng).

Input:
    data/processed/sample/ibm_aml/
Output:
    results/ibm_aml/communities.csv
    results/ibm_aml/community_summary.csv

Mục tiêu kỹ thuật:
    1. Cấu hình setCheckpointDir riêng biệt: checkpoints/ibm_aml_lpa.
    2. Chạy GraphFrames labelPropagation(maxIter=5) trên đồ thị ngân hàng đa tài khoản.
    3. Thống kê phân bố cộng đồng (kích thước, phân bổ liên ngân hàng vs nội bộ ngân hàng).
    4. Đối chiếu nhãn rửa tiền (isFraud / Is Laundering == 1) để tìm các cụm rủi ro cao.
    5. Xuất báo cáo CSV phục vụ việc so sánh cấu trúc mạng lưới giữa PaySim và IBM AML.
"""

import argparse
import os
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

DEFAULT_INPUT_DIR = Path("data/processed/sample/ibm_aml")
DEFAULT_OUTPUT_DIR = Path("results/ibm_aml")
DEFAULT_CHECKPOINT_DIR = Path("checkpoints/ibm_aml_lpa")

COMMUNITIES_FILENAME = "communities.csv"
COMMUNITY_SUMMARY_FILENAME = "community_summary.csv"


# ============================================================
# 1. Tải Đồ thị (Graph Loading)
# ============================================================

def load_graph(spark, input_dir: Path) -> GraphFrame:
    """Đọc Vertices và Edges Parquet của IBM AML sample để tạo GraphFrame."""
    vertices_path = input_dir / "vertices.parquet"
    edges_path = input_dir / "edges.parquet"

    if not vertices_path.exists() or not edges_path.exists():
        raise FileNotFoundError(
            f"Không tìm thấy Parquet tại {input_dir}. "
            "Vui lòng chạy IBM AML ETL trước khi thực hiện Task 4."
        )

    vertices = spark.read.parquet(str(vertices_path))
    edges = spark.read.parquet(str(edges_path))

    print("\n=== [Task 4] Nạp Đồ thị IBM AML (HI-Small) ===")
    print(f"  Thư mục dữ liệu: {input_dir}")
    print(f"  Số đỉnh (Vertices): {vertices.count():,}")
    print(f"  Số cạnh (Edges):    {edges.count():,}")

    return GraphFrame(vertices, edges)


# ============================================================
# 2. Thuật toán LPA & Quản lý Checkpoint
# ============================================================

def run_lpa(graph: GraphFrame, spark, max_iter: int = 5, checkpoint_dir: Path = DEFAULT_CHECKPOINT_DIR):
    """
    Thực thi Label Propagation Algorithm (LPA) trên IBM AML graph.
    """
    checkpoint_dir.mkdir(parents=True, exist_ok=True)
    spark.sparkContext.setCheckpointDir(str(checkpoint_dir.resolve()))

    print(f"\n[*] Đang thực thi LPA trên IBM AML (maxIter={max_iter}) với checkpoint tại: {checkpoint_dir} ...")
    lpa_result = graph.labelPropagation(maxIter=max_iter)

    lpa_result.cache()
    total_labeled = lpa_result.count()
    print(f"[+] LPA IBM AML hoàn tất. Tổng số đỉnh đã gán nhãn: {total_labeled:,}")

    return lpa_result


# ============================================================
# 3. Phân tích Thống kê Cộng đồng IBM AML
# ============================================================

def analyze_communities(lpa_vertices, graph: GraphFrame, top_n: int = 15):
    """
    Phân tích đặc trưng cộng đồng trong dữ liệu ngân hàng IBM AML:
      - Kích thước cộng đồng và số ngân hàng tham gia (bank diversity).
      - Tỷ lệ giao dịch nội bộ cộng đồng vs liên cộng đồng.
      - Phân bổ giao dịch rửa tiền (Is Laundering / isFraud).
    """
    print("\n=== [Task 4] Phân tích Thống kê Cộng đồng IBM AML ===")

    # Kiểm tra cột có sẵn trong vertices
    has_bank = "bank_id" in lpa_vertices.columns

    agg_exprs = [F.count("*").alias("member_count")]
    if has_bank:
        agg_exprs.append(F.countDistinct("bank_id").alias("unique_banks_count"))
    if "balance" in lpa_vertices.columns:
        agg_exprs.append(F.round(F.avg("balance"), 2).alias("avg_balance"))

    community_sizes = (
        lpa_vertices
        .groupBy("label")
        .agg(*agg_exprs)
        .orderBy(F.desc("member_count"), F.asc("label"))
    )

    total_communities = community_sizes.count()
    singleton_count = community_sizes.filter(F.col("member_count") == 1).count()
    multi_member_count = total_communities - singleton_count

    print(f"  Tổng số cộng đồng phát hiện: {total_communities:,}")
    print(f"  Số cộng đồng đơn lẻ (Singletons - size=1): {singleton_count:,} ({singleton_count / total_communities * 100:.1f}%)")
    print(f"  Số cộng đồng có từ 2 thành viên trở lên:  {multi_member_count:,} ({multi_member_count / total_communities * 100:.1f}%)")

    # B. Gán nhãn cộng đồng vào Edges
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
    print(f"    Giao dịch nội bộ cộng đồng: {internal_count:,} ({internal_count / total_edges * 100:.1f}%)")
    print(f"    Giao dịch liên cộng đồng:    {cross_count:,} ({cross_count / total_edges * 100:.1f}%)")

    # C. Thống kê rửa tiền theo cộng đồng nguồn (src_label)
    fraud_col = "isFraud" if "isFraud" in edges.columns else "isLaundering"

    fraud_stats = (
        edges_with_labels
        .groupBy("src_label")
        .agg(
            F.count("*").alias("total_tx_count"),
            F.sum("amount").alias("total_tx_amount"),
            F.sum(fraud_col).alias("laundering_tx_count"),
            F.sum(F.when(F.col("src_label") == F.col("dst_label"), 1).otherwise(0)).alias("internal_tx_count"),
            F.sum(F.when((F.col("src_label") == F.col("dst_label")) & (F.col(fraud_col) == 1), 1).otherwise(0)).alias("internal_laundering_count"),
        )
        .withColumnRenamed("src_label", "label")
    )

    summary_df = (
        community_sizes
        .join(fraud_stats, on="label", how="left")
        .na.fill(0, subset=["total_tx_count", "laundering_tx_count", "internal_tx_count", "internal_laundering_count", "total_tx_amount"])
        .withColumn(
            "laundering_rate",
            F.round(F.col("laundering_tx_count") / F.when(F.col("total_tx_count") == 0, 1).otherwise(F.col("total_tx_count")), 4)
        )
        .orderBy(F.desc("member_count"), F.asc("label"))
    )

    print(f"\n=== Top {top_n} Cộng đồng IBM AML lớn nhất ===")
    summary_df.show(top_n, truncate=False)

    # Đánh giá cụm rửa tiền
    laundering_hotspots = summary_df.filter(F.col("laundering_tx_count") > 0).orderBy(F.desc("laundering_tx_count"))
    laundering_community_count = laundering_hotspots.count()
    print(f"\n  Số lượng cộng đồng chứa giao dịch rửa tiền (Laundering): {laundering_community_count:,}")
    if laundering_community_count > 0:
        print("  Top 5 cộng đồng tập trung nhiều giao dịch rửa tiền nhất:")
        laundering_hotspots.show(5, truncate=False)

    return community_sizes, summary_df


# ============================================================
# 4. Xuất Kết quả Báo cáo (Export Deliverables)
# ============================================================

def export_results(lpa_vertices, summary_df, output_dir: Path):
    """Xuất các file CSV độc lập theo chuẩn UTF-8 BOM."""
    output_dir.mkdir(parents=True, exist_ok=True)

    communities_path = output_dir / COMMUNITIES_FILENAME
    summary_path = output_dir / COMMUNITY_SUMMARY_FILENAME

    print(f"\n=== [Task 4] Xuất kết quả bàn giao IBM AML ===")

    # 1. Xuất file communities.csv
    export_cols = ["id", "label"]
    if "bank_id" in lpa_vertices.columns:
        export_cols.insert(1, "bank_id")
    if "account_type" in lpa_vertices.columns:
        export_cols.append("account_type")

    pdf_communities = (
        lpa_vertices
        .select(*export_cols)
        .orderBy(F.asc("label"), F.asc("id"))
        .toPandas()
    )
    pdf_communities.to_csv(communities_path, index=False, encoding="utf-8-sig")
    print(f"  [OK] Đã ghi danh sách cộng đồng IBM AML: {communities_path} ({len(pdf_communities):,} accounts)")

    # 2. Xuất file community_summary.csv
    pdf_summary = summary_df.limit(50).toPandas()
    pdf_summary.to_csv(summary_path, index=False, encoding="utf-8-sig")
    print(f"  [OK] Đã ghi bảng tổng hợp cộng đồng IBM AML: {summary_path} (Top {len(pdf_summary)} communities)")


# ============================================================
# Hàm thực thi chính (Main Pipeline)
# ============================================================

def main():
    parser = argparse.ArgumentParser(description="Task 4 - IBM AML Community Detection (LPA)")
    parser.add_argument("--input-dir", type=str, default=str(DEFAULT_INPUT_DIR), help="Thư mục Parquet đầu vào IBM AML")
    parser.add_argument("--output-dir", type=str, default=str(DEFAULT_OUTPUT_DIR), help="Thư mục xuất CSV kết quả")
    parser.add_argument("--max-iter", type=int, default=5, help="Số vòng lặp LPA")
    args = parser.parse_args()

    input_dir = Path(args.input_dir)
    output_dir = Path(args.output_dir)

    spark = get_graph_session(
        app_name="IBM-AML-Task4-CommunityDetection-LPA",
        driver_memory="4g",
        shuffle_partitions=8,
        checkpoint_dir=str(DEFAULT_CHECKPOINT_DIR),
    )

    try:
        # 1. Nạp đồ thị IBM AML
        graph = load_graph(spark, input_dir)

        # 2. Chạy thuật toán LPA
        lpa_vertices = run_lpa(graph, spark, max_iter=args.max_iter, checkpoint_dir=DEFAULT_CHECKPOINT_DIR)

        # 3. Phân tích thống kê đặc trưng cộng đồng
        community_sizes, summary_df = analyze_communities(lpa_vertices, graph)

        # 4. Xuất kết quả CSV
        export_results(lpa_vertices, summary_df, output_dir)

        print("\n" + "=" * 70)
        print("LƯU Ý SO SÁNH DATASET (CROSS-DATASET INSIGHT):")
        print("  - Khác với PaySim chỉ có luồng 1 chiều (0 cycle), đồ thị IBM AML chứa nhiều chu trình")
        print("    và topology mạng lưới phức tạp (fan-in, fan-out, gather-scatter).")
        print("  - Sự phân mảnh hay tập trung của các cộng đồng trong IBM AML cung cấp cơ sở đối chiếu")
        print("    rất giá trị cho Báo cáo Part B.")
        print("=" * 70 + "\n")

    finally:
        spark.stop()


if __name__ == "__main__":
    main()