"""Local rule-based comment category inference."""

CATEGORY_RULES = (
    ("批量上传", ("上传", "批量", "excel", "xlsx", "txt", "文件", "模板", "格式")),
    ("报告导出", ("报告", "pdf", "导出", "下载", "汇报")),
    ("模型训练", ("模型", "训练", "识别", "关键词", "准确率", "人工判断")),
    ("界面导航", ("界面", "页面", "侧边栏", "按钮", "布局", "标题", "图标", "路由")),
    ("账户安全", ("登录", "注册", "验证码", "密码", "账号", "账户", "邮箱")),
    ("性能稳定", ("加载", "响应", "速度", "卡顿", "稳定", "报错", "空白页")),
    ("价格成本", ("价格", "成本", "便宜", "贵", "小团队")),
    ("售后服务", ("客服", "售后", "服务", "回复", "投诉")),
    ("物流包装", ("物流", "包装", "收到", "破损")),
    ("权限后台", ("管理员", "后台", "权限", "角色", "用户管理", "分析师")),
    ("数据安全", ("备份", "数据安全", "恢复", "安全")),
    ("功能建议", ("希望", "建议", "支持", "优化", "提醒", "搜索", "引导")),
)

DEFAULT_CATEGORY = "综合体验"


def infer_comment_category(content):
    text = str(content or "").strip().lower()
    if not text:
        return DEFAULT_CATEGORY

    for category, keywords in CATEGORY_RULES:
        if any(keyword.lower() in text for keyword in keywords):
            return category

    return DEFAULT_CATEGORY


__all__ = ["DEFAULT_CATEGORY", "CATEGORY_RULES", "infer_comment_category"]
