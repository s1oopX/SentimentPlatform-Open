<script setup>
import { computed } from 'vue'
import { useRouter } from 'vue-router'
import AuthBrandBadge from '@/components/AuthBrandBadge.vue'
import { useAuthStore } from '@/stores/auth'
import { getDefaultHomeRoute } from '@/router/access'
import { isResolvedAuthenticated } from '@/router/guardState'
import {
  DataLine,
  Lightning,
  Lock,
  MagicStick,
  Odometer,
  SwitchButton,
  TrendCharts,
  UserFilled,
} from '@element-plus/icons-vue'
import { useLogout } from '@/composables/useLogout'

const router = useRouter()
const authStore = useAuthStore()

const isAuthenticated = computed(() =>
  isResolvedAuthenticated({
    token: authStore.token,
    user: authStore.user,
  })
)
const user = computed(() => authStore.user)

const authenticatedCtaLabel = computed(() => {
  const role = user.value?.role
  if (role === 'admin') return '进入管理控制台'
  if (role === 'analyst') return '进入分析师工作台'
  return '进入仪表盘'
})

const { handleLogout } = useLogout({ redirectTo: null })

const scrollToFeatures = () => {
  window.document.getElementById('features')?.scrollIntoView({ behavior: 'smooth' })
}
</script>

