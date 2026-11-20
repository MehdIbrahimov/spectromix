"""Core spectroscopy parsing, peak detection, and functional group matching.

This module intentionally has zero GUI or plotting dependencies so it can be
tested standalone and reused easily across different interfaces.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any


def _strip_decimal_commas_for_delimiter_count(line: str) -> str:
    """Replace commas between two digits (e.g. '4,00') so they aren't read as delimiters."""
    chars = list(line)
    cleaned: list[str] = []
    for i, ch in enumerate(chars):
        if (
            ch == ","
            and 0 < i < len(chars) - 1
            and chars[i - 1].isdigit()
            and chars[i + 1].isdigit()
        ):
            cleaned.append(".")
        else:
            cleaned.append(ch)
    return "".join(cleaned)


def _parse_number(token: str, decimal_comma: bool = False) -> float | None:
    """Convert a string token to float, returning None if it isn't numeric."""
    cleaned = token.strip().strip('"').strip("'")
    if not cleaned:
        return None
    if decimal_comma:
        cleaned = cleaned.replace(",", ".")
    try:
        value = float(cleaned)
    except ValueError:
        return None
    # Reject NaN / inf
    if value != value or value in (float("inf"), float("-inf")):
        return None
    return value


def detect_csv_format(
    filepath: str | Path,
    max_probe_lines: int = 150,
    streak_length: int = 4,
) -> dict[str, Any]:
    """Guess delimiter, decimal separator, and starting data row for a spectrum CSV.

    Looks for a consecutive streak of rows sharing the same count of numeric
    columns so isolated numbers inside instrument headers do not cause false stops.
    """
    path = Path(filepath)
    with path.open("r", encoding="utf-8-sig", errors="replace") as f:
        raw_lines = [next(f, "") for _ in range(max_probe_lines)]

    non_empty = [line.rstrip("\r\n") for line in raw_lines if line.strip()]
    if not non_empty:
        return {
            "delimiter": ",",
            "decimal_comma": False,
            "skip_rows": 0,
            "num_columns": 0,
        }

    # Guess delimiter from candidate lines using delimiter-count consistency
    candidates = [",", ";", "\t", " "]
    sample_for_delim = [
        _strip_decimal_commas_for_delimiter_count(line) for line in non_empty[:25]
    ]

    best_delim = ","
    best_score = (-1, -1)  # (consistent_nonzero_lines, total_occurrences)
    for delim in candidates:
        counts = []
        for line in sample_for_delim:
            if delim == " ":
                # Collapse multiple spaces into one separator for counting
                parts = [p for p in line.strip().split() if p]
                c = max(0, len(parts) - 1)
            else:
                c = line.count(delim)
            counts.append(c)

        nonzero = [c for c in counts if c > 0]
        if not nonzero:
            continue
        most_common_count = max(set(nonzero), key=nonzero.count)
        consistent_lines = sum(1 for c in counts if c == most_common_count)
        score = (consistent_lines, sum(nonzero))
        if score > best_score:
            best_score = score
            best_delim = delim

    # Detect whether decimal commas appear in numeric-looking tokens
    decimal_comma_hits = 0
    for line in non_empty[:40]:
        tokens = line.strip().split() if best_delim == " " else line.split(best_delim)
        for tok in tokens:
            t = tok.strip().strip('"')
            if "," in t and "." not in t:
                parts = t.split(",")
                if len(parts) == 2 and parts[0].lstrip("-").isdigit() and parts[1].isdigit():
                    decimal_comma_hits += 1

    use_decimal_comma = decimal_comma_hits >= 3 and best_delim != ","

    # Find the first streak of `streak_length` rows with >=2 numeric columns
    # of equal width. Map back to 0-based index in the original file.
    with path.open("r", encoding="utf-8-sig", errors="replace") as f:
        all_probe_lines = [next(f, None) for _ in range(max_probe_lines)]

    row_numeric_counts: list[int] = []
    valid_line_indices: list[int] = []

    for idx, raw in enumerate(all_probe_lines):
        if raw is None:
            break
        stripped = raw.strip()
        if not stripped:
            row_numeric_counts.append(0)
            valid_line_indices.append(idx)
            continue

        if best_delim == " ":
            tokens = stripped.split()
        else:
            tokens = next(csv.reader([stripped], delimiter=best_delim), [])

        numeric_cols = sum(
            1 for tok in tokens if _parse_number(tok, decimal_comma=use_decimal_comma) is not None
        )
        row_numeric_counts.append(numeric_cols)
        valid_line_indices.append(idx)

    skip_rows = 0
    detected_cols = 2
    n = len(row_numeric_counts)

    for i in range(n - streak_length + 1):
        count_i = row_numeric_counts[i]
        if count_i < 2:
            continue
        if all(row_numeric_counts[i + k] == count_i for k in range(streak_length)):
            skip_rows = valid_line_indices[i]
            detected_cols = count_i
            break

    return {
        "delimiter": best_delim,
        "decimal_comma": use_decimal_comma,
        "skip_rows": skip_rows,
        "num_columns": detected_cols,
    }


