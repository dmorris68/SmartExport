import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

from smart_export_core import next_sequence, safe_stem, timestamp_filename, unique_path


class SmartExportCoreTests(unittest.TestCase):
    def test_safe_stem(self):
        self.assertEqual(safe_stem('Gear: 2/Final.f3d'), "Final")
        self.assertEqual(safe_stem("bad:name"), "bad_name")

    def test_first_sequence_uses_unpadded_fusion_pattern(self):
        with tempfile.TemporaryDirectory() as folder:
            self.assertEqual(next_sequence(folder, "Part", "step"), "Part_v1.step")

    def test_sequence_scans_unpadded_versions_for_matching_format_and_stem(self):
        with tempfile.TemporaryDirectory() as folder:
            for name in ("Part_v1.step", "part_v9.STEP", "Part_v100.stl",
                         "Other_v50.step", "Part.step"):
                Path(folder, name).touch()
            self.assertEqual(next_sequence(folder, "Part", "step"), "Part_v10.step")

    def test_sequence_stays_unpadded_at_large_values(self):
        with tempfile.TemporaryDirectory() as folder:
            Path(folder, "Part_v999.step").touch()
            self.assertEqual(next_sequence(folder, "Part", "step"), "Part_v1000.step")

    def test_sequence_recognizes_legacy_padded_exports(self):
        with tempfile.TemporaryDirectory() as folder:
            Path(folder, "Part_v009.step").touch()
            self.assertEqual(next_sequence(folder, "Part", "step"), "Part_v10.step")

    @patch("smart_export_core.datetime")
    def test_timestamp_uses_local_time(self, mocked_datetime):
        mocked_datetime.fromtimestamp.return_value = datetime(2026, 7, 20, 14, 35, 2)
        self.assertEqual(
            timestamp_filename("Part", "3mf", 123),
            "Part_2026-07-20_14-35-02.3mf",
        )

    def test_unique_path_does_not_overwrite(self):
        with tempfile.TemporaryDirectory() as folder:
            original = Path(folder, "Part_2026.step")
            original.touch()
            Path(folder, "Part_2026_2.step").touch()
            self.assertEqual(unique_path(original).name, "Part_2026_3.step")


if __name__ == "__main__":
    unittest.main()
