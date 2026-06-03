# SentimentPlatform

SentimentPlatform（云析智研）是一个面向中文评论数据的智能情感分析与洞察平台。项目覆盖用户注册登录、单条/批量评论分析、分析历史、分析师审核、报告生成、管理员数据集与模型管理、训练任务编排、操作审计等完整流程。

这是独立的公开源码版本，只发布系统源码、测试、文档和开发脚本；不发布模型权重、训练数据集、本地数据库、演示账号、日志、上传文件、报告导出或训练产物。运行分析功能前，请按 `docs/model-and-data-assets.md` 在本地准备模型和数据。

## 项目定位

- **业务目标**：对中文评论文本进行积极、中性、消极三分类，沉淀历史结果，并以图表、报告和管理后台支撑数据分析工作。
- **用户角色**：普通用户、分析师、管理员三类角色分权访问。
- **系统形态**：Vue 3 单页应用 + Django REST API + MySQL + Redis/Celery + 本地机器学习模型工作区。
- **开源价值点**：包含数据预处理、模型训练与对比、模型部署推理、前后端分离、RBAC 权限、异步任务、可视化报表、审计日志、自动化测试和 CI。
- **教学/论文价值点**：可作为“基于机器学习的中文情感分析平台”类课程设计、毕业设计或实验项目参考。

## 技术栈

| 层 | 技术 |
| --- | --- |
| 后端 | Python 3.12+、Django 6、Django REST Framework、Simple JWT、drf-spectacular |
| 前端 | Vue 3.5、Vite 8、Pinia、Vue Router 5、Element Plus、Tailwind CSS 4、ECharts |
| 数据库与缓存 | MySQL 8+、Redis |
| 异步任务 | Celery 5.6、Celery Beat |
| 机器学习 | PyTorch、Transformers、scikit-learn、jieba、datasets、safetensors |
| 报告与文件 | ReportLab、openpyxl、CSV/TXT/XLSX 文件处理 |
| 本地开发 | PowerShell 启停脚本、前后端质量检查与构建脚本 |

## 项目结构

```text
SentimentPlatform/
├── sentiment_server/                 # Django REST API、Celery、模型推理与训练工作区
├── sentiment_webapp/                 # Vue 3 + Vite 前端单页应用
├── docs/                             # 公开发布、模型与数据资产说明
├── .github/                          # CI、issue 模板和 PR 模板
├── start-dev.ps1                     # 一键启动后端、Celery、前端
├── stop-dev.ps1                      # 一键停止本地服务
├── dev-services.ps1                  # 本地服务定义与复用函数
├── LICENSE                           # MIT License
├── CONTRIBUTING.md                   # 贡献指南
├── SECURITY.md                       # 安全策略
└── README.md                         # 项目总览、启动与验证说明
```

公开版采用 monorepo 组织，后端和前端位于同一个 Git 仓库中，便于 issue、CI 和版本管理统一协作。

运行时输出与本地资产主要位于 `sentiment_server/`：`ml_assets/` 保存模型、数据集和训练工作区，`generated_reports/` 保存报告输出，`exports/` 保存导出文件，`uploads/` 与 `media/` 保存上传和媒体文件，`logs/` 保存服务日志，`backups/` 保存数据库备份。

## 公开资产策略

| 类别 | 公开仓库策略 |
| --- | --- |
| 源码、测试、文档、开发脚本 | 发布 |
| 前端品牌资源、小型停用词表 | 发布 |
| `.env`、真实密钥、本地账号 | 不发布 |
| 训练数据集、Arrow 文件、数据切分 | 不发布 |
| 模型权重、`.joblib`、`.pt`、`.safetensors` | 不发布 |
| 日志、上传、报告、导出、备份 | 不发布 |

## 核心业务模块

