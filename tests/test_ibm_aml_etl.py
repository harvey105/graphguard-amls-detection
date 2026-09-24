"""
File: tests/test_ibm_aml_etl.py
Role: Person 2 (Data Engineering Lead)
Description: 
  Automated Integration & Unit Test Suite for IBM AML (HI-Small) ETL Pipeline.
  Verifies schema conformance, cardinality, referential integrity, bank ID normalization,
  successful matching of formerly padded banks (e.g. 001241 -> 1241), self-loops,
  epoch time range, and multi-currency distributions.

Usage:
  python tests/test_ibm_aml_etl.py                    # Fast mode: tests persisted Parquet (< 5s)
  python tests/test_ibm_aml_etl.py --sample            # Prototype mode: tests ~100k sample graph
  python tests/test_ibm_aml_etl.py --from-raw          # Deep ETL mode: runs functions directly on raw CSV
  python tests/test_ibm_aml_etl.py --from-raw --sample # Build from raw, subsample to ~100k edges
"""

import os
import sys
import argparse
from pyspark.sql import DataFrame, SparkSession
from pyspark.sql import functions as F
from graphframes import GraphFrame

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from src.common.spark_session import get_graph_session
from src.common.graph_utils import load_graph, check_integrity
from src.ibm_aml.etl import build_ibm_edges, build_ibm_vertices

# Ground-truth constants đã nghiệm thu (Edges, Fraud, Loops giữ nguyên)
# Cập nhật số liệu thực chứng chính xác sau khi chuẩn hóa Bank ID:
EXPECTED_VERTEX_COUNT = 518_581   # 100% khớp với số lượng tài khoản trong accounts.csv
EXPECTED_EDGE_COUNT = 5_078_345
EXPECTED_FRAUD_COUNT = 5_177
EXPECTED_SELF_LOOPS = 591_212
EXPECTED_CURRENCY_COUNT = 15
EXPECTED_STEP_MIN = 1_661_965_200
EXPECTED_STEP_MAX = 1_663_492_680


def induce_sample(vertices_df: DataFrame, edges_df: DataFrame, target_edges: int = 100_000, seed: int = 42):
    """Tạo subgraph mẫu ~100k cạnh tự đóng (self-contained) khi dùng --from-raw --sample."""
    total_edges = edges_df.count()
    fraction = min(1.0, target_edges / total_edges)
    sample_edges = edges_df.sample(withReplacement=False, fraction=fraction, seed=seed).cache()
    sample_ids = sample_edges.select(F.col("src").alias("id")) \
        .union(sample_edges.select(F.col("dst").alias("id"))).distinct()
    sample_vertices = vertices_df.join(sample_ids, on="id", how="inner").cache()
    return sample_vertices, sample_edges


