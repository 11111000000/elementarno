#!/usr/bin/env python3
"""Генератор синтетических пар «до/после» для проверки правил отсутствия.

Пара — это три сцены одной комнаты:

  «до»    — кадр, на котором отрицательная улика видна (правило должно сработать);
  «после» — тот же кадр после того, как предмет убрали и след перестал читаться
             (правило не должно сработать);
  «чистая» — контроль: та же комната, где такого предмета никогда не было
             (правило не должно сработать).

Синтетика не заменяет настоящую съёмку. Она проверяет одно: движок реагирует
на наличие аннотации следа и не дорисовывает отсутствие там, где следа нет.
Метрика ложных срабатываний на таких парах измеряет работу движка, а не мир.

    python3 tools/make_pairs.py
    python3 tools/make_pairs.py --only syn-dust-outline-shelf
"""

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from make_fixture import Canvas  # noqa: E402

PAIRS_DIR = ROOT / "eval" / "pairs"
SYNTHETIC_DIR = PAIRS_DIR / "synthetic"
MANIFEST_PATH = PAIRS_DIR / "manifest.json"

MANIFEST_NOTE = (
    "СЕЙЧАС ВСЕ ПАРЫ СИНТЕТИЧЕСКИЕ. Сцены нарисованы генератором tools/make_pairs.py, "
    "фотографий нет. Метрика ложных срабатываний на синтетике измеряет работу движка "
    "(срабатывает ли правило там, где в сцене стоит аннотация следа), а не мир: "
    "настоящий пылевой контур, пустой крючок и невыцветший участок на фотографиях "
    "выглядят иначе, чем в нарисованной сцене. Настоящие пары добавляются в этот же "
    "формат с \"real\": true, \"synthetic\": false; методика съёмки — docs/CAPTURE-PROTOCOL.md."
)

W, H = 480, 320


def surface(sid, name, material, dust=False, dust_state="none"):
    return {
        "id": sid,
        "name": name,
        "material": material,
        "dust_present": dust,
        "dust_state": dust_state,
    }


def obj(oid, category, material, on, **extra):
    item = {"id": oid, "category": category, "material": material, "on": on, "state": "clean"}
    item.update(extra)
    return item


def region(rid, kind, **extra):
    item = {"id": rid, "kind": kind}
    item.update(extra)
    return item


def scene(image_id, surfaces, objects, regions, notes=""):
    return {
        "meta": {
            "image_id": image_id,
            "source": "synthetic",
            "geometry": "relative",
            "notes": notes,
        },
        "surfaces": surfaces,
        "objects": objects,
        "regions": regions,
        "observations": [],
        "light": [],
    }


def draw_shelf(canvas, x1, x2, y):
    canvas.rect(0, 250, W, H, (168, 142, 112))
    canvas.rect(x1, y, x2, y + 26, (150, 110, 72))
    canvas.rect(x1, y + 26, x2, 250, (92, 62, 40))


def draw_stain(canvas, x, y):
    canvas.ellipse(x, y, 20, 7, (126, 92, 58))


