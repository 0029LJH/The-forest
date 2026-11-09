# Fix reranker.py: inputs -> input
fp1 = r'D:\Ai应用工程师\RAG_agent\forest-python\app\qa\reranker.py'
with open(fp1, 'r', encoding='utf-8') as f:
    c = f.read()
c = c.replace('"inputs": [{"query": query, "documents": documents}]', '"input": {"query": query, "documents": documents}')
c = c.replace('"inputs": [{"query": "...", "documents": [...]}]', '"input": {"query": "...", "documents": [...]}}')
with open(fp1, 'w', encoding='utf-8') as f:
    f.write(c)
print('reranker.py fixed')

# Fix service.py test_reranker
fp2 = r'D:\Ai应用工程师\RAG_agent\forest-python\app\models_config\service.py'
with open(fp2, 'r', encoding='utf-8') as f:
    c = f.read()
c = c.replace('"inputs": [{"query": "电力系统操作规程", "documents": ["操作前请断开开关"]}]', '"input": {"query": "电力系统操作规程", "documents": ["操作前请断开开关"]}')
with open(fp2, 'w', encoding='utf-8') as f:
    f.write(c)
print('service.py fixed')