def run_tests(spark: SparkSession, vertices_df: DataFrame, edges_df: DataFrame, is_sample: bool = False):
    print("\n" + "=" * 65)
    print(f"IBM AML ETL VERIFICATION SUITE {'[SAMPLE MODE]' if is_sample else '[FULL DATASET]'}")
    print("=" * 65)

    test_results = {}

    vertices_df.cache()
    edges_df.cache()

    v_count = vertices_df.count()
    e_count = edges_df.count()

    # -------------------------------------------------------------
    # 1. KIỂM TRA SCHEMA
    # -------------------------------------------------------------
    expected_v_cols = {"id", "account_type", "bank_name", "balance"}
    expected_e_cols = {
        "src", "dst", "amount", "amount_received",
        "payment_currency", "receiving_currency", "step", "type", "isFraud"
    }

    v_schema_ok = expected_v_cols.issubset(set(vertices_df.columns))
    e_schema_ok = expected_e_cols.issubset(set(edges_df.columns))

    test_results["Vertices Schema Conformance"] = (
        v_schema_ok, f"Columns: {sorted(list(expected_v_cols))}"
    )
    test_results["Edges Schema Conformance"] = (
        e_schema_ok, f"Columns: {sorted(list(expected_e_cols))}"
    )

    # -------------------------------------------------------------
    # 2. KIỂM TRA NULL + TOÀN VẸN THAM CHIẾU (GRAPH INTEGRITY)
    # -------------------------------------------------------------
    graph = GraphFrame(vertices_df, edges_df)
    integrity = check_integrity(graph, verbose=False)

    test_results["No Null Vertex IDs"] = (
        integrity["null_vertices"] == 0, f"{integrity['null_vertices']} nulls"
    )
    test_results["No Null Edge Endpoints"] = (
        integrity["null_edges"] == 0, f"{integrity['null_edges']} nulls"
    )
    test_results["Referential Integrity (0 Dangling, both sides)"] = (
        integrity["dangling_edges"] == 0,
        f"src-side: {integrity['dangling_src']}, dst-side: {integrity['dangling_dst']}"
    )

    null_v_type = vertices_df.filter(F.col("account_type").isNull()).count()
    test_results["No Null Account Types"] = (null_v_type == 0, f"{null_v_type} nulls")

    null_e_amount = edges_df.filter(F.col("amount").isNull()).count()
    test_results["No Null Edge Amount"] = (null_e_amount == 0, f"{null_e_amount} nulls")

    # -------------------------------------------------------------
    # 3. KIỂM TRA CHUẨN HÓA BANK ID & KHỚP TÀI KHOẢN (LOGIC MỚI CHUẨN XÁC)
    # -------------------------------------------------------------
    # Kiểm tra 1: Không còn bất kỳ ID nào bị đệm số 0 thừa ở đầu (vd: '001241_...' phải thành '1241_...')
    unnormalized_edges = edges_df.filter(F.col("src").rlike("^0[0-9]+_") | F.col("dst").rlike("^0[0-9]+_")).count()
    unnormalized_vertices = vertices_df.filter(F.col("id").rlike("^0[0-9]+_")).count()
    no_leading_zeros = (unnormalized_edges == 0 and unnormalized_vertices == 0)

    test_results["Bank IDs Cleanly Normalized (No Leading Zeros)"] = (
        no_leading_zeros,
        f"Unnormalized found: {unnormalized_vertices} vertices, {unnormalized_edges} edges"
    )

    # Kiểm tra 2: Chứng minh các ngân hàng vốn có số 0 đầu trong raw CSV (như 1241 vốn là 001241, 701 vốn là 00701)
    # NAY ĐÃ KHỚP THÀNH CÔNG với accounts.csv (không bị đẩy vào External/Unknown)
    sample_banks = ["1241", "701", "1244", "31125"]
    matched_padded_banks = vertices_df.filter(
        (F.split(F.col("id"), "_").getItem(0).isin(sample_banks)) & 
        (F.col("account_type") != "External/Unknown")
    ).count()

    test_results["Formerly-Padded Banks Successfully Matched"] = (
        matched_padded_banks > 0 or is_sample,
        f"Found {matched_padded_banks:,} vertices from banks {sample_banks} correctly resolved to real account_type"
    )

    # -------------------------------------------------------------
    # 4. KIỂM TRA SỐ LƯỢNG VÀ MIỀN GIÁ TRỊ (CARDINALITY & DOMAIN)
    # -------------------------------------------------------------
    if not is_sample:
        # Số cạnh phải tuyệt đối bằng raw CSV
        test_results["Exact Edge Cardinality"] = (
            e_count == EXPECTED_EDGE_COUNT, f"{e_count:,} vs expected {EXPECTED_EDGE_COUNT:,}"
        )

        # Số lượng gian lận
        fraud_count = edges_df.filter(F.col("isFraud") == 1).count()
        test_results["Ground-truth Fraud Count"] = (
            fraud_count == EXPECTED_FRAUD_COUNT, f"{fraud_count:,} vs expected {EXPECTED_FRAUD_COUNT:,}"
        )

        # Số lượng đỉnh hợp lệ: phải có ít nhất 518,581 đỉnh nội bộ từ accounts.csv
        test_results["Valid Vertex Population (>518k)"] = (
            v_count >= 518_581, f"Total unique vertices: {v_count:,}"
        )

        # Vòng lặp tự thân
        self_loops = integrity["self_loops"]
        test_results["Self-loop Invariant"] = (
            self_loops == EXPECTED_SELF_LOOPS, f"{self_loops:,} self-loops (expected {EXPECTED_SELF_LOOPS:,})"
        )

        # Số loại tiền tệ
        distinct_curr = edges_df.select("payment_currency").distinct().count()
        test_results["Multi-currency Invariant"] = (
            distinct_curr == EXPECTED_CURRENCY_COUNT, f"{distinct_curr} distinct payment currencies"
        )

        # Dải thời gian epoch
        step_bounds = edges_df.agg(F.min("step").alias("mn"), F.max("step").alias("mx")).collect()[0]
        step_ok = (step_bounds["mn"] == EXPECTED_STEP_MIN and step_bounds["mx"] == EXPECTED_STEP_MAX)
        test_results["Epoch Time Range (step, NOT 1-744)"] = (
            step_ok, f"min={step_bounds['mn']}, max={step_bounds['mx']} "
                     f"(expected {EXPECTED_STEP_MIN}..{EXPECTED_STEP_MAX})"
        )
    else:
        test_results["Sample Size Check"] = (
            e_count > 0 and v_count > 0, f"Sample: {v_count:,} vertices, {e_count:,} edges"
        )

    # -------------------------------------------------------------
    # IN KẾT QUẢ TỔNG HỢP DATA QUALITY REPORT
    # -------------------------------------------------------------
    all_passed = True
    print("\n" + "-" * 65)
    print("DETAILED VERIFICATION RESULTS")
    print("-" * 65)
    for name, (passed, detail) in test_results.items():
        status = "PASS" if passed else "FAIL"
        if not passed:
            all_passed = False
        print(f"  [{status}] {name:<50} : {detail}")
    print("-" * 65)

    if all_passed:
        print("[+] SUCCESS: Tat ca cac bai kiem thu IBM AML deu DAT CHUAN [PASS].")
    else:
        print("[-] FAILED: Co bai kiem tra that bai. Vui long kiem tra lai pipeline.")
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(description="Test Suite for IBM AML ETL")
    parser.add_argument("--sample", action="store_true", help="Chay test tren ban sample (~100k canh)")
    parser.add_argument("--from-raw", action="store_true", help="Chay test truc tiep ham ETL tu CSV tho")
    args = parser.parse_args()

    spark = get_graph_session(app_name="Test-IBM-AML-ETL")

    if args.from_raw:
        print("[*] Dang kiem thu truc tiep ham ETL tu CSV goc...")
        trans_path = "data/raw/ibm_aml/HI-Small_Trans.csv"
        acc_path = "data/raw/ibm_aml/HI-Small_accounts.csv"

        edges_df = build_ibm_edges(spark, trans_path).cache()
        vertices_df = build_ibm_vertices(spark, acc_path, edges_df)

        if args.sample:
            print("[*] --sample duoc yeu cau cung --from-raw: dang tao subgraph ~100k canh...")
            vertices_df, edges_df = induce_sample(vertices_df, edges_df)

        run_tests(spark, vertices_df, edges_df, is_sample=args.sample)
    else:
        target_dir = "data/processed/sample/ibm_aml" if args.sample else "data/processed/ibm_aml"
        print(f"[*] Dang nap Parquet tu: {target_dir}")
        graph = load_graph(spark, target_dir)
        run_tests(spark, graph.vertices, graph.edges, is_sample=args.sample)

    spark.stop()


if __name__ == "__main__":
    main()