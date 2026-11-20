# FTIR Spectrum Viewer & Peak Tagger

A modular Python 3 desktop application for loading, overlaying, visualizing, and annotating ATR-FTIR spectra from raw spectrophotometer CSV/text exports. Built with **Tkinter (`ttk`)** and **Matplotlib**, it separates core spectroscopy processing from the graphical interface so experimental data can be inspected interactively or processed via the command line.

---

## Key Features

### Smart CSV Parsing (Zero-Config Import)
* **Automatic format detection:** Detects delimiters (`,`, `;`, tab, space) and European decimal commas (e.g., `3999,50`) while ignoring commas sandwiched inside numeric values.
* **Header skipping:** Identifies the start of spectral data by locating a consecutive streak of numeric rows, safely bypassing instrument metadata headers.

### Tab 1: Data & Axes
* **Multi-spectrum overlay:** Load multiple `.csv`, `.txt`, or `.dat` files simultaneously.
* **List management:** Toggle individual spectra on/off, remove files, and edit legend display names.
* **FTIR axis conventions:** One-click X-axis inversion (`4000 → 400 cm⁻¹`).
* **Normalization & stacking:** Switch between raw intensity (`none`), `minmax` (0–1), and `max` (peak = 1) normalization without mutating source data, plus a vertical offset slider for waterfall comparison.

### Tab 2: Peaks & Tags
* **Absorbance & Transmittance modes:** Detect upward absorption peaks (`maxima`) or downward transmittance dips (`minima`).
* **Interactive sensitivity tuning:** Adjust minimum prominence ratio and minimum peak spacing (`cm⁻¹`) in real time to filter baseline noise.
* **Functional group assignment:** Automatically matches detected peaks against an editable external `functional_groups.json` library with live **Reload JSON** support.
* **Peak summary table:** Displays wavenumber (`cm⁻¹`), intensity, and assigned functional group for the selected spectrum alongside optional on-plot markers and labels.

### Tab 3: Style & Export
* **Per-curve styling:** Customize color (via color picker or hex code), line width, and line style (solid, dashed, dotted, dash-dot) for each spectrum.
* **Figure typography & layout:** Toggle gridlines and legend, scale base font sizes, and set custom titles and axis labels.
* **Exports:** Save publication-ready figures (`.png`, `.svg`, `.pdf`) at `150`, `300`, or `600` DPI, and export detected peak tables to `.csv`.

---

## Project Structure

The codebase follows a clean separation of concerns between computation, plotting, and UI state:

```text
spectromix/
├── pyproject.toml
├── requirements.txt
├── README.md
├── .gitignore
├── examples/
│   └── cs.csv
└── src/
    └── spectromix/
        ├── __init__.py          
        ├── main.py
        ├── ui.py
        ├── plotter.py
        ├── spectroscopy.py
        └── functional_groups.json
```

---

## Requirements & Installation

* **Python 3.10+**
* **Matplotlib** (`matplotlib`)
* **Tkinter** (included with standard Python installations on Windows and macOS)

Install Matplotlib in your active Python or Conda environment:

```bash
pip install matplotlib
```

*(or with Conda: `conda install matplotlib`)*

> **Linux users:** If `tkinter` is not bundled with your system Python, install it via your package manager (e.g., `sudo apt-get install python3-tk` on Ubuntu/Debian or `sudo dnf install python3-tkinter` on Fedora).

---

## Usage

### Launch the Desktop GUI
Run the application from the project directory:

```bash
python main.py
```

1. Open **Tab 1 (`Data & Axes`)** and click **Add CSV(s)...** to load one or more spectrum files.
2. Switch to **Tab 2 (`Peaks & Tags`)** to select **Absorbance (maxima)** or **Transmittance (minima)** and adjust peak prominence and spacing sliders.
3. Use **Tab 3 (`Style & Export`)** to customize colors, labels, and line styles, then export your figure or peak table.

### Standalone Command-Line Test (`spectroscopy.py`)
Because `spectroscopy.py` has zero GUI dependencies, you can test parsing and peak tagging directly in the terminal:

```bash
python spectroscopy.py examples/cs.csv functional_groups.json
```

---

## Customizing `functional_groups.json`

Reference band assignments are stored externally in `functional_groups.json` as a list of JSON objects:

```json
[
  {
    "label": "O-H / N-H",
    "min_cm": 3150,
    "max_cm": 3600,
    "vibration": "Hydrogen-bonded O-H and N-H stretching"
  },
  {
    "label": "Amide I (C=O)",
    "min_cm": 1635,
    "max_cm": 1695,
    "vibration": "Amide I C=O stretching"
  }
]
```

* **`label`**: Short display name shown on plot annotations and in the peak table.
* **`min_cm` / `max_cm`**: Inclusive wavenumber interval in `cm⁻¹`.
* **`vibration`**: Optional descriptive note on the vibrational mode.

After editing and saving `functional_groups.json`, click **Reload JSON** in **Tab 2** to update assignments immediately without restarting the application.

---

## Notes on Spectral Interpretation

* **Peak detection accuracy:** Peak detection is always computed on each spectrum's unshifted intensity data before visual vertical offsets are applied, ensuring reported intensities remain faithful to the source file.
* **Vertical offsets:** Use vertical stacking for qualitative comparison of band positions and shapes across overlaid samples; set the offset back to `0.00` when comparing relative peak intensities.