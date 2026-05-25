from hermes.pipeline.dedup import compute_simhash, hamming_distance, dedup_items


def test_compute_simhash_returns_hex():
    sig = compute_simhash("hello world this is some test content for hashing")
    assert isinstance(sig, str)
    assert len(sig) == 16  # 64 bits = 16 hex chars


def test_identical_texts_same_simhash():
    a = compute_simhash("The quick brown fox jumps over the lazy dog")
    b = compute_simhash("The quick brown fox jumps over the lazy dog")
    assert a == b


def test_similar_texts_have_small_hamming_distance():
    a = compute_simhash(
        "Breaking news: scientists discover new exoplanet in habitable zone "
        "of nearby star system, NASA confirms. The planet is roughly Earth-sized."
    )
    b = compute_simhash(
        "Breaking news: scientists discover new exoplanet in habitable zone "
        "of nearby star system, NASA confirmed. The planet is approximately Earth-sized."
    )
    assert hamming_distance(a, b) <= 9


def test_different_texts_have_large_hamming_distance():
    a = compute_simhash("AI models achieve new benchmark on reasoning tasks")
    b = compute_simhash(
        "The local weather forecast predicts rain for the next three days "
        "with temperatures dropping below freezing at night"
    )
    assert hamming_distance(a, b) > 3


def test_dedup_items_groups_similar():
    from hermes.ingestors.rss import RawItem

    items = [
        RawItem("1", "Blog A", "AI News", "https://a.com/1",
                "Breaking: GPT-5 released today, with major improvements in reasoning and coding. "
                "The new model outperforms all previous versions.", None),
        RawItem("2", "Blog B", "GPT-5 Launched",
                "https://b.com/1",
                "Breaking: GPT-5 released today. With major improvements in reasoning and coding. "
                "The new model outperforms all previous versions.", None),
        RawItem("3", "Blog C", "Weather Report",
                "https://c.com/1",
                "Tomorrow will be sunny with a high of 75 degrees.", None),
    ]

    result = dedup_items(items, existing_urls=set())

    # Items 1 and 2 should share a cluster_id
    assert result[0].cluster_id == result[1].cluster_id
    # Item 3 should have a different cluster_id
    assert result[2].cluster_id != result[0].cluster_id


def test_dedup_skips_existing_urls():
    from hermes.ingestors.rss import RawItem

    items = [
        RawItem("id1", "Blog A", "T", "https://a.com/1", "Content here", None),
    ]
    result = dedup_items(items, existing_urls={"https://a.com/1"})
    assert len(result) == 0
