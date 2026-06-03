# SentimentPlatform Server

`sentiment_server` 是 SentimentPlatform 的 Django REST API 后端，负责用户认证、情感分析、分析结果管理、报告生成、管理员控制台、模型注册与训练任务编排。后端同时承载机器学习运行时工作区，是论文中“系统服务层、数据层、模型服务层”的主要实现部分。

公开仓库不包含模型权重、训练数据集、训练输出、本地数据库、上传文件、报告导出、日志或备份。运行前请根据根目录 `docs/model-and-data-assets.md` 准备本地模型和数据资产。

## 技术栈

- Python `3.12+`
- Django `6`、Django REST Framework、Simple JWT、drf-spectacular
- MySQL `8+`
- Redis、Celery、Celery Beat
- PyTorch、Transformers、scikit-learn、jieba、datasets
- ReportLab、openpyxl、CSV/TXT/XLSX 文件处理

## 分层架构

业务 app 基本遵循 DDD 风格的分层组织：

```text
apps/<app_name>/
├── api/             # 接口层：APIView、serializer、HTTP response
├── application/     # 应用层：命令、查询、业务流程编排
├── domain/          # 领域层：规则、策略、错误定义
├── infra/           # 基础设施层：数据库查询、文件、任务、外部依赖
├── models.py        # Django ORM 模型
└── urls.py          # 路由
```

这种组织方式便于论文从“表现层、业务逻辑层、数据访问层、模型服务层”角度描述系统实现。

## 目录结构

```text
sentiment_server/
├── apps/
│   ├── users/               # 认证、注册、邮箱验证码、密码、个人资料
│   ├── analysis/            # 单条/批量分析、历史、分析师审核、模型推理入口
│   ├── reports/             # 报告生成、列表、下载、文件渲染
│   └── admin_panel/         # 管理后台、数据集、模型、训练、日志、备份
├── core/                    # 分页、路径、OpenAPI、邮件、脱敏等通用能力
├── ml_assets/               # 空模型/数据目录说明、训练脚本、训练/评估工作区
├── sentiment_server/        # Django settings、URL、ASGI/WSGI、Celery
├── tests/                   # 后端接口与业务测试
├── generated_reports/       # 运行时报告输出目录，不提交
├── exports/                 # 数据集导出目录，不提交
├── uploads/                 # 用户上传目录，不提交
└── scripts/ops/             # 数据库备份等运维脚本
```

## 应用模块

| App | 职责 |
| --- | --- |
| `users` | 邮箱登录用户体系、验证码、JWT、HttpOnly refresh cookie、资料维护 |
| `analysis` | 评论解析、模型推理、结果保存、历史查询、分析师工作台 |
| `reports` | 报告请求、异步生成、PDF/Excel/CSV 渲染、下载权限校验 |
| `admin_panel` | 用户管理、数据集导入导出、模型管理、训练中心、审计日志、备份 |

## 数据库表

| 表 | 模型 | 说明 |
| --- | --- | --- |
| `users` | `users.User` | 自定义用户表，邮箱唯一，三角色与启停状态 |
| `email_verification_codes` | `users.EmailVerificationCode` | 验证码哈希、用途、失败尝试、过期控制 |
| `comments` | `analysis.Comment` | 评论内容、项目、评分、类别、来源、评论时间 |
| `analysis_results` | `analysis.AnalysisResult` | 情感类别、置信度、关键词、备注、重点标记 |
| `models` | `analysis.Model` | 模型名称、版本、路径、指标、激活与兼容状态 |
| `training_runs` | `admin_panel.TrainingRun` | 训练任务、配置快照、指标快照、产物路径、日志 |
| `reports` | `reports.Report` | 报告类型、格式、状态、文件路径、摘要 |
| `operation_logs` | `admin_panel.OperationLog` | 登录、分析、导入导出、训练和模型切换等日志 |

## API 路由

| 前缀 | 关键接口 |
| --- | --- |
| `/api/healthz/` | 服务健康检查 |
| `/api/auth/` | `captcha`、`send-code`、`register`、`login`、`refresh`、`logout`、`profile`、`change-password`、`reset-password` |
| `/api/analyze/` | `single`、`batch`、`batch/template`、`batch/schema`、`history`、`result/<id>`、`runtime-capabilities` |
| `/api/analyze/analyst/` | `overview`、`comments`、`comments/<id>`、`report` |
| `/api/report/` | `generate`、`list`、`download/<id>` |
| `/api/admin/` | 用户、日志、仪表盘、备份、数据集、模型、训练记录与日志 |
| `/api/schema/`、`/swagger/`、`/redoc/` | OpenAPI 文档，需开启 `SWAGGER_ENABLED` |

