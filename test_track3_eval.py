import json
import unittest
from pathlib import Path

from experiments.track3_eval import evaluate_predictions, load_dataset, score_case


DATASET_PATH = Path("experiments/track3_eval_cases.json")


class Track3EvalTests(unittest.TestCase):
    def setUp(self):
        self.dataset = load_dataset(DATASET_PATH)

    def test_dataset_case_ids_are_unique(self):
        case_ids = [case["id"] for case in self.dataset["cases"]]
        self.assertEqual(len(case_ids), len(set(case_ids)))

    def test_dataset_target_labels_exist(self):
        labels = set(self.dataset["label_signals"])
        for case in self.dataset["cases"]:
            self.assertIn(case["target_label"], labels)

    def test_scoring_detects_forbidden_substitution(self):
        case = next(case for case in self.dataset["cases"] if case["id"] == "bars-skip-change-stephen")
        result = score_case(
            case,
            "It uses pas de basque there.",
            self.dataset["label_signals"],
        )
        self.assertFalse(result.passed)
        self.assertEqual(result.predicted_label, "pas_de_basque")
        self.assertIn("pas de basque", result.forbidden_hits)

    def test_scoring_marks_correct_step_answer(self):
        case = next(case for case in self.dataset["cases"] if case["id"] == "bars-travelling-step-kirkcudbright")
        result = score_case(
            case,
            "The pivot is a travelling step left.",
            self.dataset["label_signals"],
        )
        self.assertTrue(result.passed)
        self.assertEqual(result.predicted_label, "travelling_step")

    def test_candidate_labels_prevent_irrelevant_label_match(self):
        case = next(case for case in self.dataset["cases"] if case["id"] == "bars-diplomat-setting-steps")
        result = score_case(
            case,
            "The Diplomat uses two setting steps as they pass left shoulder.",
            self.dataset["label_signals"],
        )
        self.assertEqual(result.predicted_label, "setting_step")

    def test_evaluate_predictions_builds_confusion_matrix(self):
        predictions = {
            "bars-skip-change-stephen": "skip change",
            "bars-pas-de-basque-discounted-suit": "skip change",
        }
        trimmed_dataset = {
            "label_signals": self.dataset["label_signals"],
            "cases": [
                next(case for case in self.dataset["cases"] if case["id"] == "bars-skip-change-stephen"),
                next(case for case in self.dataset["cases"] if case["id"] == "bars-pas-de-basque-discounted-suit"),
            ],
        }
        report = evaluate_predictions(trimmed_dataset, predictions)
        self.assertEqual(report["confusion_matrix"]["skip_change"]["skip_change"], 1)
        self.assertEqual(report["confusion_matrix"]["pas_de_basque"]["skip_change"], 1)


if __name__ == "__main__":
    unittest.main()
