"""Кроп-интеррогейт: спросить модель про один участок, а не про всю картину.

Открытый вопрос «что here происходит» на всём кадре плохо работает для
отсутствия: модель пересказывает видимое. Вопрос «вот этот кроп — есть ли
здесь след удалённого предмета?» работает существенно лучше, потому что
задача сводится к бинарному решению на малом контексте.

Pillow опционален: без него работаем с координатами в тексте запроса.
"""

from pathlib import Path

try:
    from PIL import Image  # noqa: F401
    HAS_PIL = True
except ImportError:
    HAS_PIL = False


def crop_normalized(src, dst, bbox, pad=0.02, min_size=32):
    """Вырезать область по нормализованному bbox. None — если кроп невозможен."""
    if not HAS_PIL:
        return None
    from PIL import Image

    path = Path(src)
    with Image.open(path) as image:
        width, height = image.size
        x1, y1, x2, y2 = [float(v) for v in bbox[:4]]
        px1, py1 = int(x1 * width), int(y1 * height)
        px2, py2 = int(x2 * width), int(y2 * height)
        pad_x, pad_y = int(pad * width), int(pad * height)
        px1, py1 = max(0, px1 - pad_x), max(0, py1 - pad_y)
        px2, py2 = min(width, px2 + pad_x), min(height, py2 + pad_y)
        if px2 - px1 < min_size or py2 - py1 < min_size:
            return None
        crop = image.crop((px1, py1, px2, py2)).convert("RGB")
        crop.save(dst)
        return str(dst)


def bbox_area(bbox):
    if not bbox or len(bbox) < 4:
        return 0.0
    x1, y1, x2, y2 = [float(v) for v in bbox[:4]]
    return max(0.0, x2 - x1) * max(0.0, y2 - y1)


def bbox_center(bbox):
    x1, y1, x2, y2 = [float(v) for v in bbox[:4]]
    return ((x1 + x2) / 2, (y1 + y2) / 2)