def pair_dust_outline_shelf():
    def draw(canvas, frame):
        draw_shelf(canvas, 40, 420, 150)
        if frame == "before":
            canvas.outline(146, 144, 204, 164, (238, 228, 206), thickness=4)
            canvas.rect(152, 100, 198, 150, (178, 46, 44))
            canvas.rect(164, 84, 186, 100, (178, 46, 44))
        if frame == "clean":
            draw_stain(canvas, 320, 165)

    return {
        "id": "syn-dust-outline-shelf",
        "truth": (
            "С полки сняли керамическую вазу. В кадре «до» у её основания видна граница "
            "пыли — пылевой контур; в кадре «после» вазы нет и граница не читается."
        ),
        "expect": {"finding_ids": ["F-ABS-001"], "trace_frame": "before"},
        "before": scene(
            "syn-dust-outline-shelf/before",
            [surface("s1", "shelf", "wood", dust=True, dust_state="even")],
            [obj("o1", "vase", "ceramic", "s1", size_m=0.24)],
            [region("r1", "dust_outline", shape="round", area_m2=0.03, contrast=0.15,
                    freshness="sharp", edges="concave", bbox=[0.44, 0.56, 0.62, 0.74],
                    note="граница пыли у основания вазы")],
            notes="предмет на месте, отрицательная улика читается",
        ),
        "after": scene(
            "syn-dust-outline-shelf/after",
            [surface("s1", "shelf", "wood", dust=True, dust_state="even")],
            [],
            [],
            notes="предмет убран, след не читается",
        ),
        "clean": scene(
            "syn-dust-outline-shelf/clean",
            [surface("s9", "shelf_left", "wood", dust=True, dust_state="even")],
            [],
            [region("r9", "stain", shape="round", area_m2=0.004, contrast=0.1,
                    freshness="soft", edges="ragged", bbox=[0.6, 0.48, 0.72, 0.56],
                    note="старое пятно, не связанное с уборкой")],
            notes="контроль: здесь предмета никогда не было",
        ),
        "draw": draw,
    }


def pair_dust_outline_table():
    def draw(canvas, frame):
        canvas.rect(0, 235, W, H, (168, 142, 112))
        canvas.rect(30, 175, 450, 205, (146, 104, 66))
        canvas.rect(30, 205, 450, 235, (84, 56, 36))
        if frame == "before":
            canvas.outline(196, 168, 300, 190, (236, 226, 204), thickness=4)
            canvas.rect(204, 128, 292, 176, (120, 122, 126))
            canvas.rect(214, 118, 282, 130, (96, 98, 102))
        if frame == "clean":
            canvas.rect(330, 182, 392, 188, (120, 88, 56))

    return {
        "id": "syn-dust-outline-table",
        "truth": (
            "С рабочего стола убрали жестяную коробку. В кадре «до» виден прямоугольный "
            "пылевой контур на месте коробки; в кадре «после» след не читается."
        ),
        "expect": {"finding_ids": ["F-ABS-001"], "trace_frame": "before"},
        "before": scene(
            "syn-dust-outline-table/before",
            [surface("s1", "table", "wood", dust=True, dust_state="uneven")],
            [obj("o1", "tin", "metal", "s1", size_m=0.32),
             obj("o2", "bowl", "ceramic", "s1", size_m=0.16)],
            [region("r1", "dust_outline", shape="rectangular", area_m2=0.05, contrast=0.12,
                    freshness="sharp", edges="concave", bbox=[0.58, 0.5, 0.78, 0.68],
                    note="прямоугольная граница пыли на месте коробки")],
            notes="предмет на месте, отрицательная улика читается",
        ),
        "after": scene(
            "syn-dust-outline-table/after",
            [surface("s1", "table", "wood", dust=True, dust_state="uneven")],
            [],
            [],
            notes="предмет убран, след не читается",
        ),
        "clean": scene(
            "syn-dust-outline-table/clean",
            [surface("s9", "table_far", "wood", dust=True, dust_state="uneven")],
            [],
            [region("r9", "scratch", shape="linear", area_m2=0.002, contrast=0.2,
                    freshness="soft", edges="ragged", bbox=[0.2, 0.55, 0.4, 0.6],
                    note="старая царапина, не связанная с уборкой")],
            notes="контроль: здесь предмета никогда не было",
        ),
        "draw": draw,
    }


