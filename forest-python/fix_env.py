with open(r'D:\Ai应用工程师\RAG_agent\forest-python\.env', 'r', encoding='utf-8') as f:
    c = f.read()

# Add RERANKER config after EMBEDDING section
if 'RERANKER_BASE_URL' not in c:
    c = c.replace(
        'EMBEDDING_DIMENSIONS=1024\n',
        'EMBEDDING_DIMENSIONS=1024\n\n# Reranker (可选，DashScope 免费)\nRERANKER_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1\nRERANKER_API_KEY=sk-ws-H.PDHRIIR.FhD2.MEYCIQDOc8pmZIcVI3mnfDG22noakNQfT2krq20wSWls10VAuwIhAOaCitti0VlKkhpLhPoS5VR1wRW-dXSFqxqy0PCiTCp6\nRERANKER_MODEL_NAME=gte-rerank-v2\n'
    )
    with open(r'D:\Ai应用工程师\RAG_agent\forest-python\.env', 'w', encoding='utf-8') as f:
        f.write(c)
    print('.env updated')
else:
    print('.env already has RERANKER config')

with open(r'D:\Ai应用工程师\RAG_agent\forest-python\.env.example', 'r', encoding='utf-8') as f:
    c = f.read()

if 'RERANKER_BASE_URL' not in c:
    c = c.replace(
        'EMBEDDING_DIMENSIONS=1024\n',
        'EMBEDDING_DIMENSIONS=1024\n\n# Reranker (可选)\nRERANKER_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1\nRERANKER_API_KEY=sk-your-dashscope-api-key\nRERANKER_MODEL_NAME=gte-rerank-v2\n'
    )
    with open(r'D:\Ai应用工程师\RAG_agent\forest-python\.env.example', 'w', encoding='utf-8') as f:
        f.write(c)
    print('.env.example updated')
else:
    print('.env.example already has RERANKER config')
