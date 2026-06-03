import re

import torch
from transformers import AutoModelForSequenceClassification, AutoTokenizer

from ml_assets.workspace.data.constants import CLASS_LABEL_NAMES, DEFAULT_API_MODEL_DIR, ID2LABEL


STOPWORDS = {
    "这个",
    "那个",
    "我们",
    "你们",
    "他们",
    "真的",
    "觉得",
    "一个",
    "一种",
    "已经",
    "非常",
}


def _predict_probabilities(tokenizer, model, device, texts, max_length):
    if not texts:
        return [], []
    encoded = tokenizer(
        texts,
        truncation=True,
        padding=True,
        max_length=max_length,
        return_tensors="pt",
    )
    encoded = {key: value.to(device) for key, value in encoded.items()}
    logits = model(**encoded).logits
    probabilities = torch.softmax(logits, dim=-1)
    predictions = torch.argmax(probabilities, dim=-1)
    return probabilities.cpu().tolist(), predictions.cpu().tolist()


def _remove_first_occurrence(text, token):
    return re.sub(re.escape(token), "", text, count=1)


def load_transformer_model(model_path=DEFAULT_API_MODEL_DIR, device=None):
    tokenizer = AutoTokenizer.from_pretrained(str(model_path))
    model = AutoModelForSequenceClassification.from_pretrained(str(model_path))
    if device is None:
        device = "cuda" if torch.cuda.is_available() else "cpu"
    model.to(device)
    model.eval()
    return tokenizer, model, device


def extract_keywords(text, top_k=5):
    candidates = re.findall(r"[A-Za-z0-9]+|[\u4e00-\u9fff]{2,4}", text)
    scored = []
    seen = set()
    for token in candidates:
        if token in STOPWORDS or token in seen:
            continue
        seen.add(token)
        score = len(token) + text.count(token)
        scored.append((token, score))
    scored.sort(key=lambda item: item[1], reverse=True)
    return [token for token, _ in scored[:top_k]]


@torch.no_grad()
def _extract_model_keywords(
    tokenizer,
    model,
    device,
    text,
    predicted_label_id,
    max_length=256,
    top_k=5,
    batch_size=16,
):
    tokens = tokenizer.tokenize(text)[: max(0, min(max_length - 2, 48))]
    if not tokens:
        return extract_keywords(text, top_k=top_k)

    baseline_probabilities, _ = _predict_probabilities(
        tokenizer,
        model,
        device,
        [text],
        max_length=max_length,
    )
    baseline_confidence = baseline_probabilities[0][predicted_label_id]

    # Collect all (normalized_token, reduced_text) pairs first
    reduced_pairs = []  # list of (normalized_token, reduced_text)
    seen_tokens = set()
    for index, token in enumerate(tokens):
        normalized_token = token.replace("##", "").strip()
        normalized_token = re.sub(r"\s+", "", normalized_token)
        normalized_token = re.sub(r"^[^\w\u4e00-\u9fff]+|[^\w\u4e00-\u9fff]+$", "", normalized_token)
        if not normalized_token or normalized_token in STOPWORDS:
            continue

        reduced_tokens = tokens[:index] + tokens[index + 1 :]
        if not reduced_tokens:
            continue

        reduced_text = tokenizer.convert_tokens_to_string(reduced_tokens).replace(" ", "")
        if not reduced_text:
            continue

        # Deduplicate: keep first occurrence of each normalized token
        if normalized_token in seen_tokens:
            continue
        seen_tokens.add(normalized_token)
        reduced_pairs.append((normalized_token, reduced_text))

    if not reduced_pairs:
        return extract_keywords(text, top_k=top_k)

    # Batch inference: process all reduced texts in chunks
    token_scores = {}
    for chunk_start in range(0, len(reduced_pairs), batch_size):
        chunk = reduced_pairs[chunk_start : chunk_start + batch_size]
        chunk_texts = [rt for _, rt in chunk]
        chunk_probs, _ = _predict_probabilities(
            tokenizer,
            model,
            device,
            chunk_texts,
            max_length=max_length,
        )
        for (normalized_token, _), prob in zip(chunk, chunk_probs):
            reduced_confidence = prob[predicted_label_id]
            contribution = baseline_confidence - reduced_confidence
            if contribution > 0:
                token_scores[normalized_token] = max(
                    contribution,
                    token_scores.get(normalized_token, float("-inf")),
                )

    if not token_scores:
        return extract_keywords(text, top_k=top_k)

    ranked_tokens = sorted(token_scores.items(), key=lambda item: item[1], reverse=True)
    return [token for token, _ in ranked_tokens[:top_k]]


