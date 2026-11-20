"""Unit tests for core CSV parsing, peak detection, and functional group tagging."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from spectromix.spectroscopy import (
    assign_functional_groups,
    detect_csv_format,
    detect_peaks,
    load_functional_groups,
    load_spectrum_csv,
)


class TestSpectroscopy(unittest.TestCase):
    def test_detect_and_load_european_semicolon_csv(self) -> None:
        sample_text = (
            "Instrument: ATR-FTIR\n"
            "Wavenumber;Absorbance\n"
            "4000,0;0,10\n"
            "3500,0;0,25\n"
            "3000,0;0,15\n"
            "2500,0;0,05\n"
            "2000,0;0,12\n"
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            csv_path = Path(tmpdir) / "sample.csv"
            csv_path.write_text(sample_text, encoding="utf-8")

            fmt = detect_csv_format(csv_path)
            self.assertEqual(fmt["delimiter"], ";")
            self.assertTrue(fmt["decimal_comma"])
            self.assertEqual(fmt["skip_rows"], 2)

            spectrum = load_spectrum_csv(csv_path)
            self.assertEqual(spectrum["points"], 5)
            # Loaded x-values are sorted ascending
            self.assertEqual(spectrum["x"], [2000.0, 2500.0, 3000.0, 3500.0, 4000.0])
            self.assertAlmostEqual(spectrum["y"][3], 0.25)

    def test_detect_peaks_absorbance_maxima(self) -> None:
        x = [1000.0, 1020.0, 1040.0, 1060.0, 1080.0, 1100.0, 1120.0]
        y = [0.05, 0.10, 0.80, 0.12, 0.08, 0.55, 0.06]

        peaks = detect_peaks(x, y, mode="maxima", min_prominence_ratio=0.1, min_wavenumber_gap=20.0)
        wavenumbers = [p["wavenumber"] for p in peaks]
        self.assertEqual(wavenumbers, [1100.0, 1040.0])

    def test_detect_peaks_transmittance_minima(self) -> None:
        x = [1500.0, 1520.0, 1540.0, 1560.0, 1580.0]
        y = [0.95, 0.90, 0.20, 0.88, 0.96]

        peaks = detect_peaks(x, y, mode="minima", min_prominence_ratio=0.1, min_wavenumber_gap=15.0)
        self.assertEqual(len(peaks), 1)
        self.assertEqual(peaks[0]["wavenumber"], 1540.0)

    def test_load_empty_functional_groups_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            empty_json = Path(tmpdir) / "empty.json"
            empty_json.write_text("", encoding="utf-8")

            groups = load_functional_groups(empty_json)
            self.assertEqual(groups, [])

    def test_assign_functional_groups(self) -> None:
        rules = [
            {"label": "O-H / N-H", "min_cm": 3150, "max_cm": 3600, "vibration": "Stretch"},
            {"label": "Amide I", "min_cm": 1635, "max_cm": 1695, "vibration": "C=O"},
        ]
        with tempfile.TemporaryDirectory() as tmpdir:
            json_path = Path(tmpdir) / "groups.json"
            json_path.write_text(json.dumps(rules), encoding="utf-8")

            loaded_groups = load_functional_groups(json_path)
            peaks = [
                {"wavenumber": 3358.0, "intensity": 0.80},
                {"wavenumber": 2100.0, "intensity": 0.10},
            ]
            tagged = assign_functional_groups(peaks, loaded_groups)

            self.assertEqual(tagged[0]["assigned_label"], "O-H / N-H")
            self.assertIsNone(tagged[1]["assigned_label"])


if __name__ == "__main__":
    unittest.main()