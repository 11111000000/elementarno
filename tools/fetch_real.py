#!/usr/bin/env python3
"""Скачивание реальных фотографий для бенчмарка.

Источник — Wikimedia Commons. Ссылки и атрибуция берутся из API, поэтому
манифест хранит названия файлов, а не хрупкие ссылки. Каждая картинка
сопровождается лицензией и автором: данные открытые, но атрибуция обязательна.

    python3 tools/fetch_real.py --limit 12
"""

import argparse
import json
import time
import urllib.parse
import urllib.request
from pathlib import Path

API = "https://commons.wikimedia.org/w/api.php"
UA = {"User-Agent": "elementarno-bench/0.1 (research prototype)"}
ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "eval/real/manifest.json"
IMAGES = ROOT / "eval/real/images"


def api(params, tries=4):
    params = dict(params)
    params["format"] = "json"
    for attempt in range(tries):
        try:
            request = urllib.request.Request(
                API + "?" + urllib.parse.urlencode(params), headers=UA)
            with urllib.request.urlopen(request, timeout=60) as response:
                return json.loads(response.read().decode("utf-8"))
        except Exception:
            if attempt == tries - 1:
                raise
            time.sleep(6 * (attempt + 1))


def resolve(title):
    payload = api({
        "action": "query",
        "titles": title,
        "prop": "imageinfo",
        "iiprop": "url|extmetadata|size",
        "iiurlwidth": 1024,
    })
    for page in (payload.get("query", {}).get("pages", {}) or {}).values():
        info = (page.get("imageinfo") or [{}])[0]
        if not info:
            continue
        meta = info.get("extmetadata", {})
        artist = (meta.get("Artist", {}) or {}).get("value", "") or ""
        artist = " ".join(artist.replace("<br>", " ").split())[:120]
        return {
            "title": page.get("title"),
            "thumb_url": info.get("thumburl"),
            "license": (meta.get("LicenseShortName", {}) or {}).get("value", ""),
            "artist": artist,
            "page_url": info.get("descriptionurl", ""),
        }
    raise LookupError(f"нет данных по файлу: {title}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--width", type=int, default=1024)
    args = parser.parse_args()

    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    cases = manifest["cases"][:args.limit] if args.limit else manifest["cases"]
    IMAGES.mkdir(parents=True, exist_ok=True)
    attribution = ["# Атрибуция фотографий", "",
                   f"Источник: {manifest['source']}. Все работы — под указанными лицензиями.",
                   "Атрибуция обязательна при публикации результатов.", ""]

    for case in cases:
        target = IMAGES / f"{case['id']}.jpg"
        try:
            info = resolve(case["commons_title"])
        except Exception as exc:
            print(f"✗ {case['id']}: {exc}")
            continue
        if not target.exists():
            request = urllib.request.Request(info["thumb_url"], headers=UA)
            with urllib.request.urlopen(request, timeout=90) as response:
                target.write_bytes(response.read())
        case["image"] = str(target.relative_to(ROOT))
        case["license_resolved"] = info["license"]
        case["artist"] = info["artist"]
        case["page_url"] = info["page_url"]
        attribution.append(f"- `{case['id']}.jpg` — {info['title']} · {info['license']} · {info['artist'] or 'автор не указан'} · {info['page_url']}")
        print(f"✓ {case['id']}: {info['license']} · {target.stat().st_size // 1024} КБ")
        time.sleep(1.2)

    manifest["cases"] = cases
    MANIFEST.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (ROOT / "eval/real/ATTRIBUTION.md").write_text("\n".join(attribution) + "\n", encoding="utf-8")
    print(f"\nскачано: {len(cases)}; атрибуция: eval/real/ATTRIBUTION.md")


if __name__ == "__main__":
    main()
