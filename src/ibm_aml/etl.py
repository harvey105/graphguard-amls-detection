"""
File: src/ibm_aml/etl.py
Role: Person 2 (Data Engineering Lead)
Description:
  ETL Pipeline for IBM AML (HI-Small) dataset.
  Transforms raw CSVs into GraphGuard standard Parquet schema (Vertices & Edges).
  Implements composite keys (Bank_Account) and defensive vertex generation to
  guarantee 0 dangling edges.

QUAN TRONG -- khac biet ngu nghia so voi PaySim (doc truoc khi dung o Task 2-4):
  1. `step` o day la Unix epoch second (tu Timestamp that), KHONG PHAI chi so
     gio mo phong 1..744 nhu PaySim. Dung duoc cho so sanh thu tu (e1.step <
     e2.step van dung), nhung DUNG gia dinh gia tri nam trong [1, 744].
  2. `amount` = Amount Paid, GIU NGUYEN don vi tien te goc -- KHONG quy doi ve
     1 dong tien chung. File nay giu them cot `payment_currency` /
     `receiving_currency` de tham chieu. Bat ky filter amount > threshold nao
     o Task 3/4 PHAI loc theo currency truoc, neu khong se so sanh nham don
     vi (vd USD voi Yen).
  3. Du lieu co self-loop that (src == dst) -- khac PaySim (0 self-loop, da
     xac nhan Task 2.1). Xem so luong duoc in ra trong QUALITY REPORT.
"""

import os
import sys
from pyspark.sql import DataFrame, SparkSession
from pyspark.sql import functions as F
from pyspark.sql.types import (
    StructType, StructField, StringType, DoubleType, ShortType
)

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))
from src.common.spark_session import get_graph_session


def build_ibm_edges(spark: SparkSession, trans_csv_path: str) -> DataFrame:
    """Xay dung DataFrame Edges tu HI-Small_Trans.csv"""
    print(f"[*] Dang xu ly Edges tu: {trans_csv_path}")

    schema = StructType([
        StructField("Timestamp", StringType(), True),
        StructField("From Bank", StringType(), True),
        StructField("Account", StringType(), True),
        StructField("To Bank", StringType(), True),
        # Dat ten khong co dau cham: "Account.1" khien F.col("Account.1") bi
        # Spark hieu nham la truy cap truong long "1" ben trong struct
        # "Account" (dotted nested-field access), gay loi resolve. Doi ten
        # khong anh huong gia tri doc duoc, vi enforceSchema=true (mac dinh)
        # doc CSV theo VI TRI cot, khong theo ten header.
        StructField("Account_Dest", StringType(), True),
        StructField("Amount Received", DoubleType(), True),
        StructField("Receiving Currency", StringType(), True),
        StructField("Amount Paid", DoubleType(), True),
        StructField("Payment Currency", StringType(), True),
        StructField("Payment Format", StringType(), True),
        StructField("Is Laundering", ShortType(), True),
    ])

    raw_trans = spark.read.csv(trans_csv_path, header=True, schema=schema)

    # CHUAN HOA Bank ID: ep qua Long roi tra ve String truoc khi noi chuoi.
    # Ly do: StringType() (fix truoc do) chi dam bao Spark KHONG tu y lam mat
    # so 0 dau -- nhung khong dam bao Trans.csv va accounts.csv dung CHUNG 1
    # kieu dinh dang. Neu Trans.csv ghi "021174" con accounts.csv ghi "21174"
    # cho CUNG 1 ngan hang, composite key se KHONG BAO GIO khop du ca 2 deu
    # la StringType chinh xac. Ep qua Long xoa moi kieu dem so 0 mot cach
    # nhat quan tren ca 2 phia (edges va vertices), dam bao khop dung.
    from_bank_norm = F.col("From Bank").cast("long").cast("string")
    to_bank_norm = F.col("To Bank").cast("long").cast("string")

    edges_df = raw_trans.select(
        F.concat_ws("_", from_bank_norm, F.col("Account")).alias("src"),
        F.concat_ws("_", to_bank_norm, F.col("Account_Dest")).alias("dst"),
        F.col("Amount Paid").alias("amount"),
        # Giu them Amount Received + ca 2 currency de doi chieu/loc theo don
        # vi tien te sau nay -- KHONG duoc so sanh amount qua lai neu currency
        # khac nhau.
        F.col("Amount Received").alias("amount_received"),
        F.col("Payment Currency").alias("payment_currency"),
        F.col("Receiving Currency").alias("receiving_currency"),
        # Unix epoch second, KHONG PHAI hour-index nhu PaySim -- xem docstring
        F.unix_timestamp(F.col("Timestamp"), "yyyy/MM/dd HH:mm").cast("integer").alias("step"),
        F.col("Payment Format").alias("type"),
        F.col("Is Laundering").alias("isFraud"),
    )

    return edges_df


