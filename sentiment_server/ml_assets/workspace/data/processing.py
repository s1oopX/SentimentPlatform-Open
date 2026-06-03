from datasets import Dataset, load_from_disk
from sklearn.model_selection import train_test_split

from ml_assets.workspace.data.constants import LABEL2ID


def load_dataset_split(dataset_path):
    return load_from_disk(str(dataset_path))


def encode_label(example):
    label = example["label"]
    if isinstance(label, int):
        if label not in LABEL2ID.values():
            raise ValueError(f"未知标签编号: {label}")
        return example
    if label not in LABEL2ID:
        raise ValueError(f"未知标签: {label}")
    example["label"] = LABEL2ID[label]
    return example


def prepare_labeled_dataset(dataset):
    return dataset.map(encode_label, keep_in_memory=True)


def build_dataset_from_texts_and_labels(texts, labels):
    return Dataset.from_dict(
        {
            "text": list(texts),
            "label": list(labels),
        }
    )


def stratified_split_dataset(dataset, test_size, seed):
    prepared_dataset = prepare_labeled_dataset(dataset)
    texts, labels = dataset_to_texts_and_labels(prepared_dataset)
    train_texts, eval_texts, train_labels, eval_labels = train_test_split(
        texts,
        labels,
        test_size=test_size,
        random_state=seed,
        shuffle=True,
        stratify=labels,
    )
    train_dataset = build_dataset_from_texts_and_labels(train_texts, train_labels)
    eval_dataset = build_dataset_from_texts_and_labels(eval_texts, eval_labels)
    return train_dataset, eval_dataset


def stratified_three_way_split(
    dataset,
    train_size=0.7,
    val_size=0.1,
    test_size=0.2,
    seed=42,
):
    """7:1:2 三路分层划分（训练/验证/测试）。

    Args:
        dataset: HuggingFace Dataset
        train_size: 训练集比例，默认 0.7
        val_size: 验证集比例，默认 0.1
        test_size: 测试集比例，默认 0.2
        seed: 随机种子

    Returns:
        (train_dataset, val_dataset, test_dataset)
    """
    if abs(train_size + val_size + test_size - 1.0) > 1e-6:
        raise ValueError(
            f"train_size + val_size + test_size 必须等于 1.0，"
            f"当前: {train_size} + {val_size} + {test_size} = {train_size + val_size + test_size}"
        )

    prepared_dataset = prepare_labeled_dataset(dataset)
    texts, labels = dataset_to_texts_and_labels(prepared_dataset)

    # Step 1: 训练集 vs 临时集
    temp_size = val_size + test_size
    train_texts, temp_texts, train_labels, temp_labels = train_test_split(
        texts,
        labels,
        test_size=temp_size,
        random_state=seed,
        shuffle=True,
        stratify=labels,
    )

    # Step 2: 临时集 → 验证集 vs 测试集
    val_ratio = test_size / temp_size
    val_texts, test_texts, val_labels, test_labels = train_test_split(
        temp_texts,
        temp_labels,
        test_size=val_ratio,
        random_state=seed,
        shuffle=True,
        stratify=temp_labels,
    )

    return (
        build_dataset_from_texts_and_labels(train_texts, train_labels),
        build_dataset_from_texts_and_labels(val_texts, val_labels),
        build_dataset_from_texts_and_labels(test_texts, test_labels),
    )


def build_train_eval_datasets(args):
    train_dataset = prepare_labeled_dataset(load_dataset_split(args.train_dataset_path))
    eval_dataset = prepare_labeled_dataset(load_dataset_split(args.eval_dataset_path))
    return train_dataset, eval_dataset


def dataset_to_texts_and_labels(dataset):
    return list(dataset["text"]), list(dataset["label"])


def load_texts_and_labels(dataset_path):
    dataset = prepare_labeled_dataset(load_dataset_split(dataset_path))
    return dataset_to_texts_and_labels(dataset)


def load_train_eval_texts_and_labels(train_dataset_path, eval_dataset_path):
    train_dataset = prepare_labeled_dataset(load_dataset_split(train_dataset_path))
    eval_dataset = prepare_labeled_dataset(load_dataset_split(eval_dataset_path))
    train_texts, train_labels = dataset_to_texts_and_labels(train_dataset)
    eval_texts, eval_labels = dataset_to_texts_and_labels(eval_dataset)
    return train_texts, train_labels, eval_texts, eval_labels


def tokenize_function(tokenizer, max_length):
    def _tokenize(batch):
        return tokenizer(
            batch["text"],
            truncation=True,
            max_length=max_length,
        )

    return _tokenize


def build_tokenized_datasets(train_dataset, eval_dataset, tokenizer, max_length):
    tokenized_train = train_dataset.map(
        tokenize_function(tokenizer, max_length),
        batched=True,
        remove_columns=["text"],
    )
    tokenized_eval = eval_dataset.map(
        tokenize_function(tokenizer, max_length),
        batched=True,
        remove_columns=["text"],
    )
    return tokenized_train, tokenized_eval

