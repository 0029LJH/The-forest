fp = r'D:\Ai应用工程师\RAG_agent\forest-frontend\src\views\qa\QaView.vue'
with open(fp, 'r', encoding='utf-8') as f:
    c = f.read()

# 1. Add rerank bar above QaComposer in template
old_composer = '''      <QaComposer
        ref="composerRef"
        :disabled="!hasGroup"
        :loading="asking"
        :group-name="selectedGroupName"
        @submit="handleAsk"
        @stop="stopAsking"
      />'''
new_composer = '''      <div class="qa-rerank-bar">
        <el-switch
          v-model="rerankEnabled"
          size="small"
          :active-text="'重排序'"
          :inactive-text="'重排序'"
        />
      </div>
      <QaComposer
        ref="composerRef"
        :disabled="!hasGroup"
        :loading="asking"
        :group-name="selectedGroupName"
        :rerank="rerankEnabled"
        @submit="handleAsk"
        @stop="stopAsking"
      />'''
c = c.replace(old_composer, new_composer)

# 2. Pass rerank in handleAsk payload  
old_call = '''        rerank: rerankEnabled.value,'''
new_call = '''        rerank: rerank.value,'''
c = c.replace(old_call, new_call)

with open(fp, 'w', encoding='utf-8') as f:
    f.write(c)
print('QaView.vue updated')
