import unittest

from elementarno.nextshot import discriminator_questions, tied_groups

from tests.test_modules import make_finding


class DiscriminatorTests(unittest.TestCase):
    def setUp(self):
        self.findings = [make_finding("F-HOME-003", rule_id="HOME-003", step="activity",
                                      tags=["household_habit"])]
        self.hypotheses = [
            {"hypothesis_id": "H-1", "text": "после использования", "log_odds": -0.7,
             "support_findings": ["F-HOME-003"],
             "discriminator": {"question": "что в коробке: блистер или пусто?",
                               "would_confirm": "блистер целый"}},
            {"hypothesis_id": "H-2", "text": "давно пустое", "log_odds": -0.7,
             "support_findings": ["F-HOME-003"],
             "discriminator": {"question": "что в коробке: блистер или пусто?",
                               "would_confirm": "коробка пуста"}},
        ]

    def test_versions_with_same_weight_are_still_separable_by_question(self):
        questions = discriminator_questions(self.hypotheses)
        self.assertEqual(len(questions), 1)
        self.assertEqual(questions[0]["splits"], 2)
        self.assertEqual(questions[0]["group"], 2)
        self.assertGreater(questions[0]["eig"], 0.0)

    def test_version_without_discriminator_produces_no_question(self):
        questions = discriminator_questions([{"hypothesis_id": "H-1", "log_odds": 1.0}])
        self.assertEqual(questions, [])

    def test_tied_versions_are_grouped_by_weight(self):
        groups = tied_groups(self.hypotheses + [
            {"hypothesis_id": "H-3", "log_odds": 2.0, "support_findings": ["F-HOME-003"]}])
        self.assertEqual(sorted(len(g) for g in groups.values()), [1, 2])
