"""Các hàm dùng chung để load, save và validate GraphFrame."""

from pathlib import Path

from graphframes import GraphFrame
from pyspark.sql import SparkSession
from pyspark.sql.functions import col


def load_graph(spark: SparkSession, data_dir: str) -> GraphFrame:
    """Load GraphFrame từ thư mục chứa vertices.parquet và edges.parquet."""
    data_path = Path(data_dir)
    vertices_path = data_path / "vertices.parquet"
    edges_path = data_path / "edges.parquet"
    if not vertices_path.exists():
        raise FileNotFoundError(f"Không tìm thấy: {vertices_path}")
    if not edges_path.exists():
        raise FileNotFoundError(f"Không tìm thấy: {edges_path}")
    return GraphFrame(
        spark.read.parquet(str(vertices_path)),
        spark.read.parquet(str(edges_path)),
    )


def save_graph(graph: GraphFrame, output_dir: str) -> None:
    """Lưu vertices và edges của GraphFrame thành Parquet."""
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    graph.vertices.write.mode("overwrite").parquet(str(output_path / "vertices.parquet"))
    graph.edges.write.mode("overwrite").parquet(str(output_path / "edges.parquet"))


def check_integrity(graph: GraphFrame, verbose: bool = True) -> dict:
    """Kiểm tra count, null và dangling edges của GraphFrame."""
    num_vertices = graph.vertices.count()
    num_edges = graph.edges.count()
    null_vertices = graph.vertices.filter(col("id").isNull()).count()
    null_edges = graph.edges.filter(
        col("src").isNull() | col("dst").isNull()
    ).count()
    valid_ids = graph.vertices.select("id").distinct()
    dangling_src = graph.edges.select(col("src").alias("id")).subtract(valid_ids).count()
    dangling_dst = graph.edges.select(col("dst").alias("id")).subtract(valid_ids).count()
    result = {
        "num_vertices": num_vertices,
        "num_edges": num_edges,
        "null_vertices": null_vertices,
        "null_edges": null_edges,
        "dangling_edges": dangling_src + dangling_dst,
    }
    if verbose:
        print("=" * 60)
        print("INTEGRITY CHECK")
        print("=" * 60)
        print(f"  Vertices:        {num_vertices:,}")
        print(f"  Edges:           {num_edges:,}")
        print(f"  Null vertices:   {null_vertices}  {'[PASS]' if null_vertices == 0 else '[FAIL]'}")
        print(f"  Null edges:      {null_edges}  {'[PASS]' if null_edges == 0 else '[FAIL]'}")
        print(f"  Dangling edges:  {result['dangling_edges']}  {'[PASS]' if result['dangling_edges'] == 0 else '[FAIL]'}")
        print("=" * 60)
    return result