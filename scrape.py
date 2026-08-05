#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
OI 竞赛聚合爬虫（方向1 · GitHub Actions 版）
============================================================================
定时抓取 Codeforces / 洛谷 / AtCoder / 牛客 即将开始的比赛，
统一输出 contests.json（含每场比赛题目数组），供前端 fetch 渲染。

稳定性策略（贴合用户资料）：
  - 串行抓取，禁止并发同时请求多个网站
  - 单平台请求间隔 >= 2s
  - 连续失败 3 次暂停该平台本轮
  - 某平台失败不阻塞其他平台
  - 统一时间转 UTC+8 存字符串（前端按本地时间渲染）
  - 失败写入日志，便于监控数据源是否失效

题目列表（决斗预填用）：
  - Codeforces：用官方 API contest.standings 取 problems（稳定，默认开启）
  - 洛谷/AtCoder/牛客：best-effort，失败则 problems=[]，不阻塞

输出格式（contests.json）：
  {
    "updated": "2026-08-04T09:00:00+08:00",
    "contests": [
      {
        "id": "cf-1234",
        "oj": "Codeforces",
        "name": "...",
        "url": "https://codeforces.com/contest/1234",
        "time": "2026-08-10T14:35",      # YYYY-MM-DDTHH:MM (UTC+8)
        "oj_type": "Div. 2",
        "rated": true,
        "reg": false,
        "problems": [
          {"oj":"Codeforces","pid":"1234A","name":"...","url":"...","tags":["dp"]}
        ]
      }, ...
    ]
  }
