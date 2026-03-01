import unittest

from activity_snapshot import parse_manual_activity_snapshot_from_email


class TestActivitySnapshotParser(unittest.TestCase):
    def test_returns_none_when_no_activity_signal(self):
        result = parse_manual_activity_snapshot_from_email(
            "Can you help with my training plan next week?",
            now_epoch=1735732800,
        )
        self.assertIsNone(result)

    def test_parses_running_snapshot_with_subjective_state(self):
        body = (
            "I did a run for 45 minutes today. Distance was 8 km. "
            "Felt good and had good sleep but little sore."
        )
        result = parse_manual_activity_snapshot_from_email(body, now_epoch=1735732800)
        self.assertIsNotNone(result)
        self.assertEqual(result["activity_type"], "running")
        self.assertEqual(result["duration"], "45m")
        self.assertEqual(result["key_metric"], "distance:8km")
        self.assertEqual(result["subjective_state"]["sleep"], "good")
        self.assertEqual(result["subjective_state"]["soreness"], "low")


if __name__ == "__main__":
    unittest.main()
