"""Fix reranker.py: correct API format and response parsing."""
path = r'D:\Ai应用工程师\RAG_agent\forest-python\app\qa\reranker.py'
with open(path, 'r', encoding='utf-8') as f:
    content = f.read()

# Fix payload format: flat structure
old = '''        payload = {
            "model": model_name,
            "input": {"query": query, "documents": documents},
        }'''
new = '''        payload = {
            "model": model_name,
            "query": query,
            "documents": documents,
        }'''
content = content.replace(old, new)

# Fix response parsing: relevance_score
old2 = '            score = r.get("score", 0.0)'
new2 = '            score = r.get("relevance_score", r.get("score", 0.0))'
content = content.replace(old2, new2)

with open(path, 'w', encoding='utf-8') as f:
    f.write(content)
print('Fixed, length:', len(content))
