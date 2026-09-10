<script setup lang="ts">
import { ref, onMounted, onUnmounted, nextTick } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import LoginModal from '@/components/LoginModal.vue'

const router = useRouter()
const authStore = useAuthStore()
const showLoginModal = ref(false)
const activeSection = ref("hero")

function navigateToApp() {
  if (authStore.isAuthenticated) { router.push(authStore.homePath) }
  else { showLoginModal.value = true }
}

const scrollObserver = ref<IntersectionObserver | null>(null)
const navSections = ['features', 'workflow', 'cases']

onMounted(() => {
  nextTick(() => {
    // Scroll reveal observer
    const reveals = document.querySelectorAll('.scroll-reveal')
    const obs = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (entry.isIntersecting) {
            entry.target.classList.add('is-visible')
            obs.unobserve(entry.target)
          }
        })
      },
      { threshold: 0.15 }
    )
    reveals.forEach((el) => obs.observe(el))
    scrollObserver.value = obs

    // Active nav section observer
    const sectionEls = navSections.map(id => document.getElementById(id)).filter(Boolean)
    const navObs = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (entry.isIntersecting) {
            activeSection.value = entry.target.id
          }
        })
      },
      { threshold: 0.5, rootMargin: '-80px 0px -50% 0px' }
    )
    sectionEls.forEach((el) => navObs.observe(el as Element))
  })
})

onUnmounted(() => { scrollObserver.value?.disconnect() })

const features = [
  {icon: "<svg width=\"22\" height=\"22\" viewBox=\"0 0 24 24\" fill=\"none\"><path d=\"M12 2L2 7L12 12L22 7L12 2Z\" stroke=\"currentColor\" stroke-width=\"1.5\" stroke-linejoin=\"round\"/><path d=\"M2 17L12 22L22 17\" stroke=\"currentColor\" stroke-width=\"1.5\" stroke-linecap=\"round\" stroke-linejoin=\"round\"/></svg>", title: "文档知识管理", desc: "上传多种格式文档，自动切片、向量化、索引入库，支持断点续传。"},
  {icon: "<svg width=\"22\" height=\"22\" viewBox=\"0 0 24 24\" fill=\"none\"><circle cx=\"11\" cy=\"11\" r=\"7\" stroke=\"currentColor\" stroke-width=\"1.5\"/><path d=\"M19 19L16 16\" stroke=\"currentColor\" stroke-width=\"1.5\" stroke-linecap=\"round\"/></svg>", title: "知识库问答", desc: "群组内提问，混合检索驱动 LLM 生成可溯源回答。"},
  {icon: "<svg width=\"22\" height=\"22\" viewBox=\"0 0 24 24\" fill=\"none\"><circle cx=\"12\" cy=\"12\" r=\"9\" stroke=\"currentColor\" stroke-width=\"1.5\"/><path d=\"M8.5 12C8.5 10.067 10.067 8.5 12 8.5C13.933 8.5 15.5 10.067 15.5 12C15.5 13.933 13.933 15.5 12 15.5C10.067 15.5 8.5 13.933 8.5 12Z\" stroke=\"currentColor\" stroke-width=\"1.5\"/></svg>", title: "AI 智能助手", desc: "多轮对话 Agent，支持 SSE 流式输出、工具编排与短期记忆管理。"},
  {icon: "<svg width=\"22\" height=\"22\" viewBox=\"0 0 24 24\" fill=\"none\"><circle cx=\"9\" cy=\"6\" r=\"3\" stroke=\"currentColor\" stroke-width=\"1.5\"/><circle cx=\"15\" cy=\"6\" r=\"3\" stroke=\"currentColor\" stroke-width=\"1.5\"/><path d=\"M3 18V17C3 14.7909 4.79086 13 7 13H11C13.2091 13 15 14.7909 15 17V18\" stroke=\"currentColor\" stroke-width=\"1.5\" stroke-linecap=\"round\"/><path d=\"M15 13H17C19.2091 13 21 14.7909 21 17V18\" stroke=\"currentColor\" stroke-width=\"1.5\" stroke-linecap=\"round\"/></svg>", title: "团队协作", desc: "创建知识库群组，邀请成员，审批申请，群组间数据隔离。"},
  {icon: "<svg width=\"22\" height=\"22\" viewBox=\"0 0 24 24\" fill=\"none\"><path d=\"M8 3H5C3.89543 3 3 3.89543 3 5V8M21 8V5C21 3.89543 20.1046 3 19 3H16M3 16V19C3 20.1046 3.89543 21 5 21H8M16 21H19C20.1046 21 21 20.1046 21 19V16\" stroke=\"currentColor\" stroke-width=\"1.5\" stroke-linecap=\"round\"/></svg>", title: "答案溯源", desc: "每条回答附带引用片段与相关度评分，让 AI 回答有据可查。"},
  {icon: "<svg width=\"22\" height=\"22\" viewBox=\"0 0 24 24\" fill=\"none\"><rect x=\"3\" y=\"3\" width=\"18\" height=\"18\" rx=\"4\" stroke=\"currentColor\" stroke-width=\"1.5\"/><path d=\"M12 7V12L15 14\" stroke=\"currentColor\" stroke-width=\"1.5\" stroke-linecap=\"round\"/></svg>", title: "安全保障", desc: "三级权限体系，JWT + BCrypt 认证，全链路数据加密。"},
]