<template>
  <div class="landing-page min-h-screen">
    <header class="landing-header">
      <div class="mx-auto flex max-w-7xl flex-wrap items-center justify-between gap-4 px-6 py-4">
        <button class="brand-button" type="button" @click="router.push('/')">
          <AuthBrandBadge size="compact" />
          <span>云析智研</span>
        </button>

        <div class="flex flex-wrap items-center justify-end gap-3">
          <template v-if="isAuthenticated">
            <div class="session-pill">
              <span class="session-avatar">
                {{
                  (user?.display_name || user?.nickname || user?.email || 'U')
                    .charAt(0)
                    .toUpperCase()
                }}
              </span>
              <span class="session-name">{{
                user?.display_name || user?.nickname || user?.email
              }}</span>
            </div>
            <el-button
              class="landing-secondary-button"
              @click="router.push(getDefaultHomeRoute(user))"
            >
              <el-icon class="mr-2"><Odometer /></el-icon>
              {{ authenticatedCtaLabel }}
            </el-button>
            <el-button class="landing-secondary-button" @click="handleLogout">
              <el-icon class="mr-2"><SwitchButton /></el-icon>
              退出
            </el-button>
          </template>
          <template v-else>
            <el-button class="landing-secondary-button" @click="router.push('/login')"
              >登录</el-button
            >
            <el-button
              type="primary"
              class="landing-primary-button"
              @click="router.push('/register')"
            >
              开始使用
            </el-button>
          </template>
        </div>
      </div>
    </header>

    <main>
      <section class="hero-section">
        <div class="hero-grid mx-auto max-w-7xl px-6">
          <div class="hero-copy">
            <div class="eyebrow">
              <el-icon><MagicStick /></el-icon>
              <span>开源中文情感分析平台</span>
            </div>

            <h1>从评论流到可执行洞察</h1>
            <p class="hero-lead">
              面向产品反馈、客服工单和电商评论，提供评论解析、情感识别、分析师审核、报告生成与后台运维的一体化工作台。
            </p>

            <div class="hero-actions">
              <el-button
                v-if="isAuthenticated"
                type="primary"
                size="large"
                class="landing-primary-button landing-primary-button--large"
                @click="router.push(getDefaultHomeRoute(user))"
              >
                <el-icon class="mr-2"><Odometer /></el-icon>
                {{ authenticatedCtaLabel }}
              </el-button>
              <el-button
                v-else
                type="primary"
                size="large"
                class="landing-primary-button landing-primary-button--large"
                @click="router.push('/register')"
              >
                <el-icon class="mr-2"><MagicStick /></el-icon>
                开始分析
              </el-button>
              <el-button
                size="large"
                class="landing-secondary-button landing-secondary-button--large"
                @click="scrollToFeatures"
              >
                查看能力
              </el-button>
            </div>

            <div class="boundary-strip">
              <span>公开版仅包含源码、测试与文档</span>
              <strong>模型权重与数据集需本地接入</strong>
            </div>
          </div>

          <div class="console-preview" aria-label="情感分析工作台预览">
            <div class="console-topbar">
              <div class="console-dots" aria-hidden="true">
                <span></span>
                <span></span>
                <span></span>
              </div>
              <span>Sentiment Console</span>
              <strong>Local Ready</strong>
            </div>

            <div class="console-body">
              <aside class="console-rail" aria-hidden="true">
                <span class="rail-item rail-item--active"></span>
                <span class="rail-item"></span>
                <span class="rail-item"></span>
                <span class="rail-item"></span>
              </aside>

              <div class="insight-panel insight-panel--input">
                <div class="panel-label">评论样本</div>
                <p>“界面响应很快，批量导入后几分钟就能看到趋势，客服记录也更容易归类。”</p>
                <div class="keyword-row">
                  <span>响应快</span>
                  <span>批量导入</span>
                  <span>易归类</span>
                </div>
              </div>

              <div class="insight-panel insight-panel--chart">
                <div class="panel-label">情感分布</div>
                <div class="bar-row">
                  <span>积极</span>
                  <div><i class="bar-positive"></i></div>
                  <strong>62</strong>
                </div>
                <div class="bar-row">
                  <span>中性</span>
                  <div><i class="bar-neutral"></i></div>
                  <strong>21</strong>
                </div>
                <div class="bar-row">
                  <span>消极</span>
                  <div><i class="bar-negative"></i></div>
                  <strong>17</strong>
                </div>
              </div>

              <div class="insight-panel insight-panel--queue">
                <div class="panel-label">审核队列</div>
                <ul>
                  <li><span data-tone="risk"></span> 高风险差评待复核</li>
                  <li><span data-tone="note"></span> 分析师备注已同步</li>
                  <li><span data-tone="done"></span> 报告任务已入队</li>
                </ul>
              </div>

              <div class="insight-panel insight-panel--metric">
                <div>
                  <span>覆盖流程</span>
                  <strong>分析 · 审核 · 报告 · 运维</strong>
                </div>
                <TrendCharts class="metric-mark" />
              </div>
            </div>
          </div>
        </div>
      </section>

      <section id="features" class="feature-section">
        <div class="mx-auto max-w-7xl px-6">
          <div class="section-heading">
            <span>Workflow</span>
            <h2>围绕真实评论处理链路组织</h2>
          </div>

          <div class="capability-grid">
            <article class="capability-card">
              <el-icon><MagicStick /></el-icon>
              <h3>文本分析</h3>
              <p>单条与批量评论进入统一分析流程，结果包含情感标签、置信度、关键词和历史记录。</p>
            </article>
            <article class="capability-card">
              <el-icon><TrendCharts /></el-icon>
              <h3>可视化洞察</h3>
              <p>面向情感分布、趋势、关键词、模型指标和报告摘要提供可复用图表组件。</p>
            </article>
            <article class="capability-card">
              <el-icon><UserFilled /></el-icon>
              <h3>角色工作台</h3>
              <p>普通用户、分析师、管理员拥有独立导航、权限边界和默认工作入口。</p>
            </article>
            <article class="capability-card">
              <el-icon><DataLine /></el-icon>
              <h3>模型与数据管理</h3>
              <p>公开版保留模型注册、训练任务和数据集管理代码，资产由部署者在本地准备。</p>
            </article>
            <article class="capability-card">
              <el-icon><Lightning /></el-icon>
              <h3>异步任务</h3>
              <p>报告生成、训练队列、定时清理和自动重训检查通过 Celery 统一编排。</p>
            </article>
            <article class="capability-card">
              <el-icon><Lock /></el-icon>
              <h3>审计与边界</h3>
              <p>JWT、HttpOnly refresh cookie、RBAC、路径校验和操作日志共同守住高权限操作。</p>
            </article>
          </div>
        </div>
      </section>

      <section class="flow-section">
        <div class="mx-auto max-w-7xl px-6">
          <div class="flow-panel">
            <div class="flow-copy">
              <span>Open Source Boundary</span>
              <h2>源码公开，资产留在部署环境</h2>
              <p>
                仓库包含前后端源码、测试、CI、文档和空资产目录说明；模型权重、训练数据、本地账号、日志、上传文件与报告导出不进入公开版本。
              </p>
            </div>
            <div class="flow-steps">
              <div>
                <strong>01</strong>
                <span>准备本地模型与数据</span>
              </div>
              <div>
                <strong>02</strong>
                <span>启动 Django、Redis、Celery 与 Vite</span>
              </div>
              <div>
                <strong>03</strong>
                <span>在三角色工作台完成分析与运维</span>
              </div>
            </div>
          </div>
        </div>
      </section>
    </main>

    <footer class="landing-footer">
      <div class="mx-auto flex max-w-7xl flex-wrap items-center justify-between gap-3 px-6 py-8">
        <div class="flex items-center gap-2">
          <AuthBrandBadge size="compact" />
          <span>SentimentPlatform</span>
        </div>
        <p>MIT licensed source release · model and dataset assets are intentionally excluded</p>
      </div>
    </footer>
  </div>