| 模块 | 主要能力 |
| --- | --- |
| 认证与账号 | 图形验证码、邮箱验证码、注册、登录、HttpOnly refresh cookie、无感刷新、个人资料、修改/重置密码 |
| 情感分析 | 单条文本分析、TXT/XLSX 批量分析、批量模板下载、运行时模型能力检测、历史查询和详情查看 |
| 分析师工作台 | 全局分析概览、评论筛选、重点标记、分析备注、统计报表 |
| 报告中心 | PDF/Excel/CSV 报告生成、异步入队、状态流转、下载与文件路径校验 |
| 管理后台 | 用户管理、数据集导入导出、模型注册与激活、训练中心、数据库备份、操作日志 |
| 模型训练 | Transformer 微调、Transformer 超参搜索、传统模型对比、TextCNN/BiLSTM 神经网络基线训练 |
| 运维与审计 | Celery 定时清理、自动重训检查、训练日志下载、数据库备份、操作日志保留 |

## 三角色访问设计

| 角色 | 前端路径 | 后端权限重点 | 典型操作 |
| --- | --- | --- | --- |
| 普通用户 | `/user/*` | 只能访问自己的分析历史和报告 | 单条/批量分析、查看历史、生成报告、维护资料 |
| 分析师 | `/analyst/*` | 可查看全局分析结果和报表 | 评论审核、重点标注、趋势与分布分析 |
| 管理员 | `/admin/*` | 管理系统级资源 | 用户、数据集、模型、训练、日志、备份、API 文档 |

登录成功后前端根据 `user.role` 自动跳转到对应首页；路由守卫与后端权限共同限制越权访问。

## 数据库设计

项目当前围绕 8 张业务表组织数据：

| 表名 | Django 模型 | 说明 |
| --- | --- | --- |
| `users` | `users.User` | 自定义用户表，邮箱登录，含 user/analyst/admin 三角色 |
| `email_verification_codes` | `users.EmailVerificationCode` | 邮箱验证码、用途、失败次数和过期控制 |
| `comments` | `analysis.Comment` | 评论正文、项目名、评分、类别、来源、评论时间 |
| `analysis_results` | `analysis.AnalysisResult` | 情感类别、置信度、关键词、分析师备注、重点标记 |
| `models` | `analysis.Model` | 模型注册、版本、指标、路径、激活状态、运行时兼容性 |
| `training_runs` | `admin_panel.TrainingRun` | 训练任务、数据集引用、配置快照、指标、产物、日志路径 |
| `reports` | `reports.Report` | 报告类型、格式、状态、文件路径、摘要和入队信息 |
| `operation_logs` | `admin_panel.OperationLog` | 登录、分析、导入导出、训练、模型切换等审计日志 |

## 机器学习与推理流程

当前运行时模型由后端 `MODEL_PATH` 或已激活的 `models` 记录解析。推理加载器支持三类产物：

- **Transformer**：目录中包含 `config.json`、`model.safetensors`、`tokenizer_config.json` 等文件，默认路径为 `ml_assets/models/bert`。
- **传统模型**：`.joblib` 产物，适配 Logistic Regression、Linear SVM、Random Forest 等训练结果。
- **神经网络模型**：`.pt` 产物，配套 `vocab.json` 与 `config_snapshot.json`，支持 TextCNN、BiLSTM。

单条分析流程为“文本校验 -> 模型推理 -> 关键词归一化 -> 写入评论和分析结果 -> 写操作日志”。批量分析支持 TXT 与 XLSX，按配置限制单次最大条数，优先使用批量推理接口，失败时不保存半成品结果。

训练中心可使用本地准备的数据集，围绕 BERT 训练与记录管理展开：

- `auto_split`：对原始数据集执行自动 7:1:2 分层划分。
- 管理员可在训练记录详情中删除失败、已取消或演示命名的训练记录。

## API 概览

| 前缀 | 说明 |
| --- | --- |
| `/api/healthz/` | 健康检查 |
| `/api/auth/` | 验证码、注册、登录、刷新、退出、资料、密码 |
| `/api/analyze/` | 单条/批量分析、模板、历史、详情、分析师视图 |
| `/api/report/` | 报告生成、列表、下载 |
| `/api/admin/` | 用户、日志、仪表盘、备份、数据集、模型、训练中心 |
| `/swagger/`、`/redoc/` | OpenAPI 文档，需设置 `SWAGGER_ENABLED=True`，且管理员访问 |

## 本地环境要求

- Python `3.12+`
- Node.js `22.18+` 或 `24.11+`
- MySQL `8+`，默认 `127.0.0.1:3306`
- Redis，默认 `127.0.0.1:6379/0`
- PowerShell `7.0+`，用于一键脚本

