"""Tkinter user interface with Tab 1 (Data & Axes), Tab 2 (Peaks & Tags), and Tab 3 (Style & Export)."""

from __future__ import annotations

import csv
import tkinter as tk
from pathlib import Path
from tkinter import colorchooser, filedialog, messagebox, ttk
from typing import Any

from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
from matplotlib.figure import Figure

from .plotter import DEFAULT_COLORS, draw_spectra
from .spectroscopy import (
    assign_functional_groups,
    detect_peaks,
    load_functional_groups,
    load_spectrum_csv,
)

LINE_STYLE_MAP: dict[str, str] = {
    "Solid (-)": "-",
    "Dashed (--)": "--",
    "Dotted (:)": ":",
    "Dash-Dot (-.)": "-.",
}


class SpectrumApp(ttk.Frame):
    """GUI with a three-tab sidebar and live Matplotlib canvas."""

    def __init__(self, master: tk.Tk) -> None:
        super().__init__(master, padding=10)
        self.master = master
        self.master.title("FTIR Spectrum Viewer")
        self.master.geometry("1200x740")

        # Central app state (single source of truth)
        self.state: dict[str, Any] = {
            "spectra": [],               # list of spectrum dicts
            "selected_index": None,
            "invert_x": True,
            "normalize_mode": "none",    # "none" | "minmax" | "max"
            "vertical_offset": 0.0,
            # Tab 2 peak & functional-group settings
            "peak_mode": "maxima",       # "maxima" | "minima"
            "prominence_ratio": 0.05,
            "min_wavenumber_gap": 20.0,
            "peak_scope": "visible",     # "visible" | "selected"
            "show_markers": True,
            "show_wavenumbers": True,
            "show_group_labels": True,
            "groups_path": str(Path(__file__).resolve().parent / "functional_groups.json"),
            "functional_groups": [],
            # Tab 3 styling & export settings
            "style": {
                "show_grid": True,
                "show_legend": True,
                "font_size": 10.0,
                "title": "",
                "xlabel": "",
                "ylabel": "",
            },
            "export_dpi": 300,
        }

        self.state["functional_groups"] = load_functional_groups(self.state["groups_path"])

        # Tk control variables synced with `self.state`
        self.invert_x_var = tk.BooleanVar(value=self.state["invert_x"])
        self.norm_var = tk.StringVar(value=self.state["normalize_mode"])
        self.offset_var = tk.DoubleVar(value=self.state["vertical_offset"])
        self.rename_var = tk.StringVar(value="")

        self.peak_mode_label_var = tk.StringVar(value="Absorbance (maxima)")
        self.prominence_var = tk.DoubleVar(value=self.state["prominence_ratio"])
        self.gap_var = tk.DoubleVar(value=self.state["min_wavenumber_gap"])
        self.scope_var = tk.StringVar(value=self.state["peak_scope"])
        self.show_markers_var = tk.BooleanVar(value=self.state["show_markers"])
        self.show_wn_var = tk.BooleanVar(value=self.state["show_wavenumbers"])
        self.show_groups_var = tk.BooleanVar(value=self.state["show_group_labels"])
        self.groups_file_var = tk.StringVar(
            value=f"{Path(self.state['groups_path']).name} ({len(self.state['functional_groups'])} rules)"
        )

        # Tab 3 variables
        self.spec_color_var = tk.StringVar(value=DEFAULT_COLORS[0])
        self.spec_lw_var = tk.DoubleVar(value=1.3)
        self.spec_ls_label_var = tk.StringVar(value="Solid (-)")
        self.show_grid_var = tk.BooleanVar(value=self.state["style"]["show_grid"])
        self.show_legend_var = tk.BooleanVar(value=self.state["style"]["show_legend"])
        self.font_size_var = tk.DoubleVar(value=self.state["style"]["font_size"])
        self.title_var = tk.StringVar(value="")
        self.xlabel_var = tk.StringVar(value="")
        self.ylabel_var = tk.StringVar(value="")
        self.dpi_var = tk.StringVar(value=str(self.state["export_dpi"]))

        self.status_var = tk.StringVar(value="Ready — load one or more spectrum CSV files.")

        self.pack(fill=tk.BOTH, expand=True)
        self._build_layout()
        self._refresh_all()

    def _build_layout(self) -> None:
        top_bar = ttk.Frame(self)
        top_bar.pack(side=tk.TOP, fill=tk.X, pady=(0, 8))
        ttk.Label(top_bar, textvariable=self.status_var).pack(side=tk.LEFT)

        main_pane = ttk.PanedWindow(self, orient=tk.HORIZONTAL)
        main_pane.pack(side=tk.TOP, fill=tk.BOTH, expand=True)

        sidebar = ttk.Frame(main_pane, width=385)
        plot_container = ttk.Frame(main_pane)

        main_pane.add(sidebar, weight=0)
        main_pane.add(plot_container, weight=1)

        notebook = ttk.Notebook(sidebar)
        notebook.pack(fill=tk.BOTH, expand=True)

        tab_data = ttk.Frame(notebook, padding=10)
        tab_peaks = ttk.Frame(notebook, padding=10)
        tab_style = ttk.Frame(notebook, padding=10)

        notebook.add(tab_data, text="Data & Axes")
        notebook.add(tab_peaks, text="Peaks & Tags")
        notebook.add(tab_style, text="Style & Export")

        self._build_tab_data_axes(tab_data)
        self._build_tab_peaks_tags(tab_peaks)
        self._build_tab_style_export(tab_style)

        self.figure = Figure(figsize=(8, 5), dpi=100)
        self.canvas = FigureCanvasTkAgg(self.figure, master=plot_container)
        self.canvas_widget = self.canvas.get_tk_widget()

        toolbar = NavigationToolbar2Tk(self.canvas, plot_container)
        toolbar.update()
        toolbar.pack(side=tk.BOTTOM, fill=tk.X)

        self.canvas_widget.pack(side=tk.TOP, fill=tk.BOTH, expand=True)

    # ------------------------------------------------------------------
    # Tab 1: Data & Axes
    # ------------------------------------------------------------------
    def _build_tab_data_axes(self, parent: ttk.Frame) -> None:
        files_box = ttk.LabelFrame(parent, text="Loaded Spectra", padding=8)
        files_box.pack(fill=tk.BOTH, expand=True)

        btn_row = ttk.Frame(files_box)
        btn_row.pack(fill=tk.X, pady=(0, 6))

        ttk.Button(btn_row, text="Add CSV(s)...", command=self._on_add_files).pack(
            side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 4)
        )
        ttk.Button(btn_row, text="Remove", command=self._on_remove_selected).pack(
            side=tk.LEFT, fill=tk.X, expand=True, padx=(4, 0)
        )

        list_frame = ttk.Frame(files_box)
        list_frame.pack(fill=tk.BOTH, expand=True)

        self.listbox = tk.Listbox(list_frame, height=7, exportselection=False)
        self.listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.listbox.bind("<<ListboxSelect>>", self._on_listbox_select)

        scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.listbox.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.listbox.configure(yscrollcommand=scrollbar.set)

        vis_row = ttk.Frame(files_box)
        vis_row.pack(fill=tk.X, pady=(6, 4))

        self.selected_visible_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(
            vis_row,
            text="Show selected spectrum",
            variable=self.selected_visible_var,
            command=self._on_toggle_selected_visible,
        ).pack(side=tk.LEFT)

        rename_row = ttk.Frame(files_box)
        rename_row.pack(fill=tk.X, pady=(2, 0))

        ttk.Label(rename_row, text="Label:").pack(side=tk.LEFT)
        rename_entry = ttk.Entry(rename_row, textvariable=self.rename_var)
        rename_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(4, 4))
        rename_entry.bind("<Return>", lambda _e: self._on_apply_rename())
        ttk.Button(rename_row, text="Set", width=4, command=self._on_apply_rename).pack(
            side=tk.RIGHT
        )

        axes_box = ttk.LabelFrame(parent, text="Axis & Normalization", padding=8)
        axes_box.pack(fill=tk.X, pady=(10, 0))

        ttk.Checkbutton(
            axes_box,
            text="Invert X-Axis (4000 → 400 cm⁻¹)",
            variable=self.invert_x_var,
            command=self._on_axis_option_changed,
        ).pack(anchor=tk.W, pady=(0, 6))

        ttk.Label(axes_box, text="Normalization:").pack(anchor=tk.W)
        norm_combo = ttk.Combobox(
            axes_box,
            textvariable=self.norm_var,
            state="readonly",
            values=["none", "minmax", "max"],
        )
        norm_combo.pack(fill=tk.X, pady=(2, 8))
        norm_combo.bind("<<ComboboxSelected>>", lambda _e: self._on_axis_option_changed())

        offset_header = ttk.Frame(axes_box)
        offset_header.pack(fill=tk.X)
        ttk.Label(offset_header, text="Vertical Offset:").pack(side=tk.LEFT)
        self.offset_val_label = ttk.Label(offset_header, text="0.00")
        self.offset_val_label.pack(side=tk.RIGHT)

        offset_scale = ttk.Scale(
            axes_box,
            from_=0.0,
            to=2.0,
            variable=self.offset_var,
            command=self._on_offset_changed,
        )
        offset_scale.pack(fill=tk.X, pady=(2, 4))

        ttk.Button(axes_box, text="Reset View Options", command=self._on_reset_options).pack(
            fill=tk.X, pady=(4, 0)
        )

    # ------------------------------------------------------------------
    # Tab 2: Peaks & Tags
    # ------------------------------------------------------------------
    def _build_tab_peaks_tags(self, parent: ttk.Frame) -> None:
        detect_box = ttk.LabelFrame(parent, text="Peak Detection Parameters", padding=8)
        detect_box.pack(fill=tk.X)

        ttk.Label(detect_box, text="Spectrum Signal Mode:").pack(anchor=tk.W)
        mode_combo = ttk.Combobox(
            detect_box,
            textvariable=self.peak_mode_label_var,
            state="readonly",
            values=["Absorbance (maxima)", "Transmittance (minima)"],
        )
        mode_combo.pack(fill=tk.X, pady=(2, 6))
        mode_combo.bind("<<ComboboxSelected>>", lambda _e: self._on_peak_params_changed())

        ttk.Label(detect_box, text="Detect Peaks For:").pack(anchor=tk.W)
        scope_combo = ttk.Combobox(
            detect_box,
            textvariable=self.scope_var,
            state="readonly",
            values=["visible", "selected"],
        )
        scope_combo.pack(fill=tk.X, pady=(2, 8))
        scope_combo.bind("<<ComboboxSelected>>", lambda _e: self._on_peak_params_changed())

        prom_header = ttk.Frame(detect_box)
        prom_header.pack(fill=tk.X)
        ttk.Label(prom_header, text="Min Prominence Ratio:").pack(side=tk.LEFT)
        self.prom_val_label = ttk.Label(
            prom_header, text=f"{self.state['prominence_ratio']:.2f}"
        )
        self.prom_val_label.pack(side=tk.RIGHT)

        ttk.Scale(
            detect_box,
            from_=0.01,
            to=0.25,
            variable=self.prominence_var,
            command=self._on_prominence_changed,
        ).pack(fill=tk.X, pady=(2, 8))

        gap_header = ttk.Frame(detect_box)
        gap_header.pack(fill=tk.X)
        ttk.Label(gap_header, text="Min Peak Spacing (cm⁻¹):").pack(side=tk.LEFT)
        self.gap_val_label = ttk.Label(
            gap_header, text=f"{self.state['min_wavenumber_gap']:.0f}"
        )
        self.gap_val_label.pack(side=tk.RIGHT)

        ttk.Scale(
            detect_box,
            from_=5.0,
            to=80.0,
            variable=self.gap_var,
            command=self._on_gap_changed,
        ).pack(fill=tk.X, pady=(2, 2))

        labels_box = ttk.LabelFrame(parent, text="Plot Labels & Reference Library", padding=8)
        labels_box.pack(fill=tk.X, pady=(8, 0))

        ttk.Checkbutton(
            labels_box,
            text="Show peak markers",
            variable=self.show_markers_var,
            command=self._on_label_options_changed,
        ).pack(anchor=tk.W)

        ttk.Checkbutton(
            labels_box,
            text="Show wavenumber labels (cm⁻¹)",
            variable=self.show_wn_var,
            command=self._on_label_options_changed,
        ).pack(anchor=tk.W)

        ttk.Checkbutton(
            labels_box,
            text="Show assigned functional group labels",
            variable=self.show_groups_var,
            command=self._on_label_options_changed,
        ).pack(anchor=tk.W, pady=(0, 6))

        json_row = ttk.Frame(labels_box)
        json_row.pack(fill=tk.X)
        ttk.Label(json_row, textvariable=self.groups_file_var).pack(side=tk.LEFT)
        ttk.Button(json_row, text="Reload JSON", command=self._on_reload_groups).pack(
            side=tk.RIGHT
        )

        table_box = ttk.LabelFrame(parent, text="Detected Peaks (Selected Spectrum)", padding=6)
        table_box.pack(fill=tk.BOTH, expand=True, pady=(8, 0))

        columns = ("wn", "intensity", "group")
        self.peaks_tree = ttk.Treeview(
            table_box, columns=columns, show="headings", height=6
        )
        self.peaks_tree.heading("wn", text="cm⁻¹")
        self.peaks_tree.heading("intensity", text="Intensity")
        self.peaks_tree.heading("group", text="Functional Group")

        self.peaks_tree.column("wn", width=70, anchor=tk.E)
        self.peaks_tree.column("intensity", width=85, anchor=tk.E)
        self.peaks_tree.column("group", width=155, anchor=tk.W)

        tree_scroll = ttk.Scrollbar(
            table_box, orient=tk.VERTICAL, command=self.peaks_tree.yview
        )
        self.peaks_tree.configure(yscrollcommand=tree_scroll.set)

        self.peaks_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        tree_scroll.pack(side=tk.RIGHT, fill=tk.Y)

    # ------------------------------------------------------------------
    # Tab 3: Style & Export
    # ------------------------------------------------------------------
    def _build_tab_style_export(self, parent: ttk.Frame) -> None:
        curve_box = ttk.LabelFrame(parent, text="Selected Curve Style", padding=8)
        curve_box.pack(fill=tk.X)

        color_row = ttk.Frame(curve_box)
        color_row.pack(fill=tk.X, pady=(0, 6))
        ttk.Label(color_row, text="Color:").pack(side=tk.LEFT)
        ttk.Entry(color_row, textvariable=self.spec_color_var, width=10).pack(
            side=tk.LEFT, padx=(6, 6)
        )
        ttk.Button(color_row, text="Pick...", command=self._on_pick_color).pack(side=tk.LEFT)
        ttk.Button(color_row, text="Apply", command=self._on_apply_curve_style).pack(
            side=tk.RIGHT
        )

        lw_header = ttk.Frame(curve_box)
        lw_header.pack(fill=tk.X)
        ttk.Label(lw_header, text="Line Width:").pack(side=tk.LEFT)
        self.lw_val_label = ttk.Label(lw_header, text=f"{self.spec_lw_var.get():.1f}")
        self.lw_val_label.pack(side=tk.RIGHT)

        ttk.Scale(
            curve_box,
            from_=0.5,
            to=4.0,
            variable=self.spec_lw_var,
            command=self._on_lw_changed,
        ).pack(fill=tk.X, pady=(2, 6))

        ttk.Label(curve_box, text="Line Style:").pack(anchor=tk.W)
        ls_combo = ttk.Combobox(
            curve_box,
            textvariable=self.spec_ls_label_var,
            state="readonly",
            values=list(LINE_STYLE_MAP.keys()),
        )
        ls_combo.pack(fill=tk.X, pady=(2, 0))
        ls_combo.bind("<<ComboboxSelected>>", lambda _e: self._on_apply_curve_style())

        axes_style_box = ttk.LabelFrame(parent, text="Plot & Labels Style", padding=8)
        axes_style_box.pack(fill=tk.X, pady=(8, 0))

        toggles_row = ttk.Frame(axes_style_box)
        toggles_row.pack(fill=tk.X, pady=(0, 6))
        ttk.Checkbutton(
            toggles_row,
            text="Gridlines",
            variable=self.show_grid_var,
            command=self._on_global_style_changed,
        ).pack(side=tk.LEFT)
        ttk.Checkbutton(
            toggles_row,
            text="Legend",
            variable=self.show_legend_var,
            command=self._on_global_style_changed,
        ).pack(side=tk.LEFT, padx=(14, 0))

        fs_header = ttk.Frame(axes_style_box)
        fs_header.pack(fill=tk.X)
        ttk.Label(fs_header, text="Base Font Size:").pack(side=tk.LEFT)
        self.fs_val_label = ttk.Label(fs_header, text=f"{self.font_size_var.get():.0f}")
        self.fs_val_label.pack(side=tk.RIGHT)

        ttk.Scale(
            axes_style_box,
            from_=8.0,
            to=16.0,
            variable=self.font_size_var,
            command=self._on_font_size_changed,
        ).pack(fill=tk.X, pady=(2, 6))

        for label_text, var in [
            ("Title:", self.title_var),
            ("X Label:", self.xlabel_var),
            ("Y Label:", self.ylabel_var),
        ]:
            row = ttk.Frame(axes_style_box)
            row.pack(fill=tk.X, pady=(2, 0))
            ttk.Label(row, text=label_text, width=8).pack(side=tk.LEFT)
            ent = ttk.Entry(row, textvariable=var)
            ent.pack(side=tk.LEFT, fill=tk.X, expand=True)
            ent.bind("<Return>", lambda _e: self._on_global_style_changed())

        ttk.Button(
            axes_style_box, text="Apply Text Labels", command=self._on_global_style_changed
        ).pack(fill=tk.X, pady=(6, 0))

        export_box = ttk.LabelFrame(parent, text="Export", padding=8)
        export_box.pack(fill=tk.X, pady=(8, 0))

        dpi_row = ttk.Frame(export_box)
        dpi_row.pack(fill=tk.X, pady=(0, 6))
        ttk.Label(dpi_row, text="Figure DPI:").pack(side=tk.LEFT)
        dpi_combo = ttk.Combobox(
            dpi_row,
            textvariable=self.dpi_var,
            state="readonly",
            values=["150", "300", "600"],
            width=8,
        )
        dpi_combo.pack(side=tk.RIGHT)
        dpi_combo.bind("<<ComboboxSelected>>", lambda _e: self._on_dpi_changed())

        ttk.Button(
            export_box, text="Export Figure (PNG / SVG / PDF)...", command=self._on_export_figure
        ).pack(fill=tk.X, pady=(0, 4))
        ttk.Button(
            export_box, text="Export Detected Peaks (CSV)...", command=self._on_export_peaks_csv
        ).pack(fill=tk.X)

    def _sync_curve_controls_from_selected(self) -> None:
        sel = self.state["selected_index"]
        if sel is None or not (0 <= sel < len(self.state["spectra"])):
            return
        spec = self.state["spectra"][sel]
        color = spec.get("color") or DEFAULT_COLORS[sel % len(DEFAULT_COLORS)]
        lw = float(spec.get("line_width", 1.3))
        ls = spec.get("line_style", "-")

        self.spec_color_var.set(color)
        self.spec_lw_var.set(lw)
        self.lw_val_label.configure(text=f"{lw:.1f}")

        reverse_ls = {v: k for k, v in LINE_STYLE_MAP.items()}
        self.spec_ls_label_var.set(reverse_ls.get(ls, "Solid (-)"))

    # ------------------------------------------------------------------
    # Peak Detection & Table Sync
    # ------------------------------------------------------------------
    def _recompute_peaks(self) -> None:
        mode = self.state["peak_mode"]
        prom = float(self.state["prominence_ratio"])
        gap = float(self.state["min_wavenumber_gap"])
        scope = self.state["peak_scope"]
        selected_idx = self.state["selected_index"]
        groups = self.state["functional_groups"]

        for idx, spec in enumerate(self.state["spectra"]):
            should_detect = (
                idx == selected_idx
                if scope == "selected"
                else bool(spec.get("visible", True))
            )

            if should_detect and spec.get("x") and spec.get("y"):
                raw_peaks = detect_peaks(
                    x=spec["x"],
                    y=spec["y"],
                    mode=mode,
                    min_prominence_ratio=prom,
                    min_wavenumber_gap=gap,
                )
                spec["peaks"] = assign_functional_groups(raw_peaks, groups)
            else:
                spec["peaks"] = []

    def _rebuild_peaks_table(self) -> None:
        for item in self.peaks_tree.get_children():
            self.peaks_tree.delete(item)

        sel = self.state["selected_index"]
        if sel is None or not (0 <= sel < len(self.state["spectra"])):
            return

        peaks = self.state["spectra"][sel].get("peaks") or []
        for p in peaks:
            group_text = p.get("assigned_label") or "—"
            self.peaks_tree.insert(
                "",
                tk.END,
                values=(f"{p['wavenumber']:.1f}", f"{p['intensity']:.4f}", group_text),
            )

    # ------------------------------------------------------------------
    # Tab 1 Event Handlers
    # ------------------------------------------------------------------
    def _format_row_text(self, idx: int, spec: dict[str, Any]) -> str:
        eye = "[ON] " if spec.get("visible", True) else "[OFF] "
        label = spec.get("display_name") or spec.get("name") or f"Spectrum {idx + 1}"
        peak_count = len(spec.get("peaks") or [])
        return f"{eye}{label} ({spec.get('points', 0)} pts | {peak_count} peaks)"

    def _rebuild_listbox(self) -> None:
        self.listbox.delete(0, tk.END)
        for idx, spec in enumerate(self.state["spectra"]):
            self.listbox.insert(tk.END, self._format_row_text(idx, spec))

        sel = self.state["selected_index"]
        if sel is not None and 0 <= sel < len(self.state["spectra"]):
            self.listbox.selection_clear(0, tk.END)
            self.listbox.selection_set(sel)
            self.listbox.see(sel)
            spec = self.state["spectra"][sel]
            self.selected_visible_var.set(bool(spec.get("visible", True)))
            self.rename_var.set(spec.get("display_name") or spec.get("name") or "")
        else:
            self.rename_var.set("")

    def _on_add_files(self) -> None:
        file_paths = filedialog.askopenfilenames(
            title="Select Spectrum CSV File(s)",
            filetypes=[
                ("CSV / Text files", "*.csv *.txt *.dat"),
                ("All files", "*.*"),
            ],
        )
        if not file_paths:
            return

        added_count = 0
        for fp in file_paths:
            try:
                spec = load_spectrum_csv(fp)
            except Exception as exc:
                messagebox.showerror("Import Error", f"Could not load {Path(fp).name}:\n{exc}")
                continue

            if not spec["x"] or not spec["y"]:
                messagebox.showwarning(
                    "No Data Found",
                    f"No valid numeric (X, Y) rows were found in {Path(fp).name}.",
                )
                continue

            idx_after = len(self.state["spectra"])
            spec["display_name"] = spec["name"]
            spec["visible"] = True
            spec["peaks"] = []
            spec["color"] = DEFAULT_COLORS[idx_after % len(DEFAULT_COLORS)]
            spec["line_width"] = 1.3
            spec["line_style"] = "-"
            self.state["spectra"].append(spec)
            added_count += 1

        if added_count > 0:
            self.state["selected_index"] = len(self.state["spectra"]) - 1
            self.status_var.set(
                f"Loaded {added_count} file(s). Total spectra in session: {len(self.state['spectra'])}."
            )
            self._refresh_all()

    def _on_remove_selected(self) -> None:
        sel = self.state["selected_index"]
        if sel is None or not (0 <= sel < len(self.state["spectra"])):
            return

        removed = self.state["spectra"].pop(sel)
        if not self.state["spectra"]:
            self.state["selected_index"] = None
        else:
            self.state["selected_index"] = min(sel, len(self.state["spectra"]) - 1)

        self.status_var.set(f"Removed '{removed.get('display_name', removed.get('name'))}'.")
        self._refresh_all()

    def _on_listbox_select(self, _event: tk.Event[tk.Listbox] | None = None) -> None:
        selection = self.listbox.curselection()
        if not selection:
            return
        idx = int(selection[0])
        self.state["selected_index"] = idx
        spec = self.state["spectra"][idx]
        self.selected_visible_var.set(bool(spec.get("visible", True)))
        self.rename_var.set(spec.get("display_name") or spec.get("name") or "")
        self._sync_curve_controls_from_selected()
        if self.state["peak_scope"] == "selected":
            self._recompute_peaks()
            self._rebuild_listbox()
            self._refresh_plot()
        self._rebuild_peaks_table()

    def _on_toggle_selected_visible(self) -> None:
        sel = self.state["selected_index"]
        if sel is None or not (0 <= sel < len(self.state["spectra"])):
            return
        self.state["spectra"][sel]["visible"] = bool(self.selected_visible_var.get())
        self._refresh_all()

    def _on_apply_rename(self) -> None:
        sel = self.state["selected_index"]
        if sel is None or not (0 <= sel < len(self.state["spectra"])):
            return
        new_name = self.rename_var.get().strip()
        if new_name:
            self.state["spectra"][sel]["display_name"] = new_name
            self._refresh_all()

    def _on_axis_option_changed(self) -> None:
        self.state["invert_x"] = bool(self.invert_x_var.get())
        self.state["normalize_mode"] = self.norm_var.get()
        self._refresh_plot()

    def _on_offset_changed(self, value: str) -> None:
        val = round(float(value), 2)
        self.state["vertical_offset"] = val
        self.offset_val_label.configure(text=f"{val:.2f}")
        self._refresh_plot()

    def _on_reset_options(self) -> None:
        self.state["invert_x"] = True
        self.state["normalize_mode"] = "none"
        self.state["vertical_offset"] = 0.0

        self.invert_x_var.set(True)
        self.norm_var.set("none")
        self.offset_var.set(0.0)
        self.offset_val_label.configure(text="0.00")
        self._refresh_plot()

    # ------------------------------------------------------------------
    # Tab 2 Event Handlers
    # ------------------------------------------------------------------
    def _on_peak_params_changed(self) -> None:
        selected_label = self.peak_mode_label_var.get()
        self.state["peak_mode"] = (
            "minima" if "Transmittance" in selected_label else "maxima"
        )
        self.state["peak_scope"] = self.scope_var.get()
        self._recompute_peaks()
        self._rebuild_listbox()
        self._rebuild_peaks_table()
        self._refresh_plot()

    def _on_prominence_changed(self, value: str) -> None:
        val = round(float(value), 3)
        self.state["prominence_ratio"] = val
        self.prom_val_label.configure(text=f"{val:.2f}")
        self._recompute_peaks()
        self._rebuild_listbox()
        self._rebuild_peaks_table()
        self._refresh_plot()

    def _on_gap_changed(self, value: str) -> None:
        val = round(float(value), 1)
        self.state["min_wavenumber_gap"] = val
        self.gap_val_label.configure(text=f"{val:.0f}")
        self._recompute_peaks()
        self._rebuild_listbox()
        self._rebuild_peaks_table()
        self._refresh_plot()

    def _on_label_options_changed(self) -> None:
        self.state["show_markers"] = bool(self.show_markers_var.get())
        self.state["show_wavenumbers"] = bool(self.show_wn_var.get())
        self.state["show_group_labels"] = bool(self.show_groups_var.get())
        self._refresh_plot()

    def _on_reload_groups(self) -> None:
        groups = load_functional_groups(self.state["groups_path"])
        self.state["functional_groups"] = groups
        self.groups_file_var.set(
            f"{Path(self.state['groups_path']).name} ({len(groups)} rules)"
        )
        self._recompute_peaks()
        self._rebuild_peaks_table()
        self._refresh_plot()
        self.status_var.set(f"Reloaded {len(groups)} functional group rule(s).")

    # ------------------------------------------------------------------
    # Tab 3 Event Handlers (Style & Export)
    # ------------------------------------------------------------------
    def _on_pick_color(self) -> None:
        initial = self.spec_color_var.get().strip() or DEFAULT_COLORS[0]
        _, hex_color = colorchooser.askcolor(color=initial, title="Choose Curve Color")
        if hex_color:
            self.spec_color_var.set(hex_color)
            self._on_apply_curve_style()

    def _on_lw_changed(self, value: str) -> None:
        val = round(float(value), 1)
        self.lw_val_label.configure(text=f"{val:.1f}")
        self._on_apply_curve_style()

    def _on_apply_curve_style(self) -> None:
        sel = self.state["selected_index"]
        if sel is None or not (0 <= sel < len(self.state["spectra"])):
            return

        spec = self.state["spectra"][sel]
        color_text = self.spec_color_var.get().strip()
        if color_text:
            spec["color"] = color_text
        spec["line_width"] = float(self.spec_lw_var.get())
        spec["line_style"] = LINE_STYLE_MAP.get(self.spec_ls_label_var.get(), "-")
        self._refresh_plot()

    def _on_font_size_changed(self, value: str) -> None:
        val = round(float(value), 1)
        self.fs_val_label.configure(text=f"{val:.0f}")
        self.state["style"]["font_size"] = val
        self._refresh_plot()

    def _on_global_style_changed(self) -> None:
        self.state["style"]["show_grid"] = bool(self.show_grid_var.get())
        self.state["style"]["show_legend"] = bool(self.show_legend_var.get())
        self.state["style"]["font_size"] = float(self.font_size_var.get())
        self.state["style"]["title"] = self.title_var.get().strip()
        self.state["style"]["xlabel"] = self.xlabel_var.get().strip()
        self.state["style"]["ylabel"] = self.ylabel_var.get().strip()
        self._refresh_plot()

    def _on_dpi_changed(self) -> None:
        try:
            self.state["export_dpi"] = int(self.dpi_var.get())
        except ValueError:
            self.state["export_dpi"] = 300

    def _on_export_figure(self) -> None:
        out_path = filedialog.asksaveasfilename(
            title="Export Spectrum Figure",
            defaultextension=".png",
            filetypes=[
                ("PNG Image", "*.png"),
                ("SVG Vector", "*.svg"),
                ("PDF Document", "*.pdf"),
            ],
        )
        if not out_path:
            return

        dpi = int(self.state.get("export_dpi", 300))
        try:
            self.figure.savefig(out_path, dpi=dpi)
        except Exception as exc:
            messagebox.showerror("Export Error", f"Could not save figure:\n{exc}")
            return

        self.status_var.set(f"Saved figure to '{Path(out_path).name}' ({dpi} DPI).")

    def _on_export_peaks_csv(self) -> None:
        rows: list[list[Any]] = []
        for spec in self.state["spectra"]:
            spec_label = spec.get("display_name") or spec.get("name") or "Spectrum"
            for p in spec.get("peaks") or []:
                rows.append(
                    [
                        spec_label,
                        p["wavenumber"],
                        p["intensity"],
                        p.get("assigned_label") or "",
                    ]
                )

        if not rows:
            messagebox.showinfo(
                "No Peaks to Export",
                "No detected peaks are currently available to export.",
            )
            return

        out_path = filedialog.asksaveasfilename(
            title="Export Detected Peaks CSV",
            defaultextension=".csv",
            filetypes=[("CSV File", "*.csv")],
        )
        if not out_path:
            return

        try:
            with open(out_path, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(["spectrum", "wavenumber_cm-1", "intensity", "functional_group"])
                writer.writerows(rows)
        except Exception as exc:
            messagebox.showerror("Export Error", f"Could not export peaks CSV:\n{exc}")
            return

        self.status_var.set(f"Exported {len(rows)} peak row(s) to '{Path(out_path).name}'.")

    # ------------------------------------------------------------------
    # Plot & Full Refresh
    # ------------------------------------------------------------------
    def _refresh_plot(self) -> None:
        draw_spectra(
            figure=self.figure,
            spectra=self.state["spectra"],
            invert_x=self.state["invert_x"],
            normalize_mode=self.state["normalize_mode"],
            vertical_offset=self.state["vertical_offset"],
            peak_mode=self.state["peak_mode"],
            show_markers=self.state["show_markers"],
            show_wavenumbers=self.state["show_wavenumbers"],
            show_group_labels=self.state["show_group_labels"],
            style=self.state["style"],
        )
        self.canvas.draw_idle()

    def _refresh_all(self) -> None:
        self._recompute_peaks()
        self._rebuild_listbox()
        self._rebuild_peaks_table()
        self._sync_curve_controls_from_selected()
        self._refresh_plot()