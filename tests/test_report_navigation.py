from __future__ import annotations

from bs4 import BeautifulSoup

from stray_ai.report_navigation import add_archive_link


def test_kicker_links_back_to_relative_archive_index() -> None:
    html = """<!doctype html><html><head></head><body>
    <div class="kicker">Stray AI · Visit Report v0</div>
    </body></html>"""

    rendered = add_archive_link(html)
    soup = BeautifulSoup(rendered, "html.parser")
    link = soup.select_one('.kicker a[href="index.html"]')

    assert link is not None
    assert link.get_text(" ", strip=True) == "Stray AI · Visit Report v0"
    assert link.get("target") is None
    assert link.get("aria-label") == "Back to visit index"


def test_archive_link_augmentation_is_idempotent() -> None:
    html = """<!doctype html><html><head></head><body>
    <div class="kicker">Stray AI · Visit Report v0</div>
    </body></html>"""

    rendered = add_archive_link(add_archive_link(html))
    soup = BeautifulSoup(rendered, "html.parser")

    assert len(soup.select('.kicker a[href="index.html"]')) == 1
