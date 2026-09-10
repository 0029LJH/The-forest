import re

filepath = r'D:\Ai应用工程师\RAG_agent\forest-python\app\models_config\models.py'
with open(filepath, 'r', encoding='utf-8') as f:
    content = f.read()

content = content.replace(
    'model_type: Mapped[str] = mapped_column(String(16), nullable=False)  # "chat" or "embedding"',
    'model_type: Mapped[str] = mapped_column(String(16), nullable=False)  # "chat" / "embedding" / "reranker" / "mineru"'
)

with open(filepath, 'w', encoding='utf-8') as f:
    f.write(content)
print('models.py updated')
