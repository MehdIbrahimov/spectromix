"""Matplotlib drawing helpers for the FTIR spectrum viewer."""

from __future__ import annotations

from typing import Any

from matplotlib.axes import Axes
from matplotlib.figure import Figure

DEFAULT_COLORS: list[str] = [
    "#1f77b4",
    "#d62728",
    "#2ca02c",
    "#9467bd",
    "#ff7f0e",
    "#17becf",
    "#8c564b",
    "#e377c2",
]


def normalize_series(y: list[float], mode: str) -> list[float]:
    """Return a normalized copy of `y` without mutating original data."""
    if not y or mode == "none":
        return list(y)

    if mode == "minmax":
        y_min = min(y)
        y_max = max(y)
        span = y_max - y_min
        if span == 0:
            return [0.0 for _ in y]
        return [(val - y_min) / span for val in y]

    if mode == "max":
        max_abs = max(abs(val) for val in y)
        if max_abs == 0:
            return list(y)
        return [val / max_abs for val in y]

    return list(y)


def _transform_intensity(
    raw_y: float,
    all_raw_y: list[float],
    normalize_mode: str,
    offset: float,
) -> float:
    """Apply the same normalization and vertical offset used on the curve."""
    if not all_raw_y or normalize_mode == "none":
        norm_val = raw_y
    elif normalize_mode == "minmax":
        y_min = min(all_raw_y)
        y_max = max(all_raw_y)
        span = y_max - y_min
        norm_val = (raw_y - y_min) / span if span != 0 else 0.0
    elif normalize_mode == "max":
        max_abs = max(abs(v) for v in all_raw_y)
        norm_val = raw_y / max_abs if max_abs != 0 else raw_y
    else:
        norm_val = raw_y

    return norm_val + offset


def draw_spectra(
    figure: Figure,
    spectra: list[dict[str, Any]],
    invert_x: bool = True,
    normalize_mode: str = "none",
    vertical_offset: float = 0.0,
    peak_mode: str = "maxima",
    show_markers: bool = True,
    show_wavenumbers: bool = True,
    show_group_labels: bool = True,
    style: dict[str, Any] | None = None,
) -> Axes:
    """Render spectra along with peak tags and styling options."""
    style = style or {}
    show_grid = bool(style.get("show_grid", True))
    show_legend = bool(style.get("show_legend", True))
    font_size = float(style.get("font_size", 10.0))

    figure.clear()
    ax = figure.add_subplot(111)

    visible_entries = [
        (idx, spec)
        for idx, spec in enumerate(spectra)
        if spec.get("visible", True) and spec.get("x") and spec.get("y")
    ]

    if not visible_entries:
        ax.set_title(style.get("title") or "No visible spectra", fontsize=font_size + 2)
        ax.set_xlabel(style.get("xlabel") or "Wavenumber (cm⁻¹)", fontsize=font_size)
        ax.set_ylabel(style.get("ylabel") or "Intensity", fontsize=font_size)
        ax.tick_params(labelsize=max(7.5, font_size - 1.5))
        ax.grid(show_grid, linestyle="--", alpha=0.4)
        figure.tight_layout()
        return ax

    all_x: list[float] = []
    label_direction = -1.0 if peak_mode == "minima" else 1.0

    for plot_order, (_, spec) in enumerate(visible_entries):
        x = spec["x"]
        raw_y = spec["y"]
        norm_y = normalize_series(raw_y, normalize_mode)
        offset = plot_order * vertical_offset
        shifted_y = [val + offset for val in norm_y]

        label = spec.get("display_name") or spec.get("name") or f"Spectrum {plot_order + 1}"
        spec_color = spec.get("color") or DEFAULT_COLORS[plot_order % len(DEFAULT_COLORS)]
        spec_lw = float(spec.get("line_width", 1.3))
        spec_ls = spec.get("line_style", "-")

        line = ax.plot(
            x,
            shifted_y,
            color=spec_color,
            linewidth=spec_lw,
            linestyle=spec_ls,
            label=label,
        )[0]
        curve_color = line.get_color()
        all_x.extend(x)

        peaks = spec.get("peaks") or []
        if not peaks:
            continue

        peak_xs: list[float] = []
        peak_ys: list[float] = []

        for peak in peaks:
            wn = float(peak["wavenumber"])
            raw_val = float(peak["intensity"])
            plot_val = _transform_intensity(raw_val, raw_y, normalize_mode, offset)

            peak_xs.append(wn)
            peak_ys.append(plot_val)

            text_parts: list[str] = []
            if show_wavenumbers:
                text_parts.append(f"{wn:.0f}")
            if show_group_labels and peak.get("assigned_label"):
                text_parts.append(str(peak["assigned_label"]))

            if text_parts:
                tag_text = " | ".join(text_parts)
                ax.annotate(
                    tag_text,
                    xy=(wn, plot_val),
                    xytext=(0, 10 * label_direction),
                    textcoords="offset points",
                    ha="center",
                    va="bottom" if label_direction > 0 else "top",
                    fontsize=max(6.5, font_size - 2.5),
                    color=curve_color,
                    rotation=35,
                )

        if show_markers and peak_xs:
            marker_style = "v" if peak_mode == "minima" else "^"
            ax.scatter(
                peak_xs,
                peak_ys,
                marker=marker_style,
                s=28,
                color=curve_color,
                edgecolors="black",
                linewidths=0.4,
                zorder=5,
            )

    default_title = "FTIR Spectra & Detected Peaks"
    ax.set_title(style.get("title") or default_title, fontsize=font_size + 2)
    ax.set_xlabel(style.get("xlabel") or "Wavenumber (cm⁻¹)", fontsize=font_size)

    if style.get("ylabel"):
        ylabel = style["ylabel"]
    elif normalize_mode == "minmax":
        ylabel = "Normalized Intensity (0–1)"
    elif normalize_mode == "max":
        ylabel = "Normalized Intensity (Peak = 1)"
    else:
        ylabel = "Transmittance" if peak_mode == "minima" else "Absorbance / Intensity"

    if not style.get("ylabel") and vertical_offset != 0.0:
        ylabel = f"{ylabel} (offset)"

    ax.set_ylabel(ylabel, fontsize=font_size)
    ax.tick_params(labelsize=max(7.5, font_size - 1.5))
    ax.grid(show_grid, linestyle="--", alpha=0.4)

    if show_legend:
        ax.legend(loc="best", fontsize=max(7.5, font_size - 1.5))

    if invert_x and all_x:
        ax.set_xlim(max(all_x), min(all_x))

    figure.tight_layout()
    return ax