# -*- coding: utf-8 -*-
"""
热搜新闻模块：从多个热搜平台获取今日热点 Top N。

数据源优先级：今日头条 → 微博热搜 → 百度热搜
"""
import sys
import requests
from datetime import datetime, timezone, timedelta
from urllib.parse import urlparse

BEIJING_TZ = timezone(timedelta(hours=8))

TOUTIAO_HOT_URL = "https://www.toutiao.com/hot-event/hot-board/?origin=toutiao_pc"
WEIBO_HOT_URL = "https://weibo.com/ajax/side/hotSearch"
BAIDU_HOT_URL = "https://top.baidu.com/api/board?platform=wise&tab=realtime"

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"


def _log(msg):
    print(msg, file=sys.stderr, flush=True)


def _clean_url(url):
    if not url:
        return url
    try:
        parsed = urlparse(url)
        if "toutiao.com" in parsed.netloc and "/trending/" in parsed.path:
            return f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
        return url
    except Exception:
        return url


def fetch_hot_news(top_n=10):
    """获取今日热搜 Top N，依次尝试头条→微博→百度"""
    result = _fetch_toutiao(top_n)
    if result:
        return result
    _log("[HotNews] 头条失败，尝试微博")
    result = _fetch_weibo(top_n)
    if result:
        return result
    _log("[HotNews] 微博失败，尝试百度")
    result = _fetch_baidu(top_n)
    if result:
        return result
    _log("[HotNews] 所有热搜源均失败")
    return []


def fetch_hot_news_multi(top_n=5):
    """
    从头条+微博各取 top_n 条，合并去重，标注来源。
    供晨报/日报使用，内容更多元。
    """
    results = []
    for source_name, fetch_fn in [("头条", _fetch_toutiao), ("微博", _fetch_weibo)]:
        try:
            items = fetch_fn(top_n)
            for item in items:
                item["source"] = source_name
            results.extend(items)
        except Exception as e:
            _log(f"[HotNews] {source_name} 获取失败: {e}")

    # 去重（取标题前10字作为key）
    seen, deduped = set(), []
    for item in results:
        key = item["title"][:10]
        if key not in seen:
            seen.add(key)
            deduped.append(item)

    for i, item in enumerate(deduped):
        item["rank"] = i + 1

    return deduped


def _fetch_toutiao(top_n):
    try:
        resp = requests.get(TOUTIAO_HOT_URL, headers={"User-Agent": USER_AGENT}, timeout=10)
        if resp.status_code != 200:
            return []
        data = resp.json()
        items = data.get("data", [])
        if not items:
            return []
        result = []
        for i, item in enumerate(items[:top_n]):
            result.append({
                "rank": i + 1,
                "title": item.get("Title", ""),
                "hot_value": item.get("HotValue", 0),
                "url": _clean_url(item.get("Url", "")),
                "source": "头条",
            })
        _log(f"[HotNews] 头条热搜获取成功: {len(result)} 条")
        return result
    except Exception as e:
        _log(f"[HotNews] 头条热搜异常: {e}")
        return []


def _fetch_weibo(top_n):
    try:
        resp = requests.get(
            WEIBO_HOT_URL,
            headers={"User-Agent": USER_AGENT, "Referer": "https://weibo.com/"},
            timeout=10
        )
        if resp.status_code != 200:
            return []
        data = resp.json()
        realtime = data.get("data", {}).get("realtime", [])
        if not realtime:
            return []
        result, rank = [], 1
        for item in realtime:
            if item.get("is_ad"):
                continue
            title = item.get("note") or item.get("word", "")
            if not title:
                continue
            result.append({
                "rank": rank,
                "title": title,
                "hot_value": item.get("num", 0),
                "url": f"https://s.weibo.com/weibo?q=%23{title}%23",
                "source": "微博",
            })
            rank += 1
            if rank > top_n:
                break
        _log(f"[HotNews] 微博热搜获取成功: {len(result)} 条")
        return result
    except Exception as e:
        _log(f"[HotNews] 微博热搜异常: {e}")
        return []


def _fetch_baidu(top_n):
    try:
        resp = requests.get(BAIDU_HOT_URL, headers={"User-Agent": USER_AGENT}, timeout=10)
        if resp.status_code != 200:
            return []
        data = resp.json()
        cards = data.get("data", {}).get("cards", [])
        if not cards:
            return []
        items = cards[0].get("content", [])
        result = []
        for i, item in enumerate(items[:top_n]):
            result.append({
                "rank": i + 1,
                "title": item.get("word", "") or item.get("query", ""),
                "hot_value": item.get("hotScore", 0),
                "url": _clean_url(item.get("url", "")),
                "source": "百度",
            })
        _log(f"[HotNews] 百度热搜获取成功: {len(result)} 条")
        return result
    except Exception as e:
        _log(f"[HotNews] 百度热搜异常: {e}")
        return []


def format_hot_news_markdown(items, title="🔥 今日热点"):
    """Markdown 格式（存文件用）"""
    if not items:
        return ""
    now = datetime.now(BEIJING_TZ).strftime("%H:%M")
    lines = [f"## {title}", ""]
    for item in items:
        t = item["title"]
        url = item.get("url", "")
        source = item.get("source", "")
        tag = f"[{source}]" if source else ""
        if url:
            lines.append(f"{item['rank']}. [{t}]({url}) {tag}")
        else:
            lines.append(f"{item['rank']}. {t} {tag}")
    lines.extend(["", f"*{now} 更新*"])
    return "\n".join(lines)


def format_hot_news_reply(items):
    """
    企微推送格式（纯文字，不含 HTML 标签）。
    """
    if not items:
        return "暂时获取不到热搜数据，稍后再试试吧～"

    lines = [f"🔥 今日热点 Top {len(items)}：", ""]
    for item in items:
        rank = item["rank"]
        title = item["title"]
        lines.append(f"{rank}. {title}")

    return "\n".join(lines)
