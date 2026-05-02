"""PyQt5 GUI for absorption imaging analysis."""

import sys
import threading
import logging
from pathlib import Path
from typing import Optional

from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QGroupBox, QGridLayout, QComboBox,
    QDoubleSpinBox, QFileDialog, QTextEdit, QSplitter, QMessageBox,
)
from PyQt5.QtCore import Qt, pyqtSignal, QObject
from PyQt5.QtGui import QFont

import matplotlib
matplotlib.use("Qt5Agg")
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
import numpy as np

from .species import SPECIES_PRESETS, get_species
from .config import CameraConfig, ImagingConfig
from .io import load_image_set
from .pipeline import process_shot
from .datatypes import ShotResult

logger = logging.getLogger(__name__)


class WorkerSignals(QObject):
    result_ready = pyqtSignal(object)  # ShotResult
    error = pyqtSignal(str)


class ResultPlot(FigureCanvas):
    """Displays OD image, fit overlay, and marginal projections."""

    def __init__(self, parent=None):
        self.fig = Figure(figsize=(10, 8))
        super().__init__(self.fig)
        self.setParent(parent)

    def plot_result(self, result: ShotResult):
        self.fig.clear()
        od = result.od.od_image
        fit_img = result.fit.fit_image

        # Use ROI region for fit overlay
        roi = result.od.roi_used
        if roi:
            x0, y0, x1, y1 = roi
            od_roi = od[y0:y1, x0:x1]
        else:
            od_roi = od

        # 2x2 layout: OD image | fit image | x-marginal | y-marginal
        ax_od = self.fig.add_subplot(221)
        ax_fit = self.fig.add_subplot(222)
        ax_mx = self.fig.add_subplot(223)
        ax_my = self.fig.add_subplot(224)

        # OD image
        im = ax_od.imshow(od, cmap="inferno", origin="lower", aspect="equal")
        self.fig.colorbar(im, ax=ax_od, fraction=0.046)
        ax_od.set_title("Optical Depth")

        # Mark fit center
        cx = result.fit.center_x_px
        cy = result.fit.center_y_px
        ax_od.plot(cx, cy, "w+", markersize=12, markeredgewidth=2)

        # Fit image
        ax_fit.imshow(fit_img, cmap="inferno", origin="lower", aspect="equal",
                      vmin=0, vmax=od_roi.max())
        ax_fit.set_title("Gaussian Fit")

        # X marginal (sum along y)
        x_data = od_roi.sum(axis=0)
        x_fit = fit_img.sum(axis=0)
        ax_mx.plot(x_data, "b-", alpha=0.7, label="Data")
        ax_mx.plot(x_fit, "r--", linewidth=2, label="Fit")
        ax_mx.set_xlabel("X (px)")
        ax_mx.set_ylabel("Sum OD")
        ax_mx.legend(fontsize=8)
        ax_mx.set_title("X Projection")

        # Y marginal (sum along x)
        y_data = od_roi.sum(axis=1)
        y_fit = fit_img.sum(axis=1)
        ax_my.plot(y_data, "b-", alpha=0.7, label="Data")
        ax_my.plot(y_fit, "r--", linewidth=2, label="Fit")
        ax_my.set_xlabel("Y (px)")
        ax_my.set_ylabel("Sum OD")
        ax_my.legend(fontsize=8)
        ax_my.set_title("Y Projection")

        self.fig.tight_layout()
        self.draw()


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Cold Atom Imaging Analyzer")
        self.resize(1100, 750)

        self.signals = WorkerSignals()
        self.signals.result_ready.connect(self._on_result)
        self.signals.error.connect(self._on_error)

        self._probe_path: Optional[str] = None
        self._ref_path: Optional[str] = None
        self._dark_path: Optional[str] = None

        self._build_ui()

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        layout = QHBoxLayout(central)

        # --- Left: controls ---
        left = QWidget()
        left.setMaximumWidth(320)
        left_layout = QVBoxLayout(left)

        # Species
        species_group = QGroupBox("Species")
        sg_layout = QVBoxLayout()
        self.species_combo = QComboBox()
        seen = set()
        for key, sp in sorted(SPECIES_PRESETS.items()):
            if sp.name not in seen:
                self.species_combo.addItem(f"{sp.symbol} ({sp.name})", key)
                seen.add(sp.name)
        sg_layout.addWidget(self.species_combo)
        species_group.setLayout(sg_layout)
        left_layout.addWidget(species_group)

        # Camera
        cam_group = QGroupBox("Camera")
        cg_layout = QGridLayout()
        cg_layout.addWidget(QLabel("Pixel size (um):"), 0, 0)
        self.spin_pixel = QDoubleSpinBox()
        self.spin_pixel.setRange(0.1, 100.0)
        self.spin_pixel.setValue(6.45)
        self.spin_pixel.setDecimals(2)
        cg_layout.addWidget(self.spin_pixel, 0, 1)

        cg_layout.addWidget(QLabel("Magnification:"), 1, 0)
        self.spin_mag = QDoubleSpinBox()
        self.spin_mag.setRange(0.01, 100.0)
        self.spin_mag.setValue(1.0)
        self.spin_mag.setDecimals(2)
        cg_layout.addWidget(self.spin_mag, 1, 1)
        cam_group.setLayout(cg_layout)
        left_layout.addWidget(cam_group)

        # Files
        file_group = QGroupBox("Images")
        fg_layout = QVBoxLayout()

        self.lbl_probe = QLabel("Probe: (none)")
        btn_probe = QPushButton("Select Probe")
        btn_probe.clicked.connect(lambda: self._select_file("probe"))
        fg_layout.addWidget(self.lbl_probe)
        fg_layout.addWidget(btn_probe)

        self.lbl_ref = QLabel("Reference: (none)")
        btn_ref = QPushButton("Select Reference")
        btn_ref.clicked.connect(lambda: self._select_file("reference"))
        fg_layout.addWidget(self.lbl_ref)
        fg_layout.addWidget(btn_ref)

        self.lbl_dark = QLabel("Dark: (none)")
        btn_dark = QPushButton("Select Dark (optional)")
        btn_dark.clicked.connect(lambda: self._select_file("dark"))
        fg_layout.addWidget(self.lbl_dark)
        fg_layout.addWidget(btn_dark)

        file_group.setLayout(fg_layout)
        left_layout.addWidget(file_group)

        # Analyze button
        self.btn_analyze = QPushButton("ANALYZE")
        self.btn_analyze.setFont(QFont("sans-serif", 14, QFont.Bold))
        self.btn_analyze.setMinimumHeight(50)
        self.btn_analyze.setStyleSheet("background-color: #2ecc71; color: white;")
        self.btn_analyze.clicked.connect(self._on_analyze)
        left_layout.addWidget(self.btn_analyze)

        # Results text
        self.result_text = QTextEdit()
        self.result_text.setReadOnly(True)
        self.result_text.setFont(QFont("monospace", 10))
        self.result_text.setMaximumHeight(200)
        left_layout.addWidget(self.result_text)

        left_layout.addStretch()
        layout.addWidget(left)

        # --- Right: plots ---
        self.plot = ResultPlot()
        layout.addWidget(self.plot)

    def _select_file(self, role: str):
        path, _ = QFileDialog.getOpenFileName(
            self, f"Select {role} image", "",
            "Images (*.bmp *.tiff *.tif *.png *.fits *.fit);;All files (*)",
        )
        if not path:
            return
        name = Path(path).name
        if role == "probe":
            self._probe_path = path
            self.lbl_probe.setText(f"Probe: {name}")
        elif role == "reference":
            self._ref_path = path
            self.lbl_ref.setText(f"Reference: {name}")
        elif role == "dark":
            self._dark_path = path
            self.lbl_dark.setText(f"Dark: {name}")

    def _on_analyze(self):
        if not self._probe_path or not self._ref_path:
            QMessageBox.warning(self, "Missing files",
                                "Select at least probe and reference images.")
            return

        self.btn_analyze.setEnabled(False)
        self.result_text.setText("Analyzing...")

        species_key = self.species_combo.currentData()
        config = ImagingConfig(
            species=species_key,
            camera=CameraConfig(
                pixel_size_um=self.spin_pixel.value(),
                magnification=self.spin_mag.value(),
            ),
        )

        def worker():
            try:
                probe, ref, dark = load_image_set(
                    self._probe_path, self._ref_path, self._dark_path
                )
                result = process_shot(probe, ref, dark, config)
                self.signals.result_ready.emit(result)
            except Exception as e:
                self.signals.error.emit(str(e))

        threading.Thread(target=worker, daemon=True).start()

    def _on_result(self, result: ShotResult):
        self.btn_analyze.setEnabled(True)
        self.result_text.setText(
            result.fit.summary()
            + f"\n\nSpecies: {result.species.name}\n"
            + f"sigma0: {result.species.sigma0:.4e} m^2\n"
            + f"Pixel: {result.effective_pixel_um:.2f} um/px"
        )
        self.plot.plot_result(result)

    def _on_error(self, msg: str):
        self.btn_analyze.setEnabled(True)
        self.result_text.setText(f"ERROR: {msg}")
        QMessageBox.critical(self, "Error", msg)


def run_gui():
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())