def build_ibm_vertices(spark: SparkSession, accounts_csv_path: str, edges_df: DataFrame) -> DataFrame:
    """
    Xay dung DataFrame Vertices tu HI-Small_accounts.csv.
    Ket hop ra soat canh (edges_df) de bo sung cac dinh vang mat (External nodes).
    """
    print(f"[*] Dang xu ly Vertices tu: {accounts_csv_path}")

    # Schema tuong minh -- KHONG dung inferSchema=True. Bank ID trong file nay
    # co the co so 0 dau (vd "012", xem HI-Small_Patterns.txt: From Bank =
    # "021174", To Bank = "012"). Neu de Spark tu suy kieu, cot toan chu so
    # se bi doan thanh kieu so va MAT so 0 dau khi cast lai string ("012" ->
    # 12 -> "12"), khien composite key voi edges_df ("012_...") KHONG BAO GIO
    # khop voi vertices_df ("12_..."). Day la bug nghiem trong nhat trong ban
    # goc: no khong lam assert dangling that bai (fallback-vertex logic se
    # am tham tao node "External/Unknown" trung lap) nen se khong bi phat
    # hien qua kiem tra thong thuong.
    accounts_schema = StructType([
        StructField("Bank Name", StringType(), True),
        StructField("Bank ID", StringType(), True),
        StructField("Account Number", StringType(), True),
        StructField("Entity ID", StringType(), True),
        StructField("Entity Name", StringType(), True),
    ])

    raw_acc = spark.read.csv(accounts_csv_path, header=True, schema=accounts_schema)

    # Chuan hoa GIONG HET phia edges (ep Long -> String) de bao dam khop
    # composite key bat ke Trans.csv/accounts.csv dung quy uoc dem so 0 khac
    # nhau cho cung 1 Bank ID.
    bank_id_norm = F.col("Bank ID").cast("long").cast("string")
    bank_id_cast_fail = raw_acc.filter(F.col("Bank ID").cast("long").isNull()).count()
    if bank_id_cast_fail > 0:
        raise ValueError(f"{bank_id_cast_fail} Bank ID trong accounts.csv khong ep duoc sang so")

    explicit_vertices = raw_acc.select(
        F.concat_ws("_", bank_id_norm, F.col("Account Number")).alias("id"),
        F.trim(F.split(F.col("Entity Name"), "#").getItem(0)).alias("account_type"),
        F.col("Bank Name").alias("bank_name"),
    ).withColumn("balance", F.lit(0.0))  # IBM khong cung cap balance hien tai

    # Xu ly phong thu (Defensive Vertex Generation): chong Dangling Edges
    active_ids = edges_df.select(F.col("src").alias("id")) \
        .union(edges_df.select(F.col("dst").alias("id"))).distinct()

    missing_ids = active_ids.join(explicit_vertices, on="id", how="left_anti")

    fallback_vertices = missing_ids.select(
        F.col("id"),
        F.lit("External/Unknown").alias("account_type"),
        F.lit(None).cast("string").alias("bank_name"),
        F.lit(0.0).alias("balance"),
    )

    final_vertices = explicit_vertices.unionByName(fallback_vertices).dropDuplicates(["id"])
    return final_vertices


