#!/usr/bin/env python3
"""Установка и синхронизация скилла detective с глобальным каталогом opencode.

Агент грузит скилл из ~/.config/opencode/skills/, а не из репозитория. Поэтому
правка скилла в репозитории без установки молча остаётся в репозитории: в
живой сессии работает старая версия, и правка не даёт эффекта.

    python3 tools/install_skill.py           # установить или обновить
    python3 tools/install_skill.py --check   # только проверить, ничего не писать

Код возврата: 0 — совпадает, 1 — расхождение (при --check), 2 — ошибка.
"""

import argparse
import filecmp
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / ".opencode" / "skills" / "detective"
TARGET = Path.home() / ".config" / "opencode" / "skills" / "detective"
COMMAND_SOURCE = ROOT / ".opencode" / "command" / "detective.md"
COMMAND_TARGET = Path.home() / ".config" / "opencode" / "command" / "detective.md"
FILES = ("SKILL.md", "REFERENCE.md")


def differences():
    """Список расхождений между репозиторием и установленной копией."""
    problems = []
    for name in FILES:
        source = SOURCE / name
        target = TARGET / name
        if not source.exists():
            problems.append(f"нет в репозитории: {source}")
            continue
        if not target.exists():
            problems.append(f"не установлен: {target}")
            continue
        if not filecmp.cmp(source, target, shallow=False):
            problems.append(f"устарел: {target}")
    if COMMAND_SOURCE.exists():
        if not COMMAND_TARGET.exists():
            problems.append(f"не установлена команда: {COMMAND_TARGET}")
        elif not filecmp.cmp(COMMAND_SOURCE, COMMAND_TARGET, shallow=False):
            problems.append(f"устарела команда: {COMMAND_TARGET}")
    return problems


def install():
    TARGET.mkdir(parents=True, exist_ok=True)
    for name in FILES:
        shutil.copy2(SOURCE / name, TARGET / name)
    if COMMAND_SOURCE.exists():
        COMMAND_TARGET.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(COMMAND_SOURCE, COMMAND_TARGET)
    return TARGET


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true",
                        help="только проверить, ничего не устанавливать")
    args = parser.parse_args(argv)

    if args.check:
        problems = differences()
        if problems:
            print("скилл в ~/.config/opencode устарел:")
            for problem in problems:
                print(f"  - {problem}")
            print("исправить: python3 tools/install_skill.py")
            return 1
        print("скилл установлен и совпадает с репозиторием")
        return 0

    target = install()
    print(f"скилл установлен: {target}")
    if COMMAND_TARGET.exists():
        print(f"команда установлена: {COMMAND_TARGET}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
