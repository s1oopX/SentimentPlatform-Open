from sklearn.ensemble import RandomForestClassifier
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.svm import LinearSVC


MODEL_SPECS = {
    "logistic_regression": {
        "grid": {
            "vectorizer__ngram_range": [(1, 2), (1, 3)],
            "vectorizer__min_df": [1, 2, 3],
            "vectorizer__max_features": [15000, 30000],
            "classifier__C": [0.5, 1.0, 2.0, 4.0],
        },
        "random": {
            "vectorizer__ngram_range": [(1, 2), (1, 3)],
            "vectorizer__min_df": [1, 2, 3, 5],
            "vectorizer__max_features": [10000, 15000, 20000, 30000],
            "classifier__C": [0.25, 0.5, 1.0, 2.0, 4.0, 8.0],
        },
    },
    "linear_svm": {
        "grid": {
            "vectorizer__ngram_range": [(1, 2), (1, 3)],
            "vectorizer__min_df": [1, 2, 3],
            "vectorizer__max_features": [15000, 30000],
            "classifier__C": [0.25, 0.5, 1.0, 2.0, 4.0],
        },
        "random": {
            "vectorizer__ngram_range": [(1, 2), (1, 3)],
            "vectorizer__min_df": [1, 2, 3, 5],
            "vectorizer__max_features": [10000, 15000, 20000, 30000],
            "classifier__C": [0.125, 0.25, 0.5, 1.0, 2.0, 4.0],
        },
    },
    "random_forest": {
        "grid": {
            "vectorizer__ngram_range": [(1, 2), (1, 3)],
            "vectorizer__min_df": [1, 2],
            "vectorizer__max_features": [10000, 15000],
            "classifier__n_estimators": [200, 400],
            "classifier__max_depth": [None, 20, 40],
            "classifier__min_samples_split": [2, 4],
        },
        "random": {
            "vectorizer__ngram_range": [(1, 2), (1, 3)],
            "vectorizer__min_df": [1, 2, 3],
            "vectorizer__max_features": [8000, 10000, 15000, 20000],
            "classifier__n_estimators": [200, 300, 400, 500],
            "classifier__max_depth": [None, 20, 40, 60],
            "classifier__min_samples_split": [2, 4, 6],
            "classifier__min_samples_leaf": [1, 2, 4],
        },
    },
}


def build_estimator(model_name, seed):
    vectorizer = TfidfVectorizer(
        analyzer="char",
        sublinear_tf=True,
        lowercase=False,
    )

    if model_name == "logistic_regression":
        classifier = LogisticRegression(
            max_iter=2000,
            class_weight="balanced",
            random_state=seed,
        )
    elif model_name == "linear_svm":
        classifier = LinearSVC(
            class_weight="balanced",
            random_state=seed,
        )
    elif model_name == "random_forest":
        classifier = RandomForestClassifier(
            random_state=seed,
            class_weight="balanced_subsample",
            n_jobs=1,
        )
    else:
        raise ValueError(f"不支持的模型: {model_name}")

    return Pipeline(
        [
            ("vectorizer", vectorizer),
            ("classifier", classifier),
        ]
    )


def get_supported_model_names():
    return list(MODEL_SPECS.keys())


def get_search_space(model_name, search_type):
    if model_name not in MODEL_SPECS:
        raise ValueError(f"不支持的模型: {model_name}")
    if search_type not in ("grid", "random"):
        raise ValueError(f"不支持的搜索策略: {search_type}")
    return MODEL_SPECS[model_name][search_type]