@torch.no_grad()
def extract_sentiment_keywords(
    tokenizer,
    model,
    device,
    text,
    predicted_label_id,
    max_length=256,
    top_k=5,
    mode="hybrid",
    batch_size=16,
):
    if mode == "fast":
        return extract_keywords(text, top_k=top_k)

    if mode == "model":
        return _extract_model_keywords(
            tokenizer=tokenizer,
            model=model,
            device=device,
            text=text,
            predicted_label_id=predicted_label_id,
            max_length=max_length,
            top_k=top_k,
            batch_size=batch_size,
        )

    candidate_terms = extract_keywords(text, top_k=max(top_k * 3, 8))
    if not candidate_terms:
        return []

    baseline_probabilities, _ = _predict_probabilities(
        tokenizer,
        model,
        device,
        [text],
        max_length=max_length,
    )
    baseline_confidence = baseline_probabilities[0][predicted_label_id]

    # Batch inference: collect all reduced texts first
    reduced_pairs = []  # list of (term, reduced_text)
    for term in candidate_terms:
        reduced_text = _remove_first_occurrence(text, term).strip()
        if reduced_text:
            reduced_pairs.append((term, reduced_text))

    if not reduced_pairs:
        return extract_keywords(text, top_k=top_k)

    term_scores = {}
    for chunk_start in range(0, len(reduced_pairs), batch_size):
        chunk = reduced_pairs[chunk_start : chunk_start + batch_size]
        chunk_texts = [rt for _, rt in chunk]
        chunk_probs, _ = _predict_probabilities(
            tokenizer,
            model,
            device,
            chunk_texts,
            max_length=max_length,
        )
        for (term, _), prob in zip(chunk, chunk_probs):
            reduced_confidence = prob[predicted_label_id]
            contribution = baseline_confidence - reduced_confidence
            if contribution > 0:
                term_scores[term] = contribution

    if not term_scores:
        return extract_keywords(text, top_k=top_k)

    ranked_terms = sorted(term_scores.items(), key=lambda item: item[1], reverse=True)
    return [term for term, _ in ranked_terms[:top_k]]


@torch.no_grad()
def predict_texts(
    tokenizer,
    model,
    device,
    texts,
    max_length=256,
    keyword_top_k=5,
    keyword_mode="hybrid",
):
    if not texts:
        return []
    probabilities, predictions = _predict_probabilities(
        tokenizer,
        model,
        device,
        texts,
        max_length=max_length,
    )

    results = []
    for text, prediction, probability_vector in zip(texts, predictions, probabilities):
        confidence = max(probability_vector)
        results.append(
            {
                "text": text,
                "label_id": prediction,
                "label": ID2LABEL[prediction],
                "confidence": confidence,
                "probabilities": {
                    label_name: probability_vector[index]
                    for index, label_name in enumerate(CLASS_LABEL_NAMES)
                },
                "keywords": extract_sentiment_keywords(
                    tokenizer=tokenizer,
                    model=model,
                    device=device,
                    text=text,
                    predicted_label_id=prediction,
                    max_length=max_length,
                    top_k=keyword_top_k,
                    mode=keyword_mode,
                ),
            }
        )
    return results

