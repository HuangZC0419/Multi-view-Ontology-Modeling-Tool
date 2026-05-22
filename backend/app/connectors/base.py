"""数据源连接器抽象基类"""

from __future__ import annotations

from abc import ABC, abstractmethod
from app.models import TableInfo, ColumnInfo


class DataSourceConnector(ABC):
    """所有数据源的统一抽象接口"""

    @abstractmethod
    async def connect(self, config: dict) -> bool:
        """建立连接，返回是否成功"""
        ...

    @abstractmethod
    async def disconnect(self):
        """断开连接，释放资源"""
        ...

    @abstractmethod
    async def test_connection(self, config: dict) -> bool:
        """测试连接参数是否可用（不保持连接）"""
        ...

    @abstractmethod
    async def get_tables(self) -> list[TableInfo]:
        """获取所有表/Sheet/文件列表"""
        ...

    @abstractmethod
    async def get_columns(self, table: str, schema: str = "") -> list[ColumnInfo]:
        """获取指定表的列信息"""
        ...

    @abstractmethod
    async def preview_data(self, table: str, schema: str = "", limit: int = 10) -> list[dict]:
        """预览表的前N行数据"""
        ...
