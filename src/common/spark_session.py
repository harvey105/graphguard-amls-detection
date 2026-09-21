"""Spark session dùng chung cho cả PaySim và IBM AML."""

from pyspark.sql import SparkSession

from src.common.windows_runtime import prepare_windows_spark


def get_graph_session(app_name: str = "GraphGuard-Analytics") -> SparkSession:
    """Khởi tạo SparkSession với GraphFrames 0.12.2."""
    prepare_windows_spark()
    return (
        SparkSession.builder
        .appName(app_name)
        .master("local[*]")
        .config("spark.driver.memory", "6g")
        .config("spark.driver.maxResultSize", "2g")
        .config("spark.sql.shuffle.partitions", "8")
        .config("spark.jars.packages", "io.graphframes:graphframes-spark3_2.12:0.12.2")
        .config("spark.sql.adaptive.enabled", "true")
        .config("spark.sql.adaptive.coalescePartitions.enabled", "true")
        .getOrCreate()
    )
