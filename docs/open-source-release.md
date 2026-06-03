# Open Source Release

This repository is a sanitized public version of SentimentPlatform.

It includes:

- Django REST API backend.
- Vue 3 frontend.
- ML preprocessing, training, and inference adapter code.
- Tests, development scripts, and documentation.

It excludes:

- Model weights and training artifacts.
- Datasets and generated dataset splits.
- Local `.env` files and secrets.
- Demo accounts and local database content.
- Runtime reports, uploads, exports, logs, and backups.

The backend can start and run checks without bundled model assets. Actual sentiment analysis requests require a locally configured model; see `docs/model-and-data-assets.md`.