## 认证与权限

- 使用 `rest_framework_simplejwt` 签发 access token。
- `JWT_SIGNING_KEY` 与 Django `SECRET_KEY` 分离，降低密钥泄漏影响面。
- Refresh token 通过 HttpOnly cookie 保存，前端不可直接读取。
- 自定义认证类会检查用户状态，禁用账号无法继续访问。
- 后端接口按角色控制访问，管理员接口继承 `AdminOnlyAPIView`。
- 前端路由守卫只是体验层约束，最终权限以后端判断为准。

## 情感分析流程

单条分析：

```text
用户提交文本
-> serializer 参数校验
-> SentimentModelLoader 加载/复用运行时模型
-> predict_sentiment 推理
-> 情感标签、置信度、关键词归一化
-> Comment 与 AnalysisResult 入库
-> OperationLog 写入审计
```

批量分析：

- 支持 `.txt` 与 `.xlsx`。
- TXT 要求 UTF-8 编码；XLSX 会校验 ZIP magic bytes，避免伪装文件。
- 默认上传大小上限为 `10MB`，单次最大条数由 `MAX_BATCH_RECORDS` 控制，默认 `1000`。
- 解析完成后优先调用批量推理；推理或保存失败时不写入部分结果。
- 返回总数、逐条结果、情感分布、平均置信度和高频关键词。

## 模型运行时

`apps.analysis.infra.model_runtime.SentimentModelLoader` 是统一推理入口，采用单例加载和路径变更检测。模型路径解析顺序为：

1. 数据库 `models` 表中当前激活模型。
2. settings 中的 `MODEL_PATH`，默认 `ml_assets/models/bert`。

支持的运行时产物：

| 类型 | 识别条件 | 说明 |
| --- | --- | --- |
| Transformer | 目录包含 `config.json`、`model.safetensors`、`tokenizer_config.json` | BERT/RoBERTa 等微调模型 |
| 传统模型 | `.joblib` 文件 | Logistic Regression、Linear SVM、Random Forest |
| 神经网络 | `.pt` 文件且同目录含 `vocab.json`、`config_snapshot.json` | TextCNN、BiLSTM |

模型路径会被限制在 `MODEL_WORKSPACE_DIR` 内，避免加载任意外部文件。

公开仓库中的 `ml_assets/models/` 只保留说明文件，默认 Transformer 权重和训练产物需要本地准备。缺少模型时，健康检查和大部分管理功能仍可启动，实际分析接口会返回模型不可用错误。

## 训练中心

训练任务类型：

| `task_type` | 说明 |
| --- | --- |
| `transformer_train` | Transformer 微调 |
| `transformer_search` | Transformer 超参数搜索 |
| `classical_compare` | 传统机器学习模型对比 |
| `neural_baseline_train` | TextCNN/BiLSTM 神经网络基线训练 |

候选模型：

- Transformer：`bert`、`roberta`
- 传统模型：`logistic_regression`、`linear_svm`、`random_forest`
- 神经网络：`textcnn`、`bilstm`

训练任务会保存请求配置、解析后的数据集路径、输出目录、日志路径、指标快照和产物路径。成功产物可登记到 `models` 表，并通过后台激活成为线上推理模型。公开仓库不内置训练数据集，请在本地准备数据后再使用训练中心；BERT 页面可使用 `auto_split` 生成训练/验证/测试切分。

训练记录管理支持：

- 删除失败、已取消或演示命名的训练记录。
- 仪表盘、最近记录和对比视图自动过滤失败记录与演示命名记录。
- 训练详情页可按权限展示删除、重试、后处理重试和激活入口。

## 数据集管理

管理员数据集导入支持：

- TXT：逐行读取评论，UTF-8 编码，自动跳过空行、重复行和长度异常数据。
- XLSX：从第二行开始读取，支持评论内容、评分、类别、来源等字段归一化。
- 文件大小受 `MAX_UPLOAD_SIZE` 控制。
- 导入时进行文件内去重和数据库已有内容去重。

