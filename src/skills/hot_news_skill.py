# -*- coding: utf-8 -*-
"""
Skill: hot.news
获取今日热搜 Top N，直接回复给用户。
"""
import sys


def _log(msg):
    print(msg, file=sys.stderr, flush=True)


def fetch(params, state, ctx):
    """
    获取今日热搜并回复给用户。

    params:
        top_n: int — 可选，返回条数，默认 10，最多 30
    """
    top_n = min(int(params.get("top_n", 10)), 30)
    _log(f"[hot.news] 获取热搜 Top {top_n}")

    try:
        from hot_news import fetch_hot_news, format_hot_news_reply
        items = fetch_hot_news(top_n=top_n)
        reply = format_hot_news_reply(items)
        return {"success": True, "reply": reply}
    except Exception as e:
        _log(f"[hot.news] 获取失败: {e}")
        return {"success": False, "reply": "热搜获取失败，稍后再试试吧～"}


# Skill 热加载注册表
SKILL_REGISTRY = {
    "hot.news": fetch,
}
