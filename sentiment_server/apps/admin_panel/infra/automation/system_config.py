"""
系统配置简化模块。

原来使用 SystemConfig 数据库表存储配置，现在改为直接读取 Django settings 常量。
保留函数签名以兼容现有调用方。
"""
from django.conf import settings


def get_default_system_config():
    return {
        "site_name": "情感分析平台",
        "default_report_format": "pdf",
        "default_report_type": "weekly",
        "max_batch_records": getattr(settings, "MAX_BATCH_RECORDS", 1000),
        "keyword_top_k": int(getattr(settings, "MODEL_KEYWORD_TOP_K", 5)),
        "operation_log_retention_days": getattr(settings, "OPERATION_LOG_RETENTION_DAYS", 180),
        "dashboard_refresh_interval": 60,
        "report_pdf_title": getattr(settings, "REPORT_PDF_TITLE", "情感分析报告"),
        "report_pdf_subtitle": getattr(settings, "REPORT_PDF_SUBTITLE", "情感分析数据汇总"),
        "report_pdf_show_summary": True,
        "report_pdf_show_keywords": True,
        "report_pdf_show_category_distribution": True,
        "report_pdf_show_confidence_buckets": True,
        "report_pdf_footer_note": "由情感分析平台生成",
        "auto_retrain_enabled": False,
        "auto_retrain_mode": "signal",
        "auto_retrain_threshold": 5000,
    }


def load_system_config():
    return get_default_system_config()


def load_system_config_with_status():
    return get_default_system_config(), "healthy", ""


def get_system_config_value(key, default=None):
    return load_system_config().get(key, default)


def get_max_batch_records():
    return int(getattr(settings, "MAX_BATCH_RECORDS", 1000))


def get_keyword_top_k():
    return int(getattr(settings, "MODEL_KEYWORD_TOP_K", 5))
