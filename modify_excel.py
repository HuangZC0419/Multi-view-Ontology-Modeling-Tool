import json
import pandas as pd

# 1. Read JSON to extract edges and node attributes
with open(r'h:\Git\OCR_benti-main_win7\backend\projects\machining-demo.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

nodes = data.get('nodes', [])
edges = data.get('edges', [])
inference_rules = data.get('inference_rules', [])
mutex_rules = data.get('mutex_rules', [])

# Create relationships dataframe
relations = []
node_name_map = {n['id']: n['name'] for n in nodes}
for e in edges:
    if e.get('kind') == 'relation':
        relations.append({
            '头实体': node_name_map.get(e['source'], e['source']),
            '关系': e.get('relation', ''),
            '关系权重': e.get('weight', 1.0),
            '尾实体': node_name_map.get(e['target'], e['target'])
        })
df_relations = pd.DataFrame(relations)

# Create attributes dataframe
attributes = []
for n in nodes:
    name = n.get('name', '')
    for attr in n.get('attributes', []):
        attributes.append({
            '实体名称': name,
            '属性名': attr.get('key', '')
        })
df_attributes = pd.DataFrame(attributes)

# Create inference rules dataframe
inference_data = []
for rule in inference_rules:
    inference_data.append({
        '关系1': rule['rel1'],
        '关系2': rule['rel2'],
        '推导关系': rule['inferred_rel']
    })
df_inference = pd.DataFrame(inference_data)

# Create mutex rules dataframe
mutex_data = []
for rule in mutex_rules:
    mutex_data.append({
        '关系1': rule['rel1'],
        '关系2': rule['rel2']
    })
df_mutex = pd.DataFrame(mutex_data)

# Write to Excel
with pd.ExcelWriter(r'h:\Git\OCR_benti-main_win7\测试数据\机械加工本体关系表.xlsx') as writer:
    df_attributes.to_excel(writer, sheet_name='实体属性', index=False)
    df_relations.to_excel(writer, sheet_name='实体关系', index=False)
    if not df_inference.empty:
        df_inference.to_excel(writer, sheet_name='推理规则', index=False)
    if not df_mutex.empty:
        df_mutex.to_excel(writer, sheet_name='互斥规则', index=False)

print("Excel file modified successfully.")