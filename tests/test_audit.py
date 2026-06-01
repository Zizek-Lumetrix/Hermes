import json
from unittest.mock import MagicMock, patch
from hermes.audit import run_audit


def test_audit_no_items(capsys):
    mock_db = MagicMock()
    mock_db._query.return_value = []

    run_audit(mock_db, n=3)
    captured = capsys.readouterr()
    assert "No analyzed items found" in captured.out


def test_audit_with_items(capsys):
    items = [
        {
            "id": "a1",
            "title": "AI Safety Breakthrough",
            "source": "ArXiv",
            "url": "https://arxiv.org/abs/test",
            "content": "Researchers have made significant progress in AI alignment. "
                       "The new technique reduces harmful outputs by 90% while "
                       "maintaining model performance.",
            "analysis": json.dumps({
                "title_cn": "AI安全突破",
                "summary": "研究者在AI对齐方面取得重大进展，新技术减少有害输出90%。",
                "key_points": ["对齐技术突破", "90%有害输出减少"],
                "implications": "从业者应关注新方法的可复现性",
                "confidence": "high",
            }),
            "entities": json.dumps([
                {"name": "AI Alignment", "type": "CONCEPT"},
            ]),
        },
    ]

    mock_db = MagicMock()
    mock_db._query.return_value = items

    # Simulate user input: 5, 4, 3
    with patch("builtins.input", side_effect=["5", "4", "3"]):
        run_audit(mock_db, n=1)

    captured = capsys.readouterr()
    assert "AUDIT REPORT" in captured.out
    assert "Factual accuracy:" in captured.out
    assert "Overall quality:" in captured.out