"""

import json
import os
import re
import sys
import time
import urllib.parse
from datetime import datetime, timedelta, timezone

import requests
from bs4 import BeautifulSoup

CST = timezone(timedelta(hours=8))  # UTC+8
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
HEADERS = {"User-Agent": UA, "Accept-Language": "zh-CN,zh;q=0.9"}

# 连续失败计数：平台 -> 次数（>=3 暂停本轮）
_FAIL = {}

OUT = os.environ.get("OUT_FILE", "contests.json")


def log(msg):
    print(f"[{datetime.now(CST).strftime('%Y-%m-%d %H:%M:%S')}] {msg}", flush=True)


def now_ts():
    return int(time.time())


def fail(platform):
    _FAIL[platform] = _FAIL.get(platform, 0) + 1


def ok_reset(platform):
    _FAIL[platform] = 0


def paused(platform):
    if _FAIL.get(platform, 0) >= 3:
        log(f"[{platform}] 连续失败3次，本轮跳过（下轮重试）")
        return True
    return False


def throttle():
    """单平台请求间隔 >= 2s"""
    time.sleep(2)


def to_local_str(utc_seconds):
    """UNIX 秒 -> UTC+8 的 YYYY-MM-DDTHH:MM"""
    return datetime.fromtimestamp(utc_seconds, CST).strftime("%Y-%m-%dT%H:%M")


def get(url, extra_headers=None, **kw):
    throttle()
    h = dict(HEADERS)
    if extra_headers:
        h.update(extra_headers)
    return requests.get(url, headers=h, timeout=15, **kw)


# ---------------------------------------------------------------------------
# 1) Codeforces（官方 API，最稳）
# ---------------------------------------------------------------------------
def scrape_codeforces():
    if paused("codeforces"):
        return []
    try:
        r = get("https://codeforces.com/api/contest.list?gym=false")
        r.raise_for_status()
        j = r.json()
        if j.get("status") != "OK":
            raise RuntimeError("status " + str(j.get("status")))
        now = now_ts()
        out = []
        for c in j["result"]:
            if c.get("phase") != "BEFORE":
                continue
            cid = c["id"]
            rec = {
                "id": "cf-" + str(cid),
                "oj": "Codeforces",
                "name": c["name"],
                "url": "https://codeforces.com/contest/" + str(cid),
                "time": to_local_str(c["startTimeSeconds"]),
                "oj_type": "Div. " + str(c.get("div", "")).split(".")[-1] if c.get("div") else "CF",
                "rated": c.get("type", "") == "CF",
                "reg": False,
                "problems": []
            }
            # 题目列表（best-effort）
            try:
                sr = get(f"https://codeforces.com/api/contest.standings?contestId={cid}&from=1&count=1")
                sj = sr.json()
                if sj.get("status") == "OK":
                    rec["problems"] = [
                        {
                            "oj": "Codeforces",
                            "pid": f"{cid}{p['index']}",
                            "name": p.get("name", ""),
                            "url": f"https://codeforces.com/contest/{cid}/problem/{p['index']}",
                            "tags": p.get("tags", [])
                        }
                        for p in sj.get("result", {}).get("problems", [])
                    ]
            except Exception as e:
                log(f"[codeforces] 题目抓取失败({cid}): {e}")
            out.append(rec)
        ok_reset("codeforces")
        log(f"[codeforces] 抓取 {len(out)} 场即将开始的比赛")
        return out
    except Exception as e:
        fail("codeforces")
        log(f"[codeforces] 抓取失败: {e}")
        return []


# ---------------------------------------------------------------------------
# 2) 洛谷（无官方 API，解析内嵌 decodeURIComponent JSON）
# ---------------------------------------------------------------------------
def scrape_luogu():
    if paused("luogu"):
        return []
    try:
        r = get("https://www.luogu.com.cn/contest/list",
                extra_headers={"Referer": "https://www.luogu.com.cn/"})
        r.raise_for_status()
        m = re.search(r'JSON\.parse\(decodeURIComponent\("([^"]+)"\)', r.text)
        if not m:
            raise RuntimeError("data not found (likely Cloudflare challenge)")
        data = json.loads(urllib.parse.unquote(m.group(1)))
        now = now_ts() * 1000
        out = []
        for c in data["currentData"]["contests"]["result"]:
            if (c.get("endTime", 0)) * 1000 <= now:
                continue
            cid = c["id"]
            rec = {
                "id": "luogu-" + str(cid),
                "oj": "洛谷",
                "name": c["name"],
                "url": f"https://www.luogu.com.cn/contest/{cid}",
                "time": to_local_str(c["startTime"]),
                "oj_type": str(c.get("type", "")),
                "rated": bool(c.get("rated", False)),
                "reg": False,
                "problems": []
            }
            # 题目列表（best-effort，洛谷风控强，失败即跳过）
            try:
                pr = get(f"https://www.luogu.com.cn/contest/{cid}",
                         extra_headers={"Referer": "https://www.luogu.com.cn/contest/" + str(cid)})
                pm = re.search(r'JSON\.parse\(decodeURIComponent\("([^"]+)"\)', pr.text)
                if pm:
                    pdata = json.loads(urllib.parse.unquote(pm.group(1)))
                    probs = (pdata.get("currentData", {}).get("contest", {}).get("problems") or [])
                    rec["problems"] = [
                        {
                            "oj": "洛谷",
                            "pid": p.get("pid", ""),
                            "name": p.get("title", ""),
                            "url": f"https://www.luogu.com.cn/problem/{p.get('pid', '')}",
                            "tags": []
                        }
                        for p in probs
                    ]
            except Exception as e:
                log(f"[luogu] 题目抓取失败({cid}): {e}")
            out.append(rec)
        ok_reset("luogu")
        log(f"[luogu] 抓取 {len(out)} 场即将开始的比赛")
        return out
    except Exception as e:
        fail("luogu")
        log(f"[luogu] 抓取失败: {e}")
        return []


# ---------------------------------------------------------------------------
# 3) AtCoder（无官方 API，解析 contest-table-upcoming 表格，时间 JST=UTC+9）
# ---------------------------------------------------------------------------
def scrape_atcoder():
    if paused("atcoder"):
        return []
    try:
        r = get("https://atcoder.jp/contests/?lang=en")
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "html.parser")
        table = soup.find("table", id="contest-table-upcoming")
        out = []
        if table:
            for tr in table.find("tbody").find_all("tr"):
                tds = tr.find_all("td")
                if len(tds) < 3:
                    continue
                # 第一格是开始时间(本地JST文本)，第二格是时长，第三格是名称+链接
                a = tds[2].find("a")
                if not a:
                    continue
                name = a.get_text(strip=True)
                href = a.get("href", "")
                cid = href.rstrip("/").split("/")[-1]
                # 时间文本形如 "2026-08-10 14:35:00+09:00"
                tstr = tds[0].get_text(strip=True)
                try:
                    dt = datetime.strptime(tstr, "%Y-%m-%d %H:%M:%S%z")
                    local = dt.astimezone(CST)
                    timestr = local.strftime("%Y-%m-%dT%H:%M")
                except Exception:
                    timestr = ""
                rec = {
                    "id": "atcoder-" + cid,
                    "oj": "AtCoder",
                    "name": name,
                    "url": "https://atcoder.jp" + href,
                    "time": timestr,
                    "oj_type": cid[:3].upper() if cid[:3].isalpha() else "AT",
                    "rated": False,
                    "reg": False,
                    "problems": []
                }
                # 题目列表（best-effort）
                try:
                    tk = get(f"https://atcoder.jp/contests/{cid}/tasks")
                    tsoup = BeautifulSoup(tk.text, "html.parser")
                    ttable = tsoup.find("table", id="tasks-table")
                    probs = []
                    if ttable:
                        for row in ttable.find("tbody").find_all("tr"):
                            ta = row.find("a")
                            if ta:
                                pid = ta.get_text(strip=True)
                                phref = ta.get("href", "")
                                probs.append({
                                    "oj": "AtCoder",
                                    "pid": pid,
                                    "name": pid,
                                    "url": "https://atcoder.jp" + phref,
                                    "tags": []
                                })
                    rec["problems"] = probs
                except Exception as e:
                    log(f"[atcoder] 题目抓取失败({cid}): {e}")
                out.append(rec)
        ok_reset("atcoder")
        log(f"[atcoder] 抓取 {len(out)} 场即将开始的比赛")
        return out
    except Exception as e:
        fail("atcoder")
        log(f"[atcoder] 抓取失败: {e}")
        return []


# ---------------------------------------------------------------------------
# 4) 牛客（无官方 API，内部 XHR json 接口）
# ---------------------------------------------------------------------------
def scrape_nowcoder():
    if paused("nowcoder"):
        return []
    try:
        # 内部接口（抓包可得），带 Referer 否则返回空
        url = "https://ac.nowcoder.com/acm/acm/contest/list?from=0&size=50"
        r = get(url, extra_headers={
            "Referer": "https://ac.nowcoder.com/acm/contest/list",
            "Accept": "application/json"
        })
        r.raise_for_status()
        j = r.json()
        if j.get("code") != 0:
            raise RuntimeError("code " + str(j.get("code")))
        out = []
        now = now_ts() * 1000
        for c in j.get("data", {}).get("data", []):
            start = c.get("startTime", 0)
            if start and start < now:
                continue
            cid = c.get("id")
            rec = {
                "id": "nowcoder-" + str(cid),
                "oj": "牛客",
                "name": c.get("name", ""),
                "url": f"https://ac.nowcoder.com/acm/contest/{cid}",
                "time": to_local_str(start / 1000) if start else "",
                "oj_type": c.get("contestType", "") or "",
                "rated": False,
                "reg": False,
                "problems": []  # 牛客题目需进比赛页解析，best-effort 暂留空
            }
            out.append(rec)
        ok_reset("nowcoder")
        log(f"[nowcoder] 抓取 {len(out)} 场即将开始的比赛")
        return out
    except Exception as e:
        fail("nowcoder")
        log(f"[nowcoder] 抓取失败: {e}")
        return []


# ---------------------------------------------------------------------------
# 主流程
# ---------------------------------------------------------------------------
def main():
    log("=== 开始抓取竞赛 ===")
    all_contests = []
    for fn in (scrape_codeforces, scrape_luogu, scrape_atcoder, scrape_nowcoder):
        try:
            all_contests.extend(fn())
        except Exception as e:
            log(f"[{fn.__name__}] 未捕获异常: {e}")

    # 去重（按 id）
    seen = set()
    uniq = []
    for c in all_contests:
        if c["id"] in seen:
            continue
        seen.add(c["id"])
        uniq.append(c)

    result = {
        "updated": datetime.now(CST).isoformat(),
        "contests": uniq
    }
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    log(f"=== 完成，共 {len(uniq)} 场，写入 {OUT} ===")


if __name__ == "__main__":
    main()
