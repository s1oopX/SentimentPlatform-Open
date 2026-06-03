from collections import Counter

import torch
from torch import nn
from torch.utils.data import DataLoader, Dataset

from ml_assets.workspace.evaluation.metrics import calculate_classification_metrics


PAD_TOKEN = "<pad>"
UNK_TOKEN = "<unk>"


class CharVocab:
    def __init__(self, token_to_id):
        self.token_to_id = token_to_id
        self.id_to_token = {index: token for token, index in token_to_id.items()}
        self.pad_id = token_to_id[PAD_TOKEN]
        self.unk_id = token_to_id[UNK_TOKEN]

    def encode(self, text, max_length):
        token_ids = [self.token_to_id.get(char, self.unk_id) for char in text[:max_length]]
        length = len(token_ids)
        if length < max_length:
            token_ids.extend([self.pad_id] * (max_length - length))
        return token_ids, min(length, max_length)

    def __len__(self):
        return len(self.token_to_id)


def build_char_vocab(texts, min_freq=2):
    counter = Counter()
    for text in texts:
        counter.update(text)

    token_to_id = {
        PAD_TOKEN: 0,
        UNK_TOKEN: 1,
    }
    for token, count in counter.items():
        if count >= min_freq and token not in token_to_id:
            token_to_id[token] = len(token_to_id)
    return CharVocab(token_to_id)


class TextClassificationDataset(Dataset):
    def __init__(self, texts, labels, vocab, max_length):
        self.texts = texts
        self.labels = labels
        self.vocab = vocab
        self.max_length = max_length

    def __len__(self):
        return len(self.texts)

    def __getitem__(self, index):
        token_ids, length = self.vocab.encode(self.texts[index], self.max_length)
        return {
            "input_ids": torch.tensor(token_ids, dtype=torch.long),
            "length": torch.tensor(length, dtype=torch.long),
            "labels": torch.tensor(self.labels[index], dtype=torch.long),
        }


class TextCNNClassifier(nn.Module):
    def __init__(self, vocab_size, num_classes, embed_dim, num_filters, kernel_sizes, dropout):
        super().__init__()
        self.embedding = nn.Embedding(vocab_size, embed_dim, padding_idx=0)
        self.convs = nn.ModuleList(
            [
                nn.Conv1d(embed_dim, num_filters, kernel_size=kernel_size)
                for kernel_size in kernel_sizes
            ]
        )
        self.dropout = nn.Dropout(dropout)
        self.classifier = nn.Linear(num_filters * len(kernel_sizes), num_classes)

    def forward(self, input_ids, _lengths=None):
        embedded = self.embedding(input_ids).transpose(1, 2)
        features = []
        for conv in self.convs:
            convolved = torch.relu(conv(embedded))
            pooled = torch.max(convolved, dim=2).values
            features.append(pooled)
        combined = torch.cat(features, dim=1)
        return self.classifier(self.dropout(combined))


class BiLSTMClassifier(nn.Module):
    def __init__(self, vocab_size, num_classes, embed_dim, hidden_size, dropout):
        super().__init__()
        self.embedding = nn.Embedding(vocab_size, embed_dim, padding_idx=0)
        self.encoder = nn.LSTM(
            input_size=embed_dim,
            hidden_size=hidden_size,
            batch_first=True,
            bidirectional=True,
        )
        self.dropout = nn.Dropout(dropout)
        self.classifier = nn.Linear(hidden_size * 2, num_classes)

    def forward(self, input_ids, lengths):
        embedded = self.embedding(input_ids)
        packed = nn.utils.rnn.pack_padded_sequence(
            embedded,
            lengths.cpu(),
            batch_first=True,
            enforce_sorted=False,
        )
        _, (hidden, _) = self.encoder(packed)
        forward_hidden = hidden[-2]
        backward_hidden = hidden[-1]
        features = torch.cat([forward_hidden, backward_hidden], dim=1)
        return self.classifier(self.dropout(features))