</template>

<style scoped>
.landing-page {
  min-height: 100vh;
  background:
    linear-gradient(180deg, rgba(248, 250, 252, 0.96), rgba(241, 245, 249, 0.92)),
    repeating-linear-gradient(90deg, rgba(15, 23, 42, 0.035) 0 1px, transparent 1px 104px);
  color: #0f172a;
}

.landing-header {
  position: sticky;
  top: 0;
  z-index: 50;
  border-bottom: 1px solid rgba(203, 213, 225, 0.82);
  background: rgba(255, 255, 255, 0.88);
  backdrop-filter: blur(18px);
}

.brand-button {
  display: inline-flex;
  align-items: center;
  gap: 0.625rem;
  border: 0;
  background: transparent;
  color: #0f172a;
  cursor: pointer;
  font-size: 1.05rem;
  font-weight: 800;
  padding: 0;
}

.session-pill {
  display: inline-flex;
  align-items: center;
  gap: 0.5rem;
  max-width: 18rem;
  border: 1px solid #e2e8f0;
  border-radius: 999px;
  background: #ffffff;
  padding: 0.375rem 0.75rem 0.375rem 0.375rem;
  box-shadow: 0 10px 24px rgba(15, 23, 42, 0.06);
}

.session-avatar {
  display: inline-flex;
  width: 1.75rem;
  height: 1.75rem;
  align-items: center;
  justify-content: center;
  border-radius: 999px;
  background: #0f172a;
  color: #ffffff;
  font-size: 0.75rem;
  font-weight: 800;
}

.session-name {
  min-width: 0;
  overflow: hidden;
  color: #475569;
  font-size: 0.875rem;
  font-weight: 600;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.hero-section {
  padding: 3rem 0 1.5rem;
}

.hero-grid {
  display: grid;
  grid-template-columns: minmax(0, 0.9fr) minmax(420px, 1.1fr);
  gap: 3rem;
  align-items: center;
}

.hero-copy {
  max-width: 42rem;
}

.eyebrow {
  display: inline-flex;
  align-items: center;
  gap: 0.5rem;
  border: 1px solid #cbd5e1;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.78);
  color: #334155;
  font-size: 0.875rem;
  font-weight: 700;
  padding: 0.5rem 0.8rem;
}

.hero-copy h1 {
  margin: 1.25rem 0 1rem;
  max-width: 11ch;
  color: #0f172a;
  font-size: 3.65rem;
  font-weight: 850;
  line-height: 1.03;
}

.hero-lead {
  max-width: 40rem;
  color: #475569;
  font-size: 1.06rem;
  line-height: 1.75;
}

.hero-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 0.85rem;
  margin-top: 1.6rem;
}

.boundary-strip {
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;
  align-items: center;
  margin-top: 1.4rem;
  color: #64748b;
  font-size: 0.9rem;
}

.boundary-strip strong {
  color: #0f766e;
  font-weight: 800;
}

.console-preview {
  overflow: hidden;
  border: 1px solid rgba(148, 163, 184, 0.34);
  border-radius: 8px;
  background: #0f172a;
  box-shadow: 0 28px 70px rgba(15, 23, 42, 0.18);
}

.console-topbar {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  border-bottom: 1px solid rgba(148, 163, 184, 0.18);
  background: #111827;
  color: #cbd5e1;
  font-size: 0.78rem;
  font-weight: 700;
  padding: 0.8rem 1rem;
}

.console-topbar strong {
  margin-left: auto;
  border: 1px solid rgba(20, 184, 166, 0.32);
  border-radius: 999px;
  background: rgba(20, 184, 166, 0.12);
  color: #5eead4;
  font-size: 0.72rem;
  padding: 0.2rem 0.55rem;
}

.console-dots {
  display: inline-flex;
  gap: 0.35rem;
}

.console-dots span {
  width: 0.58rem;
  height: 0.58rem;
  border-radius: 999px;
  background: #64748b;
}

.console-dots span:nth-child(1) {
  background: #fb7185;
}

.console-dots span:nth-child(2) {
  background: #facc15;
}

