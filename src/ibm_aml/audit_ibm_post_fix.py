"""
File: audit_ibm_post_fix.py
Muc dich: Do luong chinh xac 100% so lieu thuc nghiem sau khi fix loi Bank ID:
  1. Dung luong thuc te tren dia (MB) cua vertices.parquet va edges.parquet.
  2. So luong giao dich gian lan (isFraud == 1) trong ban sample ~100k canh.
  3. Kiem chung chu trinh 3 dinh (3-node cycle):
     - Dem so giao dich chu trinh trong file kich ban goc (HI-Small_Patterns.txt),
       PHAN THEO DO DAI CHU TRINH (vi CYCLE pattern trong dataset nay co the dai
       toi 10 hop, khong phai tat ca deu la 3-node cycle).
     - Chay truy van Motif thuc te tren GraphFrame de dem so chu trinh 3 dinh thuc te.
"""

import os
import sys
from pyspark.sql import functions as F

sys.path.insert(0, os.path.abspath("."))
from src.common.spark_session import get_graph_session
from src.common.graph_utils import load_graph


def get_dir_size_mb(path: str) -> float:
    """Do dung luong thuc te cua thu muc Parquet tren o cung."""
    total_bytes = 0
    for dirpath, _, filenames in os.walk(path):
        for f in filenames:
            total_bytes += os.path.getsize(os.path.join(dirpath, f))
    return total_bytes / (1024 * 1024)


def audit_patterns_txt(patterns_path: str):
    """
    Doc file kich ban goc va tra ve:
      - cycle_blocks: tong so chuoi kich ban CYCLE duoc cay (moi chuoi = 1 vong
        lap rua tien, BAT KY do dai bao nhieu hop)
      - cycle_tx_total: tong so dong giao dich nam trong TAT CA chuoi CYCLE
      - blocks_by_length: dict {do dai chu trinh (so hop): so chuoi co do dai do}
        Dung de tach rieng chu trinh DUNG 3 dinh (khop Task 3) khoi chu trinh dai
        hon. LUU Y: theo tai lieu cong khai ve AMLworld/HI-Small, CYCLE pattern
        duoc cay co do dai tu 3 den toi da 10 hop -- KHONG phai tat ca deu la
        3-node cycle, nen so sanh truc tiep blocks/cycle_tx_total voi ket qua
        motif 3-node se khong khop 1:1. So nen dung de doi chieu Task 3 la
        blocks_by_length.get(3, 0).
    """
    if not os.path.exists(patterns_path):
        return None

    cycle_blocks = 0
    cycle_tx_total = 0
    blocks_by_length = {}
    in_cycle = False
    current_len = 0

    def _close_block():
        nonlocal current_len
        if in_cycle and current_len > 0:
            blocks_by_length[current_len] = blocks_by_length.get(current_len, 0) + 1
        current_len = 0

    with open(patterns_path, "r", encoding="utf-8") as f:
        for line in f:
            line_str = line.strip()

            if "BEGIN LAUNDERING ATTEMPT - CYCLE" in line_str:
                in_cycle = True
                cycle_blocks += 1
                current_len = 0
                continue
            elif "BEGIN LAUNDERING ATTEMPT" in line_str:
                # A non-CYCLE pattern block is starting -- close out whatever
                # CYCLE block (if any) was open before this line.
                _close_block()
                in_cycle = False
                continue
            elif "END LAUNDERING ATTEMPT" in line_str:
                _close_block()
                in_cycle = False
                continue

            if in_cycle and line_str and not line_str.startswith("#"):
                cycle_tx_total += 1
                current_len += 1

        _close_block()  # in case the file ends mid-block with no explicit END line

    return cycle_blocks, cycle_tx_total, blocks_by_length


