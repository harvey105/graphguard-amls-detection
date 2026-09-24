"""
File: probe_bank_ids.py
Mục đích: Soi trực tiếp định dạng Bank ID thô giữa file Trans và file Accounts
để xác nhận giả thuyết lệch số 0 đầu.
"""

import os
import sys
from pyspark.sql import functions as F

# Chèn đường dẫn để dùng spark_session chung
sys.path.insert(0, os.path.abspath("."))
from src.common.spark_session import get_graph_session

def main():
    spark = get_graph_session("Bank-ID-Probe")
    
    trans_path = "data/raw/ibm_aml/HI-Small_Trans.csv"
    acc_path = "data/raw/ibm_aml/HI-Small_accounts.csv"
    
    print("\n[*] Đang đọc CSV thô (dạng String thuần túy, không ép kiểu)...")
    # Đọc thuần túy dạng chuỗi để xem nguyên bản trong file CSV lưu như thế nào
    raw_trans = spark.read.option("header", "true").csv(trans_path)
    raw_acc = spark.read.option("header", "true").csv(acc_path)
    
    print("\n" + "=" * 65)
    print("1. SOI ĐỊNH DẠNG 'From Bank' & 'To Bank' TRONG FILE TRANS")
    print("=" * 65)
    raw_trans.select(
        F.col("From Bank"), 
        F.length("From Bank").alias("len_from"),
        F.col("To Bank"),
        F.length("To Bank").alias("len_to")
    ).distinct().orderBy(F.col("len_from").desc()).show(15, truncate=False)
    
    print("\n" + "=" * 65)
    print("2. SOI ĐỊNH DẠNG 'Bank ID' TRONG FILE ACCOUNTS")
    print("=" * 65)
    raw_acc.select(
        F.col("Bank ID"), 
        F.length("Bank ID").alias("len_bank_id")
    ).distinct().orderBy(F.col("len_bank_id").desc()).show(15, truncate=False)
    
    print("\n" + "=" * 65)
    print("3. THỬ NGHIỆM KHỚP MÃ CỤ THỂ (Ví dụ: Mã có chứa số 0 đầu)")
    print("=" * 65)
    # Lấy thử một vài mã From Bank bắt đầu bằng số '0'
    sample_zeros = raw_trans.filter(F.col("From Bank").startswith("0")) \
                            .select("From Bank").distinct().limit(5).collect()
    
    if sample_zeros:
        print("Tìm thấy các mã From Bank có số 0 đầu trong Trans.csv:")
        for r in sample_zeros:
            val = r["From Bank"]
            # Thử tìm giá trị nguyên bản trong Accounts
            match_raw = raw_acc.filter(F.col("Bank ID") == val).count()
            # Thử tìm giá trị sau khi bỏ số 0 đầu (ép int rồi về str)
            val_stripped = str(int(val)) if val.isdigit() else val
            match_stripped = raw_acc.filter(F.col("Bank ID") == val_stripped).count()
            
            print(f"  -> Mã '{val}':")
            print(f"       + Khớp nguyên bản ('{val}') trong accounts.csv: {match_raw} dòng")
            print(f"       + Khớp sau khi bỏ số 0 ('{val_stripped}') trong accounts.csv: {match_stripped} dòng")
    else:
        print("Không tìm thấy mã From Bank nào có số 0 đầu trong Trans.csv!")

    spark.stop()

if __name__ == "__main__":
    main()