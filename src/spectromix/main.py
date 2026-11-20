"""Entry point for the FTIR Spectrum Viewer application."""

from __future__ import annotations

import tkinter as tk

from spectromix.ui import SpectrumApp


def main() -> None:
    root = tk.Tk()
    SpectrumApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()