def load_spectrum_csv(
    filepath: str | Path,
    skip_rows: int | None = None,
    delimiter: str | None = None,
    decimal_comma: bool | None = None,
    x_col: int = 0,
    y_col: int = 1,
) -> dict[str, Any]:
    """Load wavenumber (x) and intensity (y) data from a CSV/text spectrum file.

    Any parameter left as None is auto-detected via `detect_csv_format`.
    """
    path = Path(filepath)
    detected = detect_csv_format(path)

    actual_skip = detected["skip_rows"] if skip_rows is None else max(0, skip_rows)
    actual_delim = detected["delimiter"] if delimiter is None else delimiter
    actual_dec_comma = (
        detected["decimal_comma"] if decimal_comma is None else decimal_comma
    )

    x_values: list[float] = []
    y_values: list[float] = []
    skipped_malformed = 0

    with path.open("r", encoding="utf-8-sig", errors="replace") as f:
        for current_row_idx, line in enumerate(f):
            if current_row_idx < actual_skip:
                continue
            stripped = line.strip()
            if not stripped:
                continue

            if actual_delim == " ":
                row = stripped.split()
            else:
                row = next(csv.reader([stripped], delimiter=actual_delim), [])

            if max(x_col, y_col) >= len(row):
                skipped_malformed += 1
                continue

            x_num = _parse_number(row[x_col], decimal_comma=actual_dec_comma)
            y_num = _parse_number(row[y_col], decimal_comma=actual_dec_comma)

            if x_num is None or y_num is None:
                skipped_malformed += 1
                continue

            x_values.append(x_num)
            y_values.append(y_num)

    # Sort by ascending wavenumber so peak finding behaves predictably
    # regardless of whether the file starts at 4000 or 400 cm^-1.
    paired = sorted(zip(x_values, y_values), key=lambda pair: pair[0])
    sorted_x = [p[0] for p in paired]
    sorted_y = [p[1] for p in paired]

    return {
        "source": str(path),
        "name": path.stem,
        "x": sorted_x,
        "y": sorted_y,
        "points": len(sorted_x),
        "skipped_malformed": skipped_malformed,
        "format": {
            "delimiter": actual_delim,
            "decimal_comma": actual_dec_comma,
            "skip_rows": actual_skip,
        },
    }


