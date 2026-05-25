import asyncio
import sys
import os

# Add the backend directory to sys.path so we can import app modules
sys.path.append(os.path.join(os.path.dirname(__file__), 'backend'))

from app.connectors.file_parser import FileParserConnector
from app.services.ontology_extract import extract_ontology_from_data

async def main():
    parser = FileParserConnector()
    await parser.connect({"file_path": r"h:\Git\OCR_benti-main_win7\测试数据\机械加工本体关系表.xlsx", "file_type": ".xlsx"})
    tables = await parser.get_tables()
    print("Tables:", [t.name for t in tables])
    rel_data = await parser.preview_data("实体关系", limit=1000)
    attr_data = await parser.preview_data("实体属性", limit=1000)
    nodes, edges = extract_ontology_from_data(rel_data, attr_data)
    print("Nodes:", len(nodes))
    print("Edges:", len(edges))

asyncio.run(main())
