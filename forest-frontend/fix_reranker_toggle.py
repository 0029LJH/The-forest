fp = r'D:\Ai应用工程师\RAG_agent\forest-frontend\src\views\admin\ModelManagementView.vue'
with open(fp, 'r', encoding='utf-8') as f:
    c = f.read()

old = '''        <template v-if="addType === 'mineru'">
          <el-form-item label="Token">
            <el-input v-model="addForm.apiKey" type="password" placeholder="sk-...（mineru.net 免费创建）" />
          </el-form-item>
          <el-form-item label="模型">
            <el-input v-model="addForm.modelName" placeholder="vlm / pipeline" />
          </el-form-item>
          <p class="mm-hint">模型说明：vlm（精度高，复杂版式/扫描件/公式）、pipeline（零幻觉，内容逐字准确）</p>
        </template>

        <template v-else>'''

new = '''        <template v-if="addType === 'mineru'">
          <el-form-item label="Token">
            <el-input v-model="addForm.apiKey" type="password" placeholder="sk-...（mineru.net 免费创建）" />
          </el-form-item>
          <el-form-item label="模型">
            <el-input v-model="addForm.modelName" placeholder="vlm / pipeline" />
          </el-form-item>
          <p class="mm-hint">模型说明：vlm（精度高，复杂版式/扫描件/公式）、pipeline（零幻觉，内容逐字准确）</p>
        </template>

        <template v-else-if="addType === 'reranker'">
          <el-form-item label="启用重排序">
            <el-switch v-model="addForm.parameters.rerank_enabled" />
            <span class="mm-hint">关闭后仅使用 RRF 融合检索，跳过 cross-encoder 重排序（节省延迟）</span>
          </el-form-item>
        </template>

        <template v-else>'''

if old in c:
    c = c.replace(old, new)
    with open(fp, 'w', encoding='utf-8') as f:
        f.write(c)
    print('Added reranker toggle to form')
else:
    print('Pattern not found, checking...')
    # Find the mineru template
    idx = c.find("addType === 'mineru'")
    if idx >= 0:
        print('Found mineru at index', idx)
        print(c[idx:idx+500])
    else:
        print('mineru not found')
