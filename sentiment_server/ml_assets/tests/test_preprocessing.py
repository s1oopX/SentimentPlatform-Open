import pytest
from ml_assets.workspace.data.preprocessing import (
    apply_cleaning_rules,
    clean_text,
    filter_stopwords,
    filter_stopwords_en,
    lemmatize_en,
    load_stopwords,
    load_stopwords_en,
    segment_cn,
    segment_en,
)


class TestCleanText:
    def test_removes_urls(self):
        result = clean_text("看看这个链接 https://example.com/page 怎么样")
        assert "https://example.com/page" not in result
        assert "看看这个链接" in result

    def test_removes_emojis(self):
        result = clean_text("很棒的产品确实很好")
        assert "👍" not in result
        assert "很棒的产品确实很好" == result

    def test_removes_special_chars_but_keeps_chinese(self):
        result = clean_text("价格是多少一百美元超值推荐")
        assert "价格是多少一百美元超值推荐" == result

    def test_collapses_whitespace(self):
        result = clean_text("  好东西  值得购买  ")
        assert result == "好东西 值得购买"

    def test_handles_non_string(self):
        assert clean_text(None) == ""
        assert clean_text(123) == ""

    def test_preserves_alphanumeric(self):
        result = clean_text("iPhone15很好用推荐购买")
        assert "iPhone15" in result
        assert "很好用推荐购买" in result


class TestApplyCleaningRules:
    def test_filters_short_texts(self):
        result = apply_cleaning_rules(["ab", "abcde", "12345"], min_length=5)
        assert "abcde" in result

    def test_filters_long_texts(self):
        long_text = "a" * 1001
        result = apply_cleaning_rules([long_text], max_length=1000)
        assert len(result) == 0

    def test_dedup_keeps_first(self):
        result = apply_cleaning_rules(
            ["一样的内容测试", "一样的内容测试", "不同内容测试"]
        )
        assert result.count("一样的内容测试") == 1
        assert "不同内容测试" in result

    def test_filters_nonsense(self):
        result = apply_cleaning_rules(["12345!@#"])
        assert len(result) == 0

    def test_handles_non_string_items(self):
        result = apply_cleaning_rules(
            ["好东西推荐购买", None, "可以试试看推荐", 123],
            min_length=2,
        )
        assert result == ["好东西推荐购买", "可以试试看推荐"]


class TestChineseSegmentation:
    def test_segment_basic(self):
        tokens = segment_cn("今天天气真好")
        assert len(tokens) > 1
        assert "今天天气" in tokens
        assert "真" in tokens
        assert "好" in tokens

    def test_filter_stopwords_default(self):
        tokens = ["的", "了", "天气", "不错"]
        result = filter_stopwords(tokens)
        assert "的" not in result
        assert "了" not in result
        assert "天气" in result

    def test_filter_stopwords_custom(self):
        tokens = ["a", "b", "c"]
        result = filter_stopwords(tokens, stopwords={"a", "c"})
        assert result == ["b"]


class TestLoadStopwords:
    def test_loads_default(self):
        stopwords = load_stopwords()
        assert isinstance(stopwords, set)
        assert len(stopwords) > 100
        assert "的" in stopwords
        assert "了" in stopwords

    def test_raises_on_missing_file(self):
        with pytest.raises(FileNotFoundError):
            load_stopwords("/nonexistent/path.txt")


class TestEnglishNLP:
    def test_segment_en(self):
        tokens = segment_en("This product is great")
        assert len(tokens) >= 4
        assert "product" in tokens
        assert "great" in tokens

    def test_lemmatize_en(self):
        tokens = ["cats", "dogs", "happily"]
        lemmas = lemmatize_en(tokens)
        assert "cats" not in lemmas  # lemma: cat
        assert "dogs" not in lemmas  # lemma: dog

    def test_filter_stopwords_en(self):
        tokens = ["the", "this", "product", "is", "amazing"]
        result = filter_stopwords_en(tokens)
        assert "the" not in result
        assert "is" not in result
        assert "product" in result
        assert "amazing" in result

    def test_load_stopwords_en(self):
        stopwords = load_stopwords_en()
        assert isinstance(stopwords, set)
        assert len(stopwords) > 100
        assert "the" in stopwords
        assert "a" in stopwords
