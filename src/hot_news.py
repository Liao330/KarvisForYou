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

# 头条热搜 API
TOUTIAO_HOT_URL = "https://www.toutiao.com/hot-event/hot-board/?origin=toutiao_pc"
# 微博热搜 API
WEIBO_HOT_URL = "https://weibo.com/ajax/side/hotSearch"
# 备用：百度热搜
BAIDU_HOT_URL = "https://top.baidu.com/api/board?platform=wise&tab=realtime"

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"


def _log(msg):
    print(msg, file=sys.stderr, flush=True)


def _clean_url(url):
    """清理URL，去除跟踪参数"""
    if not url:
        return url
    try:
        parsed = urlparse(url)
        if "toutiao.com" in parsed.netloc and "/trending/" in parsed.path:
            return f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
        if "toutiao.com" in parsed.netloc and "/article/" in parsed.path:
            return url
        return url
    except Exception:
        return url


def fetch_hot_news(top_n=10):
    """
    获取今日热搜 Top N，合并多个平台去重。

    返回:
        list[dict]: [{"rank": 1, "title": "...", "hot_value": 12345, "source": "头条"}, ...]
    """
    # 优先头条
    result = _fetch_toutiao(top_n)
    if result:
        return result

    # 备用微博
    _log("[HotNews] 头条失败，尝试微博热搜")
    result = _fetch_weibo(top_n)
    if result:
        return result

    # 备用百度
    _log("[HotNews] 微博失败，尝试百度热搜")
    result = _fetch_baidu(top_n)
    if result:
        return result

    _log("[HotNews] 所有热搜源均失败")
    return []


def fetch_hot_news_multi(top_n=5):
    """
    从多个平台各取 top_n 条，合并返回，标注来源。
    供晨报使用，内容更多元。
    """
    results = []
    sources = [
        ("头条", _fetch_toutiao),
        ("微博", _fetch_weibo),
    ]
    for source_name, fetch_fn in sources:
        try:
            items = fetch_fn(top_n)
            for item in items:
                item["source"] = source_name
            results.extend(items)
        except Exception as e:
            _log(f"[HotNews] {source_name} 获取失败: {e}")

    # 去重（标题相似的保留第一个）
    seen = set()
    deduped = []
    for item in results:
        key = item["title"][:10]
        if key not in seen:
            seen.add(key)
            deduped.append(item)

    # 重新编号
    for i, item in enumerate(deduped):
        item["rank"] = i + 1

    return deduped


