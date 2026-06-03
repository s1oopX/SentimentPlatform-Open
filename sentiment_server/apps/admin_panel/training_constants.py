WORKSPACE_DATASET_SOURCE = "workspace_dataset"

TASK_TYPE_TRANSFORMER_TRAIN = "transformer_train"
TASK_TYPE_TRANSFORMER_SEARCH = "transformer_search"
TASK_TYPE_CLASSICAL_COMPARE = "classical_compare"
TASK_TYPE_NEURAL_BASELINE_TRAIN = "neural_baseline_train"

TRAINING_TASK_TYPE_CHOICES = (
    (TASK_TYPE_TRANSFORMER_TRAIN, "Transformer 训练"),
    (TASK_TYPE_TRANSFORMER_SEARCH, "Transformer 搜索"),
    (TASK_TYPE_CLASSICAL_COMPARE, "传统模型比较"),
    (TASK_TYPE_NEURAL_BASELINE_TRAIN, "神经网络基线训练"),
)

TRAINING_STATUS_CHOICES = (
    ("queued", "已排队"),
    ("running", "执行中"),
    ("succeeded", "成功"),
    ("failed", "失败"),
    ("cancelled", "已取消"),
)

TRAINING_PENDING_ENQUEUE_ERROR = "训练任务等待加入队列"

TRAINING_POST_RUN_STATUS_CHOICES = (
    ("pending", "待处理"),
    ("succeeded", "成功"),
    ("warning", "告警"),
    ("failed", "失败"),
)

DATASET_SOURCE_CHOICES = ((WORKSPACE_DATASET_SOURCE, "工作区数据集"),)

TRANSFORMER_MODEL_FAMILIES = ("bert", "roberta")
TRANSFORMER_MODEL_FAMILY_CHOICES = tuple(
    (value, value) for value in TRANSFORMER_MODEL_FAMILIES
)

CLASSICAL_CANDIDATE_MODELS = (
    "logistic_regression",
    "linear_svm",
    "random_forest",
)
NEURAL_CANDIDATE_MODELS = (
    "textcnn",
    "bilstm",
)
ALL_CANDIDATE_MODELS = CLASSICAL_CANDIDATE_MODELS + NEURAL_CANDIDATE_MODELS

SEARCH_TYPE_CHOICES = (
    ("none", "不搜索"),
    ("grid", "网格搜索"),
    ("random", "随机搜索"),
)

SPLIT_STRATEGY_CHOICES = (
    ("pre_split", "预切分数据集"),
    ("auto_split", "自动 7:1:2 分层划分"),
)
