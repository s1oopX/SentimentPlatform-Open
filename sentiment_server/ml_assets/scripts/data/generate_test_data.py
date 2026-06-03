"""Faker 模拟评论测试数据生成。

使用方式:
    python scripts/data/generate_test_data.py --count 500 --output test_data.json
"""

import argparse
import json
import random
from pathlib import Path

from faker import Faker

fake = Faker("zh_CN")

CATEGORIES = [
    "电子产品",
    "服饰鞋包",
    "食品饮料",
    "家居用品",
    "美妆护肤",
    "图书音像",
    "运动户外",
    "母婴用品",
]

_POSITIVE_TEMPLATES = [
    "质量非常好，{noun}很满意，推荐购买。",
    "{noun}很漂亮，做工精致，物流也快。",
    "性价比很高，{noun}超出预期，好评！",
    "已经用了几天了，{noun}效果不错。",
    "包装很好，{noun}是正品，价格也实惠。",
    "第二次购买了，{noun}一如既往地好。",
    "{noun}手感很好，细节处理到位，值得入手。",
    "朋友推荐买的，{noun}确实好用，五星好评。",
]

_NEGATIVE_TEMPLATES = [
    "质量太差了，{noun}用了一次就坏了，不推荐。",
    "{noun}和图片不符，色差严重，很失望。",
    "物流太慢，{noun}包装也破损了，差评。",
    "用了几天就出问题，{noun}质量堪忧。",
    "{noun}性价比低，不值这个价格。",
    "售后很差，{noun}有问题也不处理。",
    "{noun}做工粗糙，边角有毛刺，不满意。",
    "买回来就后悔了，{noun}完全不符合预期。",
]

_NEUTRAL_TEMPLATES = [
    "{noun}中规中矩，没有亮点也没有明显缺点。",
    "用了{time}，{noun}表现一般吧。",
    "{noun}还行，对得起这个价格。",
    "没什么特别的，{noun}跟普通款差不多。",
    "勉强能用，{noun}需要改进的地方还有。",
]

_POSITIVE_NOUNS = ["做工", "材质", "外观", "功能", "效果", "使用体验", "质感"]
_NEGATIVE_NOUNS = ["做工", "材质", "外观", "功能", "效果", "手感", "颜色"]
_NEUTRAL_NOUNS = ["做工", "材质", "外观", "功能", "效果", "整体表现"]
_TIME_WORDS = ["一周", "几天", "半个月", "一个月"]


def generate_review(sentiment):
    if sentiment == "positive":
        template = random.choice(_POSITIVE_TEMPLATES)
        noun = random.choice(_POSITIVE_NOUNS)
    elif sentiment == "negative":
        template = random.choice(_NEGATIVE_TEMPLATES)
        noun = random.choice(_NEGATIVE_NOUNS)
    else:
        template = random.choice(_NEUTRAL_TEMPLATES)
        noun = random.choice(_NEUTRAL_NOUNS)

    text = template.format(noun=noun, time=random.choice(_TIME_WORDS))
    return text


def generate_dataset(count, seed=42):
    random.seed(seed)
    fake.seed_instance(seed)

    records = []
    for i in range(count):
        sentiment = random.choices(
            ["positive", "neutral", "negative"],
            weights=[0.5, 0.2, 0.3],
        )[0]

        label = {"positive": 1, "neutral": 0, "negative": -1}[sentiment]

        records.append(
            {
                "id": i + 1,
                "text": generate_review(sentiment),
                "label": label,
                "category": random.choice(CATEGORIES),
                "date": fake.date_between(start_date="-1y", end_date="today").strftime(
                    "%Y-%m-%d %H:%M:%S"
                ),
            }
        )

    return records


def main():
    parser = argparse.ArgumentParser(description="生成模拟评论测试数据")
    parser.add_argument(
        "--count", type=int, default=500, help="生成数据条数，默认 500"
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("test_data.json"),
        help="输出文件路径，默认 test_data.json",
    )
    parser.add_argument(
        "--seed", type=int, default=42, help="随机种子，默认 42"
    )
    args = parser.parse_args()

    records = generate_dataset(args.count, seed=args.seed)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8") as f:
        json.dump(records, f, ensure_ascii=False, indent=2)

    pos = sum(1 for r in records if r["label"] == 1)
    neu = sum(1 for r in records if r["label"] == 0)
    neg = sum(1 for r in records if r["label"] == -1)
    print(f"生成 {len(records)} 条模拟评论 → {args.output}")
    print(f"  积极: {pos}, 中性: {neu}, 消极: {neg}")


if __name__ == "__main__":
    main()