def pair_unfaded_patch_sill():
    def draw(canvas, frame):
        canvas.rect(0, 210, W, H, (168, 142, 112))
        canvas.rect(60, 160, 420, 186, (156, 116, 76))
        canvas.rect(60, 186, 420, 210, (88, 60, 38))
        if frame == "before":
            canvas.ellipse(240, 172, 62, 15, (232, 226, 208))
            canvas.rect(206, 118, 274, 166, (176, 84, 56))
            canvas.rect(216, 106, 264, 118, (150, 70, 46))
        if frame == "clean":
            canvas.ellipse(340, 176, 26, 8, (122, 88, 56))

    return {
        "id": "syn-unfaded-patch-sill",
        "truth": (
            "С подоконника убрали глиняный горшок. В кадре «до» вокруг основания виден "
            "невыцветший участок без пыли; в кадре «после» участок засыпан пылью."
        ),
        "expect": {"finding_ids": ["F-ABS-002"], "trace_frame": "before"},
        "before": scene(
            "syn-unfaded-patch-sill/before",
            [surface("s1", "sill", "wood", dust=True, dust_state="patchy")],
            [obj("o1", "pot", "ceramic", "s1", size_m=0.18)],
            [region("r1", "unfaded_patch", shape="round", area_m2=0.02, contrast=0.22,
                    freshness="sharp", edges="flat", bbox=[0.35, 0.48, 0.65, 0.62],
                    note="участок без пыли вокруг основания горшка")],
            notes="предмет на месте, отрицательная улика читается",
        ),
        "after": scene(
            "syn-unfaded-patch-sill/after",
            [surface("s1", "sill", "wood", dust=True, dust_state="patchy")],
            [],
            [],
            notes="предмет убран, след не читается",
        ),
        "clean": scene(
            "syn-unfaded-patch-sill/clean",
            [surface("s9", "sill_other", "wood", dust=True, dust_state="patchy")],
            [],
            [region("r9", "crack", shape="linear", area_m2=0.001, contrast=0.25,
                    freshness="soft", edges="ragged", bbox=[0.15, 0.52, 0.3, 0.56],
                    note="старая трещина, не связанная с уборкой")],
            notes="контроль: здесь предмета никогда не было",
        ),
        "draw": draw,
    }


def pair_unfaded_patch_shelf():
    def draw(canvas, frame):
        canvas.rect(0, 245, W, H, (168, 142, 112))
        canvas.rect(50, 140, 430, 166, (150, 110, 72))
        canvas.rect(50, 166, 430, 245, (92, 62, 40))
        if frame == "before":
            canvas.ellipse(300, 156, 52, 12, (230, 224, 206))
            canvas.rect(258, 96, 342, 150, (176, 142, 96))
            canvas.rect(258, 96, 342, 104, (150, 118, 78))
        if frame == "clean":
            canvas.ellipse(140, 152, 18, 6, (124, 90, 58))

    return {
        "id": "syn-unfaded-patch-shelf",
        "truth": (
            "С полки убрали картонную коробку. В кадре «до» под ней виден невыцветший "
            "участок без пыли; в кадре «после» участок выцвел."
        ),
        "expect": {"finding_ids": ["F-ABS-002"], "trace_frame": "before"},
        "before": scene(
            "syn-unfaded-patch-shelf/before",
            [surface("s1", "shelf", "wood", dust=True, dust_state="even")],
            [obj("o1", "box", "cardboard", "s1", size_m=0.28)],
            [region("r1", "unfaded_patch", shape="rectangular", area_m2=0.07, contrast=0.18,
                    freshness="sharp", edges="flat", bbox=[0.52, 0.42, 0.78, 0.56],
                    note="прямоугольный участок без пыли на месте коробки")],
            notes="предмет на месте, отрицательная улика читается",
        ),
        "after": scene(
            "syn-unfaded-patch-shelf/after",
            [surface("s1", "shelf", "wood", dust=True, dust_state="even")],
            [],
            [],
            notes="предмет убран, след не читается",
        ),
        "clean": scene(
            "syn-unfaded-patch-shelf/clean",
            [surface("s9", "shelf_right", "wood", dust=True, dust_state="even")],
            [],
            [region("r9", "dent", shape="round", area_m2=0.003, contrast=0.16,
                    freshness="soft", edges="convex", bbox=[0.22, 0.46, 0.34, 0.56],
                    note="старая вмятина, не связанная с уборкой")],
            notes="контроль: здесь предмета никогда не было",
        ),
        "draw": draw,
    }