def sample_ibm_edges(edges_df: DataFrame, target_edges: int = 100_000,
                     target_fraud: int = 89, seed: int = 42) -> DataFrame:
    """Lay ~target_edges canh, voi dung target_fraud canh gian lan."""
    fraud_edges = edges_df.filter(F.col("isFraud") == 1)
    benign_edges = edges_df.filter(F.col("isFraud") == 0)
    fraud_count = fraud_edges.count()
    benign_count = benign_edges.count()
    if fraud_count < target_fraud or benign_count == 0:
        raise ValueError("Khong du canh gian lan/hop le de tao IBM AML sample")

    # Fraud duoc chon theo noi dung canh, khong phu thuoc thu tu partition Spark.
    chosen_fraud = fraud_edges.orderBy(
        F.xxhash64(*[F.col(name) for name in edges_df.columns])
    ).limit(target_fraud)
    benign_fraction = min(1.0, max(0.0, (target_edges - target_fraud) / benign_count))
    return benign_edges.sample(False, benign_fraction, seed).unionByName(chosen_fraud)


def main():
    print("=" * 65)
    print("IBM AML (HI-SMALL) - ETL PIPELINE")
    print("=" * 65)

    spark = get_graph_session(app_name="GraphGuard-IBM-ETL")

    data_raw_dir = "data/raw/ibm_aml"
    trans_path = os.path.join(data_raw_dir, "HI-Small_Trans.csv")
    accounts_path = os.path.join(data_raw_dir, "HI-Small_accounts.csv")
    out_dir = "data/processed/ibm_aml"
    out_sample_dir = "data/processed/sample/ibm_aml"

    if not os.path.exists(trans_path) or not os.path.exists(accounts_path):
        print(f"[-] LOI: Khong tim thay CSV tai {data_raw_dir}.")
        sys.exit(1)

    # 1. Xu ly du lieu
    edges_df = build_ibm_edges(spark, trans_path).cache()
    vertices_df = build_ibm_vertices(spark, accounts_path, edges_df).cache()

    v_count = vertices_df.count()
    e_count = edges_df.count()
    fraud_count = edges_df.filter(F.col("isFraud") == 1).count()
    fallback_count = vertices_df.filter(F.col("account_type") == "External/Unknown").count()

    print("\n[+] HOAN TAT TRICH XUAT:")
    print(f"    - Tong so Dinh (Vertices): {v_count:,}  ({fallback_count:,} la fallback/External)")
    print(f"    - Tong so Canh (Edges):    {e_count:,}")
    print(f"    - Giao dich gian lan:      {fraud_count:,}")

    # 2. Data Quality Report -- PASS/FAIL tuong minh, khong crash cung bang assert
    print("\n" + "-" * 65)
    print("DATA QUALITY REPORT")
    print("-" * 65)
    checks = {}

    null_v = vertices_df.filter(F.col("id").isNull()).count()
    checks["No null vertex ids"] = (null_v == 0, f"{null_v} nulls")

    null_e = edges_df.filter(
        F.col("src").isNull() | F.col("dst").isNull() | F.col("amount").isNull()
    ).count()
    checks["No null src/dst/amount"] = (null_e == 0, f"{null_e} nulls")

    invalid_ids = edges_df.filter(
        ~F.col("src").rlike(r"^[0-9]+_.+") | ~F.col("dst").rlike(r"^[0-9]+_.+")
    ).count()
    checks["Valid composite edge IDs"] = (invalid_ids == 0, f"{invalid_ids} invalid IDs")
    checks["No fallback vertices"] = (fallback_count == 0, f"{fallback_count} fallback vertices")

    dangling_src = edges_df.join(vertices_df, edges_df["src"] == vertices_df["id"], "left_anti").count()
    dangling_dst = edges_df.join(vertices_df, edges_df["dst"] == vertices_df["id"], "left_anti").count()
    checks["Referential integrity (both src and dst)"] = (
        dangling_src == 0 and dangling_dst == 0,
        f"{dangling_src} dangling src, {dangling_dst} dangling dst",
    )

    raw_row_count = spark.read.csv(trans_path, header=True).count()
    checks["Edge count matches raw row count"] = (
        e_count == raw_row_count, f"{e_count:,} edges vs {raw_row_count:,} raw rows"
    )

    self_loops = edges_df.filter(F.col("src") == F.col("dst")).count()
    checks["Self-loop audit (informational -- expected > 0, unlike PaySim)"] = (
        True, f"{self_loops:,} self-loop edges found"
    )

    step_bounds = edges_df.agg(F.min("step").alias("mn"), F.max("step").alias("mx")).collect()[0]
    checks["step range (epoch seconds, NOT 1-744 like PaySim)"] = (
        True, f"min={step_bounds['mn']}, max={step_bounds['mx']}"
    )

    currency_note = edges_df.select("payment_currency").distinct().count()
    checks["Currency mixing warning"] = (
        True, f"{currency_note} distinct payment currencies present in 'amount' -- "
              f"filter by payment_currency before any amount-threshold logic"
    )

    all_hard_passed = True
    for name, (passed, detail) in checks.items():
        status = "PASS" if passed else "FAIL"
        if not passed:
            all_hard_passed = False
        print(f"  [{status}] {name}  ({detail})")
    print("-" * 65)

    if not all_hard_passed:
        print("[ERROR] One or more quality checks failed. Aborting export before "
              "writing Parquet.")
        spark.stop()
        sys.exit(1)

    # 3. Xuat du lieu Parquet Day du (Full)
    print(f"\n[*] Dang luu Parquet (Full Dataset) tai {out_dir}...")
    os.makedirs(out_dir, exist_ok=True)
    # vertices_df da qua 1 shuffle (dropDuplicates) nen da o 8 partition roi
    # (spark.sql.shuffle.partitions=8) -- khong can repartition(8) lai lan nua.
    vertices_df.write.mode("overwrite").parquet(os.path.join(out_dir, "vertices.parquet"))
    # edges_df la select thang tu CSV (chua qua shuffle nao) nen repartition
    # o day la can thiet, khong thua.
    edges_df.repartition(8).write.mode("overwrite").parquet(os.path.join(out_dir, "edges.parquet"))

    def dir_size_mb(path):
        return sum(os.path.getsize(os.path.join(d, f)) for d, _, files in os.walk(path) for f in files) / (1024 * 1024)
    print(f"      [OK] {out_dir}/vertices.parquet  ({dir_size_mb(out_dir + '/vertices.parquet'):.2f} MB on disk)")
    print(f"      [OK] {out_dir}/edges.parquet     ({dir_size_mb(out_dir + '/edges.parquet'):.2f} MB on disk)")

    print("[+] Luu Full Parquet THANH CONG.")

    # 4. Tao Subgraph Sample (~100k canh) cho Team
    print(f"\n[*] Dang tao Sample Subgraph (~100k edges) tai {out_sample_dir}...")
    sample_edges = sample_ibm_edges(edges_df).cache()

    sample_ids = sample_edges.select(F.col("src").alias("id")) \
        .union(sample_edges.select(F.col("dst").alias("id"))).distinct()
    sample_id_count = sample_ids.count()
    sample_vertices = vertices_df.join(sample_ids, on="id", how="inner").cache()
    sample_v_count = sample_vertices.count()

    if sample_v_count != sample_id_count:
        print(f"      [WARNING] {sample_id_count - sample_v_count} node id(s) from the "
              f"sample edges did not resolve to a vertex -- sample would have dangling "
              f"edges. Investigate before sharing.")
    else:
        print(f"      [OK] Sample is self-contained: all {sample_id_count:,} node ids resolved.")

    os.makedirs(out_sample_dir, exist_ok=True)
    sample_vertices.coalesce(1).write.mode("overwrite").parquet(os.path.join(out_sample_dir, "vertices.parquet"))
    sample_edges.coalesce(1).write.mode("overwrite").parquet(os.path.join(out_sample_dir, "edges.parquet"))
    print(f"      Sample Vertices: {sample_v_count:,} rows")
    print(f"      Sample Edges:    {sample_edges.count():,} rows")
    print(f"      Sample Fraud:    {sample_edges.filter(F.col('isFraud') == 1).count():,} rows")
    print("[+] Luu Sample Parquet THANH CONG.")

    print("\n" + "=" * 65)
    print("ACCOUNT-TYPE BREAKDOWN (FULL VERTICES)")
    print("=" * 65)
    vertices_df.groupBy("account_type").count().orderBy(F.col("count").desc()).show(truncate=False)

    spark.stop()


if __name__ == "__main__":
    main()
