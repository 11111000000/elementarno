#!/usr/bin/env python3
"""Генератор синтетических сцен с известной истиной.

Нужен для замкнутого контура качества: мы знаем, что на картинке, поэтому
эталонные улики и правильный ответ задаются, а не выводятся из мнения
эксперта. Без этого бенчмарк измеряет согласие с нами, а не качество.

    python3 tools/make_fixture.py --preset study --out /tmp/study.png
"""

import argparse
import json
import struct
import zlib
from pathlib import Path

W, H = 480, 320


class Canvas:
    def __init__(self, width=W, height=H, background=(214, 199, 176)):
        self.width = width
        self.height = height
        self.px = [[background for _ in range(width)] for _ in range(height)]

    def rect(self, x1, y1, x2, y2, color):
        for y in range(max(0, y1), min(self.height, y2)):
            for x in range(max(0, x1), min(self.width, x2)):
                self.px[y][x] = color

    def outline(self, x1, y1, x2, y2, color, thickness=2):
        self.rect(x1, y1, x2, y1 + thickness, color)
        self.rect(x1, y2 - thickness, x2, y2, color)
        self.rect(x1, y1, x1 + thickness, y2, color)
        self.rect(x2 - thickness, y1, x2, y2, color)

    def ellipse(self, cx, cy, rx, ry, color):
        for y in range(max(0, cy - ry), min(self.height, cy + ry)):
            for x in range(max(0, cx - rx), min(self.width, cx + rx)):
                if ((x - cx) / rx) ** 2 + ((y - cy) / ry) ** 2 <= 1:
                    self.px[y][x] = color

    def png(self):
        raw = b""
        for row in self.px:
            raw += b"\x00" + bytes(v for pixel in row for v in pixel)

        def chunk(tag, data):
            body = struct.pack(">I", len(data)) + tag + data
            return body + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)

        data = b"\x89PNG\r\n\x1a\n"
        data += chunk(b"IHDR", struct.pack(">IIBBBBB", self.width, self.height, 8, 2, 0, 0, 0))
        data += chunk(b"IDAT", zlib.compress(raw, 9))
        data += chunk(b"IEND", b"")
        return data


PRESETS = {}


def preset(name):
    def wrap(fn):
        PRESETS[name] = fn
        return fn
    return wrap


@preset("study")
def study():
    """Кабинет: на столе ваза, рядом пустой пылевой контур, на полу грязный след."""
    canvas = Canvas()
    canvas.rect(0, 240, W, H, (168, 142, 112))
    canvas.rect(50, 150, 400, 260, (92, 62, 40))
    canvas.rect(50, 150, 400, 156, (120, 86, 56))
    canvas.rect(120, 95, 165, 150, (178, 46, 44))
    canvas.rect(132, 78, 153, 95, (178, 46, 44))
    canvas.rect(220, 118, 255, 150, (232, 228, 216))
    canvas.outline(255, 185, 305, 230, (238, 228, 206), thickness=5)
    canvas.ellipse(60, 285, 12, 20, (86, 66, 46))
    canvas.ellipse(95, 285, 12, 20, (86, 66, 46))
    canvas.ellipse(130, 285, 12, 20, (86, 66, 46))
    return canvas


@preset("empty")
def empty():
    """Пустая комната: проверка на отказ от вывода."""
    canvas = Canvas()
    canvas.rect(0, 250, W, H, (168, 142, 112))
    return canvas


@preset("water")
def water():
    """Комната после залива: линия воды, плесень, лужа."""
    canvas = Canvas()
    canvas.rect(0, 200, W, H, (120, 116, 108))
    canvas.rect(0, 195, W, 203, (86, 82, 76))
    canvas.ellipse(300, 260, 70, 26, (72, 84, 96))
    canvas.rect(60, 60, 150, 130, (78, 92, 74))
    return canvas


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--preset", default="study", choices=sorted(PRESETS))
    parser.add_argument("--out", required=True)
    parser.add_argument("--ground-truth", help="куда записать эталонные сведения о сцене")
    args = parser.parse_args()

    canvas = PRESETS[args.preset]()
    Path(args.out).write_bytes(canvas.png())
    truth = {
        "preset": args.preset,
        "expected_regions": {
            "study": ["dust_outline", "mud_footprint"],
            "empty": [],
            "water": ["water_line", "mold_patch", "puddle"],
        }[args.preset],
        "expected_objects": {
            "study": ["vase", "mug"],
            "empty": [],
            "water": [],
        }[args.preset],
    }
    if args.ground_truth:
        Path(args.ground_truth).write_text(json.dumps(truth, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"{args.out}: {args.preset}")


if __name__ == "__main__":
    main()
