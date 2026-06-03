REPORT_ENQUEUE_FAILURE_MESSAGE = "后台提交报表任务失败，请稍后重试"
REPORT_ENQUEUE_ERROR_FALLBACK = "报表任务状态异常，请稍后重试"
STALE_PENDING_ENQUEUE_LIMIT_ERROR = "后台提交报告任务失败次数过多"

KNOWN_USER_VISIBLE_ENQUEUE_ERRORS = {
    REPORT_ENQUEUE_FAILURE_MESSAGE,
    REPORT_ENQUEUE_ERROR_FALLBACK,
    STALE_PENDING_ENQUEUE_LIMIT_ERROR,
}


def get_user_visible_enqueue_error(error_message):
    normalized_error = (error_message or "").strip()
    if not normalized_error:
        return ""

    if normalized_error in KNOWN_USER_VISIBLE_ENQUEUE_ERRORS:
        return normalized_error

    return REPORT_ENQUEUE_ERROR_FALLBACK
