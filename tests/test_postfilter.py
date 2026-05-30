from unittest.mock import MagicMock
from hermes.pipeline.postfilter import score_items


def test_postfilter_scores_items():
    items = [
        {"id": "1", "title": "AI Safety Paper", "content": "Research on alignment.", "source": "ArXiv"},
        {"id": "2", "title": "Oil Prices", "content": "Crude oil up 5%.", "source": "Reuters"},
    ]

    mock_client = MagicMock()
    scores = ['{"exploit_score": 8}', '{"exploit_score": 4}']
    responses = []
    for s in scores:
        m = MagicMock()
        m.choices = [MagicMock(message=MagicMock(content=s))]
        responses.append(m)
    mock_client.chat.completions.create.side_effect = responses

    result = score_items(items, ["AI", "能源"], mock_client)
    assert len(result) == 2
    assert result[0]["exploit_score"] == 0.8
    assert result[0]["status"] == "scored"
    assert result[1]["exploit_score"] == 0.4


def test_postfilter_handles_parse_error():
    items = [{"id": "1", "title": "Test", "content": "Test content.", "source": "Test"}]
    mock_client = MagicMock()
    m = MagicMock()
    m.choices = [MagicMock(message=MagicMock(content="bad json"))]
    mock_client.chat.completions.create.return_value = m

    result = score_items(items, ["AI"], mock_client)
    assert result[0]["exploit_score"] == 0.0
    assert result[0]["status"] == "scored"


def test_postfilter_normalizes_score():
    items = [{"id": "1", "title": "Test", "content": "Test content.", "source": "Test"}]
    mock_client = MagicMock()
    m = MagicMock()
    m.choices = [MagicMock(message=MagicMock(content='{"exploit_score": 10}'))]
    mock_client.chat.completions.create.return_value = m

    result = score_items(items, ["AI"], mock_client)
    assert result[0]["exploit_score"] == 1.0