def pair_empty_hook_door():
    def draw(canvas, frame):
        canvas.rect(0, 0, W, H, (206, 198, 184))
        canvas.rect(0, 250, W, H, (150, 140, 128))
        if frame == "before":
            canvas.ellipse(240, 150, 26, 20, (182, 172, 156))
            canvas.rect(236, 116, 244, 166, (118, 118, 122))
            canvas.ellipse(240, 112, 10, 10, (118, 118, 122))
        if frame == "clean":
            canvas.rect(330, 190, 372, 196, (186, 178, 166))

    return {
        "id": "syn-empty-hook-door",
        "truth": (
            "С дверного крючка сняли связку ключей. В кадре «до» крючок пуст, но след "
            "крепления виден; в кадре «после» след затерт."
        ),
        "expect": {"finding_ids": ["F-ABS-003"], "trace_frame": "before"},
        "before": scene(
            "syn-empty-hook-door/before",
            [surface("s1", "door", "metal")],
            [],
            [region("r1", "empty_hook", shape="round", area_m2=0.004, contrast=0.19,
                    freshness="sharp", edges="flat", bbox=[0.44, 0.42, 0.56, 0.56],
                    note="пустой крючок, вокруг него видно след крепления")],
            notes="предмет уже снят, след крепления читается",
        ),
        "after": scene(
            "syn-empty-hook-door/after",
            [surface("s1", "door", "metal")],
            [],
            [],
            notes="след затерт, читать нечего",
        ),
        "clean": scene(
            "syn-empty-hook-door/clean",
            [surface("s9", "cabinet_door", "metal")],
            [],
            [region("r9", "scratch", shape="linear", area_m2=0.002, contrast=0.2,
                    freshness="soft", edges="ragged", bbox=[0.62, 0.58, 0.8, 0.62],
                    note="старая царапина, не связанная с уборкой")],
            notes="контроль: здесь крючка никогда не было",
        ),
        "draw": draw,
    }


def pair_two_traces_corner():
    def draw(canvas, frame):
        canvas.rect(0, 0, W, 210, (206, 198, 184))
        canvas.rect(0, 210, W, 250, (150, 110, 72))
        canvas.rect(0, 250, W, H, (168, 142, 112))
        if frame == "before":
            canvas.outline(96, 204, 154, 224, (238, 228, 206), thickness=4)
            canvas.rect(102, 160, 148, 210, (178, 46, 44))
            canvas.ellipse(330, 130, 24, 18, (182, 172, 156))
            canvas.rect(326, 100, 334, 146, (118, 118, 122))
            canvas.ellipse(330, 96, 9, 9, (118, 118, 122))
        if frame == "clean":
            canvas.rect(240, 224, 300, 230, (120, 88, 56))

    return {
        "id": "syn-two-traces-corner",
        "truth": (
            "Из угла убрали вазу с полки и сняли ключи с крючка. В кадре «до» видны и "
            "пылевой контур, и след крепления; в кадре «после» ни того, ни другого."
        ),
        "expect": {"finding_ids": ["F-ABS-001", "F-ABS-003"], "trace_frame": "before"},
        "before": scene(
            "syn-two-traces-corner/before",
            [surface("s1", "shelf", "wood", dust=True, dust_state="even"),
             surface("s2", "wall", "concrete")],
            [obj("o1", "vase", "ceramic", "s1", size_m=0.2)],
            [region("r1", "dust_outline", shape="round", area_m2=0.02, contrast=0.13,
                    freshness="sharp", edges="concave", bbox=[0.16, 0.58, 0.34, 0.72],
                    note="граница пыли у основания вазы"),
             region("r2", "empty_hook", shape="round", area_m2=0.003, contrast=0.17,
                    freshness="sharp", edges="flat", bbox=[0.58, 0.22, 0.72, 0.36],
                    note="пустой крючок, вокруг него видно след крепления")],
            notes="предметы на месте, обе отрицательные улики читаются",
        ),
        "after": scene(
            "syn-two-traces-corner/after",
            [surface("s1", "shelf", "wood", dust=True, dust_state="even"),
             surface("s2", "wall", "concrete")],
            [],
            [],
            notes="предметы убраны, следы не читаются",
        ),
        "clean": scene(
            "syn-two-traces-corner/clean",
            [surface("s9", "shelf_far", "wood", dust=True, dust_state="even"),
             surface("s8", "wall_far", "concrete")],
            [],
            [region("r9", "stain", shape="round", area_m2=0.004, contrast=0.1,
                    freshness="soft", edges="ragged", bbox=[0.42, 0.66, 0.58, 0.74],
                    note="старое пятно, не связанное с уборкой")],
            notes="контроль: здесь ничего никогда не стояло",
        ),
        "draw": draw,
    }


