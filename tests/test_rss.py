import hashlib
from hermes.ingestors.rss import fetch_feed

SAMPLE_XML = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>Test Blog</title>
    <link>https://example.com</link>
    <item>
      <title>AI Breakthrough Today</title>
      <link>https://example.com/ai-breakthrough</link>
      <description>Scientists announced a major breakthrough in AI reasoning.</description>
      <pubDate>Wed, 21 May 2026 15:00:00 GMT</pubDate>
      <content:encoded xmlns:content="http://purl.org/rss/1.0/modules/content/">
        <![CDATA[<p>Scientists announced a major breakthrough in AI reasoning.</p><p>The new model achieves 95% accuracy.</p>]]>
      </content:encoded>
    </item>
    <item>
      <title>No Content Item</title>
      <link>https://example.com/no-content</link>
      <description>Just a summary here.</description>
    </item>
  </channel>
</rss>"""


def test_fetch_feed_parses_entries(monkeypatch):
    import feedparser
    original_parse = feedparser.parse

    def mock_parse(url):
        return original_parse(SAMPLE_XML)

    monkeypatch.setattr("feedparser.parse", mock_parse)

    results = fetch_feed("https://example.com/feed.xml", "Test Blog")

    assert len(results) == 2
    assert results[0].title == "AI Breakthrough Today"
    assert results[0].source == "Test Blog"
    assert "Scientists announced" in results[0].content
    assert "95% accuracy" in results[0].content  # full content, not summary

    # Second item falls back to summary
    assert results[1].content == "Just a summary here."

    # ID is sha256 of URL
    expected_id = hashlib.sha256(b"https://example.com/ai-breakthrough").hexdigest()
    assert results[0].id == expected_id
