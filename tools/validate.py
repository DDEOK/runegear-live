#!/usr/bin/env python3
"""config.json을 올리기 전에 검사한다. 게임의 RemoteConfig.TryParse와 같은 기준이다.

게임은 잘못된 항목 하나만 버리고 나머지를 보이지만, 여기서는 버려질 항목이 하나라도 있으면 실패로 알린다.
main에 올리는 순간 모든 플레이어에게 나가므로, 조용히 빠지는 공지를 올리기 전에 잡기 위해서다.
사용법: python3 tools/validate.py [config.json]
"""
import json
import re
import sys
from datetime import datetime

MAX_BYTES = 65536
MAX_ITEMS = 10
MAX_TITLE = 40
MAX_BODY = 600
ID = re.compile(r"^[a-z0-9._-]{1,40}$")
VERSION = re.compile(r"^\d+\.\d+\.\d+(\+\d+)?$")
HIDE = {"none", "today", "forever"}
OPEN = {"", "shop", "codex", "research", "history", "character", "stage", "settings"}
STORE = ("https://", "market://", "itms-apps://")


def parse_date(text):
    return datetime.fromisoformat(text.replace("Z", "+00:00"))


def version_key(text):
    core = text.split("+")[0]
    return tuple(int(p) for p in core.split("."))


def check(path):
    errors = []
    raw = open(path, "rb").read()
    if len(raw) > MAX_BYTES:
        return [f"파일이 {MAX_BYTES}바이트를 넘는다({len(raw)})"]
    try:
        data = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        return [f"JSON 형식 오류: {error}"]

    if not isinstance(data.get("schema"), int) or data["schema"] < 1:
        errors.append("schema는 1 이상의 정수여야 한다")

    for platform in ("android", "ios"):
        block = data.get(platform)
        if not isinstance(block, dict):
            errors.append(f"{platform} 칸이 없다")
            continue
        for key in ("minVersion", "latestVersion"):
            value = block.get(key, "")
            if not VERSION.match(value):
                errors.append(f"{platform}.{key} 「{value}」는 MAJOR.MINOR.PATCH 형식이 아니다(게임은 이 값을 무시한다)")
        if VERSION.match(block.get("minVersion", "")) and VERSION.match(block.get("latestVersion", "")):
            if version_key(block["minVersion"]) > version_key(block["latestVersion"]):
                errors.append(f"{platform}: minVersion이 latestVersion보다 크다")
        url = block.get("storeUrl", "")
        if url and not url.startswith(STORE):
            errors.append(f"{platform}.storeUrl은 {', '.join(STORE)} 로 시작해야 한다")

    seen = set()
    for kind in ("notices", "events"):
        items = data.get(kind, [])
        if not isinstance(items, list):
            errors.append(f"{kind}는 목록이어야 한다")
            continue
        if len(items) > MAX_ITEMS:
            errors.append(f"{kind}가 {MAX_ITEMS}개를 넘는다(게임은 앞의 {MAX_ITEMS}개만 쓴다)")
        for index, item in enumerate(items):
            where = f"{kind}[{index}]"
            item_id = item.get("id", "")
            if not ID.match(item_id):
                errors.append(f"{where}: id 「{item_id}」는 소문자·숫자·.-_ 1~40자여야 한다")
            elif item_id in seen:
                errors.append(f"{where}: id 「{item_id}」가 이미 쓰였다(공지·이벤트 통틀어 하나)")
            seen.add(item_id)
            title = item.get("title") or {}
            body = item.get("body") or {}
            if not (title.get("ko") or title.get("en")):
                errors.append(f"{where}: 제목이 두 언어 모두 비었다")
            for lang in ("ko", "en"):
                if not title.get(lang):
                    print(f"주의 {where}: title.{lang}이 비어 다른 언어로 보인다")
                if len(title.get(lang, "")) > MAX_TITLE:
                    errors.append(f"{where}: title.{lang}이 {MAX_TITLE}자를 넘는다")
                if len(body.get(lang, "")) > MAX_BODY:
                    errors.append(f"{where}: body.{lang}이 {MAX_BODY}자를 넘는다")
            start = end = None
            for key in ("start", "end"):
                value = item.get(key, "")
                if value:
                    try:
                        parsed = parse_date(value)
                        if parsed.tzinfo is None:
                            errors.append(f"{where}: {key}에 시간대(Z나 +09:00)가 없다")
                        elif key == "start":
                            start = parsed
                        else:
                            end = parsed
                    except ValueError:
                        errors.append(f"{where}: {key} 「{value}」는 ISO 8601 날짜가 아니다")
            if start and end and end <= start:
                errors.append(f"{where}: end가 start보다 늦어야 한다")
            if item.get("hide", "today") not in HIDE:
                errors.append(f"{where}: hide는 {sorted(HIDE)} 중 하나다")
            if item.get("open", "") not in OPEN:
                errors.append(f"{where}: open은 {sorted(OPEN - {''})} 중 하나다")
    return errors


if __name__ == "__main__":
    target = sys.argv[1] if len(sys.argv) > 1 else "config.json"
    problems = check(target)
    for problem in problems:
        print("오류 " + problem)
    print("통과" if not problems else f"실패 {len(problems)}건")
    sys.exit(1 if problems else 0)
