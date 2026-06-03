# Model And Data Assets

The public repository intentionally does not include model weights or datasets.

## Model Directory

Put local runtime models under:

```text
sentiment_server/ml_assets/models/
```

For the default Transformer runtime, the expected local layout is:

```text
sentiment_server/ml_assets/models/bert/
├── config.json
├── model.safetensors
├── tokenizer_config.json
├── tokenizer.json
└── vocab.txt
```

You may also set `MODEL_PATH` in `sentiment_server/.env` to another path under `MODEL_WORKSPACE_DIR`.

## Dataset Directory

Put local datasets under:

```text
sentiment_server/ml_assets/data/
```

Do not commit original datasets, HuggingFace Arrow files, generated splits, or private/business data. The public repo only keeps preprocessing code and small redistributable stopword lists.

## Ignored Asset Types

```text
*.arrow
*.safetensors
*.bin
*.pt
*.pth
*.joblib
*.pkl
training_args.bin
dataset_info.json
state.json
```