def _fetch_toutiao(top_n):
    """从今日头条获取热搜"""
    try:
        resp = requests.get(
            TOUTIAO_HOT_URL,
            headers={"User-Agent": USER_AGENT},
            timeout=10
        )
        if resp.status_code != 200:
            _log(f"[HotNews] 头条 API 状态码: {resp.status_code}")
            return []

        data = resp.json()
        items = data.get("data", [])
        if not items:
            _log("[HotNews] 头条 API 返回空数据")
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
    """从微博获取热搜"""
    try:
        resp = requests.get(
            WEIBO_HOT_URL,
            headers={
                "User-Agent": USER_AGENT,
                "Referer": "https://weibo.com/",
            },
            timeout=10
        )
        if resp.status_code != 200:
            _log(f"[HotNews] 微博 API 状态码: {resp.status_code}")
            return []

        data = resp.json()
        realtime = data.get("data", {}).get("realtime", [])
        if not realtime:
            _log("[HotNews] 微博 API 返回空数据")
            return []

        result = []
        rank = 1
        for item in realtime:
            if item.get("is_ad"):  # 跳过广告
                continue
            title = item.get("note") or item.get("word", "")
            if not title:
                continue
            hot_value = item.get("num", 0)
            result.append({
                "rank": rank,
                "title": title,
                "hot_value": hot_value,
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
    """从百度获取热搜"""
    try:
        resp = requests.get(
            BAIDU_HOT_URL,
            headers={"User-Agent": USER_AGENT},
            timeout=10
        )
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
    if not items:
        return ""
    now = datetime.now(BEIJING_TZ).strftime("%H:%M")
    lines = [f"## {title}", ""]
    for item in items:
        rank = item["rank"]
        t = item["title"]
        url = item.get("url", "")
        source = item.get("source", "")
        hot = item.get("hot_value", 0)
        try:
            hot = int(hot)
        except (ValueError, TypeError):
            hot = 0
        if hot >= 10000000:
            hot_str = f"{hot / 10000000:.1f}kw"
        elif hot >= 10000:
            hot_str = f"{hot / 10000:.1f}w"
        else:
            hot_str = str(hot) if hot else ""
        source_tag = f"[{source}]" if source else ""
        if url:
            lines.append(f"{rank}. [**{t}**]({url})  {source_tag} `{hot_str}`")
        else:
            lines.append(f"{rank}. **{t}**  {source_tag}")
    lines.append("")
    lines.append(f"*{now} 更新*")
    return "\n".join(lines)


def format_hot_news_reply(items):
    if not items:
        return "暂时获取不到热搜数据，稍后再试试吧～"
    lines = [f"🔥 今日热点 Top {len(items)}：", ""]
    for item in items:
        rank = item["rank"]
        t = item["title"]
        url = item.get("url", "")
        source = item.get("source", "")
        source_tag = f"[{source}]" if source else ""
        if url:
            lines.append(f'{rank}. <a href="{url}">{t}</a> {source_tag}')
        else:
            lines.append(f"{rank}. {t} {source_tag}")
    lines.append("")
    now = datetime.now(BEIJING_TZ).strftime("%H:%M")
    lines.append(f"📡 {now} 更新")
    return "\n".join(lines)

import sys
import requests
from datetime import datetime, timezone, timedelta
from urllib.parse import urlparse, parse_qs, urlencode

BEIJING_TZ = timezone(timedelta(hours=8))

# 头条热搜 API
TOUTIAO_HOT_URL = "https://www.toutiao.com/hot-event/hot-board/?origin=toutiao_pc"

# 备用：百度热搜（如果头条挂了）
BAIDU_HOT_URL = "https://top.baidu.com/api/board?platform=wise&tab=realtime"

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"


def _log(msg):
    print(msg, file=sys.stderr, flush=True)


def _clean_url(url):
    """清理URL，去除跟踪参数，让链接更简洁"""
    if not url:
        return url
    try:
        parsed = urlparse(url)
        # 头条 trending 链接：只保留基础路径
        if "toutiao.com" in parsed.netloc and "/trending/" in parsed.path:
            return f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
        # 头条 article 链接：已经很干净
        if "toutiao.com" in parsed.netloc and "/article/" in parsed.path:
            return url
        # 百度热搜链接：保持原样（通常是短链）
        return url
    except Exception:
        return url


def fetch_hot_news(top_n=10):
    """
    获取今日热搜 Top N。

    返回:
        list[dict]: [{"rank": 1, "title": "...", "hot_value": 12345}, ...]
        如果获取失败返回空列表。
    """
    # 优先用头条
    result = _fetch_toutiao(top_n)
    if result:
        return result

    # 备用百度
    _log("[HotNews] 头条热搜失败，尝试百度热搜")
    result = _fetch_baidu(top_n)
    if result:
        return result

    _log("[HotNews] 所有热搜源均失败")
    return []


def _fetch_toutiao(top_n):
    """从今日头条获取热搜"""
    try:
        resp = requests.get(
            TOUTIAO_HOT_URL,
            headers={"User-Agent": USER_AGENT},
            timeout=10
        )
        if resp.status_code != 200:
            _log(f"[HotNews] 头条 API 状态码: {resp.status_code}")
            return []

        data = resp.json()
        items = data.get("data", [])
        if not items:
            _log("[HotNews] 头条 API 返回空数据")
            return []

        result = []
        for i, item in enumerate(items[:top_n]):
            result.append({
                "rank": i + 1,
                "title": item.get("Title", ""),
                "hot_value": item.get("HotValue", 0),
                "url": _clean_url(item.get("Url", "")),
            })

        _log(f"[HotNews] 头条热搜获取成功: {len(result)} 条")
        return result

    except Exception as e:
        _log(f"[HotNews] 头条热搜异常: {e}")
        return []


def _fetch_baidu(top_n):
    """从百度获取热搜"""
    try:
        resp = requests.get(
            BAIDU_HOT_URL,
            headers={"User-Agent": USER_AGENT},
            timeout=10
        )
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
            })

        _log(f"[HotNews] 百度热搜获取成功: {len(result)} 条")
        return result

    except Exception as e:
        _log(f"[HotNews] 百度热搜异常: {e}")
        return []


def format_hot_news_markdown(items, title="🔥 今日热点"):
    """
    将热搜列表格式化为 Markdown 文本（含可点击链接）。

    Args:
        items: fetch_hot_news 返回的列表
        title: 标题

    Returns:
        str: Markdown 格式的热点文本
    """
    if not items:
        return ""

    now = datetime.now(BEIJING_TZ).strftime("%H:%M")
    lines = [f"## {title}", ""]
    for item in items:
        rank = item["rank"]
        t = item["title"]
        url = item.get("url", "")
        # 热度转换为更易读的格式
        hot = item.get("hot_value", 0)
        try:
            hot = int(hot)
        except (ValueError, TypeError):
            hot = 0
        if hot >= 10000000:
            hot_str = f"{hot / 10000000:.1f}kw"
        elif hot >= 10000:
            hot_str = f"{hot / 10000:.1f}w"
        else:
            hot_str = str(hot)
        # 有链接时标题可点击跳转
        if url:
            lines.append(f"{rank}. [**{t}**]({url})  `{hot_str}`")
        else:
            lines.append(f"{rank}. **{t}**  `{hot_str}`")

    lines.append("")
    lines.append(f"*数据来源: 今日头条热搜 · {now}*")
    lines.append("")
    return "\n".join(lines)


def format_hot_news_reply(items):
    """
    将热搜列表格式化为企微聊天回复文本（含可点击链接）。
    企微 text 消息支持 <a> 标签，标题直接可点击跳转到详情页。
    """
    if not items:
        return "暂时获取不到热搜数据，稍后再试试吧～"

    lines = ["🔥 今日热点 Top {}：".format(len(items)), ""]
    for item in items:
        rank = item["rank"]
        t = item["title"]
        url = item.get("url", "")
        if url:
            # 企微 text 消息支持 <a> 标签，标题可直接点击跳转
            lines.append(f'{rank}. <a href="{url}">{t}</a>')
        else:
            lines.append(f"{rank}. {t}")

    lines.append("")
    now = datetime.now(BEIJING_TZ).strftime("%H:%M")
    lines.append(f"📡 来源：今日头条热搜 · {now}")
    return "\n".join(lines)
