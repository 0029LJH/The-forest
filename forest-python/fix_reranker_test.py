fp = r'D:\Ai应用工程师\RAG_agent\forest-python\app\models_config\service.py'
with open(fp, 'r', encoding='utf-8') as f:
    c = f.read()

# Add reranker dispatch in test_connection
old = '''        if model_type == "mineru":
            return await ModelConfigService._test_mineru(base_url, api_key, model_name)'''
new = '''        if model_type == "mineru":
            return await ModelConfigService._test_mineru(base_url, api_key, model_name)
        if model_type == "reranker":
            return await ModelConfigService._test_reranker(base_url, api_key, model_name, api_format)'''
c = c.replace(old, new)

# Add _test_reranker method before _test_mineru
old_test_mineru = '''    @staticmethod
    async def _test_mineru('''
new_test_methods = '''    @staticmethod
    async def _test_reranker(base_url: str, api_key: str, model_name: str,
                              api_format: str | None = None) -> dict:
        """验证 reranker 连接：发送简单 query+doc 对，检查分数返回。"""
        url = base_url.rstrip("/") + "/chat/completions"
        payload = {
            "model": model_name,
            "inputs": [{"query": "电力系统操作规程", "documents": ["操作前请断开开关"]}],
        }
        headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.post(url, json=payload, headers=headers)
            if resp.status_code >= 500:
                return {"ok": False, "status": resp.status_code, "message": f"API 返回 {resp.status_code}"}
            body = resp.json()
            results = body.get("output", {}).get("results", [])
            if results and isinstance(results[0], dict) and "score" in results[0]:
                score = results[0]["score"]
                return {"ok": True, "status": resp.status_code,
                        "message": f"连接成功（得分={score:.3f}）"}
            return {"ok": False, "status": resp.status_code,
                    "message": f"响应格式异常：{str(body)[:100]}"}
        except Exception as e:
            return {"ok": False, "status": 0, "message": str(e)[:200]}

    @staticmethod
    async def _test_mineru('''
c = c.replace(old_test_mineru, new_test_methods)

with open(fp, 'w', encoding='utf-8') as f:
    f.write(c)
print('service.py updated')
