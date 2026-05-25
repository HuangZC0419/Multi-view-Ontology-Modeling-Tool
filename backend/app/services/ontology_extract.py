"""从数据源结构中提取本体概念"""

from __future__ import annotations

import uuid
import random
from app.models import TableInfo, ColumnInfo, ImportSelection

def extract_ontology_from_data(
    relations_data: list[dict],
    attributes_data: list[dict],
    inference_data: list[dict] = None,
    mutex_data: list[dict] = None
) -> tuple[list[dict], list[dict], list[dict], list[dict]]:
    """
    从数据行中直接提取本体节点和关系。
    relations_data: [{'头实体': 'A', '关系': 'B', '关系权重': 0.5, '尾实体': 'C'}, ...]
    attributes_data: [{'实体名称': 'A', '属性名': 'attr1'}, ...]
    inference_data: [{'关系1': 'A', '关系2': 'B', '推导关系': 'C'}, ...]
    mutex_data: [{'关系1': 'A', '关系2': 'B'}, ...]
    """
    if inference_data is None:
        inference_data = []
    if mutex_data is None:
        mutex_data = []
        
    nodes_map = {}
    edges = []
    inference_rules = []
    mutex_rules = []
    
    # 1. 收集所有唯一的实体
    entities = set()
    for row in relations_data:
        if row.get('头实体'): entities.add(row['头实体'])
        if row.get('尾实体'): entities.add(row['尾实体'])
    for row in attributes_data:
        if row.get('实体名称'): entities.add(row['实体名称'])
        
    # 2. 生成节点
    for i, name in enumerate(entities):
        node_id = str(uuid.uuid4())
        nodes_map[name] = {
            "id": node_id,
            "name": name,
            "x": 100 + (i % 4) * 250 + random.randint(-20, 20),
            "y": 100 + (i // 4) * 150 + random.randint(-20, 20),
            "parent_id": None,
            "attributes": []
        }
        
    # 3. 填充属性
    for row in attributes_data:
        name = row.get('实体名称')
        if name in nodes_map and row.get('属性名'):
            nodes_map[name]['attributes'].append({
                "key": row['属性名'],
                "value": ""
            })
            
    # 4. 生成边
    for row in relations_data:
        src_name = row.get('头实体')
        tgt_name = row.get('尾实体')
        if src_name in nodes_map and tgt_name in nodes_map:
            edge_id = str(uuid.uuid4())
            try:
                weight = float(row.get('关系权重', 1.0))
            except (ValueError, TypeError):
                weight = 1.0
                
            edges.append({
                "id": edge_id,
                "source": nodes_map[src_name]["id"],
                "target": nodes_map[tgt_name]["id"],
                "relation": row.get('关系', ''),
                "kind": "relation",
                "characteristics": [],
                "weight": weight
            })

    # 5. 生成推理规则
    for row in inference_data:
        if row.get('关系1') and row.get('关系2') and row.get('推导关系'):
            inference_rules.append({
                "id": str(uuid.uuid4()),
                "rel1": row['关系1'],
                "rel2": row['关系2'],
                "inferred_rel": row['推导关系']
            })

    # 6. 生成互斥规则
    for row in mutex_data:
        if row.get('关系1') and row.get('关系2'):
            mutex_rules.append({
                "id": str(uuid.uuid4()),
                "rel1": row['关系1'],
                "rel2": row['关系2']
            })
            
    return list(nodes_map.values()), edges, inference_rules, mutex_rules


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
