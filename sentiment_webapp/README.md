# SentimentPlatform Web

`sentiment_webapp` 是 SentimentPlatform 的 Vue 3 前端应用，提供普通用户分析界面、分析师工作台、报告中心和管理员后台。前端采用三角色路由与独立布局，让论文中“表现层设计、交互流程设计、可视化设计”有清晰落点。

## 技术栈

- Vue `3.5` + Composition API
- Vite `8`
- Pinia `3`
- Vue Router `5`
- Element Plus `2.13`
- Tailwind CSS `4`
- ECharts `6`
- Axios `1.15`
- DOMPurify、VueUse、unplugin-vue-components

## 目录结构

```text
src/
├── api/           # API 请求封装：auth、analysis、admin、report、request
├── components/    # 共享 UI 组件：图表、统计卡片、布局面板、错误提示
├── composables/   # 可复用业务逻辑：分页、报告中心、训练中心、会话恢复
├── layouts/       # 三角色布局：UserLayout、AnalystLayout、AdminLayout
├── pages/         # 页面入口：auth、user、analyst、admin
├── router/        # 路由表、RBAC、登录重定向
├── stores/        # Pinia 状态：auth
├── styles/        # 全局样式、组件样式、侧边栏样式
└── utils/         # 纯工具函数：token、下载、时间、过滤、草稿、关键词高亮
```

## 页面与路由

公共页面：

| 路由 | 页面 |
| --- | --- |
| `/` | 产品入口页 |
| `/login` | 登录 |
| `/register` | 注册 |
| `/reset-password` | 重置密码 |

普通用户：

| 路由 | 功能 |
| --- | --- |
| `/user/dashboard` | 个人仪表盘 |
| `/user/analysis` | 单条评论分析 |
| `/user/analysis/batch` | 批量评论分析 |
| `/user/history` | 分析历史 |
| `/user/history/:id` | 分析详情 |
| `/user/reports` | 报告中心 |
| `/user/profile` | 个人资料 |

分析师：

| 路由 | 功能 |
| --- | --- |
| `/analyst/overview` | 分析师工作台 |
| `/analyst/comments` | 评论审核与备注 |
| `/analyst/reports` | 分析师报表 |
| `/analyst/profile` | 个人资料 |

管理员：

| 路由 | 功能 |
| --- | --- |
| `/admin/dashboard` | 控制台总览 |
| `/admin/users` | 用户管理 |
| `/admin/datasets` | 数据集管理 |
| `/admin/models` | 模型管理 |
| `/admin/training` | 训练中心，BERT 配置与训练记录管理 |
| `/admin/logs` | 操作日志 |
| `/admin/api-docs` | API 文档入口 |
| `/admin/backup` | 数据库备份 |
| `/admin/profile` | 个人资料 |

登录后会根据用户角色跳转默认首页：普通用户到仪表盘，分析师到工作台，管理员到控制台。

## 核心交互流程

| 流程 | 前端页面 | 后端接口 |
| --- | --- | --- |
| 注册登录 | `auth/*` | `/api/auth/*` |
| 单条分析 | `user/SingleAnalysis.vue` | `POST /api/analyze/single/` |
| 批量分析 | `user/BatchAnalysis.vue` | `POST /api/analyze/batch/` |
| 历史与详情 | `user/History.vue`、`ResultDetail.vue` | `/api/analyze/history/`、`/api/analyze/result/<id>/` |
| 报告中心 | `user/ReportCenter.vue` | `/api/report/generate/`、`/api/report/list/`、`/api/report/download/<id>/` |
| 评论审核 | `analyst/CommentsList.vue` | `/api/analyze/analyst/comments/` |
| 数据集管理 | `admin/DatasetManage.vue` | `/api/admin/datasets/`、`import`、`export` |
| 模型与训练 | `admin/ModelManage.vue`、`TrainingCenter.vue` | `/api/admin/models/`、`/api/admin/training/*` |

训练中心页面以管理员视角展示 BERT 训练参数、本地数据集 `chinese-news-sentiment-c3-ds`、训练终端命令要点和训练记录管理入口，支持查看详情、重试、激活和删除失败/演示命名记录。

## 请求层设计

请求层集中在 `src/api/request.js`：

- `baseURL` 为 `/api`，由 Vite 代理到 `http://127.0.0.1:8000`。
- access token 自动写入 `Authorization: Bearer <token>`。
- refresh token 由后端写入 HttpOnly cookie，前端不读取。
- 遇到 401 时自动请求 `/auth/refresh/`，刷新成功后重放原请求。
- 刷新失败时清理本地会话并跳转登录页。
- 统一提取后端错误消息，网络异常时提示服务未启动。
- 批量分析请求单独设置 `120s` 超时。

