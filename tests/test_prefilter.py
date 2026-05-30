from unittest.mock import MagicMock
from hermes.pipeline.prefilter import apply_rules, prefilter_items


def test_rules_reject_short_content():
    item = {"content": "short"}
    assert not apply_rules(item, ["AI"])


def test_rules_accept_valid_item():
    item = {
        "title": "Breakthrough in AI Safety",
        "content": "Researchers have made significant progress in AI alignment techniques, "
                   "publishing new results that demonstrate improved safety measures. "
                   "This line is added to make the total content length exceed two hundred characters "
                   "so that the rule-based prefilter accepts this item as valid.",
        "source": "ArXiv",
    }
    assert apply_rules(item, ["AI", "安全"])


def test_rules_reject_no_domain_keyword_overlap():
    item = {
        "title": "Local Sports Update",
        "content": "The local team won the championship game last night in overtime.",
        "source": "Local News",
    }
    assert not apply_rules(item, ["AI", "大模型安全", "中东局势"])


def test_prefilter_rules_only_stage():
    items = [
        {"id": "1", "title": "Short", "content": "x", "source": "Test"},
        {"id": "2", "title": "AI Safety Paper",
         "content": "Detailed research on AI alignment techniques in modern LLMs. "
                    "This article discusses recent breakthroughs in making large language models safer "
                    "and more aligned with human values. The content is now long enough to pass "
                    "the two-hundred-character minimum length requirement for the rule stage.",
         "source": "ArXiv"},
    ]
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.choices = [MagicMock(message=MagicMock(content='{"continue": 1}'))]
    mock_client.chat.completions.create.return_value = mock_response

    result = prefilter_items(items, ["AI"], mock_client)
    assert len(result) == 1
    assert result[0]["id"] == "2"
    assert result[0]["status"] == "prefiltered"


def test_prefilter_llm_rejects_low_relevance():
    items = [
        {"id": "3", "title": "Something about AI but not really",
         "content": "Random content long enough to pass rule filter but not about the domain. "
                    "This text needs to be well over two hundred characters in total length so the "
                    "rule-based stage accepts it and the LLM stage gets a chance to make its call. "
                    "The domain being checked here is geopolitics, which does not match the article.",
         "source": "Blog"},
    ]
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.choices = [MagicMock(message=MagicMock(content='{"continue": 0}'))]
    mock_client.chat.completions.create.return_value = mock_response

    result = prefilter_items(items, ["地缘政治"], mock_client)
    assert len(result) == 0


def test_prefilter_handles_parse_error():
    items = [
        {"id": "4", "title": "Test Article",
         "content": "Long enough content to pass rule filter for testing purposes. "
                    "This text is padded out to exceed two hundred characters in total length so the "
                    "rule-based stage accepts it. The LLM stage will then return malformed JSON that "
                    "should trigger the parse error fallback and reject the item gracefully.",
         "source": "Test"},
    ]
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.choices = [MagicMock(message=MagicMock(content="invalid json {{{"))]
    mock_client.chat.completions.create.return_value = mock_response

    result = prefilter_items(items, ["AI"], mock_client)
    assert len(result) == 0
