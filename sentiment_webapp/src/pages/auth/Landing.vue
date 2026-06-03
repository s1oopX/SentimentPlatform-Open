<script setup>
import { computed } from 'vue'
import { useRouter } from 'vue-router'
import AuthBrandBadge from '@/components/AuthBrandBadge.vue'
import { useAuthStore } from '@/stores/auth'
import { getDefaultHomeRoute } from '@/router/access'
import { isResolvedAuthenticated } from '@/router/guardState'
import {
  MagicStick,
  TrendCharts,
  UserFilled,
  Lock,
  Lightning,
  DataLine,
  SwitchButton,
  Odometer,
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
  <div class="min-h-screen bg-gradient-to-b from-slate-50 to-white">
    <!-- Header -->
    <header class="sticky top-0 z-50 border-b border-slate-200/80 bg-white/80 backdrop-blur-xl">
      <div class="mx-auto flex max-w-7xl items-center justify-between px-6 py-4">
        <div class="flex items-center gap-2">
          <AuthBrandBadge size="compact" />
          <h1 class="m-0 text-xl font-bold text-slate-900">云析智研</h1>
        </div>
        <div class="flex items-center gap-3">
          <template v-if="isAuthenticated">
            <div class="flex items-center gap-2 rounded-lg bg-slate-100 px-3 py-1.5">
              <div
                class="flex h-6 w-6 items-center justify-center rounded-full bg-slate-900 text-xs font-medium text-white"
              >
                {{
                  (user?.display_name || user?.nickname || user?.email || 'U')
                    .charAt(0)
                    .toUpperCase()
                }}
              </div>
              <span class="text-sm text-slate-700">{{
                user?.display_name || user?.nickname || user?.email
              }}</span>
            </div>
            <el-button @click="router.push(getDefaultHomeRoute(user))">
              <el-icon class="mr-2"><Odometer /></el-icon>
              {{ authenticatedCtaLabel }}
            </el-button>
            <el-button @click="handleLogout">
              <el-icon class="mr-2"><SwitchButton /></el-icon>
              退出
            </el-button>
          </template>
          <template v-else>
            <el-button class="landing-secondary-button" @click="router.push('/login')">
              登录
            </el-button>
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

    <!-- Hero -->
    <section class="relative overflow-hidden">
      <!-- Decorative orbs -->
      <div class="hero-orb hero-orb--blue"></div>
      <div class="hero-orb hero-orb--purple"></div>
      <div class="hero-orb hero-orb--cyan"></div>

      <div class="relative mx-auto max-w-7xl px-6 pb-10 pt-20 text-center">
        <div
          class="mb-6 inline-flex items-center rounded-full bg-slate-100/80 px-3.5 py-1.5 text-sm font-medium text-slate-600 backdrop-blur-sm"
        >
          <el-icon class="mr-2"><MagicStick /></el-icon>
          <span>AI 驱动的智能分析平台</span>
        </div>

        <h2 class="mb-6 text-4xl font-bold text-slate-900 md:text-5xl lg:text-6xl">
          精准洞察用户情感<br />
          <span class="bg-gradient-to-r from-blue-600 to-purple-600 bg-clip-text text-transparent">
            助力数据决策
          </span>
        </h2>

        <p class="mx-auto mb-10 max-w-2xl text-base leading-relaxed text-slate-600">
          云析智研是一套基于深度学习的智能情感分析与洞察平台，帮助您快速理解用户反馈，
          识别产品优化方向，提升用户体验
        </p>

        <div class="mb-14 flex flex-col items-center justify-center gap-4 sm:flex-row">
          <el-button
            type="primary"
            size="large"
            class="hero-btn shadow-lg"
            @click="router.push('/register')"
          >
            <el-icon class="mr-2"><MagicStick /></el-icon> 免费开始
          </el-button>
          <el-button size="large" class="hero-btn" @click="scrollToFeatures"> 了解更多 </el-button>
        </div>

        <!-- Product Preview Card -->
        <div class="mx-auto max-w-3xl">
          <div
            class="hero-preview-card rounded-2xl border border-slate-200/60 bg-white/70 p-6 shadow-2xl backdrop-blur-md"
          >
            <div class="mb-4 flex items-center justify-between">
              <div class="flex items-center gap-2">
                <div class="h-3 w-3 rounded-full bg-red-400"></div>
                <div class="h-3 w-3 rounded-full bg-amber-400"></div>
                <div class="h-3 w-3 rounded-full bg-green-400"></div>
              </div>
              <span class="text-xs font-medium tracking-wider text-slate-400 uppercase"
                >情感分析引擎</span
              >
            </div>

            <div class="grid grid-cols-1 gap-4 md:grid-cols-3">
              <!-- Input -->
              <div class="rounded-xl bg-slate-50 p-4 text-left md:col-span-2">
                <p class="mb-2 text-xs font-semibold uppercase tracking-wider text-slate-400">
                  输入文本
                </p>
                <p class="text-sm leading-relaxed text-slate-700">
                  “这款产品的体验非常棒，界面简洁直观，响应速度很快，客服也很耐心解答问题。”
                </p>
              </div>
              <!-- Result -->
              <div class="space-y-3 text-left">
                <div class="rounded-xl bg-emerald-50 p-3">
                  <p class="text-xs font-semibold text-emerald-600 mb-1">情感结果</p>
                  <p class="text-lg font-bold text-emerald-700">积极 ↑</p>
                </div>
                <div class="rounded-xl bg-blue-50 p-3">
                  <p class="text-xs font-semibold text-blue-600 mb-1">置信度</p>
                  <div class="flex items-center gap-2">
                    <div class="h-2 flex-1 rounded-full bg-blue-100">
                      <div class="h-2 w-[94%] rounded-full bg-blue-500"></div>
                    </div>
                    <span class="text-sm font-bold text-blue-700">94%</span>
                  </div>
                </div>
                <div class="flex flex-wrap gap-1.5">
                  <span
                    class="inline-block rounded-md bg-slate-100 px-2 py-0.5 text-xs font-medium text-slate-600"
                    >体验好</span
                  >
                  <span
                    class="inline-block rounded-md bg-slate-100 px-2 py-0.5 text-xs font-medium text-slate-600"
                    >响应快</span
                  >
                  <span
                    class="inline-block rounded-md bg-slate-100 px-2 py-0.5 text-xs font-medium text-slate-600"
                    >客服耐心</span
                  >
                </div>
              </div>
            </div>
          </div>
        </div>

        <!-- Stats -->
        <div class="mt-16 grid grid-cols-1 gap-8 md:grid-cols-3 md:gap-12">
          <div class="text-center">
            <p
              class="mb-3 text-3xl font-bold bg-gradient-to-r from-blue-600 to-purple-600 bg-clip-text text-transparent"
            >
              99.2%
            </p>
            <p class="text-base font-medium text-slate-600">分析准确率</p>
          </div>
          <div class="text-center">
            <p
              class="mb-3 text-3xl font-bold bg-gradient-to-r from-blue-600 to-purple-600 bg-clip-text text-transparent"
            >
              10M+
            </p>
            <p class="text-base font-medium text-slate-600">已处理评论</p>
          </div>
          <div class="text-center">
            <p
              class="mb-3 text-3xl font-bold bg-gradient-to-r from-blue-600 to-purple-600 bg-clip-text text-transparent"
            >
              1000+
            </p>
            <p class="text-base font-medium text-slate-600">企业用户</p>
          </div>
        </div>
      </div>
    </section>

    <!-- Features -->
    <section id="features" class="bg-slate-50 py-24">
      <div class="mx-auto max-w-7xl px-6">
        <div class="mb-16 text-center">
          <h3 class="mb-4 text-2xl font-bold text-slate-900">强大的功能特性</h3>
          <p class="text-lg text-slate-600">一站式情感分析解决方案，满足您的所有需求</p>
        </div>

        <div class="grid grid-cols-1 gap-6 md:grid-cols-2 lg:grid-cols-3">
          <el-card shadow="hover" class="feature-card">
            <div
              class="feature-icon-wrapper mb-5 flex h-12 w-12 items-center justify-center rounded-xl bg-blue-100 text-2xl text-blue-600 transition-transform"
            >
              <el-icon><MagicStick /></el-icon>
            </div>
            <h4 class="mb-3 text-lg font-semibold text-slate-900">智能分析</h4>
            <p class="leading-relaxed text-slate-600">
              基于 BERT 深度学习模型，精准识别文本中的情感倾向，支持积极、中性、消极三类情感分类
            </p>
          </el-card>

          <el-card shadow="hover" class="feature-card">
            <div
              class="feature-icon-wrapper mb-5 flex h-12 w-12 items-center justify-center rounded-xl bg-purple-100 text-2xl text-purple-600 transition-transform"
            >
              <el-icon><Lightning /></el-icon>
            </div>
            <h4 class="mb-3 text-lg font-semibold text-slate-900">批量处理</h4>
            <p class="leading-relaxed text-slate-600">
              支持 Excel、TXT 文件批量上传，一次性分析数千条评论，大幅提升工作效率
            </p>
          </el-card>

          <el-card shadow="hover" class="feature-card">
            <div
              class="feature-icon-wrapper mb-5 flex h-12 w-12 items-center justify-center rounded-xl bg-green-100 text-2xl text-green-600 transition-transform"
            >
              <el-icon><TrendCharts /></el-icon>
            </div>
            <h4 class="mb-3 text-lg font-semibold text-slate-900">数据可视化</h4>
            <p class="leading-relaxed text-slate-600">
              直观的图表展示分析结果，情感趋势一目了然，帮助您快速把握用户情绪变化
            </p>
          </el-card>

          <el-card shadow="hover" class="feature-card">
            <div
              class="feature-icon-wrapper mb-5 flex h-12 w-12 items-center justify-center rounded-xl bg-orange-100 text-2xl text-orange-600 transition-transform"
            >
              <el-icon><DataLine /></el-icon>
            </div>
            <h4 class="mb-3 text-lg font-semibold text-slate-900">报表导出</h4>
            <p class="leading-relaxed text-slate-600">
              支持 PDF、Excel、CSV 多种格式报表导出，方便分享和存档分析结果
            </p>
          </el-card>

          <el-card shadow="hover" class="feature-card">
            <div
              class="feature-icon-wrapper mb-5 flex h-12 w-12 items-center justify-center rounded-xl bg-red-100 text-2xl text-red-600 transition-transform"
            >
              <el-icon><UserFilled /></el-icon>
            </div>
            <h4 class="mb-3 text-lg font-semibold text-slate-900">团队协作</h4>
            <p class="leading-relaxed text-slate-600">
              支持多角色权限管理，分析师可标注重点评论，团队协作更高效
            </p>
          </el-card>

          <el-card shadow="hover" class="feature-card">
            <div
              class="feature-icon-wrapper mb-5 flex h-12 w-12 items-center justify-center rounded-xl bg-slate-100 text-2xl text-slate-600 transition-transform"
            >
              <el-icon><Lock /></el-icon>
            </div>
            <h4 class="mb-3 text-lg font-semibold text-slate-900">数据安全</h4>
            <p class="leading-relaxed text-slate-600">
              企业级数据安全保障，支持数据备份恢复，确保您的数据万无一失
            </p>
          </el-card>
        </div>
      </div>
    </section>

    <!-- How it works -->
    <section class="bg-white py-20">
      <div class="mx-auto max-w-5xl px-6">
        <div class="mb-14 text-center">
          <h3 class="mb-4 text-2xl font-bold text-slate-900">三步开始</h3>
          <p class="text-lg text-slate-600">从数据到洞察，只需简单三步</p>
        </div>
        <div class="grid grid-cols-1 gap-8 md:grid-cols-3">
          <div class="step-card">
            <div
              class="mb-5 flex h-12 w-12 items-center justify-center rounded-xl bg-blue-600 text-lg font-bold text-white shadow-lg shadow-blue-200"
            >
              1
            </div>
            <h4 class="mb-2 text-lg font-semibold text-slate-900">上传数据</h4>
            <p class="text-sm leading-relaxed text-slate-600">
              粘贴单条评论或批量上传 Excel/TXT 文件，支持多种数据源接入
            </p>
          </div>
          <div class="step-card">
            <div
              class="mb-5 flex h-12 w-12 items-center justify-center rounded-xl bg-purple-600 text-lg font-bold text-white shadow-lg shadow-purple-200"
            >
              2
            </div>
            <h4 class="mb-2 text-lg font-semibold text-slate-900">AI 分析</h4>
            <p class="text-sm leading-relaxed text-slate-600">
              BERT 深度学习模型自动识别情感倾向，提取关键词与主题
            </p>
          </div>
          <div class="step-card">
            <div
              class="mb-5 flex h-12 w-12 items-center justify-center rounded-xl bg-emerald-600 text-lg font-bold text-white shadow-lg shadow-emerald-200"
            >
              3
            </div>
            <h4 class="mb-2 text-lg font-semibold text-slate-900">获取洞察</h4>
            <p class="text-sm leading-relaxed text-slate-600">
              可视化图表和报表帮助您快速理解数据，赋能业务决策
            </p>
          </div>
        </div>
      </div>
    </section>

    <!-- Use Cases -->
    <section class="bg-slate-50 py-24">
      <div class="mx-auto max-w-7xl px-6">
        <div class="mb-16 text-center">
          <h3 class="mb-4 text-2xl font-bold text-slate-900">适用场景</h3>
          <p class="text-lg text-slate-600">广泛应用于各个行业和场景</p>
        </div>

        <div class="grid grid-cols-1 gap-6 md:grid-cols-2">
          <div class="usecase-card from-blue-50 to-purple-50">
            <h4 class="mb-4 text-xl font-bold text-slate-900">电商平台</h4>
            <p class="mb-4 text-slate-700">
              分析商品评论，了解用户对产品的真实评价，快速发现产品问题和优化方向
            </p>
            <ul class="usecase-list" data-tone="blue">
              <li>识别差评重点问题</li>
              <li>追踪产品口碑变化</li>
              <li>优化产品描述和服务</li>
            </ul>
          </div>

          <div class="usecase-card from-green-50 to-blue-50">
            <h4 class="mb-4 text-xl font-bold text-slate-900">社交媒体</h4>
            <p class="mb-4 text-slate-700">监测品牌舆情，及时发现负面信息，维护品牌形象和声誉</p>
            <ul class="usecase-list" data-tone="green">
              <li>实时舆情监控</li>
              <li>品牌口碑分析</li>
              <li>竞品对比分析</li>
            </ul>
          </div>

          <div class="usecase-card from-purple-50 to-pink-50">
            <h4 class="mb-4 text-xl font-bold text-slate-900">客户服务</h4>
            <p class="mb-4 text-slate-700">分析客户反馈和投诉，提升服务质量，改善用户体验</p>
            <ul class="usecase-list" data-tone="purple">
              <li>客户满意度评估</li>
              <li>服务问题识别</li>
              <li>客服质量监控</li>
            </ul>
          </div>

          <div class="usecase-card from-orange-50 to-red-50">
            <h4 class="mb-4 text-xl font-bold text-slate-900">市场调研</h4>
            <p class="mb-4 text-slate-700">分析用户调研问卷和反馈，洞察市场需求和用户偏好</p>
            <ul class="usecase-list" data-tone="orange">
              <li>用户需求挖掘</li>
              <li>市场趋势分析</li>
              <li>竞争力评估</li>
            </ul>
          </div>
        </div>
      </div>
    </section>

    <!-- CTA -->
    <section class="bg-slate-900 py-20 text-center">
      <div class="mx-auto max-w-4xl px-6">
        <h3 class="mb-4 text-3xl font-bold text-white md:text-5xl">准备好开始了吗？</h3>
        <p class="mb-10 text-xl text-slate-300">立即注册，免费体验智能情感分析服务</p>
        <el-button
          type="primary"
          size="large"
          class="landing-cta-button"
          @click="router.push('/register')"
        >
          免费注册
        </el-button>
      </div>
    </section>

    <!-- Footer -->
    <footer class="border-t border-slate-200 bg-white py-12">
      <div class="mx-auto max-w-7xl px-6">
        <div class="grid grid-cols-1 gap-8 md:grid-cols-4">
          <div>
            <div class="mb-4 flex items-center gap-2">
              <AuthBrandBadge size="compact" />
              <h4 class="font-bold text-slate-900">云析智研</h4>
            </div>
            <p class="text-sm text-slate-600">智能情感分析与洞察平台，助力企业数据决策</p>
          </div>
          <div>
            <h5 class="mb-4 font-semibold text-slate-900">产品</h5>
            <ul class="flex list-none flex-col gap-2 p-0">
              <li>
                <a href="#features" class="text-sm text-slate-600 no-underline hover:text-slate-900"
                  >功能特性</a
                >
              </li>
              <li><span class="text-sm text-slate-400">价格方案</span></li>
              <li><span class="text-sm text-slate-400">使用文档</span></li>
            </ul>
          </div>
          <div>
            <h5 class="mb-4 font-semibold text-slate-900">公司</h5>
            <ul class="flex list-none flex-col gap-2 p-0">
              <li><span class="text-sm text-slate-400">关于我们</span></li>
              <li><span class="text-sm text-slate-400">联系我们</span></li>
              <li><span class="text-sm text-slate-400">隐私政策</span></li>
            </ul>
          </div>
          <div>
            <h5 class="mb-4 font-semibold text-slate-900">支持</h5>
            <ul class="flex list-none flex-col gap-2 p-0">
              <li><span class="text-sm text-slate-400">帮助中心</span></li>
              <li><span class="text-sm text-slate-400">API 文档</span></li>
              <li><span class="text-sm text-slate-400">社区论坛</span></li>
            </ul>
          </div>
        </div>
        <div class="mt-12 border-t border-slate-200 pt-8 text-center text-sm text-slate-600">
          <p>&copy; 2026 云析智研. All rights reserved.</p>
        </div>
      </div>
    </footer>
  </div>
</template>

<style scoped>
/* ── Hero decorative orbs ── */

.hero-orb {
  position: absolute;
  border-radius: 50%;
  filter: blur(80px);
  opacity: 0.35;
  pointer-events: none;
}
.hero-orb--blue {
  width: 500px;
  height: 500px;
  background: radial-gradient(circle, #3b82f6 0%, transparent 70%);
  top: -120px;
  left: -100px;
}
.hero-orb--purple {
  width: 400px;
  height: 400px;
  background: radial-gradient(circle, #8b5cf6 0%, transparent 70%);
  top: 60px;
  right: -80px;
}
.hero-orb--cyan {
  width: 350px;
  height: 350px;
  background: radial-gradient(circle, #06b6d4 0%, transparent 70%);
  bottom: -60px;
  left: 30%;
}

.hero-preview-card {
  transition: all 0.4s ease;
}
.hero-preview-card:hover {
  transform: translateY(-4px);
  box-shadow:
    0 25px 50px -12px rgba(0, 0, 0, 0.15),
    0 0 0 1px rgba(148, 163, 184, 0.1);
}

/* ── Step cards ── */

.step-card {
  padding: 2rem;
  border-radius: 1rem;
  border: 1px solid #e2e8f0;
  background: white;
  transition: all 0.3s ease;
}
.step-card:hover {
  transform: translateY(-4px);
  box-shadow:
    0 20px 25px -5px rgba(0, 0, 0, 0.08),
    0 8px 10px -6px rgba(0, 0, 0, 0.04);
}

/* ── Element Plus button overrides ── */

.landing-primary-button {
  --el-button-bg-color: #0f172a;
  --el-button-border-color: #0f172a;
  --el-button-text-color: #ffffff;
  --el-button-hover-bg-color: #1e293b;
  --el-button-hover-border-color: #1e293b;
  --el-button-active-bg-color: #020617;
  --el-button-active-border-color: #020617;
  min-width: 110px;
  height: 2.5rem;
  padding: 0 1rem;
  border-radius: 0.875rem;
  font-size: 0.95rem;
  font-weight: 600;
  box-shadow: 0 8px 18px rgba(15, 23, 42, 0.12);
}

.landing-primary-button:hover {
  transform: translateY(-1px);
  box-shadow: 0 12px 24px rgba(15, 23, 42, 0.16);
}

.landing-secondary-button {
  --el-button-bg-color: rgba(255, 255, 255, 0.92);
  --el-button-border-color: #cbd5e1;
  --el-button-text-color: #0f172a;
  --el-button-hover-bg-color: #f8fafc;
  --el-button-hover-border-color: #94a3b8;
  --el-button-active-bg-color: #f1f5f9;
  --el-button-active-border-color: #94a3b8;
  min-width: 74px;
  height: 2.5rem;
  padding: 0 1rem;
  border-radius: 0.875rem;
  font-size: 0.95rem;
  font-weight: 500;
  box-shadow: 0 8px 18px rgba(15, 23, 42, 0.08);
}

.landing-secondary-button:hover {
  transform: translateY(-1px);
  box-shadow: 0 10px 20px rgba(15, 23, 42, 0.1);
}

.landing-cta-button {
  --el-button-bg-color: #ffffff;
  --el-button-border-color: rgba(255, 255, 255, 0.24);
  --el-button-text-color: #0f172a;
  --el-button-hover-bg-color: #f8fafc;
  --el-button-hover-border-color: rgba(255, 255, 255, 0.32);
  --el-button-active-bg-color: #f1f5f9;
  --el-button-active-border-color: rgba(255, 255, 255, 0.36);
  min-width: 176px;
  height: 3.25rem;
  padding: 0 1.5rem;
  border-radius: 1rem;
  font-size: 1rem;
  font-weight: 700;
  box-shadow: 0 18px 40px rgba(0, 0, 0, 0.22);
}

.landing-cta-button:hover {
  transform: translateY(-1px);
  box-shadow: 0 22px 48px rgba(0, 0, 0, 0.24);
}

.hero-btn {
  min-width: 160px;
  height: 3rem;
  font-weight: 600;
}

.shadow-lg {
  box-shadow: 0 14px 30px rgba(15, 23, 42, 0.18);
}

/* ── Feature cards ── */

.feature-card {
  transition: all 0.3s ease;
}

.feature-card:hover {
  transform: translateY(-4px);
  box-shadow:
    0 20px 25px -5px rgba(0, 0, 0, 0.1),
    0 10px 10px -5px rgba(0, 0, 0, 0.04);
}

.feature-card:hover .feature-icon-wrapper {
  transform: scale(1.1);
}

/* ── Use case cards ── */

.usecase-card {
  padding: 1.75rem;
  border-radius: 1rem;
  background: linear-gradient(to bottom right, var(--tw-gradient-from), var(--tw-gradient-to));
  transition: all 0.3s ease;
  border: 1px solid transparent;
}

.usecase-card:hover {
  box-shadow:
    0 20px 25px -5px rgba(0, 0, 0, 0.1),
    0 10px 10px -5px rgba(0, 0, 0, 0.04);
}

.from-blue-50 {
  --tw-gradient-from: #eff6ff;
}
.to-purple-50 {
  --tw-gradient-to: #faf5ff;
}
.from-green-50 {
  --tw-gradient-from: #f0fdf4;
}
.to-blue-50 {
  --tw-gradient-to: #eff6ff;
}
.from-purple-50 {
  --tw-gradient-from: #faf5ff;
}
.to-pink-50 {
  --tw-gradient-to: #fdf2f8;
}
.from-orange-50 {
  --tw-gradient-from: #fff7ed;
}
.to-red-50 {
  --tw-gradient-to: #fef2f2;
}

.usecase-list {
  list-style: none;
  padding: 0;
  margin: 0;
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
  color: #475569;
}

.usecase-list li {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.usecase-list li::before {
  content: '';
  display: block;
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background-color: currentColor;
}

.usecase-list[data-tone='blue'] li {
  color: #2563eb;
}
.usecase-list[data-tone='green'] li {
  color: #16a34a;
}
.usecase-list[data-tone='purple'] li {
  color: #9333ea;
}
.usecase-list[data-tone='orange'] li {
  color: #ea580c;
}

/* ── Dark mode overrides ── */

html.dark .from-blue-50 {
  --tw-gradient-from: #0f172a;
}
html.dark .to-purple-50 {
  --tw-gradient-to: #1e1b4b;
}
html.dark .from-green-50 {
  --tw-gradient-from: #0f172a;
}
html.dark .to-blue-50 {
  --tw-gradient-to: #172554;
}
html.dark .from-purple-50 {
  --tw-gradient-from: #1e1b4b;
}
html.dark .to-pink-50 {
  --tw-gradient-to: #1f1235;
}
html.dark .from-orange-50 {
  --tw-gradient-from: #1c1917;
}
html.dark .to-red-50 {
  --tw-gradient-to: #1f1235;
}

html.dark .usecase-list {
  color: #94a3b8;
}
html.dark .landing-secondary-button {
  --el-button-bg-color: rgba(15, 23, 42, 0.92);
  --el-button-border-color: #475569;
  --el-button-text-color: #e2e8f0;
  --el-button-hover-bg-color: #1e293b;
  --el-button-hover-border-color: #64748b;
}
</style>
