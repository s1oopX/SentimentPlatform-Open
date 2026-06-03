import re
import unicodedata
from pathlib import Path

# ── patterns ────────────────────────────────────────────────────────

_URL_PATTERN = re.compile(
    r"https?://[^\s]+|www\.[^\s]+",
    re.IGNORECASE,
)

_EMOJI_PATTERN = re.compile(
    "["
    "\U0001F600-\U0001F64F"  # emoticons
    "\U0001F300-\U0001F5FF"  # symbols & pictographs
    "\U0001F680-\U0001F6FF"  # transport & map
    "\U0001F1E0-\U0001F1FF"  # flags
    "\U00002702-\U000027B0"  # dingbats
    "\U000024C2-\U000024C9"  # circled Latin
    "\U0001F250-\U0001F251"  # circled ideograph
    "]+",
    re.UNICODE,
)

_SPECIAL_CHARS_PATTERN = re.compile(
    r"[^一-鿿㐀-䶿"  # CJK unified
    r"a-zA-Z0-9"                     # alphanumeric
    r"　-〿"                 # CJK punctuation
    r"＀-￯"                 # fullwidth forms
    r" -⁯"                 # general punctuation
    r"\s]+",                         # whitespace
    re.UNICODE,
)

_NONSENSE_PATTERN = re.compile(
    r"^[\d\s\W_]+$",  # pure digits, whitespace, non-word
    re.UNICODE,
)

# ── default stopwords path ───────────────────────────────────────────

_DEFAULT_STOPWORDS_PATH = (
    Path(__file__).resolve().parents[2] / "data" / "stopwords" / "hit_stopwords.txt"
)


def load_stopwords(path=None):
    path = Path(path) if path else _DEFAULT_STOPWORDS_PATH
    if not path.exists():
        raise FileNotFoundError(f"停用词文件不存在: {path}")
    with path.open("r", encoding="utf-8") as f:
        return {line.strip() for line in f if line.strip()}


# ── cleaning ─────────────────────────────────────────────────────────


def clean_text(text):
    """去除URL、表情符号、特殊字符，返回清洗后文本。"""
    if not isinstance(text, str):
        return ""
    text = _URL_PATTERN.sub(" ", text)
    text = _EMOJI_PATTERN.sub(" ", text)
    text = _SPECIAL_CHARS_PATTERN.sub(" ", text)
    text = " ".join(text.split())
    return text


def apply_cleaning_rules(
    texts,
    *,
    min_length=5,
    max_length=1000,
    dedup=True,
):
    """批量清洗 + 长度过滤 + 去重 + UTF-8 规范化。

    Returns:
        list[str]: 清洗后的文本列表，顺序保持去重后的首次出现顺序。
    """
    cleaned = []
    seen = set()

    for text in texts:
        if not isinstance(text, str):
            continue

        # UTF-8 normalization (NFC for CJK compatibility)
        text = unicodedata.normalize("NFC", text)

        # Clean
        text = clean_text(text)
        if not text:
            continue

        # Length filter
        char_count = len(text)
        if char_count < min_length or char_count > max_length:
            continue

        # Nonsense filter
        if _NONSENSE_PATTERN.match(text):
            continue

        # Dedup
        if dedup:
            if text in seen:
                continue
            seen.add(text)

        cleaned.append(text)

    return cleaned


# ── default English stopwords path ────────────────────────────────────

_EN_STOPWORDS_PATH = (
    Path(__file__).resolve().parents[2] / "data" / "stopwords" / "english_stopwords.txt"
)

_FALLBACK_CN_WORDS = (
    "今天天气",
    "天气",
    "产品",
    "服务",
    "推荐",
    "购买",
    "价格",
    "质量",
    "不错",
    "很好",
    "真",
    "好",
)


def load_stopwords_en(path=None):
    """加载英文停用词表。"""
    path = Path(path) if path else _EN_STOPWORDS_PATH
    if not path.exists():
        raise FileNotFoundError(f"停用词文件不存在: {path}")
    with path.open("r", encoding="utf-8") as f:
        return {line.strip() for line in f if line.strip()}


# ── Chinese segmentation ─────────────────────────────────────────────


def segment_cn(text):
    """Jieba 中文分词。"""
    try:
        import jieba

        return list(jieba.cut(text))
    except (ImportError, LookupError, MemoryError):
        return _segment_cn_fallback(text)


def _segment_cn_fallback(text):
    tokens = []
    index = 0
    while index < len(text):
        match = next(
            (
                word
                for word in _FALLBACK_CN_WORDS
                if text.startswith(word, index)
            ),
            None,
        )
        if match:
            tokens.append(match)
            index += len(match)
            continue
        if text[index].strip():
            tokens.append(text[index])
        index += 1
    return tokens


def filter_stopwords(tokens, stopwords=None):
    """停用词过滤（中文，哈工大表）。"""
    if stopwords is None:
        stopwords = load_stopwords()
    return [t for t in tokens if t.strip() and t not in stopwords]


# ── English segmentation ─────────────────────────────────────────────


def segment_en(text):
    """NLTK 英文分词。"""
    try:
        import nltk

        return nltk.word_tokenize(text)
    except (ImportError, LookupError, MemoryError):
        return _segment_en_fallback(text)


def _segment_en_fallback(text):
    return re.findall(r"[A-Za-z]+(?:'[A-Za-z]+)?|\d+(?:\.\d+)?|[^\w\s]", text)


def lemmatize_en(tokens):
    """WordNet 英文词形还原。"""
    try:
        from nltk.stem import WordNetLemmatizer

        lemmatizer = WordNetLemmatizer()
        return [lemmatizer.lemmatize(t) for t in tokens]
    except (ImportError, LookupError, MemoryError):
        return [_lemmatize_en_fallback(t) for t in tokens]


def _lemmatize_en_fallback(token):
    lower = token.lower()
    if len(lower) > 4 and lower.endswith("ies"):
        return token[:-3] + "y"
    if len(lower) > 3 and lower.endswith(("ses", "xes", "zes", "ches", "shes")):
        return token[:-2]
    if len(lower) > 3 and lower.endswith("s") and not lower.endswith("ss"):
        return token[:-1]
    return token


def filter_stopwords_en(tokens, stopwords=None):
    """英文停用词过滤。"""
    if stopwords is None:
        stopwords = load_stopwords_en()
    return [t for t in tokens if t.strip() and t not in stopwords]
