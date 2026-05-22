"""共享数据模型 —— 新增数据源/视角模型"""

from __future__ import annotations

from enum import Enum
from pydantic import BaseModel, Field


# ============================================================
# 视角枚举
# ============================================================

class PerspectiveType(str, Enum):
    LEADER = "leader"
    ENGINEER = "engineer"
    PROCESS = "process"


# ============================================================
# 数据源连接器相关模型
# ============================================================

class TableInfo(BaseModel):
    """表/Sheet 元信息"""
    name: str
    table_schema: str = ""
    comment: str = ""
    row_count: int = 0


class ColumnInfo(BaseModel):
    """列/字段 元信息"""
    name: str
    data_type: str
    nullable: bool = True
    is_pk: bool = False
    comment: str = ""


class ImportSelection(BaseModel):
    """用户勾选的导入项"""
    source_id: str
    tables: list[str] = Field(default_factory=list)
    columns: dict[str, list[str]] = Field(default_factory=dict)
    edited_names: dict[str, str] = Field(default_factory=dict)


# ============================================================
# 多视角相关模型
# ============================================================

class DataSourceInfo(BaseModel):
    """数据源元信息（领导视角用）"""
    id: str
    name: str
    type: str
    conn_info: dict = Field(default_factory=dict)
    tables: list[str] = Field(default_factory=list)
    covered_nodes: int = 0
    covered_domains: list[str] = Field(default_factory=list)
    total_fields: int = 0


class BusinessDomain(BaseModel):
    """业务域（领导视角用）"""
    id: str
    name: str
    ontology_node_ids: list[str] = Field(default_factory=list)
    databases: list[str] = Field(default_factory=list)


class FieldMapping(BaseModel):
    """字段映射"""
    field_name: str
    attribute_key: str
    data_type: str


class DataMapping(BaseModel):
    """数据映射（工程师视角用）"""
    ontology_node_id: str
    source_type: str
    source_name: str
    table_name: str
    field_mappings: list[FieldMapping] = Field(default_factory=list)


class LeaderViewData(BaseModel):
    """领导视角完整数据"""
    summary: dict = Field(default_factory=dict)
    data_sources: list[DataSourceInfo] = Field(default_factory=list)
    domains: list[BusinessDomain] = Field(default_factory=list)
    source_domain_map: dict = Field(default_factory=dict)


class EngineerViewData(BaseModel):
    """工程师视角完整数据"""
    nodes: list = Field(default_factory=list)
    mappings: list[DataMapping] = Field(default_factory=list)
    domains: list[BusinessDomain] = Field(default_factory=list)