BUILDERS = {
    "syn-dust-outline-shelf": pair_dust_outline_shelf,
    "syn-dust-outline-table": pair_dust_outline_table,
    "syn-unfaded-patch-sill": pair_unfaded_patch_sill,
    "syn-unfaded-patch-shelf": pair_unfaded_patch_shelf,
    "syn-empty-hook-door": pair_empty_hook_door,
    "syn-two-traces-corner": pair_two_traces_corner,
}

FRAMES = ("before", "after", "clean")


def build_pair(pair_id):
    return BUILDERS[pair_id]()


def manifest_entry(spec):
    return {
        "id": spec["id"],
        "before": f"synthetic/{spec['id']}/before.json",
        "after": f"synthetic/{spec['id']}/after.json",
        "clean": f"synthetic/{spec['id']}/clean.json",
        "expect": spec["expect"],
        "truth": spec["truth"],
        "real": False,
        "synthetic": True,
    }


def write_pair(spec, out_root=SYNTHETIC_DIR):
    folder = Path(out_root) / spec["id"]
    folder.mkdir(parents=True, exist_ok=True)
    for frame in FRAMES:
        scene_data = spec[frame]
        (folder / f"{frame}.json").write_text(
            json.dumps(scene_data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        canvas = Canvas()
        spec["draw"](canvas, frame)
        (folder / f"{frame}.png").write_bytes(canvas.png())
    return manifest_entry(spec)


def update_manifest(entries, manifest_path=MANIFEST_PATH):
    path = Path(manifest_path)
    manifest = {"note": MANIFEST_NOTE, "pairs": []}
    if path.exists():
        manifest = json.loads(path.read_text(encoding="utf-8"))
    manifest["note"] = MANIFEST_NOTE
    by_id = {pair["id"]: pair for pair in manifest.get("pairs", [])}
    for entry in entries:
        by_id[entry["id"]] = entry
    manifest["pairs"] = list(by_id.values())
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return manifest


def main(argv=None):
    parser = argparse.ArgumentParser(description="Синтетические пары «до/после» для правил отсутствия")
    parser.add_argument("--only", action="append", choices=sorted(BUILDERS),
                        help="пересобрать только указанные пары")
    parser.add_argument("--out", default=str(SYNTHETIC_DIR), help="куда класть сцены пар")
    parser.add_argument("--no-manifest", action="store_true", help="не трогать манифест")
    args = parser.parse_args(argv)

    wanted = args.only or sorted(BUILDERS)
    entries = []
    for pair_id in wanted:
        spec = build_pair(pair_id)
        entry = write_pair(spec, Path(args.out))
        entries.append(entry)
        print(f"{entry['id']}: {entry['truth']}")
    if not args.no_manifest:
        manifest = update_manifest(entries)
        print(f"манифест: {MANIFEST_PATH} (пар: {len(manifest['pairs'])})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
