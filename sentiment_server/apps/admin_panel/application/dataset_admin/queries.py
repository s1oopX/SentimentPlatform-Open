from apps.admin_panel.infra.selectors.datasets import (
    get_comments_for_export,
    get_filtered_comments,
)


def build_dataset_list_response(
    *, project_name="", category="", start_date="", end_date=""
):
    return get_filtered_comments(
        project_name=project_name,
        category=category,
        start_date=start_date,
        end_date=end_date,
    )


def build_dataset_export_query(request):
    return {
        "ids": request.query_params.get("ids", "").strip(),
        "project_name": request.query_params.get("project_name", ""),
        "category": request.query_params.get("category", ""),
        "start_date": request.query_params.get("start_date", ""),
        "end_date": request.query_params.get("end_date", ""),
    }


def build_dataset_export_response(**query):
    return get_comments_for_export(**query)
