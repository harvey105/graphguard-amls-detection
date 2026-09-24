"""
File: src/common/graph_utils.py
Các hàm dùng chung để load, save và validate GraphFrame (Hỗ trợ cả PaySim và IBM AML).
"""

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
        raise FileNotFoundError(f"Không tìm thấy vertices tại: {vertices_path}")
    if not edges_path.exists():
        raise FileNotFoundError(f"Không tìm thấy edges tại: {edges_path}")

    v_df = spark.read.parquet(str(vertices_path))
    e_df = spark.read.parquet(str(edges_path))
    return GraphFrame(v_df, e_df)


def save_graph(graph: GraphFrame, output_dir: str) -> None:
    """Lưu vertices và edges của GraphFrame thành Parquet (Snappy - default codec)."""
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    graph.vertices.write.mode("overwrite").parquet(str(output_path / "vertices.parquet"))
    graph.edges.write.mode("overwrite").parquet(str(output_path / "edges.parquet"))


def check_integrity(graph: GraphFrame, verbose: bool = True) -> dict:
    """
    Kiểm tra tính toàn vẹn của GraphFrame:
    - Số lượng Đỉnh, Cạnh
    - Kiểm tra Null
    - Kiểm tra Cạnh treo (Dangling Edges) bằng left_anti join (nhanh hơn .subtract()
      -- left_anti chỉ cần 1 shuffled join, .subtract() thường tốn 2 lần full shuffle)
    - Thống kê Self-loops (src == dst) -- quan trọng với IBM AML (591,212 cạnh loại
      này, 11.64% tổng số cạnh, đã xác nhận trong DE_Paysim_IBM_Comparison.md)

    Lưu ý về `dangling_src + dangling_dst`:
      Đây là tổng số "lượt vi phạm", KHÔNG phải số cạnh treo thực tế nếu một cạnh
      thiếu CẢ src và dst cùng lúc (sẽ bị đếm 2 lần). Hiện tại điều này không xảy ra
      trên cả 2 dataset: PaySim đã được xác nhận vét cạn 0 dangling edges (Task
      2.3/2.4), và IBM AML có defensive vertex generation trong etl.py đảm bảo mọi
      id đều có vertex tương ứng. Cố tình không sửa bằng một phép union().distinct()
      tốn thêm 1 shuffle nữa để loại trùng, vì trường hợp cần loại trùng đó về lý
      thuyết không thể xảy ra với ETL hiện tại -- nếu sau này tổng dangling > 0 một
      cách bất thường, kiểm tra riêng dangling_src/dangling_dst thay vì tin vào tổng.

    Lưu ý về hiệu năng (áp dụng cho caller, không phải bug trong hàm này):
      Hàm này gọi khoảng 6-7 lệnh .count() liên tiếp trên graph.vertices/graph.edges.
      Nếu 2 DataFrame này CHƯA được .cache() ở phía gọi hàm, Spark sẽ tính lại toàn
      bộ pipeline phía trên (đọc lại CSV/Parquet, chạy lại ETL) MỖI LẦN .count() -- 
      tốn kém với 5M+ dòng của IBM AML. Khuyến nghị: cache ngay tại nơi tạo ra
      vertices_df/edges_df (giống export_parquet.py và etl.py đã làm), rồi mới gọi
      check_integrity() trên GraphFrame đã cache.
    """
    num_vertices = graph.vertices.count()
    num_edges = graph.edges.count()

    null_vertices = graph.vertices.filter(col("id").isNull()).count()
    null_edges = graph.edges.filter(col("src").isNull() | col("dst").isNull()).count()

    dangling_src = graph.edges.join(
        graph.vertices, graph.edges["src"] == graph.vertices["id"], "left_anti"
    ).count()
    dangling_dst = graph.edges.join(
        graph.vertices, graph.edges["dst"] == graph.vertices["id"], "left_anti"
    ).count()
    total_dangling = dangling_src + dangling_dst  # see docstring caveat above

    # Self-loop check -- expected 0 for PaySim, expected ~591,212 for IBM AML
    self_loops = graph.edges.filter(col("src") == col("dst")).count()

    result = {
        "num_vertices": num_vertices,
        "num_edges": num_edges,
        "null_vertices": null_vertices,
        "null_edges": null_edges,
        "dangling_src": dangling_src,
        "dangling_dst": dangling_dst,
        "dangling_edges": total_dangling,
        "self_loops": self_loops,
    }

    if verbose:
        print("=" * 65)
        print("GRAPHFRAME INTEGRITY REPORT")
        print("=" * 65)
        print(f"  Vertices (|V|):       {num_vertices:,}")
        print(f"  Edges (|E|):          {num_edges:,}")
        print(f"  Null Vertices:        {null_vertices}  {'[PASS]' if null_vertices == 0 else '[FAIL]'}")
        print(f"  Null Edges (src/dst): {null_edges}  {'[PASS]' if null_edges == 0 else '[FAIL]'}")
        print(f"  Dangling Edges:       {total_dangling}  (src-side: {dangling_src}, dst-side: {dangling_dst})"
              f"  {'[PASS]' if total_dangling == 0 else '[FAIL]'}")
        print(f"  Self-loops (src==dst):{self_loops:,}  (PaySim: expect 0, IBM AML: expect > 0, ~591,212)")
        print("=" * 65)

    return result
