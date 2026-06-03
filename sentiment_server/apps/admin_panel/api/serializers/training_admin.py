from rest_framework import serializers

from apps.admin_panel.training_constants import (
    ALL_CANDIDATE_MODELS,
    SEARCH_TYPE_CHOICES,
    SPLIT_STRATEGY_CHOICES,
    TASK_TYPE_CLASSICAL_COMPARE,
    TASK_TYPE_NEURAL_BASELINE_TRAIN,
    TASK_TYPE_TRANSFORMER_SEARCH,
    TASK_TYPE_TRANSFORMER_TRAIN,
    TRAINING_TASK_TYPE_CHOICES,
    TRANSFORMER_MODEL_FAMILY_CHOICES,
    WORKSPACE_DATASET_SOURCE,
)
from apps.admin_panel.application.training_admin.commands import (
    TrainingServiceError,
    validate_candidate_models_for_task,
)

TRANSFORMER_TASK_TYPES = {TASK_TYPE_TRANSFORMER_TRAIN, TASK_TYPE_TRANSFORMER_SEARCH}


class TrainingRecordSerializer(serializers.Serializer):
    record_id = serializers.CharField()
    title = serializers.CharField()
    source_type = serializers.CharField()
    workflow_type = serializers.CharField(allow_null=True, required=False)
    execution_mode = serializers.CharField()
    status = serializers.CharField()
    metric_highlights = serializers.DictField()
    artifact_paths = serializers.DictField(required=False)
    created_at = serializers.CharField(
        allow_blank=True, required=False, allow_null=True
    )
    note = serializers.CharField(required=False, allow_blank=True)
    can_delete = serializers.BooleanField(required=False)


class TrainingRecordCreateSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=120)
    task_type = serializers.ChoiceField(choices=TRAINING_TASK_TYPE_CHOICES)
    dataset_source = serializers.ChoiceField(choices=[WORKSPACE_DATASET_SOURCE])
    dataset_ref = serializers.CharField(max_length=255)
    model_family = serializers.ChoiceField(
        choices=TRANSFORMER_MODEL_FAMILY_CHOICES, required=False, allow_blank=True
    )
    candidate_models = serializers.ListField(
        child=serializers.ChoiceField(choices=ALL_CANDIDATE_MODELS),
        required=False,
        allow_empty=True,
    )
    search_type = serializers.ChoiceField(
        choices=SEARCH_TYPE_CHOICES, required=False, allow_blank=True
    )
    split_strategy = serializers.ChoiceField(
        choices=SPLIT_STRATEGY_CHOICES, required=False, default="pre_split"
    )
    target_macro_f1 = serializers.FloatField(
        required=False, default=0.85, min_value=0.01, max_value=1.0
    )
    max_length = serializers.IntegerField(
        required=False, default=256, min_value=8, max_value=4096
    )
    use_gpu = serializers.BooleanField(required=False, default=False)
    max_trials = serializers.IntegerField(required=False, default=8, min_value=1)
    cv_folds = serializers.IntegerField(required=False, default=3, min_value=2)

    def _validate_transformer(
        self, _attrs, task_type, candidate_models, search_type, model_family
    ):
        if not model_family:
            raise serializers.ValidationError(
                {"model_family": "transformer 任务必须提供 model_family"}
            )
        if candidate_models:
            raise serializers.ValidationError(
                {"candidate_models": "transformer 任务不接受 candidate_models"}
            )
        if task_type == TASK_TYPE_TRANSFORMER_SEARCH and not search_type:
            raise serializers.ValidationError(
                {"search_type": "transformer_search 必须提供 search_type"}
            )
        if task_type == TASK_TYPE_TRANSFORMER_TRAIN and search_type:
            raise serializers.ValidationError(
                {"search_type": "transformer_train 不接受 search_type"}
            )

    def _validate_classical_compare(
        self, _attrs, candidate_models, search_type, model_family
    ):
        if model_family:
            raise serializers.ValidationError(
                {"model_family": "classical_compare 不接受 model_family"}
            )
        if not candidate_models:
            raise serializers.ValidationError(
                {"candidate_models": "classical_compare 必须提供 candidate_models"}
            )
        try:
            validate_candidate_models_for_task(
                TASK_TYPE_CLASSICAL_COMPARE, candidate_models
            )
        except TrainingServiceError as exc:
            raise serializers.ValidationError({"candidate_models": str(exc)})
        if not search_type:
            raise serializers.ValidationError(
                {"search_type": "classical_compare 必须提供 search_type"}
            )

    def _validate_neural_baseline(
        self, _attrs, candidate_models, search_type, model_family
    ):
        if model_family:
            raise serializers.ValidationError(
                {"model_family": "neural_baseline_train 不接受 model_family"}
            )
        if not candidate_models:
            raise serializers.ValidationError(
                {"candidate_models": "neural_baseline_train 必须提供 candidate_models"}
            )
        try:
            validate_candidate_models_for_task(
                TASK_TYPE_NEURAL_BASELINE_TRAIN, candidate_models
            )
        except TrainingServiceError as exc:
            raise serializers.ValidationError({"candidate_models": str(exc)})
        if search_type:
            raise serializers.ValidationError(
                {"search_type": "neural_baseline_train 不接受 search_type"}
            )

    def validate(self, attrs):
        task_type = attrs["task_type"]
        candidate_models = list(attrs.get("candidate_models") or [])
        search_type = attrs.get("search_type") or ""
        model_family = attrs.get("model_family") or ""
        use_gpu = bool(attrs.get("use_gpu", False))

        if use_gpu and task_type != TASK_TYPE_NEURAL_BASELINE_TRAIN:
            raise serializers.ValidationError(
                {"use_gpu": "GPU 训练仅适用于 neural_baseline_train PyTorch 任务"}
            )

        if task_type in TRANSFORMER_TASK_TYPES:
            self._validate_transformer(
                attrs, task_type, candidate_models, search_type, model_family
            )
        elif task_type == TASK_TYPE_CLASSICAL_COMPARE:
            self._validate_classical_compare(
                attrs, candidate_models, search_type, model_family
            )
        elif task_type == TASK_TYPE_NEURAL_BASELINE_TRAIN:
            self._validate_neural_baseline(
                attrs, candidate_models, search_type, model_family
            )

        attrs["candidate_models"] = candidate_models
        attrs["search_type"] = search_type
        attrs["model_family"] = model_family
        attrs["use_gpu"] = (
            use_gpu if task_type == TASK_TYPE_NEURAL_BASELINE_TRAIN else False
        )
        return attrs


class TrainingRecordQuerySerializer(serializers.Serializer):
    page = serializers.IntegerField(required=False, default=1, min_value=1)
    page_size = serializers.IntegerField(
        required=False, default=20, min_value=1, max_value=100
    )
