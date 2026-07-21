from __future__ import annotations

from collections.abc import Mapping

from bs4 import BeautifulSoup, Tag

_BILINGUAL_CSS = """
.bilingual-text{display:grid;gap:8px}
.bilingual-text>.translation{color:var(--text);line-height:1.7;margin:0}
.bilingual-text details{color:var(--muted);font-size:12px}
.bilingual-text summary{cursor:pointer;color:var(--accent)}
.bilingual-text details p{margin:8px 0 0;line-height:1.6}
.memory-translations{display:grid;gap:12px}
"""


def _translation_block(
    soup: BeautifulSoup,
    *,
    source: str,
    translation: str,
) -> Tag:
    wrapper = soup.new_tag("div", attrs={"class": "bilingual-text"})
    translated = soup.new_tag("p", attrs={"class": "translation", "lang": "ja"})
    translated.string = translation
    wrapper.append(translated)

    details = soup.new_tag("details", attrs={"class": "original-text"})
    summary = soup.new_tag("summary")
    summary.string = "原文"
    details.append(summary)
    original = soup.new_tag("p", attrs={"lang": "en"})
    original.string = source
    details.append(original)
    wrapper.append(details)
    return wrapper


def _split_br_text(paragraph: Tag) -> list[str]:
    items: list[str] = []
    current: list[str] = []
    for child in paragraph.children:
        if isinstance(child, Tag) and child.name == "br":
            text = "".join(current).strip()
            if text:
                items.append(text)
            current = []
        elif isinstance(child, Tag):
            current.append(child.get_text(" ", strip=False))
        else:
            current.append(str(child))
    text = "".join(current).strip()
    if text:
        items.append(text)
    return items


def apply_cached_translations(
    html: str,
    translations: Mapping[str, str],
) -> str:
    """Show Japanese translations first while preserving exact source text."""

    if not translations:
        return html
    soup = BeautifulSoup(html, "html.parser")

    for paragraph in soup.select(".brain-card > p"):
        if "brain-error" in paragraph.get("class", []):
            continue
        source = paragraph.get_text(" ", strip=True)
        translated = translations.get(source)
        if translated and translated != source:
            paragraph.replace_with(
                _translation_block(soup, source=source, translation=translated)
            )

    for card in soup.select(".card"):
        heading = card.find("strong")
        paragraph = card.find("p")
        if heading is None or paragraph is None:
            continue
        heading_text = heading.get_text(" ", strip=True)
        if heading_text in {"記憶", "Memory"}:
            items = _split_br_text(paragraph)
            if not any(item in translations for item in items):
                continue
            container = soup.new_tag("div", attrs={"class": "memory-translations"})
            for source in items:
                translated = translations.get(source)
                if translated and translated != source:
                    container.append(
                        _translation_block(
                            soup,
                            source=source,
                            translation=translated,
                        )
                    )
                else:
                    untranslated = soup.new_tag("p")
                    untranslated.string = source
                    container.append(untranslated)
            paragraph.replace_with(container)
        elif heading_text in {"痕跡（Trace）", "Trace", "Trace / 痕跡"}:
            source = paragraph.get_text(" ", strip=True)
            translated = translations.get(source)
            if translated and translated != source:
                paragraph.replace_with(
                    _translation_block(soup, source=source, translation=translated)
                )

    if soup.select_one("style#report-bilingual-v0") is None:
        style = soup.new_tag("style", id="report-bilingual-v0")
        style.string = _BILINGUAL_CSS
        if soup.head is not None:
            soup.head.append(style)
    return str(soup)
