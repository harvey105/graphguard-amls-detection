"""
File: src/common/spark_session.py
Role: Person 2 (Data Engineering Lead)
Spark session dung chung cho ca PaySim va IBM AML (every task: Task 1-4).
Tich hop Windows runtime fix (Leader), AQE tuning (Leader), tu dong do
coordinate GraphFrames theo phien ban PySpark dang cai (tranh lech Spark
3.x/4.x), va Checkpoint Directory bat buoc cho Task 4 (LPA / Connected
Components).
"""

import os
import sys
from typing import Optional

import pyspark
from pyspark.sql import SparkSession

# Tự động đưa thư mục gốc của project (graphguard_amls_detection) vào sys.path
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from src.common.windows_runtime import prepare_windows_spark


# Bump khi graphframes-py ra ban moi hon -- theo doi tai
# https://pypi.org/project/graphframes-py/
GRAPHFRAMES_VERSION = "0.12.2"


def _resolve_graphframes_coordinate() -> str:
    """
    Tu do coordinate Maven Central theo major version cua PySpark dang cai:
    graphframes-spark3_2.12 cho Spark 3.x, graphframes-spark4_2.13 cho
    Spark 4.x (GraphFrames chi build Scala 2.13 cho Spark 4.x). `pip install
    pyspark` co the tra ve Spark 3.x hoac 4.x tuy thoi diem chay, nen khong
    hardcode 1 gia tri co dinh -- may ban A co the khac may ban B du cung
    lenh cai dat.
    """
    major = pyspark.__version__.split(".")[0]
    scala_suffix = "2.13" if major == "4" else "2.12"
    return f"io.graphframes:graphframes-spark{major}_{scala_suffix}:{GRAPHFRAMES_VERSION}"


def get_graph_session(
    app_name: str = "GraphGuard-Analytics",
    driver_memory: str = "6g",
    shuffle_partitions: int = 8,
    checkpoint_dir: Optional[str] = None,
    extra_configs: Optional[dict[str, str]] = None,
) -> SparkSession:
    """
    Khoi tao (hoac lay lai) SparkSession dung chung, da gan GraphFrames.

    Parameters:
        app_name: Ten ung dung Spark.
        driver_memory: RAM cap cho Driver (mac dinh '6g', giam xuong '3g'
                       hoac '4g' neu may yeu -- huu ich khi chay tren bo
                       IBM AML sau nay neu dataset do nang hon PaySim).
        shuffle_partitions: So partition khi shuffle (join/aggregate/groupBy).
        checkpoint_dir: Thu muc luu lineage checkpoint. BAT BUOC truyen khi
                        chay Task 4 (LPA / Connected Components), neu khong
                        Spark se loi StackOverflowError do lineage qua sau.
        extra_configs: Config Spark bo sung tuy bien theo tung script.

    Returns:
        SparkSession da san sang dung GraphFrames (JVM package tren classpath).

    Luu y (gioi han cua Spark, khong phai bug cua ham nay): neu goi ham nay
    nhieu lan TRONG CUNG MOT process Python (vd. trong notebook, khong phai
    chay `python src/xxx.py` rieng le), `getOrCreate()` se tra ve session cu
    va bo qua driver_memory/shuffle_partitions/jars.packages o lan goi sau
    -- day la gioi han cua Spark, chi setLogLevel/checkpoint_dir la luon ap
    dung duoc o moi lan goi. Neu can doi config, phai spark.stop() session
    cu truoc khi goi lai.
    """
    # 1. Tu dong cau hinh moi truong runtime Windows (giu nguyen cua Leader)
    prepare_windows_spark()

    coord = _resolve_graphframes_coordinate()

    builder = (
        SparkSession.builder
        .appName(app_name)
        .master("local[*]")
        .config("spark.driver.memory", driver_memory)
        .config("spark.driver.maxResultSize", "2g")
        .config("spark.sql.shuffle.partitions", str(shuffle_partitions))
        .config("spark.sql.parquet.compression.codec", "snappy")
        .config("spark.jars.packages", coord)
        # AQE (giu nguyen cua Leader) -- tu gom shuffle partition nho lai;
        # them skewJoin vi do thi giao dich co hub lech manh (fan-in cao,
        # xem Max In-Degree Task 2 cua Nguoi 3).
        .config("spark.sql.adaptive.enabled", "true")
        .config("spark.sql.adaptive.coalescePartitions.enabled", "true")
        .config("spark.sql.adaptive.skewJoin.enabled", "true")
    )

    if extra_configs:
        for key, value in extra_configs.items():
            builder = builder.config(key, str(value))

    spark = builder.getOrCreate()

    # 2. Giam muc log de tranh spam terminal (chi in WARN va ERROR)
    spark.sparkContext.setLogLevel("WARN")

    # 3. Cau hinh checkpoint directory neu duoc yeu cau (bat buoc cho Task 4)
    if checkpoint_dir:
        os.makedirs(checkpoint_dir, exist_ok=True)
        spark.sparkContext.setCheckpointDir(checkpoint_dir)
        print(f"[*] Checkpoint directory: {checkpoint_dir}")

    return spark


if __name__ == "__main__":
    print("[*] Dang kiem tra khoi tao get_graph_session()...")
    print(f"    Phat hien PySpark {pyspark.__version__} -> GraphFrames coordinate: "
          f"{_resolve_graphframes_coordinate()}")

    test_checkpoint = "checkpoint_test"
    test_session = get_graph_session(
        app_name="GraphGuard-SessionTest",
        checkpoint_dir=test_checkpoint,
    )
    try:
        from graphframes import GraphFrame  # noqa: F401  (chi de test import)
        print(f"[+] Khoi tao SparkSession THANH CONG (Spark {test_session.version}).")
        print(f"    - Master: {test_session.sparkContext.master}")
        print("[+] GraphFrames wrapper da san sang hoat dong.")

        actual_ckpt = test_session.sparkContext.getCheckpointDir()
        ckpt_ok = actual_ckpt is not None
        status = "+" if ckpt_ok else "-"
        state = "da set" if ckpt_ok else "CHUA set"
        print(f"[{status}] Checkpoint directory {state}: {actual_ckpt}")
    except ImportError as e:
        print(f"[-] ERROR: GraphFrames import failed: {e}")
        raise
    finally:
        test_session.stop()
        if os.path.exists(test_checkpoint):
            import shutil
            shutil.rmtree(test_checkpoint, ignore_errors=True)
        print("[+] Da dong test session va don checkpoint test an toan.")
