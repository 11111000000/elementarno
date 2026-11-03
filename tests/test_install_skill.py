import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from install_skill import differences, install  # noqa: E402


class InstalledSkillTests(unittest.TestCase):
    """Глобальная копия скилла не должна расходиться с репозиторной.

    Агент грузит скилл из ~/.config/opencode, а правка живёт в репозитории.
    Расхождение выглядит как «правка не сработала», и найти его трудно.
    """

    def test_installed_skill_matches_the_repository(self):
        problems = differences()
        self.assertEqual(problems, [], "скилл устарел: " + "; ".join(problems))

    def test_install_is_idempotent(self):
        install()
        install()
        self.assertEqual(differences(), [])


if __name__ == "__main__":
    unittest.main()
