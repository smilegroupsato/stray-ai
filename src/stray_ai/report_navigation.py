from __future__ import annotations

from bs4 import BeautifulSoup, Tag


def add_archive_link(html: str) -> str:
    """Make the Visit Report kicker a relative link back to index.html."""

    soup = BeautifulSoup(html, "html.parser")
    kicker = soup.select_one(".kicker")
    if kicker is None:
        return html

    existing = kicker.select_one('a[href="index.html"]')
    if existing is not None:
        return str(soup)

    label = kicker.get_text(" ", strip=True) or "Stray AI · Visit Report v0"
    link: Tag = soup.new_tag(
        "a",
        href="index.html",
        attrs={
            "class": "archive-link",
            "aria-label": "Back to visit index",
        },
    )
    link.string = label
    kicker.clear()
    kicker.append(link)

    style = soup.new_tag("style")
    style.string = (
        ".archive-link{color:inherit;text-decoration:none}"
        ".archive-link:hover,.archive-link:focus-visible{text-decoration:underline}"
    )
    if soup.head is not None:
        soup.head.append(style)

    return str(soup)
