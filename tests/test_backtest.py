from unittest.mock import MagicMock
from hermes.pipeline.backtest import backtest_predictions


def test_backtest_structurable_prediction():
    pending = [
        {
            "id": "pred-1",
            "item_id": "item-1",
            "statement": "Company X will release product Y by 2026-01-01",
            "deadline": "2026-01-01",
            "outcome_var": "Product Y release announcement",
        },
    ]
    mock_client = MagicMock()
    m = MagicMock()
    m.choices = [MagicMock(message=MagicMock(
        content='{"result": "correct", "reason": "Product Y was released on schedule per news reports."}'
    ))]
    mock_client.chat.completions.create.return_value = m

    results = backtest_predictions(pending, mock_client)
    assert len(results) == 1
    assert results[0]["id"] == "pred-1"
    assert results[0]["result"] == "correct"


def test_backtest_handles_empty_list():
    results = backtest_predictions([], MagicMock())
    assert results == []


def test_backtest_parse_failure():
    pending = [
        {
            "id": "pred-2",
            "item_id": "item-2",
            "statement": "Test",
            "deadline": "2025-06-01",
            "outcome_var": "Something",
        },
    ]
    mock_client = MagicMock()
    m = MagicMock()
    m.choices = [MagicMock(message=MagicMock(content="invalid json"))]
    mock_client.chat.completions.create.return_value = m

    results = backtest_predictions(pending, mock_client)
    assert results[0]["result"] == "unverifiable"
