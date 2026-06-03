"""Matplotlib/Seaborn 静态图表生成。

生成模型评估用静态图表：模型对比 Macro-F1 柱状图、混淆矩阵热力图、训练损失曲线。
所有函数返回 base64 编码的 PNG 图片字符串，可直接嵌入 API 响应或 HTML。

用法:
    from ml_assets.workspace.evaluation.static_charts import (
        generate_model_comparison_chart,
        generate_confusion_matrix_heatmap,
        generate_training_loss_curve,
    )
"""

import io
import base64
from pathlib import Path

import matplotlib
import numpy as np

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
import seaborn as sns

# ── CJK font setup ──
_CJK_FONT_CANDIDATES = [
    "Microsoft YaHei",
    "SimHei",
    "SimSun",
    "DengXian",
    "Noto Sans SC",
    "WenQuanYi Micro Hei",
    "Noto Sans CJK SC",
    "Source Han Sans SC",
    "Arial Unicode MS",
]
_CJK_FONT_FILES = [
    Path(r"C:\Windows\Fonts\msyh.ttc"),
    Path(r"C:\Windows\Fonts\simhei.ttf"),
    Path(r"C:\Windows\Fonts\simsun.ttc"),
    Path(r"C:\Windows\Fonts\NotoSansSC-VF.ttf"),
    Path("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"),
    Path("/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc"),
    Path("/usr/share/fonts/truetype/wqy/wqy-microhei.ttc"),
]


def _resolve_cjk_font():
    available_fonts = {font.name for font in fm.fontManager.ttflist}
    font_name = next((name for name in _CJK_FONT_CANDIDATES if name in available_fonts), None)
    if font_name:
        return font_name

    for font_file in _CJK_FONT_FILES:
        if not font_file.exists():
            continue
        try:
            fm.fontManager.addfont(str(font_file))
            return fm.FontProperties(fname=str(font_file)).get_name()
        except RuntimeError:
            continue

    return None


_cjk_font = _resolve_cjk_font()


def _apply_cjk_font():
    if _cjk_font:
        plt.rcParams["font.family"] = "sans-serif"
        plt.rcParams["font.sans-serif"] = [_cjk_font, *_CJK_FONT_CANDIDATES, "DejaVu Sans"]
    plt.rcParams["axes.unicode_minus"] = False

_PLOT_STYLE = "seaborn-v0_8-whitegrid"
_CHART_DPI = 120
_CHART_SIZE_DEFAULT = (8, 5)
_CHART_SIZE_HEATMAP = (7, 6)

_COLOR_PALETTE = ["#2563eb", "#16a34a", "#dc2626", "#9333ea", "#ea580c", "#0891b2"]


def _to_base64_png():
    buf = io.BytesIO()
    plt.savefig(buf, format="png", dpi=_CHART_DPI, bbox_inches="tight")
    plt.close()
    buf.seek(0)
    return base64.b64encode(buf.read()).decode("ascii")


def _setup_style():
    try:
        plt.style.use(_PLOT_STYLE)
    except OSError:
        plt.style.use("default")
    _apply_cjk_font()
    sns.set_palette(_COLOR_PALETTE)


def generate_model_comparison_chart(model_results, title="模型 Macro-F1 对比"):
    """生成模型 Macro-F1 横向柱状对比图。

    Args:
        model_results: dict[str, float]，键为模型名称，值为 Macro-F1 分数
        title: str，图表标题

    Returns:
        str: base64 编码的 PNG 图片
    """
    _setup_style()
    names = list(model_results.keys())
    scores = list(model_results.values())

    colors = _COLOR_PALETTE[: len(names)] if len(names) <= len(_COLOR_PALETTE) else _COLOR_PALETTE

    fig, ax = plt.subplots(figsize=_CHART_SIZE_DEFAULT)
    bars = ax.barh(names, scores, color=colors)

    for bar, score in zip(bars, scores):
        ax.text(
            bar.get_width() + 0.005,
            bar.get_y() + bar.get_height() / 2,
            f"{score:.4f}",
            va="center",
            fontsize=10,
        )

    ax.set_xlim(0, min(1.05, max(scores) * 1.15))
    ax.set_xlabel("Macro-F1", fontsize=11)
    ax.set_title(title, fontsize=14, fontweight="bold")
    ax.invert_yaxis()

    # Threshold line at 0.85
    ax.axvline(x=0.85, color="#dc2626", linestyle="--", linewidth=1, alpha=0.7)
    ax.text(0.85, ax.get_ylim()[1] * 0.98, "0.85", color="#dc2626", fontsize=9, ha="right")

    plt.tight_layout()
    return _to_base64_png()


