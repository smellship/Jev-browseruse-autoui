"""原始快照 → State（事实层）：元素索引化、文本裁剪、历史动作、点击失败记录。"""

from __future__ import annotations

from ui_agent.schema.state import Element, PageInfo, RecentAction, State


def build_state(
    raw: dict,
    recent_actions: list[RecentAction],
    click_failures: dict[str, str] | None = None,
    max_elements: int = 250,
    max_text: int = 6000,
) -> State:
    page = raw.get("page", {})
    elements = [Element(**item) for item in raw.get("elements", [])[:max_elements]]
    return State(
        page=PageInfo(
            url=page.get("url", ""),
            title=page.get("title", ""),
            text=(page.get("text") or "")[:max_text],
            viewport=page.get("viewport", {}),
            scroll=page.get("scroll", {}),
        ),
        elements=elements,
        recent_actions=recent_actions,
        fingerprint=raw.get("fingerprint", ""),
        omitted=raw.get("omitted", 0),
        click_failures=click_failures or {},
    )