const steps = [
  {num: "01", title: "创建群组", desc: "组建团队，邀请成员协作"},
  {num: "02", title: "上传文档", desc: "系统自动切片、向量化与索引"},
  {num: "03", title: "提问检索", desc: "混合检索生成带引用的可信回答"},
  {num: "04", title: "AI 对话", desc: "Agent 自主编排，流式输出"},
]

function scrollToSection(id: string) {
  const el = document.getElementById(id)
  if (el) { el.scrollIntoView({ behavior: 'smooth', block: 'start' }) }
}

const cases = [
  {icon: "power", title: "电力", desc: "巡检手册、安全规程、故障排除问答", color: "#f59e0b"},
  {icon: "finance", title: "金融", desc: "合规检索、风控政策、产品知识库", color: "#8b5cf6"},
  {icon: "education", title: "教育", desc: "课程知识库、学员自助答疑", color: "#06b6d4"},
  {icon: "manufacture", title: "制造", desc: "技术文档、设备SOP、供应商资料", color: "#10b981"},
]
</script><template>
  <div class="landing">
    <LoginModal v-model:visible="showLoginModal" />
    <header class="navbar">
      <div class="nav-inner container">
        <a href="/" class="nav-brand">
          <svg width="28" height="28" viewBox="0 0 32 32" fill="none">
            <defs><linearGradient id="navGrad" x1="2" y1="2" x2="30" y2="30"><stop stop-color="#818cf8"/><stop offset="1" stop-color="#06b6d4"/></linearGradient><path id="navPetal" d="M16 3C17.5 6 20 9 22.5 10C20 11 17.5 11.5 16 13C14.5 11.5 12 11 9.5 10C12 9 14.5 6 16 3Z" fill="url(#navGrad)" opacity="0.8"/></defs>
            <use href="#navPetal"/><use href="#navPetal" transform="rotate(90 16 16)"/><use href="#navPetal" transform="rotate(180 16 16)"/><use href="#navPetal" transform="rotate(270 16 16)"/><circle cx="16" cy="16" r="5.5" fill="url(#navGrad)"/>
          </svg><span>深林知识库</span>
        </a>
        <nav class="nav-links"><a :href="'#features'" :class="{ active: activeSection === 'features' }" @click.prevent="scrollToSection('features')">核心功能</a><a :href="'#workflow'" :class="{ active: activeSection === 'workflow' }" @click.prevent="scrollToSection('workflow')">工作流</a><a :href="'#cases'" :class="{ active: activeSection === 'cases' }" @click.prevent="scrollToSection('cases')">应用场景</a></nav>
        <div class="nav-actions">
          <button class="btn-ghost" @click="showLoginModal = true">登录</button>
          <button class="btn-nav-cta" @click="showLoginModal = true">免费试用</button>
        </div>
      </div>
    </header>
    <section class="hero">
      <div class="hero-bg">
        <div class="hero-grid"></div>
        <div class="glow glow-1"></div><div class="glow glow-2"></div><div class="glow glow-3"></div>
      </div>
      <div class="hero-content container">
        <div class="hero-layout">
          <div class="hero-text">
            <div class="hero-badge"><span class="pulse-dot"></span>RAG + Agent · 企业级智能知识平台</div>
            <h1 class="hero-title">让每一次提问<br/><span class="gradient-text">都有据可查</span></h1>
            <p class="hero-desc">基于检索增强生成与 AI Agent 技术，将企业私有知识库与大语言模型深度融合，实现精准溯源、自主编排的可信智能知识服务。</p>
            <div class="hero-actions">
              <button class="btn-primary" @click="showLoginModal = true">免费试用<svg width="16" height="16" viewBox="0 0 24 24" fill="none"><path d="M5 12H19M19 12L13 6M19 12L13 18" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg></button>
              <button class="btn-secondary" @click="navigateToApp()">进入工作台</button>
            </div>
            <div class="hero-metrics">
              <div class="metric"><span class="metric-value">98<span>%</span></span><span class="metric-label">检索准确率</span></div>
              <div class="metric-divider"></div>
              <div class="metric"><span class="metric-value">200<span>ms</span></span><span class="metric-label">平均响应</span></div>
              <div class="metric-divider"></div>
              <div class="metric"><span class="metric-value">20<span>+</span></span><span class="metric-label">文件格式支持</span></div>
            </div>
          </div>
          <div class="hero-mockup scroll-reveal">
            <div class="mockup-topbar">
              <div class="mockup-dots"><span></span><span></span><span></span></div>
              <div class="mockup-url">Forest.local/qa</div>
            </div>
            <div class="mockup-body">
              <div class="mockup-query"><div class="mockup-query-bubble">关于 AI Agent 的落地实践有哪些常见问题？</div></div>
              <div class="mockup-answer">
                <div class="mockup-avatar">AI</div>
                <div class="mockup-response">
                  <p>根据知识库内容，AI Agent 落地实践中常见的问题包括：</p>
                  <ul><li><span class="tag">Tool Calling 失败</span> 函数签名与模型预期不匹配</li><li><span class="tag">工具描述模糊</span> 模型无法判断何时调用</li><li><span class="tag">返回结果过长</span> 超过上下文窗口限制</li></ul>
                  <div class="mockup-citation"><svg width="12" height="12" viewBox="0 0 24 24" fill="none"><path d="M9 2H15L11 8V12H9V2Z" stroke="currentColor" stroke-width="1.5"/><path d="M9 12H15" stroke="currentColor" stroke-width="1.5"/><path d="M9 16H13" stroke="currentColor" stroke-width="1.5"/></svg><span>AI_Agent落地实践问题.docx · 第 12 页</span></div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </section>

    <section class="features" id="features">
      <div class="container">
        <div class="section-header scroll-reveal">
          <span class="section-tag">核心功能</span>
          <h2 class="section-title">覆盖知识管理全链路</h2>
          <p class="section-desc">从文档入库到 AI 对话，一站式构建企业智能知识服务体系</p>
        </div>
        <div class="bento-grid">
          <div class="bento-card bento-wide scroll-reveal" style="transition-delay:0s">
            <div class="bento-icon" style="--c:#818cf8"><svg width="22" height="22" viewBox="0 0 24 24" fill="none"><path d="M12 2L2 7L12 12L22 7L12 2Z" stroke="currentColor" stroke-width="1.5" stroke-linejoin="round"/><path d="M2 17L12 22L22 17" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/></svg></div>
            <h3>文档知识管理</h3><p>上传多种格式文档，自动切片、向量化、索引入库，支持断点续传。</p>
          </div>
          <div class="bento-card scroll-reveal" style="transition-delay:0.06s">
            <div class="bento-icon" style="--c:#06b6d4"><svg width="22" height="22" viewBox="0 0 24 24" fill="none"><circle cx="11" cy="11" r="7" stroke="currentColor" stroke-width="1.5"/><path d="M19 19L16 16" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/></svg></div>
            <h3>知识库问答</h3><p>群组内提问，混合检索驱动 LLM 生成可溯源回答。</p>
          </div>
          <div class="bento-card scroll-reveal" style="transition-delay:0.12s">
            <div class="bento-icon" style="--c:#10b981"><svg width="22" height="22" viewBox="0 0 24 24" fill="none"><circle cx="12" cy="12" r="9" stroke="currentColor" stroke-width="1.5"/><path d="M8.5 12C8.5 10.067 10.067 8.5 12 8.5C13.933 8.5 15.5 10.067 15.5 12C15.5 13.933 13.933 15.5 12 15.5C10.067 15.5 8.5 13.933 8.5 12Z" stroke="currentColor" stroke-width="1.5"/></svg></div>
            <h3>AI 智能助手</h3><p>多轮对话 Agent，支持 SSE 流式输出、工具编排与短期记忆管理。</p>
          </div>
          <div class="bento-card scroll-reveal" style="transition-delay:0.06s">
            <div class="bento-icon" style="--c:#f59e0b"><svg width="22" height="22" viewBox="0 0 24 24" fill="none"><circle cx="9" cy="6" r="3" stroke="currentColor" stroke-width="1.5"/><circle cx="15" cy="6" r="3" stroke="currentColor" stroke-width="1.5"/><path d="M3 18V17C3 14.7909 4.79086 13 7 13H11C13.2091 13 15 14.7909 15 17V18" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/><path d="M15 13H17C19.2091 13 21 14.7909 21 17V18" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/></svg></div>
            <h3>团队协作</h3><p>创建知识库群组，邀请成员，审批申请，群组间数据隔离。</p>
          </div>
          <div class="bento-card bento-wide scroll-reveal" style="transition-delay:0.12s">
            <div class="bento-icon" style="--c:#ec4899"><svg width="22" height="22" viewBox="0 0 24 24" fill="none"><path d="M8 3H5C3.89543 3 3 3.89543 3 5V8M21 8V5C21 3.89543 20.1046 3 19 3H16M3 16V19C3 20.1046 3.89543 21 5 21H8M16 21H19C20.1046 21 21 20.1046 21 19V16" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/></svg></div>
            <h3>答案溯源</h3><p>每条回答附带引用片段与相关度评分，让 AI 回答有据可查。</p>
          </div>
          <div class="bento-card scroll-reveal" style="transition-delay:0.18s">
            <div class="bento-icon" style="--c:#8b5cf6"><svg width="22" height="22" viewBox="0 0 24 24" fill="none"><rect x="3" y="3" width="18" height="18" rx="4" stroke="currentColor" stroke-width="1.5"/><path d="M12 7V12L15 14" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/></svg></div>
            <h3>安全保障</h3><p>三级权限体系，JWT + BCrypt 认证，全链路数据加密。</p>
          </div>
        </div>
      </div>
    </section>

    <section class="workflow" id="workflow">
      <div class="container container-narrow">
        <div class="section-header scroll-reveal">
          <span class="section-tag">工作流程</span>
          <h2 class="section-title">四步开启智能知识服务</h2>
          <p class="section-desc">从零到一，快速构建企业级 RAG 应用</p>
        </div>
        <div class="steps-horizontal">
          <div v-for="(s, i) in steps" :key="s.num" class="step-item scroll-reveal" :style="{transitionDelay:(i*0.08)+'s'}">
            <div class="step-num">{{ s.num }}</div>
            <h3>{{ s.title }}</h3><p>{{ s.desc }}</p>
            <svg v-if="i < steps.length - 1" class="step-arrow" width="24" height="24" viewBox="0 0 24 24" fill="none"><path d="M5 12H19M19 12L13 6M19 12L13 18" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/></svg>
          </div>
        </div>
      </div>
    </section>

    <section class="cases" id="cases">
      <div class="container">
        <div class="section-header scroll-reveal">
          <span class="section-tag">应用场景</span>
          <h2 class="section-title">赋能各行各业</h2>
          <p class="section-desc">灵活适配不同业务场景，释放企业知识资产价值</p>
        </div>
        <div class="cases-grid">
          <div v-for="(c, i) in cases" :key="i" class="case-card scroll-reveal" :style="[{transitionDelay: (i*0.06)+'s'}, {'--accent': c.color}]">
            <div class="case-top-bar" :style="{background: 'linear-gradient(90deg, ' + c.color + ', transparent)' }"></div>
            <div class="case-icon-wrap"><div class="case-icon" v-html="caseIcons[c.icon]" :style="{color:c.color}"></div></div>
            <h3>{{ c.title }}</h3><p>{{ c.desc }}</p>
          </div>
        </div>
      </div>
    </section>

    <section class="cta">
      <div class="container">
        <div class="cta-card scroll-reveal">
          <div class="cta-glow-1"></div><div class="cta-glow-2"></div>
          <h2>准备好构建您的<br/>智能知识平台了吗？</h2>
          <p>立即体验企业级 RAG + Agent 解决方案，让每一次提问都有据可查。</p>
          <div class="cta-buttons">
            <button class="btn-cta-primary" @click="showLoginModal = true">免费试用</button>
            <button class="btn-cta-outline" @click="navigateToApp()">查看演示</button>
          </div>
        </div>
      </div>
    </section>

    <footer class="footer">
      <div class="container">
        <div class="footer-grid">
          <div class="footer-brand">
            <div class="footer-logo-row">
              <svg width="24" height="24" viewBox="0 0 32 32" fill="none"><defs><linearGradient id="ftGrad" x1="2" y1="2" x2="30" y2="30"><stop stop-color="#818cf8"/><stop offset="1" stop-color="#06b6d4"/></linearGradient><path id="ftPetal" d="M16 3C17.5 6 20 9 22.5 10C20 11 17.5 11.5 16 13C14.5 11.5 12 11 9.5 10C12 9 14.5 6 16 3Z" fill="url(#ftGrad)" opacity="0.8"/></defs><use href="#ftPetal"/><use href="#ftPetal" transform="rotate(90 16 16)"/><use href="#ftPetal" transform="rotate(180 16 16)"/><use href="#ftPetal" transform="rotate(270 16 16)"/><circle cx="16" cy="16" r="5.5" fill="url(#ftGrad)"/></svg>
              <span>深林知识库</span>
            </div>
            <p>融合 RAG 与 AI Agent 技术的企业级智能知识平台</p>
          </div>
          <div class="footer-col"><h4>产品</h4><a href="#features">核心功能</a><a href="#workflow">工作流程</a><a href="#cases">应用场景</a></div>
          <div class="footer-col"><h4>接口</h4><a href="#">REST API</a><a href="#">SSE 流式</a><a href="#">认证鉴权</a></div>
          <div class="footer-col"><h4>关于</h4><a href="#">项目文档</a><a href="#">架构设计</a><a href="#">更新日志</a></div>
        </div>
        <div class="footer-bottom"><p>&copy; 2026 深林知识库. All rights reserved.</p></div>
      </div>
    </footer>
  </div>