def main():
    print("=" * 65)
    print("BAT DAU DO LUONG SO LIEU THUC NGHIEM IBM AML (POST-FIX)")
    print("=" * 65)

    # -----------------------------------------------------------------
    # VAN DE 1: DO DUNG LUONG FILE PARQUET TREN DIA
    # -----------------------------------------------------------------
    full_v_dir = "data/processed/ibm_aml/vertices.parquet"
    full_e_dir = "data/processed/ibm_aml/edges.parquet"
    sample_v_dir = "data/processed/sample/ibm_aml/vertices.parquet"
    sample_e_dir = "data/processed/sample/ibm_aml/edges.parquet"

    v_size = get_dir_size_mb(full_v_dir)
    e_size = get_dir_size_mb(full_e_dir)
    sample_v_size = get_dir_size_mb(sample_v_dir)
    sample_e_size = get_dir_size_mb(sample_e_dir)

    print("\n[1] DUNG LUONG PARQUET TREN O CUNG (DISK FOOTPRINT):")
    print(f"    - Full Vertices Parquet: {v_size:.2f} MB")
    print(f"    - Full Edges Parquet:    {e_size:.2f} MB")
    print(f"    - Tong Full Dataset:     {v_size + e_size:.2f} MB")
    print(f"    - Sample Vertices:       {sample_v_size:.2f} MB")
    print(f"    - Sample Edges:          {sample_e_size:.2f} MB")

    # -----------------------------------------------------------------
    # VAN DE 2: DO SO GIAO DICH GIAN LAN TRONG BAN SAMPLE
    # -----------------------------------------------------------------
    spark = get_graph_session("Audit-IBM-Metrics")

    sample_graph = load_graph(spark, "data/processed/sample/ibm_aml")
    sample_graph.vertices.cache()
    sample_graph.edges.cache()

    sample_total_v = sample_graph.vertices.count()
    sample_total_edges = sample_graph.edges.count()  # <- single consistent name, used below
    sample_fraud_count = sample_graph.edges.filter(F.col("isFraud") == 1).count()

    print("\n[2] THONG KE BAN MAU THU NGHIEM (SAMPLE SUBGRAPH):")
    print(f"    - Tong so Dinh sample:   {sample_total_v:,}")
    print(f"    - Tong so Canh sample:   {sample_total_edges:,}")
    print(f"    - Canh gian lan (Fraud): {sample_fraud_count:,} "
          f"(Ty le: {sample_fraud_count / sample_total_edges:.4%})")

    # -----------------------------------------------------------------
    # VAN DE 3: KIEM CHUNG CHU TRINH 3 DINH (MOTIF 3-CYCLE)
    # -----------------------------------------------------------------
    patterns_file = "data/raw/ibm_aml/HI-Small_Patterns.txt"
    pattern_stats = audit_patterns_txt(patterns_file)

    print("\n[3] KIEM CHUNG CHU TRINH (3-NODE CYCLE):")
    if pattern_stats:
        blocks, total_tx, by_length = pattern_stats
        three_hop_blocks = by_length.get(3, 0)

        print("    a) Trong kich ban cay san (HI-Small_Patterns.txt):")
        print(f"       + Tong so chuoi kich ban CYCLE (moi do dai): {blocks} chuoi")
        print(f"       + Tong so dong giao dich trong cac chuoi CYCLE: {total_tx} giao dich")
        print("       + Phan bo theo do dai chu trinh (so hop -> so chuoi):")
        for length in sorted(by_length):
            print(f"           {length}-hop: {by_length[length]} chuoi")
        print(f"       + CHU TRINH DUNG 3 DINH (so nen doi chieu voi Task 3): "
              f"{three_hop_blocks} chuoi")
        print("       (Luu y: CYCLE pattern trong HI-Small co the dai toi 10 hop --")
        print(f"        KHONG ky vong {blocks} hoac {total_tx} khop truc tiep voi so")
        print("        chu trinh 3 dinh do duoc o buoc (b) duoi day. Con so nen dung")
        print(f"        de so sanh la {three_hop_blocks}.)")
    else:
        print("    a) Khong tim thay HI-Small_Patterns.txt de doi chieu kich ban.")
        print("       (File nay co the chua duoc tai -- README chi dinh tai Trans.csv")
        print("        va accounts.csv, khong tai Patterns.txt. Can tai rieng tu Kaggle.)")

    print("\n    b) Chay truy van Motif Finding thuc te tren do thi da sua (Full Graph)...")
    full_graph = load_graph(spark, "data/processed/ibm_aml")
    full_graph.vertices.cache()
    full_graph.edges.cache()  # reused by both queries below -- avoid re-reading Parquet twice

    # 1. Truy van chu trinh thuan tuy tren toan bo canh gian lan (Ground-truth Fraud Subgraph)
    fraud_graph = full_graph.filterEdges("isFraud = 1")
    fraud_cycles = fraud_graph.find("(a)-[e1]->(b); (b)-[e2]->(c); (c)-[e3]->(a)") \
        .filter("a.id != b.id AND b.id != c.id AND a.id != c.id")
    fraud_cycle_count = fraud_cycles.count()
    print(f"       + So chu trinh 3 dinh trong mang luoi gian lan (isFraud=1): "
          f"{fraud_cycle_count:,} chu trinh")

    # 2. Truy van chu trinh rua tien USD gia tri cao (>10k) theo dung Task 3
    usd_cycles = full_graph.find("(a)-[e1]->(b); (b)-[e2]->(c); (c)-[e3]->(a)") \
        .filter("a.id != b.id AND b.id != c.id AND a.id != c.id") \
        .filter("e1.payment_currency = 'US Dollar' AND e2.payment_currency = 'US Dollar' "
                "AND e3.payment_currency = 'US Dollar'") \
        .filter("e1.amount > 10000 AND e2.amount > 10000 AND e3.amount > 10000")
    usd_cycle_count = usd_cycles.count()
    print(f"       + So chu trinh 3 dinh USD (> $10,000) phuc vu Task 3: "
          f"{usd_cycle_count:,} chu trinh")

    print("\n" + "=" * 65)
    print("HOAN TAT DO LUONG. DUNG CAC CON SO TREN DE CAP NHAT TAI LIEU.")
    print("=" * 65)

    spark.stop()


if __name__ == "__main__":
    main()
