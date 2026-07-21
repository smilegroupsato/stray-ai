from __future__ import annotations

from bs4 import BeautifulSoup

from stray_ai.report_world_collection import augment_collection_with_world_link


_BASE_HTML = """<!doctype html>
<html lang="en">
<head><title>Stray AI — Persistent Individuals</title></head>
<body><main>
<div class="kicker">Stray AI · Visit Report v0</div>
<h1>Persistent individuals</h1>
<p class="intro">English intro.</p>
<div class="summary"><span>1 individual</span><span>5 preserved visits</span></div>
<div class="grid">
<article class="individual-card">
<div class="card-head"><div><h2>stray-001</h2><span class="badge">PRIMARY</span></div><span class="status">resting</span></div>
<div class="metrics"><div><span>Visits</span><strong>5</strong></div><div><span>Last visit</span><strong>2026-07-21T13:05:24+09:00</strong></div></div>
<nav><a href="individuals/stray-001/index.html">Visits</a><a href="individuals/stray-001/latest.html">Latest</a><a href="individuals/stray-001/map.html">Observed map</a></nav>
</article>
</div>
<footer>English footer.</footer>
</main></body></html>"""


def test_collection_entry_is_responsive_localized_and_idempotent() -> None:
    first = augment_collection_with_world_link(_BASE_HTML)
    second = augment_collection_with_world_link(first)
    soup = BeautifulSoup(second, "html.parser")

    assert soup.title is not None
    assert soup.title.get_text(strip=True) == "Stray AI — 永続個体"
    assert soup.find("h1").get_text(strip=True) == "永続個体"
    assert soup.select_one('a[href="world.html"]').get_text(strip=True) == "観測された世界地図"
    assert soup.select_one(".individual-card .status").get_text(strip=True) == "休息中"
    assert soup.select_one(".individual-card .badge").get_text(strip=True) == "主個体"
    assert "訪問回数" in second
    assert "最終訪問" in second
    assert "訪問一覧" in second
    assert "最新レポート" in second
    assert "観測地図" in second

    assert "grid-template-columns:minmax(0,1fr)" in second
    assert "html,body{width:100%;max-width:100%;min-width:0;overflow-x:hidden}" in second
    assert "@media(max-width:680px)" in second
    assert len(soup.select('a[href="world.html"]')) == 1
    assert len(soup.select("style#collection-ui-v0")) == 1