.console-dots span:nth-child(3) {
  background: #34d399;
}

.console-body {
  display: grid;
  grid-template-columns: 3.25rem minmax(0, 1.25fr) minmax(0, 1fr);
  gap: 0.85rem;
  min-height: 21rem;
  padding: 1rem;
  background:
    linear-gradient(135deg, rgba(15, 23, 42, 0.98), rgba(31, 41, 55, 0.96)),
    linear-gradient(90deg, rgba(20, 184, 166, 0.08), rgba(245, 158, 11, 0.06));
}

.console-rail {
  grid-row: span 3;
  display: flex;
  flex-direction: column;
  gap: 0.7rem;
  align-items: center;
  border: 1px solid rgba(148, 163, 184, 0.18);
  border-radius: 8px;
  background: rgba(2, 6, 23, 0.42);
  padding: 0.85rem 0;
}

.rail-item {
  width: 1.45rem;
  height: 1.45rem;
  border-radius: 8px;
  background: rgba(148, 163, 184, 0.22);
}

.rail-item--active {
  background: #14b8a6;
  box-shadow: 0 0 0 4px rgba(20, 184, 166, 0.18);
}

.insight-panel {
  border: 1px solid rgba(148, 163, 184, 0.18);
  border-radius: 8px;
  background: rgba(15, 23, 42, 0.72);
  color: #e2e8f0;
  padding: 1rem;
}

.panel-label {
  margin-bottom: 0.85rem;
  color: #94a3b8;
  font-size: 0.72rem;
  font-weight: 800;
  text-transform: uppercase;
}

.insight-panel--input {
  grid-column: span 2;
}

.insight-panel--input p {
  margin: 0;
  color: #f8fafc;
  font-size: 1.02rem;
  line-height: 1.8;
}

.keyword-row {
  display: flex;
  flex-wrap: wrap;
  gap: 0.45rem;
  margin-top: 1rem;
}

.keyword-row span {
  border: 1px solid rgba(20, 184, 166, 0.24);
  border-radius: 999px;
  background: rgba(20, 184, 166, 0.1);
  color: #99f6e4;
  font-size: 0.75rem;
  font-weight: 700;
  padding: 0.25rem 0.55rem;
}

.bar-row {
  display: grid;
  grid-template-columns: 2.7rem minmax(0, 1fr) 2.1rem;
  gap: 0.6rem;
  align-items: center;
  color: #cbd5e1;
  font-size: 0.82rem;
  margin: 0.85rem 0;
}

.bar-row div {
  overflow: hidden;
  height: 0.55rem;
  border-radius: 999px;
  background: rgba(148, 163, 184, 0.18);
}

.bar-row i {
  display: block;
  height: 100%;
  border-radius: 999px;
}

.bar-positive {
  width: 78%;
  background: #22c55e;
}

.bar-neutral {
  width: 44%;
  background: #f59e0b;
}

.bar-negative {
  width: 31%;
  background: #f43f5e;
}

.insight-panel--queue ul {
  display: grid;
  gap: 0.8rem;
  margin: 0;
  padding: 0;
  list-style: none;
}

.insight-panel--queue li {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  color: #dbeafe;
  font-size: 0.86rem;
}

.insight-panel--queue span {
  width: 0.58rem;
  height: 0.58rem;
  border-radius: 999px;
}

.insight-panel--queue span[data-tone='risk'] {
  background: #fb7185;
}

.insight-panel--queue span[data-tone='note'] {
  background: #38bdf8;
}

.insight-panel--queue span[data-tone='done'] {
  background: #34d399;
}

.insight-panel--metric {
  grid-column: span 2;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 1rem;
  background: linear-gradient(135deg, rgba(20, 184, 166, 0.18), rgba(245, 158, 11, 0.12));
}

.insight-panel--metric span {
  display: block;
  color: #99f6e4;
  font-size: 0.76rem;
  font-weight: 800;
  text-transform: uppercase;
}

.insight-panel--metric strong {
  display: block;
  margin-top: 0.3rem;
  color: #ffffff;
  font-size: 1.05rem;
}

.metric-mark {
  width: 3rem;
  height: 3rem;
  color: #fcd34d;
}

.feature-section,
.flow-section {
  padding: 4rem 0;
}

.feature-section {
  background: #ffffff;
  border-top: 1px solid #e2e8f0;
  padding-top: 0.75rem;
}

.section-heading {
  max-width: 48rem;
  margin-bottom: 2rem;
}