认证状态由 `src/stores/auth.js` 维护，包含登录、退出、资料拉取、静默刷新定时器和会话清理。

## 路由权限

`src/router/index.js` 定义路由层级，父路由通过 `meta.roles` 限定角色。`src/router/access.js` 根据登录状态、目标路由和用户角色返回跳转结果。

前端权限控制用于减少误操作和提升体验；所有高权限数据仍由后端接口进行最终鉴权。

## 共享组件

| 组件 | 用途 |
| --- | --- |
| `AppLayoutShell` | 三角色布局骨架 |
| `AppPanel` | 页面区块/图表面板 |
| `PageHeader` | 页面标题区 |
| `StatCard` | 指标统计卡片 |
| `SentimentChart` | 情感分布图 |
| `TrendChart` | 趋势折线图，支持训练 loss/metric 双 Y 轴 |
| `WordCloudChart` | 高频关键词词云 |
| `HeatmapMatrix` | 混淆矩阵热力图 |
| `MetricBarChart` | 模型指标柱状图 |
| `KeywordStatList` | 关键词频次列表 |
| `ErrorRetryAlert` | 加载失败与重试提示 |
| `SafeHtml` | 安全 HTML 渲染 |

## 可视化设计

项目使用 ECharts 展示：

- 情感分布：积极/中性/消极占比。
- 趋势图：分析数量、情感变化、训练指标变化。
- 词云：高频关键词。
- 混淆矩阵：模型评估结果。
- 指标柱状图：模型准确率、宏 F1、召回率等指标对比。

情感语义色在 `DESIGN_SPEC.md` 中统一定义：积极为绿色，消极为红色，中性为黄色，保证图表、标签和结果展示一致。

## 本地开发

```powershell
npm install
npm run check
npm run build
npm run dev
```

开发服务默认访问：

```text
http://127.0.0.1:5173/
```

Vite 代理配置：

| 前缀 | 目标 |
| --- | --- |
| `/api` | `http://127.0.0.1:8000` |
| `/media` | `http://127.0.0.1:8000` |
| `/swagger` | `http://127.0.0.1:8000` |
| `/redoc` | `http://127.0.0.1:8000` |
| `/static` | `http://127.0.0.1:8000` |

本地运行前需确保后端、MySQL、Redis、Celery worker 和 Celery beat 已启动。

## 环境变量

本地开发不要求额外前端环境变量。`.env.example` 仅保留说明，API 通过 Vite 代理访问 `/api`。

## 质量检查

```powershell
npm run lint
npm run format:check
npm run typecheck
npm run check
npm run build
```

脚本说明：

| 命令 | 说明 |
| --- | --- |
| `npm run dev` | 启动 Vite 开发服务 |
| `npm run build` | 构建生产包到 `dist/` |
| `npm run preview` | 预览构建结果 |
| `npm run lint` | ESLint 检查 |
| `npm run format:check` | Prettier 格式检查 |
| `npm run typecheck` | vue-tsc 类型检查 |
| `npm run check` | 顺序执行 lint、format、typecheck |

## 架构约定

- `src/pages/` 只放页面入口和页面级编排。
- `src/components/` 放展示组件，不直接调用 API。
- `src/composables/` 放跨页面可复用业务逻辑。
- `src/api/` 只封装 HTTP 请求，不依赖 UI。
- `src/stores/` 管理跨页面状态，不直接操作 DOM。
- `src/utils/` 放无状态纯函数。

## 设计规范

前端 UI 规范见 `DESIGN_SPEC.md`。当前定位为现代企业级 SaaS，主要特征：

- 深色侧边栏 + 浅灰内容区。
- 数据卡片、图表和表格保持高信息密度。
- 普通用户强调流程简短和结果直达。
- 分析师强调筛选、审核和统计图表。
- 管理员强调状态可见、风险操作确认和训练/模型控制。

## 论文撰写提示

前端部分可在论文中对应：

- **用户界面设计**：三角色布局、路由结构、页面功能划分。
- **交互流程设计**：登录注册、单条分析、批量上传、历史详情、报告下载。
- **权限控制设计**：路由守卫、角色首页、无权限自动跳转。
- **数据可视化设计**：情感分布、趋势、词云、模型指标和混淆矩阵。
- **前后端通信设计**：Axios 封装、JWT 注入、HttpOnly refresh cookie、自动刷新与错误提示。