</template>

<script lang="ts">
const caseIcons: Record<string, string> = {
  power: '<svg width="28" height="28" viewBox="0 0 24 24" fill="none"><path d="M13 2L4 14H11L11 22L20 10H13L13 2Z" stroke="currentColor" stroke-width="1.5" stroke-linejoin="round"/></svg>',
  finance: '<svg width="28" height="28" viewBox="0 0 24 24" fill="none"><rect x="2" y="4" width="20" height="16" rx="3" stroke="currentColor" stroke-width="1.5"/><path d="M12 9V15M9 12H15" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/></svg>',
  education: '<svg width="28" height="28" viewBox="0 0 24 24" fill="none"><path d="M4 7L12 3L20 7L12 11L4 7Z" stroke="currentColor" stroke-width="1.5" stroke-linejoin="round"/><path d="M6 10V16C6 16 8 19 12 19C16 19 18 16 18 16V10" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/></svg>',
  manufacture: '<svg width="28" height="28" viewBox="0 0 24 24" fill="none"><rect x="2" y="2" width="20" height="20" rx="3" stroke="currentColor" stroke-width="1.5"/><path d="M8 8H16M8 12H16M8 16H12" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/></svg>',
}
</script>
<style scoped>
html { scroll-behavior: smooth; }
/* Navbar */
.navbar {
  position: fixed; top: 0; left: 0; right: 0; z-index: 100;
  background: rgba(10, 15, 30, 0.85);
  backdrop-filter: blur(20px);
  -webkit-backdrop-filter: blur(20px);
  border-bottom: 1px solid rgba(255,255,255,0.06);
}
.nav-inner { height: 64px; display: flex; align-items: center; justify-content: space-between; }
.nav-brand { display: flex; align-items: center; gap: 10px; font-weight: 700; font-size: 16px; color: #f1f5f9; text-decoration: none; letter-spacing: -0.01em; }
.nav-links { display: flex; gap: 32px; }
.nav-links a { font-size: 13.5px; font-weight: 500; color: #94a3b8; text-decoration: none; transition: color 0.2s; }
 .nav-links a:hover { color: #f1f5f9; }
.nav-links a.active { color: #818cf8; font-weight: 600; position: relative; }
.nav-links a.active::after {
  content: '';
  position: absolute;
  bottom: -4px;
  left: 0;
  right: 0;
  height: 2px;
  background: linear-gradient(90deg, #818cf8, #06b6d4);
  border-radius: 1px;
}
.nav-actions { display: flex; align-items: center; gap: 8px; }
.btn-ghost { padding: 7px 18px; border-radius: 8px; font-size: 13.5px; font-weight: 500; color: #94a3b8; background: transparent; transition: all 0.2s; cursor: pointer; border: none; }
.btn-ghost:hover { color: #f1f5f9; background: rgba(255,255,255,0.05); }
.btn-nav-cta { padding: 7px 20px; border-radius: 8px; font-size: 13.5px; font-weight: 600; color: #fff; background: linear-gradient(135deg, #818cf8, #06b6d4); transition: all 0.2s; cursor: pointer; border: none; }
.btn-nav-cta:hover { opacity: 0.9; transform: translateY(-1px); }

/* Hero */
.hero { position: relative; min-height: 100vh; display: flex; align-items: center; background: #0a0f1e; overflow: hidden; padding: 80px 0 100px; }
.hero-bg { position: absolute; inset: 0; pointer-events: none; }
.hero-grid { position: absolute; inset: 0; background-image: linear-gradient(rgba(129,140,248,0.04) 1px, transparent 1px), linear-gradient(90deg, rgba(129,140,248,0.04) 1px, transparent 1px); background-size: 64px 64px; mask-image: radial-gradient(ellipse 80% 80% at 50% 50%, black 20%, transparent 70%); }
.glow { position: absolute; border-radius: 50%; filter: blur(120px); }
.glow-1 { width: 600px; height: 600px; background: rgba(129,140,248,0.12); top: -200px; right: -100px; }
.glow-2 { width: 400px; height: 400px; background: rgba(6,182,212,0.1); bottom: -100px; left: 10%; }
.glow-3 { width: 250px; height: 250px; background: rgba(139,92,246,0.08); top: 40%; left: 30%; }
.hero-content { position: relative; z-index: 2; }
.hero-layout { display: grid; grid-template-columns: 1fr 1fr; gap: 64px; align-items: center; }
.hero-text { max-width: 560px; }
.hero-badge { display: inline-flex; align-items: center; gap: 8px; padding: 5px 14px; border-radius: 100px; background: rgba(129,140,248,0.1); border: 1px solid rgba(129,140,248,0.2); font-size: 12.5px; font-weight: 500; color: #818cf8; margin-bottom: 28px; animation: fade-in-up 0.5s ease; }
.pulse-dot { width: 6px; height: 6px; border-radius: 50%; background: #06b6d4; animation: pulse-ring 2s ease-in-out infinite; }
@keyframes pulse-ring { 0%,100%{opacity:1;transform:scale(1)} 50%{opacity:0.5;transform:scale(1.5)} }
.hero-title { font-size: clamp(40px,5vw,60px); font-weight: 800; line-height: 1.1; letter-spacing: -0.03em; color: #f1f5f9; margin-bottom: 20px; animation: fade-in-up 0.5s ease 0.1s both; }
.gradient-text { background: linear-gradient(135deg, #818cf8, #06b6d4); -webkit-background-clip: text; background-clip: text; -webkit-text-fill-color: transparent; }
.hero-desc { font-size: 15px; line-height: 1.75; color: #94a3b8; margin-bottom: 36px; animation: fade-in-up 0.5s ease 0.2s both; }
.hero-actions { display: flex; gap: 12px; animation: fade-in-up 0.5s ease 0.3s both; }
.btn-primary { display: inline-flex; align-items: center; gap: 8px; padding: 14px 28px; border-radius: 10px; background: linear-gradient(135deg, #818cf8, #06b6d4); color: #fff; font-size: 15px; font-weight: 600; transition: all 0.25s; box-shadow: 0 4px 24px rgba(129,140,248,0.35); border: none; cursor: pointer; }
.btn-primary:hover { transform: translateY(-2px); box-shadow: 0 8px 32px rgba(129,140,248,0.45); }
.btn-secondary { display: inline-flex; align-items: center; gap: 8px; padding: 14px 28px; border-radius: 10px; border: 1px solid rgba(255,255,255,0.1); color: #f1f5f9; font-size: 15px; font-weight: 600; background: rgba(255,255,255,0.04); transition: all 0.2s; cursor: pointer; }
.btn-secondary:hover { background: rgba(255,255,255,0.08); border-color: rgba(255,255,255,0.15); }
.hero-metrics { display: flex; align-items: center; gap: 32px; margin-top: 56px; animation: fade-in-up 0.5s ease 0.4s both; }
.metric { text-align: left; }
.metric-value { display: block; font-size: 28px; font-weight: 800; color: #f1f5f9; line-height: 1; margin-bottom: 4px; }
.metric-unit { font-size: 16px; color: #06b6d4; font-weight: 600; }
.metric-label { font-size: 12px; color: #64748b; font-weight: 500; }
.metric-divider { width: 1px; height: 36px; background: rgba(255,255,255,0.08); }

/* Mockup */
.hero-mockup { border-radius: 16px; overflow: hidden; border: 1px solid rgba(255,255,255,0.06); background: rgba(255,255,255,0.02); backdrop-filter: blur(8px); animation: fade-in-up 0.6s ease 0.3s both; box-shadow: 0 32px 64px rgba(0,0,0,0.5); }
.mockup-topbar { display: flex; align-items: center; gap: 8px; padding: 12px 16px; background: rgba(0,0,0,0.4); border-bottom: 1px solid rgba(255,255,255,0.06); }
.mockup-dots { display: flex; gap: 6px; }
.mockup-dots span { width: 10px; height: 10px; border-radius: 50%; background: rgba(255,255,255,0.12); }
.mockup-dots span:first-child { background: #ff5f57; }
.mockup-dots span:nth-child(2) { background: #ffbd2e; }
.mockup-dots span:last-child { background: #28ca41; }
.mockup-url { font-size: 12px; color: #64748b; flex: 1; text-align: center; margin-right: 42px; }
.mockup-body { padding: 20px; display: flex; flex-direction: column; gap: 16px; }
.mockup-query-bubble { background: rgba(129,140,248,0.1); border: 1px solid rgba(129,140,248,0.2); border-radius: 10px 10px 10px 2px; padding: 10px 14px; font-size: 13px; color: #f1f5f9; align-self: flex-start; max-width: 85%; }
.mockup-answer { display: flex; gap: 12px; align-items: flex-start; }
.mockup-avatar { width: 32px; height: 32px; border-radius: 8px; background: linear-gradient(135deg, #818cf8, #06b6d4); display: flex; align-items: center; justify-content: center; font-size: 11px; font-weight: 700; color: #fff; flex-shrink: 0; }
.mockup-response { font-size: 13px; color: #94a3b8; line-height: 1.65; flex: 1; }
.mockup-response p { margin: 0 0 10px; }
.mockup-response ul { margin: 0 0 12px; padding-left: 0; list-style: none; display: flex; flex-direction: column; gap: 6px; }
.mockup-response li { display: flex; align-items: center; gap: 8px; font-size: 12.5px; color: #94a3b8; }
.tag { display: inline-block; padding: 2px 8px; border-radius: 4px; background: rgba(245,158,11,0.15); color: #f59e0b; font-size: 11.5px; font-weight: 600; white-space: nowrap; }
.mockup-citation { display: flex; align-items: center; gap: 6px; padding: 8px 12px; border-radius: 8px; background: rgba(16,185,129,0.08); border: 1px solid rgba(16,185,129,0.15); font-size: 11.5px; color: #10b981; margin-top: 10px; }

/* Section Headers */
.section-header { text-align: center; margin-bottom: 64px; }
.section-tag { display: inline-block; padding: 4px 14px; border-radius: 100px; background: rgba(129,140,248,0.1); border: 1px solid rgba(129,140,248,0.2); color: #818cf8; font-size: 12px; font-weight: 600; letter-spacing: 0.04em; margin-bottom: 16px; }
.section-title { font-size: clamp(24px,3vw,36px); font-weight: 800; color: #f1f5f9; letter-spacing: -0.02em; margin-bottom: 12px; }
.section-desc { font-size: 14.5px; color: #94a3b8; max-width: 440px; margin: 0 auto; }

/* Features Bento */
.features { padding: 120px 0; background: #0d1321; }
.bento-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 16px; }
.bento-card { padding: 28px 24px; border-radius: 16px; border: 1px solid rgba(255,255,255,0.06); background: rgba(255,255,255,0.02); transition: all 0.3s; }
.bento-card:hover { background: rgba(255,255,255,0.04); border-color: rgba(129,140,248,0.2); transform: translateY(-2px); }
.bento-wide { grid-column: span 2; }
.bento-icon { width: 40px; height: 40px; border-radius: 10px; background: color-mix(in srgb, var(--c) 15%, transparent); border: 1px solid color-mix(in srgb, var(--c) 30%, transparent); display: flex; align-items: center; justify-content: center; color: var(--c); margin-bottom: 16px; }
.bento-card h3 { font-size: 15px; font-weight: 700; color: #f1f5f9; margin-bottom: 6px; }
.bento-card p { font-size: 13px; color: #94a3b8; line-height: 1.65; margin: 0; }

/* Workflow */
.workflow { padding: 120px 0; background: #0a0f1e; }
.steps-horizontal { display: flex; align-items: flex-start; justify-content: space-between; position: relative; }
.step-item { flex: 1; text-align: center; display: flex; flex-direction: column; align-items: center; gap: 14px; position: relative; }
.step-num { width: 48px; height: 48px; border-radius: 14px; background: linear-gradient(135deg, rgba(129,140,248,0.15), rgba(6,182,212,0.1)); border: 1px solid rgba(129,140,248,0.2); display: flex; align-items: center; justify-content: center; font-family: "Poppins", sans-serif; font-size: 16px; font-weight: 800; color: #818cf8; flex-shrink: 0; }
.step-item h3 { font-size: 15px; font-weight: 700; color: #f1f5f9; margin: 0; }
.step-item p { font-size: 12.5px; color: #64748b; line-height: 1.55; max-width: 180px; margin: 0 auto; }
.step-arrow { position: absolute; top: 22px; right: -14px; color: #64748b; opacity: 0.4; }

/* Cases */
.cases { padding: 120px 0; background: #0d1321; }
.cases-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 16px; }
.case-card { padding: 0; border-radius: 16px; border: 1px solid rgba(255,255,255,0.06); background: rgba(255,255,255,0.02); overflow: hidden; transition: all 0.3s; text-align: left; }
.case-card:hover { border-color: color-mix(in srgb, var(--accent) 40%, transparent); transform: translateY(-2px); box-shadow: 0 12px 40px color-mix(in srgb, var(--accent) 10%, transparent); }
.case-top-bar { height: 3px; width: 100%; }
.case-icon-wrap { padding: 24px 20px 0; }
.case-icon { width: 44px; height: 44px; border-radius: 12px; background: color-mix(in srgb, var(--accent) 12%, transparent); display: flex; align-items: center; justify-content: center; }
.case-icon svg { width: 24px; height: 24px; }
.case-card h3 { font-size: 15px; font-weight: 700; color: #f1f5f9; margin: 14px 0 6px 20px; }
.case-card p { font-size: 12.5px; color: #94a3b8; line-height: 1.6; margin: 0 0 20px 20px; }

/* CTA */
.cta { padding: 100px 0; background: #0a0f1e; }
.cta-card { position: relative; text-align: center; padding: 80px 48px; border-radius: 24px; background: linear-gradient(135deg, rgba(129,140,248,0.08), rgba(6,182,212,0.06)); border: 1px solid rgba(129,140,248,0.15); overflow: hidden; }
.cta-glow-1 { position: absolute; width: 300px; height: 300px; border-radius: 50%; background: rgba(129,140,248,0.12); filter: blur(80px); top: -100px; right: -80px; pointer-events: none; }
.cta-glow-2 { position: absolute; width: 200px; height: 200px; border-radius: 50%; background: rgba(6,182,212,0.1); filter: blur(60px); bottom: -60px; left: -40px; pointer-events: none; }
.cta-card h2 { font-size: clamp(24px,3vw,36px); font-weight: 800; color: #f1f5f9; position: relative; z-index: 1; margin-bottom: 14px; letter-spacing: -0.02em; }
.cta-card p { font-size: 15px; color: #94a3b8; position: relative; z-index: 1; margin-bottom: 36px; max-width: 480px; margin-left: auto; margin-right: auto; }
.cta-buttons { display: flex; gap: 12px; justify-content: center; position: relative; z-index: 1; }
.btn-cta-primary { display: inline-flex; align-items: center; padding: 14px 32px; border-radius: 10px; background: linear-gradient(135deg, #818cf8, #06b6d4); color: #fff; font-size: 15px; font-weight: 600; transition: all 0.25s; box-shadow: 0 4px 24px rgba(129,140,248,0.3); border: none; cursor: pointer; }
.btn-cta-primary:hover { transform: translateY(-2px); box-shadow: 0 8px 32px rgba(129,140,248,0.4); }
.btn-cta-outline { display: inline-flex; align-items: center; padding: 14px 32px; border-radius: 10px; border: 1px solid rgba(255,255,255,0.1); color: #f1f5f9; font-size: 15px; font-weight: 600; background: rgba(255,255,255,0.04); transition: all 0.2s; cursor: pointer; }
.btn-cta-outline:hover { background: rgba(255,255,255,0.08); border-color: rgba(255,255,255,0.15); }

/* Footer */
.footer { background: #0a0f1e; border-top: 1px solid rgba(255,255,255,0.06); padding: 64px 0 28px; }
.footer-grid { display: grid; grid-template-columns: 2fr 1fr 1fr 1fr; gap: 48px; margin-bottom: 48px; }
.footer-logo-row { display: flex; align-items: center; gap: 10px; font-weight: 700; font-size: 15px; color: #f1f5f9; margin-bottom: 10px; text-decoration: none; }
.footer-brand p { font-size: 13px; color: #64748b; line-height: 1.7; margin: 0; }
.footer-col h4 { font-size: 11.5px; font-weight: 700; color: #64748b; text-transform: uppercase; letter-spacing: 0.06em; margin-bottom: 16px; }
.footer-col a { display: block; font-size: 13px; color: #94a3b8; padding: 4px 0; transition: color 0.2s; text-decoration: none; }
.footer-col a:hover { color: #f1f5f9; }
.footer-bottom { padding-top: 24px; border-top: 1px solid rgba(255,255,255,0.06); text-align: center; }
.footer-bottom p { font-size: 12.5px; color: #64748b; margin: 0; }

/* Animations */
@keyframes fade-in-up { from { opacity: 0; transform: translateY(16px); } to { opacity: 1; transform: translateY(0); } }
.scroll-reveal { opacity: 0; transform: translateY(20px); transition: opacity 0.6s ease, transform 0.6s cubic-bezier(0.16, 1, 0.3, 1); }
.scroll-reveal.is-visible { opacity: 1; transform: translateY(0); }

/* Responsive */
@media (max-width: 1024px) {
  .hero-layout { grid-template-columns: 1fr; gap: 48px; }
  .hero-text { max-width: 100%; text-align: center; }
  .hero-actions { justify-content: center; }
  .hero-metrics { justify-content: center; }
  .bento-grid { grid-template-columns: repeat(2, 1fr); }
  .bento-wide { grid-column: span 2; }
  .cases-grid { grid-template-columns: repeat(2, 1fr); }
  .footer-grid { grid-template-columns: 1fr 1fr; }
}
@media (max-width: 768px) {
  .nav-links { display: none; }
  .hero { padding: 100px 0 60px; }
  .hero-title { font-size: 32px; }
  .hero-actions { flex-direction: column; align-items: center; }
  .hero-metrics { flex-direction: column; gap: 16px; }
  .metric-divider { width: 36px; height: 1px; }
  .bento-grid { grid-template-columns: 1fr; }
  .bento-wide { grid-column: span 1; }
  .steps-horizontal { flex-direction: column; gap: 24px; }
  .step-arrow { display: none !important; }
  .cases-grid { grid-template-columns: 1fr; }
  .cta-card { padding: 48px 24px; }
  .cta-buttons { flex-direction: column; align-items: center; }
  .footer-grid { grid-template-columns: 1fr; gap: 28px; }
}
</style>