.section-heading span,
.flow-copy span {
  color: #0f766e;
  font-size: 0.78rem;
  font-weight: 850;
  text-transform: uppercase;
}

.section-heading h2,
.flow-copy h2 {
  margin: 0.55rem 0 0;
  color: #0f172a;
  font-size: 2rem;
  font-weight: 850;
}

.capability-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 1rem;
}

.capability-card {
  min-height: 13rem;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  background: #ffffff;
  padding: 1.35rem;
  box-shadow: 0 14px 30px rgba(15, 23, 42, 0.05);
  transition:
    transform 0.2s ease,
    box-shadow 0.2s ease;
}

.capability-card:hover {
  transform: translateY(-2px);
  box-shadow: 0 18px 38px rgba(15, 23, 42, 0.08);
}

.capability-card .el-icon {
  width: 2.3rem;
  height: 2.3rem;
  color: #0f766e;
}

.capability-card:nth-child(2) .el-icon,
.capability-card:nth-child(5) .el-icon {
  color: #2563eb;
}

.capability-card:nth-child(3) .el-icon,
.capability-card:nth-child(6) .el-icon {
  color: #e11d48;
}

.capability-card h3 {
  margin: 0.85rem 0 0.55rem;
  color: #0f172a;
  font-size: 1.05rem;
  font-weight: 850;
}

.capability-card p,
.flow-copy p {
  margin: 0;
  color: #475569;
  font-size: 0.95rem;
  line-height: 1.75;
}

.flow-panel {
  display: grid;
  grid-template-columns: minmax(0, 0.95fr) minmax(320px, 1.05fr);
  gap: 2rem;
  align-items: center;
  border: 1px solid #dbe3ee;
  border-radius: 8px;
  background: #f8fafc;
  padding: 2rem;
}

.flow-steps {
  display: grid;
  gap: 0.8rem;
}

.flow-steps div {
  display: grid;
  grid-template-columns: 3.5rem minmax(0, 1fr);
  gap: 1rem;
  align-items: center;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  background: #ffffff;
  padding: 1rem;
}

.flow-steps strong {
  color: #0f766e;
  font-size: 1rem;
  font-weight: 900;
}

.flow-steps span {
  color: #1e293b;
  font-weight: 750;
}

.landing-footer {
  border-top: 1px solid #e2e8f0;
  background: #ffffff;
  color: #64748b;
  font-size: 0.9rem;
}

.landing-footer span {
  color: #0f172a;
  font-weight: 850;
}

.landing-footer p {
  margin: 0;
}

.landing-primary-button {
  --el-button-bg-color: #0f172a;
  --el-button-border-color: #0f172a;
  --el-button-text-color: #ffffff;
  --el-button-hover-bg-color: #1e293b;
  --el-button-hover-border-color: #1e293b;
  --el-button-active-bg-color: #020617;
  --el-button-active-border-color: #020617;
  min-width: 7rem;
  height: 2.5rem;
  border-radius: 8px;
  font-weight: 750;
  box-shadow: 0 12px 26px rgba(15, 23, 42, 0.16);
}

.landing-primary-button--large,
.landing-secondary-button--large {
  min-width: 9.5rem;
  height: 3rem;
}

.landing-secondary-button {
  --el-button-bg-color: rgba(255, 255, 255, 0.94);
  --el-button-border-color: #cbd5e1;
  --el-button-text-color: #0f172a;
  --el-button-hover-bg-color: #f8fafc;
  --el-button-hover-border-color: #94a3b8;
  --el-button-active-bg-color: #f1f5f9;
  --el-button-active-border-color: #94a3b8;
  border-radius: 8px;
  font-weight: 700;
}

@media (max-width: 1024px) {
  .hero-grid {
    grid-template-columns: 1fr;
  }

  .hero-copy h1 {
    max-width: 14ch;
    font-size: 3.25rem;
  }

  .capability-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 720px) {
  .hero-section {
    padding: 3.5rem 0 3rem;
  }

  .hero-copy h1 {
    font-size: 2.55rem;
  }

  .hero-lead {
    font-size: 1rem;
  }

  .console-body {
    grid-template-columns: 1fr;
    min-height: auto;
  }

  .console-rail {
    display: none;
  }

  .insight-panel,
  .insight-panel--input,
  .insight-panel--metric {
    grid-column: auto;
  }

  .capability-grid,
  .flow-panel {
    grid-template-columns: 1fr;
  }

  .flow-panel {
    padding: 1.25rem;
  }
}
</style>