def generate_confusion_matrix_heatmap(
    cm, labels=None, title="混淆矩阵", normalize=False
):
    """生成混淆矩阵热力图。

    Args:
        cm: np.ndarray, 混淆矩阵 (shape: n_classes × n_classes)
        labels: list[str] | None，类别标签
        title: str
        normalize: bool, 是否按行归一化

    Returns:
        str: base64 编码的 PNG 图片
    """
    _setup_style()
    if labels is None:
        labels = ["消极", "中性", "积极"]

    if normalize:
        cm = cm.astype("float") / cm.sum(axis=1, keepdims=True)
        cm = np.nan_to_num(cm)

    fmt = ".2f" if normalize else "d"

    fig, ax = plt.subplots(figsize=_CHART_SIZE_HEATMAP)
    sns.heatmap(
        cm,
        annot=True,
        fmt=fmt,
        cmap="Blues",
        xticklabels=labels,
        yticklabels=labels,
        ax=ax,
        linewidths=0.5,
        linecolor="#e2e8f0",
    )
    ax.set_xlabel("预测标签", fontsize=11)
    ax.set_ylabel("真实标签", fontsize=11)
    ax.set_title(title, fontsize=14, fontweight="bold")

    plt.tight_layout()
    return _to_base64_png()


def generate_sentiment_pie_chart(counts, title="情感分布"):
    """生成情感分布饼图。

    Args:
        counts: dict with keys "positive", "neutral", "negative" → int
        title: str

    Returns:
        str: base64 编码的 PNG 图片
    """
    _setup_style()
    labels = ["积极", "中性", "消极"]
    sizes = [counts.get("positive", 0), counts.get("neutral", 0), counts.get("negative", 0)]
    colors = ["#16a34a", "#2563eb", "#dc2626"]

    if sum(sizes) == 0:
        sizes = [1, 1, 1]

    fig, ax = plt.subplots(figsize=(6, 5))
    wedges, texts, autotexts = ax.pie(
        sizes,
        labels=labels,
        colors=colors,
        autopct="%1.1f%%",
        startangle=90,
        textprops={"fontsize": 11},
    )
    for autotext in autotexts:
        autotext.set_fontsize(10)
    ax.set_title(title, fontsize=14, fontweight="bold")
    plt.tight_layout()
    return _to_base64_png()


def generate_training_loss_curve(
    train_losses, eval_losses=None, title="训练损失曲线"
):
    """生成训练损失曲线。

    Args:
        train_losses: list[float], 每个 epoch 的训练损失
        eval_losses: list[float] | None, 每个 epoch 的验证损失
        title: str

    Returns:
        str: base64 编码的 PNG 图片
    """
    _setup_style()
    epochs = range(1, len(train_losses) + 1)

    fig, ax = plt.subplots(figsize=_CHART_SIZE_DEFAULT)
    ax.plot(epochs, train_losses, marker="o", linewidth=1.5, label="训练损失", color=_COLOR_PALETTE[0])

    if eval_losses and len(eval_losses) == len(train_losses):
        ax.plot(epochs, eval_losses, marker="s", linewidth=1.5, label="验证损失", color=_COLOR_PALETTE[3])

    ax.set_xlabel("Epoch", fontsize=11)
    ax.set_ylabel("Loss", fontsize=11)
    ax.set_title(title, fontsize=14, fontweight="bold")
    ax.legend(loc="upper right")
    ax.grid(True, alpha=0.3)

    plt.tight_layout()
    return _to_base64_png()
