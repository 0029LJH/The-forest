fp = r'D:\Ai应用工程师\RAG_agent\forest-python\app\qa\router.py'
with open(fp, 'r', encoding='utf-8') as f:
    c = f.read()

# Add rerank to AskRequest
old = '    session_id: Optional[int] = Field(default=None, alias="sessionId")\n\n    model_config'
new = '    session_id: Optional[int] = Field(default=None, alias="sessionId")\n    rerank: Optional[bool] = Field(default=None, alias="rerank")\n\n    model_config'
c = c.replace(old, new)

# Pass rerank to ask
old2 = 'result = await qa_service.ask(current_user.user_id, request.group_id, request.question,\n                                  session_id=request.session_id)'
new2 = 'result = await qa_service.ask(current_user.user_id, request.group_id, request.question,\n                                  session_id=request.session_id, rerank=request.rerank)'
c = c.replace(old2, new2)

# Pass rerank to ask_stream
old3 = 'current_user.user_id, request.group_id, request.question,\n              session_id=request.session_id,'
new3 = 'current_user.user_id, request.group_id, request.question,\n              session_id=request.session_id, rerank=request.rerank,'
c = c.replace(old3, new3)

with open(fp, 'w', encoding='utf-8') as f:
    f.write(c)
print('router.py updated')
