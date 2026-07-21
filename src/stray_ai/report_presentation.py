from __future__ import annotations

from bs4 import BeautifulSoup

_HEADINGS = {
    "Walk": "歩いた経路",
    "Visit": "訪問",
    "Brain decisions": "判断",
    "What came home": "持ち帰ったもの",
    "Current state": "現在の状態",
    "Record": "記録",
}
_METRICS = {
    "Places": "訪問地点",
    "Exit": "退出",
    "Trace": "Trace",
    "New memories": "新しい記憶",
    "Model": "モデル",
    "Status": "状態",
    "Visit count": "訪問回数",
    "Fatigue": "疲労",
    "Current location": "現在地",
    "Entrance": "入口",
    "Visit file": "訪問記録ファイル",
}
_EXIT_VALUES = {
    "left_silently": "静かに退出",
    "Left silently": "静かに退出",
    "trace_carried_home": "Traceを持ち帰って退出",
    "Trace carried home": "Traceを持ち帰って退出",
    "brain_failed_safe_exit": "判断を受理できず安全に退出",
    "Left safely · brain rejected": "判断を受理できず安全に退出",
}
_STATE_VALUES = {
    "unborn": "未誕生",
    "awake": "覚醒中",
    "visiting": "訪問中",
    "resting": "休息中",
}
_BRAIN_VALUES = {
    "accepted": "受理",
    "not_invoked": "未実行",
    "rejected": "拒否",
    "failed": "失敗",
    "unknown": "不明",
}

_RESPONSIVE_CSS = """
html,body{min-width:0;overflow-x:hidden}
main{width:100%;max-width:1100px}
header,.grid,.grid>*,.panel,.route,.metrics,.result,.card{min-width:0}
.grid{grid-template-columns:minmax(0,2fr) minmax(260px,1fr)}
.route{max-width:100%;overscroll-behavior-inline:contain}
.node{flex:0 0 170px;min-width:0}
.title,.path,.card p,.metric strong,.status{overflow-wrap:anywhere}
.metric strong{min-width:0;text-align:right}
@media(max-width:1120px){
 main{padding:36px 20px 64px}
 header{flex-direction:column}
 .grid{grid-template-columns:minmax(0,1fr)}
 .wide{grid-column:auto}
 h1{font-size:34px}
}
@media(max-width:680px){
 main{padding:28px 14px 48px}
 .panel{padding:18px;border-radius:16px}
 .route{display:grid;grid-template-columns:minmax(0,1fr);overflow:visible;gap:10px}
 .node{width:100%;flex-basis:auto}
 .arrow{padding:0;text-align:center;line-height:1;transform:rotate(90deg)}
 .brain-head{align-items:flex-start;flex-direction:column;gap:6px}
}
@media(max-width:440px){
 h1{font-size:30px}
 .metric{align-items:flex-start;flex-direction:column;gap:4px}
 .metric strong{text-align:left}
}
"""


def _replace_exact_text(soup: BeautifulSoup, old: str, new: str) -> None:
    for node in soup.find_all(string=lambda value: value and value.strip() == old):
        node.replace_with(new)


def localize_visit_report(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")

    if soup.title is not None:
        title = soup.title.get_text(strip=True)
        if title.startswith("Visit Report —"):
            soup.title.string = title.replace("Visit Report —", "訪問レポート —", 1)

    kicker = soup.select_one(".kicker")
    if kicker is not None:
        link = kicker.find("a")
        target = link if link is not None else kicker
        target.string = "Stray AI · 訪問レポート v0"

    subtitle = soup.select_one(".subtitle")
    if subtitle is not None:
        subtitle.string = subtitle.get_text(" ", strip=True).replace(
            " · backend: ", " · 実行方式: "
        )

    status = soup.select_one("header .status")
    if status is not None:
        value = status.get_text(" ", strip=True)
        status.string = _EXIT_VALUES.get(value, value)

    for heading in soup.select(".panel h2"):
        value = heading.get_text(" ", strip=True)
        if value in _HEADINGS:
            heading.string = _HEADINGS[value]

    for badge in soup.select(".badge"):
        value = badge.get_text(" ", strip=True)
        if value.startswith("STEP "):
            badge.string = value.replace("STEP ", "ステップ ", 1)
        elif value == "LEAVE":
            badge.string = "退出"
        elif value == "TRACE":
            badge.string = "TRACE / 痕跡"

    for heading in soup.select(".brain-head strong"):
        value = heading.get_text(" ", strip=True)
        if value.startswith("Step "):
            heading.string = value.replace("Step ", "ステップ ", 1)

    for brain_status in soup.select(".brain-status"):
        value = brain_status.get_text(" ", strip=True)
        brain_status.string = _BRAIN_VALUES.get(value, value)

    for row in soup.select(".metric"):
        label = row.find("span")
        value = row.find("strong")
        if label is None:
            continue
        raw_label = label.get_text(" ", strip=True)
        if raw_label in _METRICS:
            label.string = _METRICS[raw_label]
        if value is None:
            continue
        raw_value = value.get_text(" ", strip=True)
        if raw_label == "Exit":
            value.string = _EXIT_VALUES.get(raw_value, raw_value)
        elif raw_label == "Trace":
            value.string = {"Yes": "あり", "None": "なし"}.get(raw_value, raw_value)
        elif raw_label == "Status":
            value.string = _STATE_VALUES.get(raw_value, raw_value)

    _replace_exact_text(soup, "Trace", "Trace / 痕跡")
    _replace_exact_text(soup, "Memory", "記憶")
    _replace_exact_text(soup, "No trace carried home.", "持ち帰ったTraceはない。")
    _replace_exact_text(soup, "No new memory was selected.", "新しい記憶は選ばれなかった。")
    _replace_exact_text(soup, "No steps recorded.", "経路記録なし。")
    _replace_exact_text(soup, "No brain decisions recorded.", "判断記録なし。")

    footer = soup.find("footer")
    if footer is not None:
        footer.string = "訪問者のdevbox永続記録からローカル生成。"

    style = soup.new_tag("style")
    style.string = _RESPONSIVE_CSS
    if soup.head is not None:
        soup.head.append(style)

    return str(soup)
