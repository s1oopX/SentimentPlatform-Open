from apps.admin_panel.infra.selectors.datasets import (
    get_comments_for_export,
    get_dataset_results_for_export,
    get_filtered_dataset_results,
)


def build_dataset_list_response(
    *,
    project_name="",
    category="",
    source="",
    keyword="",
    final_sentiment="",
    review_status="",
    analysis_channel="",
    start_date="",
    end_date="",
):
    return get_filtered_dataset_results(
        project_name=project_name,
        category=category,
        source=source,
        keyword=keyword,
        final_sentiment=final_sentiment,
        review_status=review_status,
        analysis_channel=analysis_channel,
        start_date=start_date,
        end_date=end_date,
    )


def build_dataset_export_query(request):
    return {
        "ids": request.query_params.get("ids", "").strip(),
        "project_name": request.query_params.get("project_name", ""),
        "category": request.query_params.get("category", ""),
        "source": request.query_params.get("source", ""),
        "keyword": request.query_params.get("keyword", ""),
        "final_sentiment": request.query_params.get("final_sentiment", ""),
        "review_status": request.query_params.get("review_status", ""),
        "analysis_channel": request.query_params.get("analysis_channel", ""),
        "start_date": request.query_params.get("start_date", ""),
        "end_date": request.query_params.get("end_date", ""),
    }


def build_dataset_export_response(**query):
    return get_dataset_results_for_export(**query)


def build_comment_export_response(**query):
    return get_comments_for_export(
        ids=query.get("ids", ""),
        project_name=query.get("project_name", ""),
        category=query.get("category", ""),
        start_date=query.get("start_date", ""),
        end_date=query.get("end_date", ""),
    )
