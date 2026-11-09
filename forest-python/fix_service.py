with open(r'D:\Ai应用工程师\RAG_agent\forest-python\app\models_config\service.py', 'r', encoding='utf-8') as f:
    content = f.read()

old = 'if model_type in ("chat", "embedding"):'
new = 'if model_type in ("chat", "embedding", "reranker"):'

if old in content:
    content = content.replace(old, new)
    with open(r'D:\Ai应用工程师\RAG_agent\forest-python\app\models_config\service.py', 'w', encoding='utf-8') as f:
        f.write(content)
    print('service.py updated')
else:
    print('Pattern not found')