数据集导出支持 `csv` 与 `xlsx`，导出文件保存在 `EXPORT_ROOT`，下载前会校验路径必须位于导出目录内。

## 报告生成

报告支持 `pdf`、`excel`、`csv` 三种格式：

- PDF 使用 ReportLab 生成，内置中文字体注册，包含时间范围、情感分布、关键词、类别分布、置信度区间等摘要。
- Excel/CSV 输出记录 ID、评论内容、情感倾向、置信度和分析时间。
- 报告生成通过 Celery 异步执行，文件写入采用临时文件再原子替换，降低半成品文件风险。
- 报告下载会校验用户权限和文件路径，避免越权读取。

## Celery 与定时任务

```powershell
# 默认队列：报告、清理等
celery -A sentiment_server worker -Q celery -l info -P solo

# 训练队列：模型训练
celery -A sentiment_server worker -Q training -l info -P solo -n training@%h

# Beat：定时任务
celery -A sentiment_server beat -l info
```

Beat 任务：

| 任务 | 频率 |
| --- | --- |
| 清理异常训练任务 | 每 5 分钟 |
| 清理操作日志 | 每 6 小时 |
| 自动重训阈值检查 | 每小时 |
| 清理过期验证码 | 每天 03:30 |

## 环境变量

复制 `.env.example` 为 `.env` 后配置：

```powershell
Copy-Item .env.example .env
```

关键变量：

| 变量 | 说明 |
| --- | --- |
| `SECRET_KEY` | Django 密钥，必填 |
| `JWT_SIGNING_KEY` | JWT 签名密钥，必填 |
| `DB_*` | MySQL 连接配置 |
| `REDIS_*` / `CELERY_*` | Redis 与 Celery 配置 |
| `MODEL_WORKSPACE_DIR` | 模型工作区根目录 |
| `MODEL_PATH` | 默认运行时模型路径 |
| `USE_GPU` | 是否尝试使用 CUDA |
| `MAX_BATCH_RECORDS` | 批量分析最大条数 |
| `OPERATION_LOG_RETENTION_DAYS` | 操作日志保留天数 |
| `SWAGGER_ENABLED` | 是否开启 Swagger/Redoc |

## 本地开发

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -e ".[training,testing]"
Copy-Item .env.example .env
```

编辑 `.env` 后执行：

```powershell
$env:DJANGO_SETTINGS_MODULE = "sentiment_server.settings.local"
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver 127.0.0.1:8000
```

健康检查：

```powershell
Invoke-RestMethod http://127.0.0.1:8000/api/healthz/
```

## 测试与质量检查

```powershell
$env:DJANGO_SETTINGS_MODULE = "sentiment_server.settings.local"
python manage.py check
python -m ruff check .
python -m pytest -q
python -m pytest ml_assets/tests -q
```

测试覆盖认证、权限、情感分析、历史趋势、报告下载与渲染、训练任务创建、模型激活、数据库备份、管理员日志等后端关键行为。

## 运行时目录

| 路径 | 用途 |
| --- | --- |
| `ml_assets/models/bert` | 默认 Transformer 推理模型，本地自备，不提交 |
| `ml_assets/models/_training_runs/` | 训练任务输出与日志，本地生成，不提交 |
| `ml_assets/data/` | 工作区数据集，本地自备，不提交 |
| `generated_reports/` | 报告输出，本地生成，不提交 |
| `exports/` | 数据集导出，本地生成，不提交 |
| `uploads/` | 用户上传文件，本地生成，不提交 |
| `media/` | 头像等媒体文件，本地生成，不提交 |
| `logs/` | Django 日志，本地生成，不提交 |
| `backups/` | 数据库备份，本地生成，不提交 |

## 数据库备份

```powershell
.\scripts\ops\backup_database.ps1
```

脚本可配合 Windows 任务计划程序定期执行，并自动清理旧备份。

## 论文撰写提示

后端部分可在论文中拆成如下章节描述：

- **系统架构设计**：Django app 分层、REST API、RBAC、Celery 异步任务。
- **数据库设计**：8 张核心业务表及用户、评论、分析结果、模型、训练任务之间的关系。
- **模型服务设计**：统一推理加载器、模型路径解析、多类型模型兼容、关键词提取。
- **数据处理设计**：TXT/XLSX 解析、长度限制、去重、文件类型校验、批量推理事务。
- **报告与审计设计**：异步报告状态流转、文件渲染、下载权限、操作日志保留。
