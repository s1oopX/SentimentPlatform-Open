import numpy as np


def train_word2vec(
    tokenized_texts,
    *,
    vector_size=300,
    window=5,
    min_count=2,
    workers=4,
    seed=42,
):
    """训练 Word2Vec 模型。

    Args:
        tokenized_texts: list[list[str]]，已分词的文本列表
        vector_size: 词向量维度
        window: 上下文窗口大小
        min_count: 最低词频阈值
        workers: 并行线程数
        seed: 随机种子

    Returns:
        gensim.models.Word2Vec
    """
    from gensim.models import Word2Vec

    model = Word2Vec(
        sentences=tokenized_texts,
        vector_size=vector_size,
        window=window,
        min_count=min_count,
        workers=workers,
        seed=seed,
    )
    return model


def load_word2vec(path):
    """加载已训练的 Word2Vec 模型。

    Args:
        path: str | Path，模型文件路径

    Returns:
        gensim.models.Word2Vec
    """
    from gensim.models import Word2Vec

    return Word2Vec.load(str(path))


def embed_texts(tokenized_texts, model):
    """将已分词文本编码为均值词向量。

    Args:
        tokenized_texts: list[list[str]]，已分词的文本列表
        model: gensim.models.Word2Vec

    Returns:
        np.ndarray，形状 (len(tokenized_texts), model.vector_size)
    """
    vector_size = model.wv.vector_size
    embeddings = np.zeros((len(tokenized_texts), vector_size), dtype=np.float32)

    for i, tokens in enumerate(tokenized_texts):
        vecs = []
        for token in tokens:
            if token in model.wv:
                vecs.append(model.wv[token])
        if vecs:
            embeddings[i] = np.mean(vecs, axis=0)

    return embeddings
