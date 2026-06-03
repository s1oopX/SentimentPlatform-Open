# Contributing

感谢你愿意参与 SentimentPlatform。这个项目欢迎问题反馈、文档改进、测试补充和功能实现。

## Development

1. Fork this repository and create a focused branch.
2. Backend: `cd sentiment_server && pip install -e ".[training,testing]"`.
3. Frontend: `cd sentiment_webapp && npm install`.
4. Copy `sentiment_server/.env.example` to `.env` and fill local secrets and service settings.

## Validation

```powershell
cd sentiment_server
$env:DJANGO_SETTINGS_MODULE = "sentiment_server.settings.local"
python manage.py check
python -m ruff check .
python -m pytest -q
```

```powershell
cd sentiment_webapp
npm run check
npm run build
```

## Asset Policy

Do not commit environment files, local databases, logs, generated reports, uploads, model weights, training outputs, or datasets. Public releases keep model and dataset directories empty except for documentation and small redistributable stopword lists.
