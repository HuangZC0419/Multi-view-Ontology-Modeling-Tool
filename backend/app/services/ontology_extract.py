"""从数据源结构中提取本体概念"""

from __future__ import annotations

import uuid
from app.models import TableInfo, ColumnInfo, ImportSelection


def extract_ontology_nodes(
    tables: list,
    columns_map: dict,
    selection: ImportSelection,
    start_x: float = 120,
    start_y: float = 120,
    spacing_x: float = 220,
    spacing_y: float = 140,
    columns_per_row: int = 3
) -> list[dict]:
    """根据用户勾选，生成本体节点列表。

    表名 -> 父节点（name=表名, attributes=[]）
    列名 -> 子节点（name=字段名, parent_id=父节点ID, attributes=[{类型: VARCHAR, ...}]）

    返回: 可直接追加到画布的 OntologyNode dict 列表
    """
    nodes = []
    col_idx = 0

    for table in tables:
        # 统一获取表名：可能来自 TableInfo 对象或 dict
        if isinstance(table, dict):
            table_name = table.get("name", "")
        else:
            table_name = getattr(table, "name", "")

        if table_name not in selection.tables:
            continue

        display_name = selection.edited_names.get(table_name, table_name)

        parent_id = str(uuid.uuid4())
        x = start_x + (col_idx % columns_per_row) * spacing_x
        y = start_y + (col_idx // columns_per_row) * spacing_y * 2

        nodes.append({
            "id": parent_id,
            "name": display_name,
            "x": x,
            "y": y,
            "parent_id": None,
            "attributes": []
        })

        # 获取勾选的列
        selected_cols = selection.columns.get(table_name, [])
        cols = columns_map.get(table_name, [])

        child_x = x
        child_y = y + spacing_y
        child_count = 0

        for col in cols:
            # 统一获取列信息：可能来自 ColumnInfo 对象或 dict
            if isinstance(col, dict):
                col_name = col.get("name", "")
                col_type = col.get("data_type", "VARCHAR")
                col_comment = col.get("comment", "")
                col_is_pk = col.get("is_pk", False)
            else:
                col_name = getattr(col, "name", "")
                col_type = getattr(col, "data_type", "VARCHAR")
                col_comment = getattr(col, "comment", "")
                col_is_pk = getattr(col, "is_pk", False)

            if col_name not in selected_cols:
                continue

            display_col_name = selection.edited_names.get(
                f"{table_name}.{col_name}", col_name
            )

            child_attrs = [
                {"key": "数据类型", "value": col_type},
            ]
            if col_comment:
                child_attrs.append({"key": "注释", "value": col_comment})
            if col_is_pk:
                child_attrs.append({"key": "主键", "value": "是"})

            child_id = str(uuid.uuid4())
            nodes.append({
                "id": child_id,
                "name": display_col_name,
                "x": child_x + child_count * 180,
                "y": child_y,
                "parent_id": parent_id,
                "attributes": child_attrs
            })
            child_count += 1

        col_idx += 1

    return nodes
