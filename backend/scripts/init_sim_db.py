"""初始化模拟达梦数据库 -- 创建系统表 + 录入测试数据"""

import sqlite3
import os
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent.parent / "projects" / "sim_dameng.db"

def init():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    if DB_PATH.exists():
        os.remove(DB_PATH)

    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    # ---- 模拟达梦系统视图 ----
    cur.execute("""
        CREATE TABLE all_tables (
            owner TEXT, table_name TEXT, comments TEXT,
            num_rows INTEGER, row_count INTEGER
        )
    """)
    cur.execute("""
        CREATE TABLE all_tab_columns (
            owner TEXT, table_name TEXT, column_name TEXT,
            data_type TEXT, nullable INTEGER, is_pk INTEGER,
            comments TEXT, column_id INTEGER
        )
    """)

    # ---- 录入测试表（5张机械加工业务表）----
    tables = [
        ("BENTI", "CUTTING_PARAM", "切削参数表", 5000, 5000),
        ("BENTI", "MACHINE_INFO", "机床信息表", 200, 200),
        ("BENTI", "TOOL_LIBRARY", "刀具库表", 800, 800),
        ("BENTI", "QUALITY_CHECK", "质检记录表", 12000, 12000),
        ("BENTI", "OPERATOR_RECORD", "操作人员记录表", 350, 350),
    ]
    cur.executemany(
        "INSERT INTO all_tables VALUES (?, ?, ?, ?, ?)", tables
    )

    # ---- 录入测试列（30个字段）----
    columns = [
        # CUTTING_PARAM (7列)
        ("BENTI", "CUTTING_PARAM", "cutting_speed", "FLOAT", 1, 0, "切削速度 m/min", 1),
        ("BENTI", "CUTTING_PARAM", "spindle_rpm", "INTEGER", 1, 0, "主轴转速 rpm", 2),
        ("BENTI", "CUTTING_PARAM", "feed_rate", "FLOAT", 1, 0, "进给量 mm/r", 3),
        ("BENTI", "CUTTING_PARAM", "depth_of_cut", "FLOAT", 1, 0, "切削深度 mm", 4),
        ("BENTI", "CUTTING_PARAM", "coolant_flow_rate", "FLOAT", 1, 0, "冷却液流量 L/min", 5),
        ("BENTI", "CUTTING_PARAM", "cutting_temp", "FLOAT", 1, 0, "切削温度 °C", 6),
        ("BENTI", "CUTTING_PARAM", "param_id", "VARCHAR", 0, 1, "参数ID（主键）", 7),
        # MACHINE_INFO (4列)
        ("BENTI", "MACHINE_INFO", "machine_model", "VARCHAR", 0, 0, "机床型号", 1),
        ("BENTI", "MACHINE_INFO", "rigidity_level", "VARCHAR", 1, 0, "刚性等级", 2),
        ("BENTI", "MACHINE_INFO", "max_rpm", "INTEGER", 1, 0, "最高转速", 3),
        ("BENTI", "MACHINE_INFO", "machine_id", "VARCHAR", 0, 1, "机床ID（主键）", 4),
        # TOOL_LIBRARY (6列)
        ("BENTI", "TOOL_LIBRARY", "material_type", "VARCHAR", 0, 0, "刀具材料类型", 1),
        ("BENTI", "TOOL_LIBRARY", "coating", "VARCHAR", 1, 0, "涂层材料", 2),
        ("BENTI", "TOOL_LIBRARY", "hardness", "FLOAT", 1, 0, "硬度 HRC", 3),
        ("BENTI", "TOOL_LIBRARY", "wear_amount", "FLOAT", 1, 0, "磨损量 mm", 4),
        ("BENTI", "TOOL_LIBRARY", "life_remaining", "INTEGER", 1, 0, "剩余寿命 h", 5),
        ("BENTI", "TOOL_LIBRARY", "tool_id", "VARCHAR", 0, 1, "刀具ID（主键）", 6),
        # QUALITY_CHECK (7列)
        ("BENTI", "QUALITY_CHECK", "surface_ra", "FLOAT", 1, 0, "表面粗糙度 Ra", 1),
        ("BENTI", "QUALITY_CHECK", "dim_tolerance", "FLOAT", 1, 0, "尺寸公差 mm", 2),
        ("BENTI", "QUALITY_CHECK", "nominal_dim", "FLOAT", 1, 0, "标称尺寸 mm", 3),
        ("BENTI", "QUALITY_CHECK", "quality_grade", "VARCHAR", 1, 0, "质量等级", 4),
        ("BENTI", "QUALITY_CHECK", "defect_count", "INTEGER", 1, 0, "缺陷数量", 5),
        ("BENTI", "QUALITY_CHECK", "measure_date", "DATE", 1, 0, "检测日期", 6),
        ("BENTI", "QUALITY_CHECK", "check_id", "VARCHAR", 0, 1, "检测ID（主键）", 7),
        # OPERATOR_RECORD (6列)
        ("BENTI", "OPERATOR_RECORD", "skill_level", "VARCHAR", 0, 0, "技能等级", 1),
        ("BENTI", "OPERATOR_RECORD", "cert_type", "VARCHAR", 1, 0, "证书类型", 2),
        ("BENTI", "OPERATOR_RECORD", "exp_years", "INTEGER", 1, 0, "从业年限", 3),
        ("BENTI", "OPERATOR_RECORD", "efficiency_rate", "FLOAT", 1, 0, "效率评分", 4),
        ("BENTI", "OPERATOR_RECORD", "output_qty", "INTEGER", 1, 0, "产出数量", 5),
        ("BENTI", "OPERATOR_RECORD", "operator_id", "VARCHAR", 0, 1, "操作人员ID（主键）", 6),
    ]
    cur.executemany(
        "INSERT INTO all_tab_columns VALUES (?, ?, ?, ?, ?, ?, ?, ?)", columns
    )

    conn.commit()
    conn.close()
    print(f"模拟数据库已创建: {DB_PATH}")


if __name__ == "__main__":
    init()
