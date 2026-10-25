"""Demo N4 (21/9): tìm chu trình có đúng ba đỉnh trên toy GraphFrame.

Chạy từ thư mục gốc dự án: python -m src.motif.toy_cycle
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from graphframes import GraphFrame
from pyspark.sql import DataFrame, SparkSession
from pyspark.sql import functions as F

from src.common.spark_session import get_graph_session


MOTIF_PATTERN = "(a)-[e1]->(b);(b)-[e2]->(c);(c)-[e3]->(a)"


def build_toy_graph(spark: SparkSession) -> GraphFrame:
    """Tạo A → B → C → A, mỗi đỉnh và cạnh có thuộc tính để quan sát."""
    vertices = spark.sql(
        "SELECT * FROM VALUES "
        "('A', 'Alice'), ('B', 'Bob'), ('C', 'Carol') "
        "AS v(id, name)"
    )
    edges = spark.sql(
        "SELECT * FROM VALUES "
        "('A', 'B', 'transfer'), ('B', 'C', 'transfer'), "
        "('C', 'A', 'transfer') "
        "AS e(src, dst, kind)"
    )
    return GraphFrame(vertices, edges)


def find_three_node_cycles(graph: GraphFrame) -> DataFrame:
    """Chạy đúng motif đã giao và loại các đường đóng có đỉnh trùng nhau."""
    return (
        graph.find(MOTIF_PATTERN)
        .where(
            (F.col("a.id") != F.col("b.id"))
            & (F.col("b.id") != F.col("c.id"))
            & (F.col("c.id") != F.col("a.id"))
        )
    )


def cycle_ids(motifs: DataFrame) -> DataFrame:
    """Lấy ID đỉnh theo thứ tự chiều cạnh; mỗi dòng là một phép xoay."""
    return motifs.select(
        F.col("a.id").alias("a"),
        F.col("b.id").alias("b"),
        F.col("c.id").alias("c"),
    )


def run_demo(spark: SparkSession) -> dict:
    """Trả dữ liệu demo và kiểm tra số kết quả mong đợi trên toy graph."""
    graph = build_toy_graph(spark)
    matches = cycle_ids(find_three_node_cycles(graph))
    rows = sorted(tuple(row) for row in matches.collect())
    expected = [("A", "B", "C"), ("B", "C", "A"), ("C", "A", "B")]
    if rows != expected:
        raise AssertionError(f"Motif sai: mong đợi {expected}, nhận {rows}")

    # Chỉ giữ phép xoay bắt đầu ở ID nhỏ nhất, tránh đếm 1 chu trình 3 lần.
    unique = sorted(row for row in rows if row[0] == min(row))
    if unique != [("A", "B", "C")]:
        raise AssertionError(f"Chu trình duy nhất sai: {unique}")

    return {
        "status": "PASS",
        "pattern": MOTIF_PATTERN,
        "vertices": ["A", "B", "C"],
        "edges": [["A", "B"], ["B", "C"], ["C", "A"]],
        "raw_match_count": len(rows),
        "raw_matches": [list(row) for row in rows],
        "unique_cycle_count": len(unique),
        "unique_cycles": [list(row) for row in unique],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Demo N4: motif chu trình ba đỉnh")
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("results/motif/toy_cycle_summary.json"),
        help="Đường dẫn JSON lưu kết quả demo",
    )
    args = parser.parse_args()
    spark = get_graph_session("GraphGuard-N4-ToyCycle")
    spark.sparkContext.setLogLevel("ERROR")
    try:
        result = run_demo(spark)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            json.dumps(result, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        print(json.dumps(result, ensure_ascii=False, indent=2))
        print(f"[PASS] Đã lưu {args.output}")
    finally:
        spark.stop()


if __name__ == "__main__":
    main()
