from ml_assets.workspace.training.orchestration import (
    build_transformer_workflow_context,
    finalize_transformer_training_run,
)


def train_transformer_model(args, train_dataset=None, eval_dataset=None):
    workflow_context = build_transformer_workflow_context(
        args,
        train_dataset,
        eval_dataset,
    )
    return finalize_transformer_training_run(args, workflow_context)