def build_neural_model(
    model_name,
    vocab_size,
    num_classes,
    embed_dim,
    hidden_size,
    dropout,
    num_filters,
    kernel_sizes,
):
    if model_name == "textcnn":
        return TextCNNClassifier(
            vocab_size=vocab_size,
            num_classes=num_classes,
            embed_dim=embed_dim,
            num_filters=num_filters,
            kernel_sizes=kernel_sizes,
            dropout=dropout,
        )
    if model_name == "bilstm":
        return BiLSTMClassifier(
            vocab_size=vocab_size,
            num_classes=num_classes,
            embed_dim=embed_dim,
            hidden_size=hidden_size,
            dropout=dropout,
        )
    raise ValueError(f"不支持的模型: {model_name}")


def build_dataloader(texts, labels, vocab, max_length, batch_size, shuffle):
    dataset = TextClassificationDataset(texts, labels, vocab, max_length)
    return DataLoader(dataset, batch_size=batch_size, shuffle=shuffle)


def run_epoch(model, dataloader, criterion, optimizer, device):
    model.train()
    total_loss = 0.0

    for batch in dataloader:
        input_ids = batch["input_ids"].to(device)
        lengths = batch["length"].to(device)
        labels = batch["labels"].to(device)

        optimizer.zero_grad()
        logits = model(input_ids, lengths)
        loss = criterion(logits, labels)
        loss.backward()
        optimizer.step()
        total_loss += loss.item()

    return total_loss / max(len(dataloader), 1)


@torch.no_grad()
def predict(model, dataloader, device):
    model.eval()
    all_labels = []
    all_predictions = []
    all_probabilities = []

    for batch in dataloader:
        input_ids = batch["input_ids"].to(device)
        lengths = batch["length"].to(device)
        labels = batch["labels"].to(device)

        logits = model(input_ids, lengths)
        probabilities = torch.softmax(logits, dim=-1)
        predictions = torch.argmax(probabilities, dim=-1)

        all_labels.extend(labels.cpu().tolist())
        all_predictions.extend(predictions.cpu().tolist())
        all_probabilities.extend(probabilities.cpu().tolist())

    return all_labels, all_predictions, all_probabilities


@torch.no_grad()
def evaluate(model, dataloader, device):
    labels, predictions, probabilities = predict(model, dataloader, device)
    metrics = calculate_classification_metrics(labels, predictions)
    return metrics, probabilities


def train_with_early_stopping(
    model,
    train_loader,
    eval_loader,
    device,
    num_epochs,
    learning_rate,
    weight_decay,
    patience,
):
    criterion = nn.CrossEntropyLoss()
    optimizer = torch.optim.AdamW(
        model.parameters(),
        lr=learning_rate,
        weight_decay=weight_decay,
    )

    best_macro_f1 = -1.0
    best_state_dict = None
    best_metrics = None
    history = []
    patience_counter = 0

    for epoch in range(1, num_epochs + 1):
        train_loss = run_epoch(model, train_loader, criterion, optimizer, device)
        eval_metrics, _ = evaluate(model, eval_loader, device)
        history.append(
            {
                "epoch": epoch,
                "train_loss": train_loss,
                "eval_accuracy": eval_metrics["accuracy"],
                "eval_macro_f1": eval_metrics["macro_f1"],
                "eval_negative_recall": eval_metrics["negative_recall"],
            }
        )

        if eval_metrics["macro_f1"] > best_macro_f1:
            best_macro_f1 = eval_metrics["macro_f1"]
            best_state_dict = {
                key: value.detach().cpu().clone() for key, value in model.state_dict().items()
            }
            best_metrics = eval_metrics
            patience_counter = 0
        else:
            patience_counter += 1

        if patience_counter >= patience:
            break

    if best_state_dict is not None:
        model.load_state_dict(best_state_dict)

    final_metrics, probabilities = evaluate(model, eval_loader, device)
    return {
        "history": history,
        "best_metrics": best_metrics or final_metrics,
        "final_metrics": final_metrics,
        "probabilities": probabilities,
    }

