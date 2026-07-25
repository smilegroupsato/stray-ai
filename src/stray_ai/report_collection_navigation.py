from __future__ import annotations

from pathlib import Path

from bs4 import BeautifulSoup, Tag

_NAV_CSS = """
.report-breadcrumbs{display:flex;gap:8px;align-items:center;flex-wrap:wrap;margin:8px 0 20px;color:var(--muted);font-size:13px}
.report-breadcrumbs a{color:var(--accent);text-decoration:none}
.report-breadcrumbs a:hover,.report-breadcrumbs a:focus-visible{text-decoration:underline}
.report-section-nav{display:flex;gap:9px;align-items:center;flex-wrap:wrap;margin:-6px 0 24px}
.report-section-nav a{color:var(--text);text-decoration:none;background:var(--panel2);border:1px solid var(--line);border-radius:12px;padding:9px 11px}
.report-section-nav a:hover,.report-section-nav a:focus-visible,.report-section-nav a[aria-current="page"]{border-color:var(--accent);color:var(--accent)}
.kicker .report-home-link{color:inherit;text-decoration:none}
.kicker .report-home-link:hover,.kicker .report-home-link:focus-visible{text-decoration:underline}
"""


def _ensure_navigation_style(soup: BeautifulSoup) -> None:
    if soup.select_one("style#report-navigation-v0") is not None:
        return
    style = soup.new_tag("style", id="report-navigation-v0")
    style.string = _NAV_CSS
    if soup.head is not None:
        soup.head.append(style)


def _set_kicker_home(soup: BeautifulSoup, href: str) -> None:
    kicker = soup.select_one(".kicker")
    if kicker is None:
        return
    link = soup.new_tag(
        "a",
        href=href,
        attrs={"class": "report-home-link", "aria-label": "Visit Reportトップへ戻る"},
    )
    link.string = "Stray AI · 訪問レポート v0"
    kicker.clear()
    kicker.append(link)


def _render_section_navigation(
    soup: BeautifulSoup,
    *,
    page_name: str,
    available_pages: frozenset[str],
) -> Tag:
    nav = soup.new_tag(
        "nav",
        attrs={"class": "report-section-nav", "aria-label": "個体レポート"},
    )
    if "visits.html" in available_pages:
        items = [
            ("index.html", "個体ページ"),
            ("visits.html", "訪問一覧"),
        ]
    else:
        items = [("index.html", "訪問一覧")]
    items.extend(
        [
            ("map.html", "観測地図"),
            ("latest.html", "最新レポート"),
            ("rummages.html", "文書漁り"),
        ]
    )
    for href, label in items:
        if href not in available_pages:
            continue
        link = soup.new_tag("a", href=href)
        link.string = label
        if href == page_name:
            link["aria-current"] = "page"
        nav.append(link)
    return nav


def apply_individual_navigation(
    html: str,
    *,
    agent_id: str,
    page_name: str,
    available_pages: frozenset[str] | None = None,
) -> str:
    """Add stable navigation inside one individual's report namespace."""

    soup = BeautifulSoup(html, "html.parser")
    _set_kicker_home(soup, "../../index.html")
    pages = available_pages or frozenset({page_name, "index.html"})

    for selector in (".report-breadcrumbs", ".report-section-nav"):
        existing = soup.select_one(selector)
        if existing is not None:
            existing.decompose()

    nav = soup.new_tag("nav", attrs={"class": "report-breadcrumbs", "aria-label": "パンくず"})
    home = soup.new_tag("a", href="../../index.html")
    home.string = "トップ"
    nav.append(home)
    nav.append(" / ")

    if page_name == "index.html":
        current = soup.new_tag("span")
        current.string = agent_id
        nav.append(current)
    else:
        individual = soup.new_tag("a", href="index.html")
        individual.string = f"{agent_id} 個体ページ"
        nav.append(individual)
        nav.append(" / ")
        current = soup.new_tag("span")
        current.string = {
            "map.html": "観測地図",
            "latest.html": "最新レポート",
            "visits.html": "訪問一覧",
            "rummages.html": "文書漁り",
        }.get(page_name, "訪問記録")
        nav.append(current)

    section_nav = _render_section_navigation(
        soup,
        page_name=page_name,
        available_pages=pages,
    )
    kicker = soup.select_one(".kicker")
    if kicker is not None:
        kicker.insert_after(nav)
        nav.insert_after(section_nav)
    elif soup.main is not None:
        soup.main.insert(0, section_nav)
        soup.main.insert(0, nav)

    _ensure_navigation_style(soup)
    return str(soup)


def apply_navigation_to_individual_directory(output_dir: Path, *, agent_id: str) -> None:
    paths = sorted(output_dir.glob("*.html"))
    available_pages = frozenset(path.name for path in paths)
    for path in paths:
        path.write_text(
            apply_individual_navigation(
                path.read_text(encoding="utf-8"),
                agent_id=agent_id,
                page_name=path.name,
                available_pages=available_pages,
            ),
            encoding="utf-8",
        )


def render_individuals_directory_index(root_collection_html: str) -> str:
    """Create /individuals/index.html from the root collection without bad relative links."""

    soup = BeautifulSoup(root_collection_html, "html.parser")
    for link in soup.find_all("a", href=True):
        href = str(link.get("href"))
        if href.startswith("individuals/"):
            link["href"] = href.removeprefix("individuals/")
        elif href == "world.html":
            link["href"] = "../world.html"

    _set_kicker_home(soup, "../index.html")
    heading = soup.find("h1")
    if heading is not None:
        heading.string = "個体一覧"
    if soup.title is not None:
        soup.title.string = "Stray AI — 個体一覧"

    existing = soup.select_one(".report-breadcrumbs")
    if existing is not None:
        existing.decompose()
    nav = soup.new_tag("nav", attrs={"class": "report-breadcrumbs", "aria-label": "パンくず"})
    home = soup.new_tag("a", href="../index.html")
    home.string = "トップ"
    nav.append(home)
    nav.append(" / ")
    current = soup.new_tag("span")
    current.string = "個体一覧"
    nav.append(current)
    kicker = soup.select_one(".kicker")
    if kicker is not None:
        kicker.insert_after(nav)

    _ensure_navigation_style(soup)
    return str(soup)