def detect_peaks(
    x: list[float],
    y: list[float],
    mode: str = "maxima",
    min_prominence_ratio: float = 0.03,
    min_wavenumber_gap: float = 15.0,
) -> list[dict[str, Any]]:
    """Detect local peaks (or transmittance valleys) in a spectrum.

    Parameters
    ----------
    x : list[float]
        Wavenumbers in cm^-1 (sorted ascending).
    y : list[float]
        Spectral intensity values (absorbance or transmittance).
    mode : str
        'maxima' for peaks (e.g. absorbance), 'minima' for downward bands
        (e.g. transmittance dips).
    min_prominence_ratio : float
        Minimum height/depth relative to the full Y range (0.0 to 1.0) used to
        filter out small baseline ripples.
    min_wavenumber_gap : float
        Minimum separation in cm^-1 between accepted peaks (keeps the stronger one).
    """
    if len(x) < 3 or len(x) != len(y):
        return []

    y_min = min(y)
    y_max = max(y)
    y_span = y_max - y_min
    if y_span == 0:
        return []

    min_prominence = max(0.0, min_prominence_ratio) * y_span
    candidates: list[dict[str, Any]] = []

    for i in range(1, len(y) - 1):
        prev_y, curr_y, next_y = y[i - 1], y[i], y[i + 1]

        if mode == "minima":
            is_extrema = curr_y <= prev_y and curr_y <= next_y and (curr_y < prev_y or curr_y < next_y)
            if not is_extrema:
                continue
            # Local baseline on left and right is the highest point before a higher rise
            left_peak = max(y[:i])
            right_peak = max(y[i + 1 :])
            prominence = min(left_peak - curr_y, right_peak - curr_y)
        else:
            is_extrema = curr_y >= prev_y and curr_y >= next_y and (curr_y > prev_y or curr_y > next_y)
            if not is_extrema:
                continue
            left_trough = min(y[:i])
            right_trough = min(y[i + 1 :])
            prominence = min(curr_y - left_trough, curr_y - right_trough)

        if prominence >= min_prominence:
            candidates.append(
                {
                    "index": i,
                    "wavenumber": round(x[i], 2),
                    "intensity": y[i],
                    "prominence": prominence,
                }
            )

    # Enforce minimum spacing in cm^-1 by keeping higher-prominence peaks first
    candidates.sort(key=lambda item: item["prominence"], reverse=True)
    accepted: list[dict[str, Any]] = []

    for cand in candidates:
        too_close = any(
            abs(cand["wavenumber"] - existing["wavenumber"]) < min_wavenumber_gap
            for existing in accepted
        )
        if not too_close:
            accepted.append(cand)

    accepted.sort(key=lambda item: item["wavenumber"], reverse=True)
    return accepted


def load_functional_groups(json_path: str | Path) -> list[dict[str, Any]]:
    """Load reference functional group ranges from a JSON file.

    Returns an empty list safely if the file is empty, missing, or not yet
    populated with a list of group definitions.
    """
    path = Path(json_path)
    if not path.exists():
        return []

    content = path.read_text(encoding="utf-8").strip()
    if not content:
        return []

    try:
        data = json.loads(content)
    except json.JSONDecodeError:
        return []

    if not isinstance(data, list):
        return []

    valid_groups: list[dict[str, Any]] = []
    for entry in data:
        if not isinstance(entry, dict):
            continue
        try:
            wn_min = float(entry["min_cm"])
            wn_max = float(entry["max_cm"])
            label = str(entry["label"]).strip()
        except (KeyError, TypeError, ValueError):
            continue

        if label:
            valid_groups.append(
                {
                    "label": label,
                    "min_cm": min(wn_min, wn_max),
                    "max_cm": max(wn_min, wn_max),
                    "vibration": str(entry.get("vibration", "")).strip(),
                }
            )
    return valid_groups


def assign_functional_groups(
    peaks: list[dict[str, Any]],
    groups: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Attach matching functional group labels to detected peaks.

    If `groups` is empty, every peak still comes back cleanly with `matches: []`
    and `assigned_label: None`.
    """
    tagged: list[dict[str, Any]] = []
    for peak in peaks:
        wn = peak["wavenumber"]
        matched = [
            g
            for g in groups
            if g["min_cm"] <= wn <= g["max_cm"]
        ]
        enriched = dict(peak)
        enriched["matches"] = matched
        enriched["assigned_label"] = (
            ", ".join(m["label"] for m in matched) if matched else None
        )
        tagged.append(enriched)
    return tagged


if __name__ == "__main__":
    # Quick smoke test from the terminal without needing a GUI
    import sys

    if len(sys.argv) < 2:
        print("Usage: python spectroscopy.py <path_to_spectrum.csv> [functional_groups.json]")
        sys.exit(0)

    csv_file = sys.argv[1]
    json_file = sys.argv[2] if len(sys.argv) > 2 else "functional_groups.json"

    spectrum = load_spectrum_csv(csv_file)
    print(f"Loaded '{spectrum['name']}': {spectrum['points']} points | format={spectrum['format']}")

    found_peaks = detect_peaks(spectrum["x"], spectrum["y"])
    groups = load_functional_groups(json_file)
    tagged_peaks = assign_functional_groups(found_peaks, groups)

    print(f"Detected {len(tagged_peaks)} peaks (reference groups loaded: {len(groups)}):")
    for p in tagged_peaks[:15]:
        tag_text = p["assigned_label"] or "Unassigned"
        print(f"  {p['wavenumber']:7.2f} cm^-1 | y={p['intensity']:.4f} | {tag_text}")