## 快速开始

### 后端

```powershell
cd sentiment_server
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -e ".[training,testing]"
Copy-Item .env.example .env
```

编辑 `.env`，至少填写 `SECRET_KEY`、`JWT_SIGNING_KEY` 和数据库连接信息。随后执行：

```powershell
$env:DJANGO_SETTINGS_MODULE = "sentiment_server.settings.local"
python manage.py migrate
python manage.py check
python -m pytest -q
python manage.py runserver 127.0.0.1:8000
```

### 前端

```powershell
cd sentiment_webapp
npm install
npm run check
npm run build
npm run dev
```

Vite 开发服务默认访问 `http://127.0.0.1:5173/`，通过代理访问后端 `/api`。

### 一键启动

```powershell
.\start-dev.ps1
.\stop-dev.ps1
```

一键启动会先检查后端 `.env` 必填密钥、MySQL 连接和 Redis 连接，再拉起 Django、Celery default worker、Celery training worker、Celery beat 和 Vite 开发服务。健康检查地址为 `http://127.0.0.1:8000/api/healthz/`。

也可以只启动部分服务，例如只启动后端和前端：

```powershell
.\start-dev.ps1 -Services backend,frontend
```

## Celery 异步任务

| 队列/任务 | 用途 |
| --- | --- |
| `celery` 默认队列 | 报告生成、验证码清理、日志清理等通用任务 |
| `training` 队列 | 模型训练、训练后处理、训练产物登记 |
| Beat 每 5 分钟 | 清理异常停留的训练任务 |
| Beat 每小时 | 自动重训阈值检查 |
| Beat 每 6 小时 | 操作日志清理 |
| Beat 每天 03:30 | 过期验证码清理 |

## 本地验证资料

- `sentiment_server/tests/fixtures/manual_usage/` 提供可复用的单条/批量手工验证素材。
- 管理员数据集导入、批量分析和报告生成也可以通过后端测试用例验证。
- 公开仓库不包含本地演示账号或真实样本数据。

## 当前验证状态

最近一次在本地工作区完成的检查：

```powershell
cd sentiment_server
$env:DJANGO_SETTINGS_MODULE = "sentiment_server.settings.local"
.\.venv\Scripts\python.exe manage.py check
.\.venv\Scripts\python.exe -m pytest -q

cd ..\sentiment_webapp
npm run check
npm run build
```

验证结果：后端系统检查通过，后端测试通过，前端 lint、Prettier、vue-tsc 和生产构建均通过。

## 论文撰写信息速览

可直接用于论文的系统信息如下：

- **需求分析**：普通用户需要评论情感识别和报告导出；分析师需要全局审核和统计洞察；管理员需要维护用户、数据、模型和训练任务。
- **总体架构**：前后端分离 + REST API + RBAC + MySQL 持久化 + Redis/Celery 异步任务 + 模型工作区。
- **数据流程**：数据导入/用户提交 -> 文本解析与校验 -> 模型推理 -> 情感结果与关键词入库 -> 图表分析/报告导出/审计记录。
- **模型路线**：传统机器学习、神经网络基线、Transformer 微调与搜索并存，训练产物可登记为运行时模型并激活切换。
- **安全设计**：JWT access token、HttpOnly refresh cookie、账号状态检查、管理员接口权限、文件类型与路径校验、操作日志审计。
- **测试与验证**：后端 pytest 覆盖认证、权限、分析、报告、训练、备份、日志等；前端通过 ESLint、Prettier、vue-tsc 与构建验证。

## 详细文档

- 公开发布说明：[`docs/open-source-release.md`](docs/open-source-release.md)
- 模型与数据资产说明：[`docs/model-and-data-assets.md`](docs/model-and-data-assets.md)
- 后端说明：[`sentiment_server/README.md`](sentiment_server/README.md)
- 前端说明：[`sentiment_webapp/README.md`](sentiment_webapp/README.md)
- 前端设计规范：[`sentiment_webapp/DESIGN_SPEC.md`](sentiment_webapp/DESIGN_SPEC.md)
- 手工测试素材：[`sentiment_server/tests/fixtures/manual_usage/README.md`](sentiment_server/tests/fixtures/manual_usage/README.md)
