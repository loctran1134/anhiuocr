import os
import sys
import re
import json
from datetime import datetime
from typing import List, Dict, Any

# Windows console & encoding setup
if hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except Exception:
        pass

# Configure local models directory for 100% offline bundled usage (Supports PyInstaller .exe)
if getattr(sys, 'frozen', False):
    candidates = [
        getattr(sys, '_MEIPASS', ''),
        os.path.join(os.path.dirname(sys.executable), '_internal'),
        os.path.dirname(sys.executable)
    ]
else:
    candidates = [os.path.dirname(os.path.abspath(__file__))]

for c in candidates:
    if c:
        m_dir = os.path.join(c, 'models')
        if os.path.exists(m_dir):
            os.environ["PADDLE_PDX_CACHE_HOME"] = m_dir
            break

# Windows DLL directory fix for PyTorch / Paddle
try:
    import torch
    torch_lib = os.path.join(os.path.dirname(torch.__file__), 'lib')
    if os.path.exists(torch_lib):
        try:
            os.add_dll_directory(torch_lib)
        except Exception:
            pass
except Exception:
    pass

import cv2
import numpy as np
import pandas as pd

from ocr_engine import TimemarkOCREngine

_GLOBAL_OCR_ENGINE = None

def get_ocr_engine() -> TimemarkOCREngine:
    global _GLOBAL_OCR_ENGINE
    if _GLOBAL_OCR_ENGINE is None:
        _GLOBAL_OCR_ENGINE = TimemarkOCREngine()
    return _GLOBAL_OCR_ENGINE

from PySide6.QtCore import Qt, QThread, Signal, QByteArray
from PySide6.QtGui import (
    QIcon, QPixmap, QImage, QPainter, QColor, QFont
)
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QLineEdit, QTableWidget, QTableWidgetItem,
    QHeaderView, QFileDialog, QMessageBox, QScrollArea, QFrame,
    QProgressBar, QDialog, QAbstractItemView, QGridLayout, QComboBox,
    QTextEdit, QTabWidget, QProgressDialog
)
from PySide6.QtSvg import QSvgRenderer

# ----------------- VECTOR SVG ICONS (NO EMOJIS) -----------------
SVG_CAMERA = '''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M14.5 4h-5L7 7H4a2 2 0 0 0-2 2v9a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2V9a2 2 0 0 0-2-2h-3l-2.5-3z"/><circle cx="12" cy="13" r="3"/></svg>'''

SVG_CLOUD_UPLOAD = '''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M4 14.899A7 7 0 1 1 15.71 8h1.79a4.5 4.5 0 0 1 2.5 8.242"/><path d="M12 12v9"/><path d="m16 16-4-4-4 4"/></svg>'''

SVG_IMAGE = '''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect width="18" height="18" x="3" y="3" rx="2" ry="2"/><circle cx="9" cy="9" r="2"/><path d="m21 15-3.086-3.086a2 2 0 0 0-2.828 0L6 21"/></svg>'''

SVG_CHECK_CIRCLE = '''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/><polyline points="22 4 12 14.01 9 11.01"/></svg>'''

SVG_ALERT_TRIANGLE = '''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3Z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg>'''

SVG_MAP_PIN = '''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M20 10c0 6-8 12-8 12s-8-6-8-12a8 8 0 0 1 16 0Z"/><circle cx="12" cy="10" r="3"/></svg>'''

SVG_SPARKLE = '''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="m12 3-1.912 5.813a2 2 0 0 1-1.275 1.275L3 12l5.813 1.912a2 2 0 0 1 1.275 1.275L12 21l1.912-5.813a2 2 0 0 1 1.275-1.275L21 12l-5.813-1.912a2 2 0 0 1-1.275-1.275L12 3Z"/></svg>'''

def get_avatar_initials(name: str) -> str:
    if not name or name == "--":
        return "?"
    words = name.strip().split()
    if len(words) == 1:
        return words[0][:2].upper()
    return (words[0][0] + words[-1][0]).upper()

AVATAR_COLORS = [
    ("#eff6ff", "#1d4ed8", "#bfdbfe"),  # Blue
    ("#fdf4ff", "#a21caf", "#f5d0fe"),  # Fuchsia
    ("#f0fdf4", "#15803d", "#bbf7d0"),  # Green
    ("#fff7ed", "#c2410c", "#fed7aa"),  # Orange
    ("#faf5ff", "#7e22ce", "#e9d5ff"),  # Purple
    ("#f0fdfa", "#0f766e", "#99f6e4"),  # Teal
]

def get_avatar_color(name: str):
    h = sum(ord(c) for c in (name or ""))
    return AVATAR_COLORS[h % len(AVATAR_COLORS)]

SVG_EXCEL = '''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" x2="12" y1="15" y2="3"/></svg>'''

SVG_TRASH = '''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 6h18"/><path d="M19 6v14c0 1-1 2-2 2H7c-1 0-2-1-2-2V6"/><path d="M8 6V4c0-1 1-2 2-2h4c1 0 2 1 2 2v2"/></svg>'''

SVG_EMPTY_ILLUST = '''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 120 120" fill="none">
<rect x="25" y="25" width="55" height="55" rx="8" fill="#EFF6FF" stroke="#BFDBFE" stroke-width="2.5"/>
<path d="M35 62L46 50C47.5 48.5 50 48.5 51.5 50L68 68" stroke="#93C5FD" stroke-width="2.5" stroke-linecap="round"/>
<circle cx="45" cy="42" r="5" fill="#93C5FD"/>
<circle cx="78" cy="78" r="18" fill="white" stroke="#2563EB" stroke-width="3"/>
<line x1="91" y1="91" x2="105" y2="105" stroke="#2563EB" stroke-width="4" stroke-linecap="round"/>
<line x1="72" y1="78" x2="84" y2="78" stroke="#93C5FD" stroke-width="2" stroke-linecap="round"/>
</svg>'''

def get_svg_pixmap(svg_template: str, color: str = "#2563eb", width: int = 24, height: int = 24) -> QPixmap:
    svg_str = svg_template.replace("{color}", color)
    renderer = QSvgRenderer(QByteArray(svg_str.encode('utf-8')))
    pix = QPixmap(width, height)
    pix.fill(Qt.transparent)
    painter = QPainter(pix)
    renderer.render(painter)
    painter.end()
    return pix

def get_svg_icon(svg_template: str, color: str = "#2563eb", size: int = 20) -> QIcon:
    return QIcon(get_svg_pixmap(svg_template, color, size, size))

def safe_load_pixmap(file_path: str, max_w: int = 80, max_h: int = 80) -> QPixmap:
    try:
        with open(file_path, 'rb') as f:
            data = f.read()
        qimg = QImage()
        qimg.loadFromData(data)
        if qimg.isNull():
            return QPixmap()
        return QPixmap.fromImage(qimg).scaled(max_w, max_h, Qt.KeepAspectRatio, Qt.SmoothTransformation)
    except Exception:
        return QPixmap()

def cv2_to_qpixmap(cv_img: np.ndarray, max_w: int = None, max_h: int = None) -> QPixmap:
    try:
        if cv_img is None or cv_img.size == 0:
            return QPixmap()
        h, w = cv_img.shape[:2]
        rgb = cv2.cvtColor(cv_img, cv2.COLOR_BGR2RGB)
        bytes_per_line = 3 * w
        qimg = QImage(rgb.data, w, h, bytes_per_line, QImage.Format_RGB888)
        pix = QPixmap.fromImage(qimg)
        if max_w and max_h:
            return pix.scaled(max_w, max_h, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        return pix
    except Exception:
        return QPixmap()

def safe_read_cv2(file_path: str):
    try:
        from PIL import Image, ImageOps
        pil_img = Image.open(file_path)
        pil_img = ImageOps.exif_transpose(pil_img)
        return cv2.cvtColor(np.array(pil_img.convert("RGB")), cv2.COLOR_RGB2BGR)
    except Exception:
        pass
    try:
        with open(file_path, 'rb') as f:
            data = f.read()
        nparr = np.frombuffer(data, np.uint8)
        return cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    except Exception:
        return None

def format_clean_address(addr: str) -> str:
    if not addr or "không tìm thấy" in addr.lower() or "không xác định" in addr.lower():
        return addr if addr else "Chưa xác định địa chỉ"
    cleaned = re.sub(r'[\,\s]*\d{1,2}\.\d{4,8}[\s\?°]*[nN]?[\,\s]+\d{2,3}\.\d{4,8}[\s\?°\-]*[eE]?', '', addr)
    cleaned = re.sub(r'^(?:xã\s+)?địa\s*chỉ\s*[:\-\s]*', '', cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r'^(?:đ\/c|address|location)\s*[:\-\s]*', '', cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r'^[a-zA-Z0-9][\.\,]\s*', '', cleaned.strip())
    parts = [p.strip() for p in cleaned.split(',')]
    formatted = []
    for p in parts:
        if p:
            words = p.split()
            formatted.append(" ".join(w.capitalize() for w in words))
    return ", ".join(formatted) if formatted else cleaned


# ----------------- OCR ENGINE PRELOADER -----------------
class EnginePreloadThread(QThread):
    def run(self):
        try:
            get_ocr_engine()
        except Exception:
            pass


# ----------------- OCR WORKER THREAD -----------------
class OCRWorkerThread(QThread):
    progress_update = Signal(dict)
    finished_success = Signal(dict)
    finished_error = Signal(str)

    def __init__(self, file_paths: List[str]):
        super().__init__()
        self.file_paths = file_paths

    def run(self):
        try:
            engine = get_ocr_engine()

            image_items = []
            for path in self.file_paths:
                img = safe_read_cv2(path)
                if img is not None:
                    image_items.append({
                        "filename": os.path.basename(path),
                        "filepath": path,
                        "image": img
                    })

            if not image_items:
                self.finished_error.emit("Không thể tải các file ảnh đã chọn!")
                return

            def on_progress(p_data):
                self.progress_update.emit(p_data)

            res = engine.process_images(image_items, progress_callback=on_progress)
            self.finished_success.emit(res)
        except Exception as e:
            import traceback
            traceback.print_exc()
            self.finished_error.emit(str(e))


# ----------------- THUMBNAIL CARD WIDGET -----------------
class ThumbnailCard(QFrame):
    delete_clicked = Signal(str)

    def __init__(self, file_path: str, parent=None):
        super().__init__(parent)
        self.file_path = file_path
        self.setFixedSize(72, 72)
        self.setStyleSheet("""
            ThumbnailCard {
                background-color: #f1f5f9;
                border: 1px solid #cbd5e1;
                border-radius: 8px;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(3, 3, 3, 3)

        self.img_label = QLabel()
        self.img_label.setAlignment(Qt.AlignCenter)
        self.img_label.setStyleSheet("border: none; background: transparent;")
        pix = safe_load_pixmap(file_path, 64, 64)
        if not pix.isNull():
            self.img_label.setPixmap(pix)
        else:
            self.img_label.setText("IMG")
        layout.addWidget(self.img_label)

        self.close_btn = QPushButton("×", self)
        self.close_btn.setFixedSize(18, 18)
        self.close_btn.move(52, 2)
        self.close_btn.setCursor(Qt.PointingHandCursor)
        self.close_btn.setStyleSheet("""
            QPushButton {
                background-color: rgba(15, 23, 42, 0.75);
                color: #ffffff;
                font-size: 13px;
                font-weight: bold;
                border: none;
                border-radius: 9px;
                padding-bottom: 2px;
            }
            QPushButton:hover {
                background-color: #ef4444;
            }
        """)
        self.close_btn.clicked.connect(lambda: self.delete_clicked.emit(self.file_path))


# ----------------- DROPZONE WIDGET -----------------
class DropZoneWidget(QFrame):
    files_dropped = Signal(list)
    browse_clicked = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.setMinimumHeight(140)
        self.setObjectName("DropZone")
        self.setStyleSheet("""
            QFrame#DropZone {
                background-color: #f8fafc;
                border: 2px dashed #cbd5e1;
                border-radius: 10px;
            }
            QFrame#DropZone:hover {
                background-color: #f1f5f9;
                border-color: #3b82f6;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(6)
        layout.setAlignment(Qt.AlignCenter)

        self.icon_label = QLabel()
        self.icon_label.setAlignment(Qt.AlignCenter)
        self.icon_label.setStyleSheet("border: none; background: transparent;")
        self.icon_label.setPixmap(get_svg_pixmap(SVG_CLOUD_UPLOAD, "#94a3b8", 36, 36))
        layout.addWidget(self.icon_label)

        self.prompt_label = QLabel("Kéo ảnh vào đây hoặc")
        self.prompt_label.setAlignment(Qt.AlignCenter)
        self.prompt_label.setStyleSheet("color: #475569; font-size: 13px; font-weight: 500; border: none; background: transparent;")
        layout.addWidget(self.prompt_label)

        self.btn_browse = QPushButton("  Chọn ảnh")
        self.btn_browse.setIcon(get_svg_icon(SVG_IMAGE, "#2563eb", 16))
        self.btn_browse.setCursor(Qt.PointingHandCursor)
        self.btn_browse.setStyleSheet("""
            QPushButton {
                background-color: #ffffff;
                color: #2563eb;
                border: 1px solid #bfdbfe;
                border-radius: 6px;
                padding: 6px 16px;
                font-size: 13px;
                font-weight: 600;
            }
            QPushButton:hover {
                background-color: #eff6ff;
                border-color: #2563eb;
            }
        """)
        self.btn_browse.clicked.connect(self.browse_clicked.emit)
        layout.addWidget(self.btn_browse, alignment=Qt.AlignCenter)

        self.hint_label = QLabel("Hỗ trợ JPG, PNG. Tối đa 100 ảnh.")
        self.hint_label.setAlignment(Qt.AlignCenter)
        self.hint_label.setStyleSheet("color: #94a3b8; font-size: 11px; border: none; background: transparent;")
        layout.addWidget(self.hint_label)

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
            self.setStyleSheet("""
                QFrame#DropZone {
                    background-color: #eff6ff;
                    border: 2px dashed #2563eb;
                    border-radius: 10px;
                }
            """)

    def dragLeaveEvent(self, event):
        self.setStyleSheet("""
            QFrame#DropZone {
                background-color: #f8fafc;
                border: 2px dashed #cbd5e1;
                border-radius: 10px;
            }
        """)

    def dropEvent(self, event):
        self.setStyleSheet("""
            QFrame#DropZone {
                background-color: #f8fafc;
                border: 2px dashed #cbd5e1;
                border-radius: 10px;
            }
        """)
        files = []
        for url in event.mimeData().urls():
            fpath = url.toLocalFile()
            if fpath.lower().endswith(('.jpg', '.jpeg', '.png', '.webp', '.bmp')):
                files.append(fpath)
        if files:
            self.files_dropped.emit(files)


# ----------------- IMAGE VIEWER MODAL (LIGHTBOX) -----------------
class ImageViewerDialog(QDialog):
    def __init__(self, image_path: str, annotated_img: np.ndarray = None, info: dict = None, parent=None):
        super().__init__(parent)
        self.image_path = image_path
        self.info = info or {}
        self.annotated_img = annotated_img
        self.show_tracking = True  # Mặc định bật chế độ tracking màu xanh lá

        # Nếu chưa có ảnh annotated, thử lấy từ cache engine
        if self.annotated_img is None:
            try:
                engine = get_ocr_engine()
                self.annotated_img = engine.get_annotated_preview(image_path)
                if self.annotated_img is None and os.path.exists(image_path):
                    raw_bgr = safe_read_cv2(image_path)
                    if raw_bgr is not None:
                        res = engine.extract_timemark_info(raw_bgr)
                        self.annotated_img = res.get("annotated_image")
                        if not self.info:
                            self.info = res
            except Exception:
                pass

        fn_base = os.path.basename(image_path)
        short_title_fn = fn_base if len(fn_base) <= 30 else (fn_base[:14] + "..." + fn_base[-12:])
        self.setWindowTitle(f"Xem ảnh & Track OCR: {short_title_fn}")
        self.resize(980, 740)
        self.setMinimumSize(700, 500)
        self.setStyleSheet("""
            QDialog {
                background-color: #1e293b;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 14, 18, 16)
        layout.setSpacing(10)

        # Top Bar
        top_bar = QHBoxLayout()
        top_bar.setSpacing(12)

        lbl_fname = QLabel(short_title_fn)
        lbl_fname.setToolTip(fn_base)
        lbl_fname.setStyleSheet("color: #f8fafc; font-size: 14px; font-weight: 700; border: none; background: transparent;")
        top_bar.addWidget(lbl_fname)

        top_bar.addStretch()

        # Nút chuyển đổi chế độ xem: ROI Tracking Xanh Lá vs Ảnh Gốc
        self.btn_toggle_mode = QPushButton("● Đang xem: Vùng ROI & Track chữ")
        self.btn_toggle_mode.setCursor(Qt.PointingHandCursor)
        self.btn_toggle_mode.setStyleSheet("""
            QPushButton {
                background-color: #064e3b;
                color: #a7f3d0;
                border: 1px solid #059669;
                border-radius: 6px;
                padding: 6px 14px;
                font-weight: 700;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #047857;
                color: #ffffff;
            }
        """)
        self.btn_toggle_mode.clicked.connect(self.toggle_tracking_mode)
        top_bar.addWidget(self.btn_toggle_mode)

        btn_close = QPushButton("Đóng (Esc)")
        btn_close.setCursor(Qt.PointingHandCursor)
        btn_close.setStyleSheet("""
            QPushButton {
                background-color: #1e293b;
                color: #f8fafc;
                border: 1px solid #334155;
                border-radius: 6px;
                padding: 6px 16px;
                font-weight: 600;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #334155;
                border-color: #475569;
            }
        """)
        btn_close.clicked.connect(self.accept)
        top_bar.addWidget(btn_close)
        layout.addLayout(top_bar)

        # Image Scroll Display
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("""
            QScrollArea {
                border: 1px solid #475569;
                border-radius: 8px;
                background-color: #334155;
            }
        """)

        container = QWidget()
        container.setStyleSheet("background-color: transparent;")
        c_layout = QVBoxLayout(container)
        c_layout.setContentsMargins(10, 10, 10, 10)
        c_layout.setAlignment(Qt.AlignCenter)

        self.img_label = QLabel()
        self.img_label.setAlignment(Qt.AlignCenter)
        self.img_label.setStyleSheet("border: none; background: transparent;")
        c_layout.addWidget(self.img_label)
        scroll.setWidget(container)
        layout.addWidget(scroll, stretch=1)

        # Bottom HUD Info Bar
        info_bar = QFrame()
        info_bar.setStyleSheet("""
            QFrame {
                background-color: #1e293b;
                border: 1px solid #334155;
                border-radius: 8px;
            }
        """)
        ib_layout = QHBoxLayout(info_bar)
        ib_layout.setContentsMargins(14, 8, 14, 8)
        ib_layout.setSpacing(16)

        addr_txt = self.info.get("address") or "Chưa xác định"
        time_txt = f"{self.info.get('date', '--')} {self.info.get('time', '--')}"
        gps_txt = self.info.get("gps_text") or "--"

        lbl_i_addr = QLabel(f"Địa chỉ: {addr_txt}")
        lbl_i_addr.setStyleSheet("color: #38bdf8; font-size: 12px; font-weight: 600; border: none; background: transparent;")
        lbl_i_addr.setWordWrap(True)
        ib_layout.addWidget(lbl_i_addr, stretch=1)

        lbl_i_time = QLabel(f"Thoi gian: {time_txt}")
        lbl_i_time.setStyleSheet("color: #e2e8f0; font-size: 12px; font-weight: 500; border: none; background: transparent;")
        ib_layout.addWidget(lbl_i_time)

        lbl_i_gps = QLabel(f"GPS: {gps_txt}")
        lbl_i_gps.setStyleSheet("color: #a7f3d0; font-size: 12px; font-weight: 500; border: none; background: transparent;")
        ib_layout.addWidget(lbl_i_gps)

        layout.addWidget(info_bar)

        self.update_image_display()

    def update_image_display(self):
        if self.show_tracking and self.annotated_img is not None:
            pix = cv2_to_qpixmap(self.annotated_img, 1800, 1300)
            if not pix.isNull():
                self.img_label.setPixmap(pix)
                self.btn_toggle_mode.setText("● Đang xem: Vùng ROI & Track chữ")
                self.btn_toggle_mode.setStyleSheet("""
                    QPushButton {
                        background-color: #064e3b;
                        color: #a7f3d0;
                        border: 1px solid #059669;
                        border-radius: 6px;
                        padding: 6px 14px;
                        font-weight: 700;
                        font-size: 12px;
                    }
                    QPushButton:hover {
                        background-color: #047857;
                        color: #ffffff;
                    }
                """)
                return

        pix = safe_load_pixmap(self.image_path, 1800, 1300)
        if not pix.isNull():
            self.img_label.setPixmap(pix)
        else:
            self.img_label.setText("Không thể tải hình ảnh này")
            self.img_label.setStyleSheet("color: #94a3b8; font-size: 14px; border: none;")
        self.btn_toggle_mode.setText("○ Đang xem: Ảnh gốc")
        self.btn_toggle_mode.setStyleSheet("""
            QPushButton {
                background-color: #1e293b;
                color: #e2e8f0;
                border: 1px solid #475569;
                border-radius: 6px;
                padding: 6px 14px;
                font-weight: 600;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #334155;
            }
        """)

    def toggle_tracking_mode(self):
        self.show_tracking = not self.show_tracking
        self.update_image_display()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape:
            self.accept()
        else:
            super().keyPressEvent(event)


# ----------------- DETAIL MODAL DIALOG -----------------
class StoreDetailDialog(QDialog):
    def __init__(self, data: dict, all_selected_files: List[str] = None, parent=None):
        super().__init__(parent)
        self.data = data  # Lưu lại để dùng trong open_image_viewer
        self.setWindowTitle("Chi tiết đối soát Timemark")
        self.resize(740, 620)
        self.setStyleSheet("QDialog { background-color: #ffffff; }")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(14)

        # 1. Header (Tiêu đề + Status Pill)
        top_h = QHBoxLayout()
        lbl_title = QLabel("Thông tin đối soát chi tiết")
        lbl_title.setStyleSheet("font-size: 16px; font-weight: 800; color: #0f172a; border: none;")
        top_h.addWidget(lbl_title)
        top_h.addStretch()

        status = data.get("status", "valid")
        cnt = data.get("count", 1)
        status_pill = QLabel()
        if status == "valid":
            status_pill.setText("Hợp lệ")
            status_pill.setStyleSheet("background-color: #ecfdf5; color: #047857; border: 1px solid #a7f3d0; border-radius: 12px; padding: 4px 14px; font-weight: 700; font-size: 12px;")
        elif status == "duplicate":
            dup_cnt = max(1, cnt - 1)
            status_pill.setText(f"Hợp lệ (Trùng {dup_cnt} ảnh)")
            status_pill.setStyleSheet("background-color: #fffbeb; color: #b45309; border: 1px solid #fde68a; border-radius: 12px; padding: 4px 14px; font-weight: 700; font-size: 12px;")
        else:
            status_pill.setText("Không liên quan")
            status_pill.setStyleSheet("background-color: #fef2f2; color: #b91c1c; border: 1px solid #fecaca; border-radius: 12px; padding: 4px 14px; font-weight: 700; font-size: 12px;")
        top_h.addWidget(status_pill)
        layout.addLayout(top_h)

        # 2. Cảnh báo trùng lặp (nếu có)
        if status == "duplicate":
            dup_cnt = max(1, cnt - 1)
            warn_card = QFrame()
            warn_card.setStyleSheet("background-color: #fffbeb; border: 1px solid #fde68a; border-radius: 8px;")
            wc_l = QHBoxLayout(warn_card)
            wc_l.setContentsMargins(12, 10, 12, 10)
            wc_l.setSpacing(10)
            w_icon = QLabel()
            w_icon.setPixmap(get_svg_pixmap(SVG_ALERT_TRIANGLE, "#d97706", 18, 18))
            wc_l.addWidget(w_icon)
            w_txt = QLabel(f"Cảnh báo trùng lặp: Điểm bán này có {cnt} ảnh ({dup_cnt} ảnh chụp trùng). Hệ thống tính 1 ảnh hợp lệ.")
            w_txt.setStyleSheet("color: #92400e; font-weight: 600; font-size: 12.5px; border: none; background: transparent;")
            wc_l.addWidget(w_txt)
            wc_l.addStretch()
            layout.addWidget(warn_card)

        # 3. Thẻ thông tin chính (Gọn gàng, chữ rõ nét không bị chìm)
        info_card = QFrame()
        info_card.setStyleSheet("background-color: #f8fafc; border: 1px solid #e2e8f0; border-radius: 10px;")
        ic_layout = QVBoxLayout(info_card)
        ic_layout.setContentsMargins(16, 14, 16, 14)
        ic_layout.setSpacing(10)

        # Hàng 1: Nhân viên & Công ty (Chia 2 cột)
        row1 = QHBoxLayout()
        row1.setSpacing(24)

        # Cột Nhân viên SR
        col_sr = QVBoxLayout()
        col_sr.setSpacing(2)
        lbl_sr_head = QLabel("NHÂN VIÊN (SR)")
        lbl_sr_head.setStyleSheet("font-size: 11px; font-weight: 700; color: #64748b; border: none; background: transparent;")
        col_sr.addWidget(lbl_sr_head)
        lbl_sr_val = QLabel(data.get("sr", "--"))
        lbl_sr_val.setStyleSheet("font-size: 12.5px; font-weight: 600; color: #1e293b; border: none; background: transparent;")
        col_sr.addWidget(lbl_sr_val)
        row1.addLayout(col_sr, stretch=1)

        # Cột Công ty
        col_cp = QVBoxLayout()
        col_cp.setSpacing(2)
        lbl_cp_head = QLabel("CÔNG TY")
        lbl_cp_head.setStyleSheet("font-size: 11px; font-weight: 700; color: #64748b; border: none; background: transparent;")
        col_cp.addWidget(lbl_cp_head)
        lbl_cp_val = QLabel(data.get("company", "--"))
        lbl_cp_val.setStyleSheet("font-size: 12.5px; font-weight: 600; color: #1e293b; border: none; background: transparent;")
        col_cp.addWidget(lbl_cp_val)
        row1.addLayout(col_cp, stretch=1)
        ic_layout.addLayout(row1)

        # Đường kẻ phân cách nhẹ 1
        line1 = QFrame()
        line1.setFrameShape(QFrame.HLine)
        line1.setStyleSheet("border: none; border-top: 1px solid #e2e8f0;")
        ic_layout.addWidget(line1)

        # Hàng 2: Địa chỉ điểm bán
        addr_box = QVBoxLayout()
        addr_box.setSpacing(3)
        lbl_addr_head = QLabel("ĐỊA CHỈ ĐIỂM BÁN")
        lbl_addr_head.setStyleSheet("font-size: 11px; font-weight: 700; color: #64748b; letter-spacing: 0.5px; border: none; background: transparent;")
        addr_box.addWidget(lbl_addr_head)

        clean_addr = format_clean_address(data.get("address", ""))
        lbl_addr = QLabel(clean_addr)
        lbl_addr.setWordWrap(True)
        lbl_addr.setStyleSheet("font-size: 13px; font-weight: 700; color: #0f172a; border: none; background: transparent;")
        addr_box.addWidget(lbl_addr)
        ic_layout.addLayout(addr_box)

        # Đường kẻ phân cách nhẹ 2
        line2 = QFrame()
        line2.setFrameShape(QFrame.HLine)
        line2.setStyleSheet("border: none; border-top: 1px solid #e2e8f0;")
        ic_layout.addWidget(line2)

        # Hàng 3: Thời gian & Mã Timemark (Chia 2 cột)
        row3 = QHBoxLayout()
        row3.setSpacing(24)

        # Cột Thời gian
        col_time = QVBoxLayout()
        col_time.setSpacing(2)
        lbl_t_head = QLabel("THỜI GIAN CHỤP")
        lbl_t_head.setStyleSheet("font-size: 11px; font-weight: 700; color: #64748b; border: none; background: transparent;")
        col_time.addWidget(lbl_t_head)
        lbl_t_val = QLabel(f"{data.get('date', '--')}  lúc  {data.get('time', '--')}")
        lbl_t_val.setStyleSheet("font-size: 12.5px; font-weight: 600; color: #1e293b; border: none; background: transparent;")
        col_time.addWidget(lbl_t_val)
        row3.addLayout(col_time, stretch=1)

        # Cột Mã Timemark
        col_tm = QVBoxLayout()
        col_tm.setSpacing(2)
        lbl_tm_head = QLabel("MÃ TIMEMARK")
        lbl_tm_head.setStyleSheet("font-size: 11px; font-weight: 700; color: #64748b; border: none; background: transparent;")
        col_tm.addWidget(lbl_tm_head)
        lbl_tm_val = QLabel(data.get("timemark_code", "--"))
        lbl_tm_val.setStyleSheet("""
            background-color: #eff6ff;
            color: #1d4ed8;
            font-size: 12px;
            font-weight: 700;
            padding: 2px 8px;
            border-radius: 6px;
            border: 1px solid #bfdbfe;
        """)
        col_tm.addWidget(lbl_tm_val, alignment=Qt.AlignLeft)
        row3.addLayout(col_tm, stretch=1)
        ic_layout.addLayout(row3)

        layout.addWidget(info_card)

        # 4. Danh sách hình ảnh (Có thể bấm vào để xem ảnh lớn)
        file_list = data.get("file_list", [])
        top_img_h = QHBoxLayout()
        lbl_sub = QLabel(f"Danh sách ảnh ({len(file_list)} file) — Click vào ảnh để phóng to:")
        lbl_sub.setStyleSheet("font-size: 13px; font-weight: 700; color: #0f172a; border: none;")
        top_img_h.addWidget(lbl_sub)
        top_img_h.addStretch()
        layout.addLayout(top_img_h)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setMinimumHeight(170)
        scroll.setStyleSheet("""
            QScrollArea {
                border: 1px solid #e2e8f0;
                border-radius: 8px;
                background-color: #ffffff;
            }
        """)

        container = QWidget()
        container.setStyleSheet("background-color: #ffffff;")
        c_layout = QVBoxLayout(container)
        c_layout.setContentsMargins(10, 10, 10, 10)
        c_layout.setSpacing(8)

        all_paths = all_selected_files or []

        for idx, fn in enumerate(file_list, 1):
            row_card = QFrame()
            row_card.setStyleSheet("""
                QFrame {
                    background-color: #f8fafc;
                    border: 1px solid #e2e8f0;
                    border-radius: 8px;
                }
                QFrame:hover {
                    background-color: #f1f5f9;
                    border-color: #cbd5e1;
                }
            """)
            r_l = QHBoxLayout(row_card)
            r_l.setContentsMargins(10, 8, 12, 8)
            r_l.setSpacing(14)

            # Tìm đường dẫn file ảnh thật
            match_p = None
            for p in all_paths:
                if os.path.basename(p) == fn:
                    match_p = p
                    break

            # Thumbnail có thể bấm vào để xem lớn
            thumb_box = QLabel()
            thumb_box.setFixedSize(72, 52)
            thumb_box.setStyleSheet("""
                QLabel {
                    border-radius: 6px;
                    border: 1px solid #cbd5e1;
                    background-color: #ffffff;
                }
                QLabel:hover {
                    border: 2px solid #2563eb;
                }
            """)
            thumb_box.setAlignment(Qt.AlignCenter)
            thumb_box.setCursor(Qt.PointingHandCursor)
            thumb_box.setToolTip("Click vào ảnh để phóng to xem chi tiết")

            if match_p:
                pix = safe_load_pixmap(match_p, 70, 50)
                if not pix.isNull():
                    thumb_box.setPixmap(pix)
                # Gán sự kiện click thumbnail mở ảnh lớn
                thumb_box.mousePressEvent = lambda ev, p=match_p: self.open_image_viewer(p)
            r_l.addWidget(thumb_box)

            # Thông tin tên file & tag
            info_col = QVBoxLayout()
            info_col.setSpacing(3)
            info_col.setAlignment(Qt.AlignVCenter)

            name_lbl = QLabel(f"{idx}. {fn}")
            name_lbl.setStyleSheet("color: #0f172a; font-size: 13px; font-weight: 700; border: none; background: transparent;")
            info_col.addWidget(name_lbl)

            if status == "duplicate":
                tag_lbl = QLabel("Ảnh chính (Tính 1)" if idx == 1 else "Ảnh trùng lặp")
                tag_style = """
                    background-color: #ecfdf5; color: #047857; font-size: 11px; font-weight: 700;
                    padding: 2px 8px; border-radius: 6px; border: 1px solid #a7f3d0;
                """ if idx == 1 else """
                    background-color: #fffbeb; color: #b45309; font-size: 11px; font-weight: 700;
                    padding: 2px 8px; border-radius: 6px; border: 1px solid #fde68a;
                """
                tag_lbl.setStyleSheet(tag_style)
                info_col.addWidget(tag_lbl)
            else:
                tag_lbl = QLabel("Ảnh hợp lệ")
                tag_lbl.setStyleSheet("background-color: #ecfdf5; color: #047857; font-size: 11px; font-weight: 700; padding: 2px 8px; border-radius: 6px; border: 1px solid #a7f3d0;")
                info_col.addWidget(tag_lbl)

            r_l.addLayout(info_col, stretch=1)

            # Nút Xem ảnh lớn
            if match_p:
                btn_zoom = QPushButton("Xem ảnh")
                btn_zoom.setCursor(Qt.PointingHandCursor)
                btn_zoom.setFixedSize(80, 30)
                btn_zoom.setStyleSheet("""
                    QPushButton {
                        background-color: #ffffff;
                        color: #2563eb;
                        border: 1px solid #bfdbfe;
                        border-radius: 6px;
                        font-size: 11.5px;
                        font-weight: 600;
                    }
                    QPushButton:hover {
                        background-color: #2563eb;
                        color: #ffffff;
                        border-color: #2563eb;
                    }
                """)
                btn_zoom.clicked.connect(lambda _, p=match_p: self.open_image_viewer(p))
                r_l.addWidget(btn_zoom)

            c_layout.addWidget(row_card)

        c_layout.addStretch()
        scroll.setWidget(container)
        layout.addWidget(scroll, stretch=1)

        # 5. Footer: Nút Đóng
        btn_close = QPushButton("Đóng")
        btn_close.setCursor(Qt.PointingHandCursor)
        btn_close.setFixedSize(80, 32)
        btn_close.setStyleSheet("""
            QPushButton {
                background-color: #f1f5f9;
                color: #334155;
                border: 1px solid #cbd5e1;
                border-radius: 6px;
                font-size: 13px;
                font-weight: 600;
            }
            QPushButton:hover {
                background-color: #e2e8f0;
                color: #0f172a;
            }
        """)
        btn_close.clicked.connect(self.accept)
        layout.addWidget(btn_close, alignment=Qt.AlignRight)

    def open_image_viewer(self, file_path: str):
        if not file_path or not os.path.exists(file_path):
            QMessageBox.information(self, "Thông báo", "Không tìm thấy file ảnh gốc trên máy tính!")
            return
        engine = get_ocr_engine()
        ann = engine.get_annotated_preview(file_path)
        dlg = ImageViewerDialog(file_path, annotated_img=ann, info=self.data, parent=self)
        dlg.exec()


# ----------------- GEMINI ASSISTANT DIALOG -----------------
class GeminiAssistantDialog(QDialog):
    def __init__(self, raw_records: list, on_apply=None, initial_tab: int = 0, parent=None):
        super().__init__(parent)
        self.raw_records = raw_records or []
        self.on_apply = on_apply
        self.setWindowTitle("Trợ lý AI Gemini - Làm sạch dữ liệu & Chấm điểm bán")
        self.resize(820, 640)
        self.setMinimumSize(720, 520)
        self.setStyleSheet("""
            QDialog {
                background-color: #f8fafc;
            }
            QLabel, QPushButton, QTextEdit {
                font-family: 'Segoe UI', -apple-system, BlinkMacSystemFont, Roboto, sans-serif;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(14)

        # Header
        hdr = QHBoxLayout()
        hdr_icon = QLabel()
        hdr_icon.setFixedSize(38, 38)
        hdr_icon.setStyleSheet("background-color: #4f46e5; border-radius: 9px;")
        hdr_icon.setAlignment(Qt.AlignCenter)
        hdr_icon.setPixmap(get_svg_pixmap(SVG_SPARKLE, "#ffffff", 22, 22))
        hdr.addWidget(hdr_icon)

        hdr_v = QVBoxLayout()
        hdr_v.setSpacing(2)
        hdr_t = QLabel("Trợ lý AI Gemini: Làm sạch JSON & Chấm điểm")
        hdr_t.setStyleSheet("font-size: 16px; font-weight: 800; color: #0f172a;")
        hdr_sub = QLabel("Xuất JSON tên SR, Địa chỉ, Tọa độ, Thời gian để Gemini chuẩn hóa, sau đó nạp lại để chấm điểm chuẩn xác 100%.")
        hdr_sub.setStyleSheet("font-size: 12px; color: #64748b;")
        hdr_v.addWidget(hdr_t)
        hdr_v.addWidget(hdr_sub)
        hdr.addLayout(hdr_v)
        hdr.addStretch()
        layout.addLayout(hdr)

        # Tab Widget
        self.tabs = QTabWidget()
        self.tabs.setStyleSheet("""
            QTabWidget::pane {
                border: 1px solid #e2e8f0;
                background-color: #ffffff;
                border-radius: 10px;
                top: -1px;
            }
            QTabBar::tab {
                background: #f1f5f9;
                color: #475569;
                font-weight: 700;
                font-size: 13px;
                padding: 9px 18px;
                margin-right: 4px;
                border-top-left-radius: 8px;
                border-top-right-radius: 8px;
                border: 1px solid #cbd5e1;
                border-bottom: none;
            }
            QTabBar::tab:selected {
                background: #ffffff;
                color: #4338ca;
                border: 1px solid #e2e8f0;
                border-bottom: 2px solid #4f46e5;
            }
            QTabBar::tab:hover:!selected {
                background: #e2e8f0;
            }
        """)

        # --- TAB 1: Xuất JSON & Lấy Prompt ---
        tab_export = QWidget()
        te_l = QVBoxLayout(tab_export)
        te_l.setContentsMargins(18, 16, 18, 16)
        te_l.setSpacing(10)

        te_info = QLabel(f"Đã trích xuất <b>{len(self.raw_records)} ảnh</b> từ watermark Timemark. Bấm <b>Sao chép Prompt + JSON</b> rồi dán thẳng vào Gemini:")
        te_info.setStyleSheet("font-size: 12.5px; color: #334155;")
        te_l.addWidget(te_info)

        self.txt_export = QTextEdit()
        self.txt_export.setReadOnly(True)
        self.txt_export.setStyleSheet("""
            QTextEdit {
                background-color: #f8fafc;
                border: 1px solid #cbd5e1;
                border-radius: 8px;
                font-family: 'Consolas', 'Courier New', monospace;
                font-size: 12px;
                color: #0f172a;
                padding: 8px;
            }
        """)
        json_export_str = json.dumps(self.raw_records, ensure_ascii=False, indent=2)
        self.txt_export.setPlainText(json_export_str)
        te_l.addWidget(self.txt_export)

        # Thanh nút thao tác Tab 1
        te_btns = QHBoxLayout()
        te_btns.setSpacing(10)

        self.btn_copy_prompt = QPushButton("📋  Sao chép Prompt + JSON cho Gemini")
        self.btn_copy_prompt.setCursor(Qt.PointingHandCursor)
        self.btn_copy_prompt.setFixedHeight(38)
        self.btn_copy_prompt.setStyleSheet("""
            QPushButton {
                background-color: #4f46e5;
                color: #ffffff;
                font-size: 13px;
                font-weight: 700;
                border: none;
                border-radius: 7px;
                padding: 0 16px;
            }
            QPushButton:hover { background-color: #4338ca; }
        """)
        self.btn_copy_prompt.clicked.connect(self.copy_prompt_to_clipboard)
        te_btns.addWidget(self.btn_copy_prompt)

        self.btn_save_json = QPushButton("💾  Lưu file JSON ra máy...")
        self.btn_save_json.setCursor(Qt.PointingHandCursor)
        self.btn_save_json.setFixedHeight(38)
        self.btn_save_json.setStyleSheet("""
            QPushButton {
                background-color: #f1f5f9;
                color: #334155;
                border: 1px solid #cbd5e1;
                border-radius: 7px;
                font-size: 13px;
                font-weight: 600;
                padding: 0 16px;
            }
            QPushButton:hover { background-color: #e2e8f0; color: #0f172a; }
        """)
        self.btn_save_json.clicked.connect(self.save_json_file)
        te_btns.addWidget(self.btn_save_json)

        te_btns.addStretch()

        self.lbl_copy_notice = QLabel("")
        self.lbl_copy_notice.setStyleSheet("color: #16a34a; font-weight: 700; font-size: 12px;")
        te_btns.addWidget(self.lbl_copy_notice)

        te_l.addLayout(te_btns)
        self.tabs.addTab(tab_export, "1. 📤 Xuất JSON & Lấy Prompt")

        # --- TAB 2: Nạp JSON đã làm sạch & Chấm điểm ---
        tab_import = QWidget()
        ti_l = QVBoxLayout(tab_import)
        ti_l.setContentsMargins(18, 16, 18, 16)
        ti_l.setSpacing(10)

        ti_info = QLabel("Dán mảng JSON kết quả từ Gemini hoặc mở file JSON đã làm sạch để tiến hành <b>chấm điểm bán</b>:")
        ti_info.setStyleSheet("font-size: 12.5px; color: #334155;")
        ti_l.addWidget(ti_info)

        ti_action_bar = QHBoxLayout()
        ti_action_bar.setSpacing(8)

        btn_open_file = QPushButton("📂  Chọn file JSON đã làm sạch...")
        btn_open_file.setCursor(Qt.PointingHandCursor)
        btn_open_file.setFixedHeight(34)
        btn_open_file.setStyleSheet("""
            QPushButton {
                background-color: #f8fafc; color: #334155;
                border: 1px solid #cbd5e1; border-radius: 6px;
                font-size: 12.5px; font-weight: 600; padding: 0 14px;
            }
            QPushButton:hover { background-color: #e2e8f0; }
        """)
        btn_open_file.clicked.connect(self.load_cleaned_json_file)
        ti_action_bar.addWidget(btn_open_file)

        btn_paste = QPushButton("📋  Dán từ Clipboard")
        btn_paste.setCursor(Qt.PointingHandCursor)
        btn_paste.setFixedHeight(34)
        btn_paste.setStyleSheet("""
            QPushButton {
                background-color: #f8fafc; color: #334155;
                border: 1px solid #cbd5e1; border-radius: 6px;
                font-size: 12.5px; font-weight: 600; padding: 0 14px;
            }
            QPushButton:hover { background-color: #e2e8f0; }
        """)
        btn_paste.clicked.connect(self.paste_from_clipboard)
        ti_action_bar.addWidget(btn_paste)

        btn_clear = QPushButton("Xóa nội dung")
        btn_clear.setCursor(Qt.PointingHandCursor)
        btn_clear.setFixedHeight(34)
        btn_clear.setStyleSheet("""
            QPushButton {
                background: transparent; color: #ef4444;
                border: none; font-size: 12px; font-weight: 600; padding: 0 8px;
            }
            QPushButton:hover { text-decoration: underline; }
        """)
        btn_clear.clicked.connect(lambda: self.txt_import.clear())
        ti_action_bar.addWidget(btn_clear)
        ti_action_bar.addStretch()
        ti_l.addLayout(ti_action_bar)

        self.txt_import = QTextEdit()
        self.txt_import.setPlaceholderText('Dán kết quả JSON từ Gemini vào đây (hỗ trợ cả khối ```json ... ```):\n[\n  {\n    "id": 1,\n    "filename": "...",\n    "sr": "Nguyễn Văn A",\n    "company": "Công ty X",\n    "address": "ĐT943, Định Mỹ, Thoại Sơn, An Giang",\n    "gps": "10.2934, 105.3421",\n    "date": "06/10/2026",\n    "time": "10:41"\n  }\n]')
        self.txt_import.setStyleSheet("""
            QTextEdit {
                background-color: #ffffff;
                border: 1px solid #cbd5e1;
                border-radius: 8px;
                font-family: 'Consolas', 'Courier New', monospace;
                font-size: 12px;
                color: #0f172a;
                padding: 8px;
            }
            QTextEdit:focus {
                border: 2px solid #4f46e5;
            }
        """)
        ti_l.addWidget(self.txt_import)

        # Nút to chấm điểm bán
        self.btn_evaluate = QPushButton("✨  BẮT ĐẦU CHẤM CỬA HÀNG TỪ DỮ LIỆU GEMINI  ✨")
        self.btn_evaluate.setCursor(Qt.PointingHandCursor)
        self.btn_evaluate.setFixedHeight(44)
        self.btn_evaluate.setStyleSheet("""
            QPushButton {
                background-color: #16a34a;
                color: #ffffff;
                font-size: 14px;
                font-weight: 800;
                border: none;
                border-radius: 8px;
                padding: 0 20px;
                letter-spacing: 0.3px;
            }
            QPushButton:hover {
                background-color: #15803d;
            }
        """)
        self.btn_evaluate.clicked.connect(self.process_cleaned_json_and_evaluate)
        ti_l.addWidget(self.btn_evaluate)

        self.tabs.addTab(tab_import, "2. 📥 Nạp JSON đã làm sạch & Chấm điểm bán")
        layout.addWidget(self.tabs)

        if initial_tab in (0, 1):
            self.tabs.setCurrentIndex(initial_tab)

        # Footer close
        footer = QHBoxLayout()
        footer.addStretch()
        btn_close = QPushButton("Đóng")
        btn_close.setCursor(Qt.PointingHandCursor)
        btn_close.setFixedSize(85, 34)
        btn_close.setStyleSheet("""
            QPushButton {
                background-color: #f1f5f9; color: #475569;
                border: 1px solid #cbd5e1; border-radius: 6px;
                font-size: 13px; font-weight: 600;
            }
            QPushButton:hover { background-color: #e2e8f0; color: #0f172a; }
        """)
        btn_close.clicked.connect(self.reject)
        footer.addWidget(btn_close)
        layout.addLayout(footer)

    def copy_prompt_to_clipboard(self):
        engine = get_ocr_engine()
        prompt = engine.get_gemini_cleaning_prompt(self.raw_records)
        QApplication.clipboard().setText(prompt)
        self.lbl_copy_notice.setText("✅ Đã sao chép Prompt + JSON! Hãy dán (Ctrl+V) vào Gemini.")

    def save_json_file(self):
        default_name = f"diem_ban_raw_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        save_path, _ = QFileDialog.getSaveFileName(self, "Lưu file JSON cho Gemini", default_name, "JSON Files (*.json)")
        if not save_path:
            return
        try:
            engine = get_ocr_engine()
            engine.export_to_gemini_json(self.raw_records, save_path, include_prompt_file=True)
            QMessageBox.information(
                self, "Đã xuất JSON",
                f"Đã lưu file JSON thành công tại:\n{save_path}\n\nKèm theo file gợi ý Prompt:\n{os.path.splitext(save_path)[0] + '_prompt_gemini.txt'}"
            )
        except Exception as e:
            QMessageBox.critical(self, "Lỗi", f"Không thể lưu file: {str(e)}")

    def load_cleaned_json_file(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "Chọn file JSON đã làm sạch", "", "JSON Files (*.json *.txt)")
        if not file_path:
            return
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()
            self.txt_import.setPlainText(content)
        except Exception as e:
            QMessageBox.critical(self, "Lỗi", f"Không thể đọc file: {str(e)}")

    def paste_from_clipboard(self):
        clip_text = QApplication.clipboard().text()
        if clip_text:
            self.txt_import.setPlainText(clip_text)

    def process_cleaned_json_and_evaluate(self):
        text = self.txt_import.toPlainText().strip()
        if not text:
            QMessageBox.warning(self, "Cảnh báo", "Vui lòng dán hoặc mở nội dung JSON từ Gemini trước khi bấm chấm điểm!")
            return

        # Làm sạch markdown backticks nếu người dùng copy cả ```json ... ```
        if "```" in text:
            m = re.search(r'```(?:json)?\s*([\s\S]*?)\s*```', text)
            if m:
                text = m.group(1).strip()

        try:
            data = json.loads(text)
        except Exception as e:
            QMessageBox.critical(self, "Lỗi định dạng JSON", f"Nội dung không phải là mã JSON hợp lệ:\n{str(e)}")
            return

        if not isinstance(data, list) or not data:
            QMessageBox.warning(self, "Dữ liệu không hợp lệ", "Dữ liệu JSON phải là một mảng (danh sách) các object [ { ... }, { ... } ]!")
            return

        if self.on_apply:
            self.on_apply(data)
            self.accept()


# ----------------- MAIN WINDOW -----------------
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Anhiu")
        icon_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "app_icon.ico")
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))
        self.resize(1200, 870)
        self.setMinimumSize(1000, 720)

        self.selected_files: List[str] = []
        self.all_results: Dict[str, Any] = {}
        self.current_filter_status: str = "all"
        self.worker_thread = None
        self.analyzed_previews: List[Dict[str, Any]] = []
        self.current_preview_idx: int = -1
        self.is_roi_zoom: bool = False
        self.current_preview_cv_img = None
        self.current_preview_info = None
        self.current_preview_fn: str = ""
        self.last_raw_ocr_items: List[Dict[str, Any]] = []

        self.setup_ui()

        # Tải trước mô hình PaddleOCR trong nền để sẵn sàng ngay lập tức khi người dùng bấm chạy
        self.preload_thread = EnginePreloadThread()
        self.preload_thread.start()

    def setup_ui(self):
        outer_scroll = QScrollArea()
        outer_scroll.setWidgetResizable(True)
        outer_scroll.setFrameShape(QFrame.NoFrame)
        outer_scroll.setStyleSheet("QScrollArea { border: none; background-color: #f8fafc; }")
        self.setCentralWidget(outer_scroll)

        central = QWidget()
        central.setObjectName("CentralWidget")
        outer_scroll.setWidget(central)

        main_vbox = QVBoxLayout(central)
        main_vbox.setContentsMargins(28, 22, 28, 28)
        main_vbox.setSpacing(16)

        self.setStyleSheet("""
            QMainWindow {
                background-color: #f8fafc;
            }
            QWidget#CentralWidget {
                background-color: #f8fafc;
            }
            QLabel, QPushButton, QLineEdit {
                font-family: 'Segoe UI', -apple-system, BlinkMacSystemFont, Roboto, sans-serif;
            }
        """)

        # ----------------- 1. HEADER -----------------
        header_layout = QHBoxLayout()
        header_layout.setSpacing(12)

        icon_box = QLabel()
        icon_box.setFixedSize(42, 42)
        icon_box.setStyleSheet("background-color: #2563eb; border-radius: 10px; border: none;")
        icon_box.setAlignment(Qt.AlignCenter)
        icon_box.setPixmap(get_svg_pixmap(SVG_CAMERA, "#ffffff", 24, 24))
        header_layout.addWidget(icon_box)

        title_vbox = QVBoxLayout()
        title_vbox.setSpacing(1)

        app_title = QLabel("Anhiu")
        app_title.setStyleSheet("font-size: 20px; font-weight: 800; color: #0f172a; border: none;")
        title_vbox.addWidget(app_title)

        app_sub = QLabel("Nhận diện điểm bán từ hình ảnh bằng AI")
        app_sub.setStyleSheet("font-size: 12px; color: #64748b; font-weight: 400; border: none;")
        title_vbox.addWidget(app_sub)
        header_layout.addLayout(title_vbox)

        header_layout.addStretch()

        badge = QLabel("TIMEMARK OCR")
        badge.setStyleSheet("""
            background-color: #eff6ff;
            color: #2563eb;
            border: 1px solid #bfdbfe;
            border-radius: 14px;
            padding: 4px 14px;
            font-size: 11px;
            font-weight: 700;
            letter-spacing: 0.5px;
        """)
        header_layout.addWidget(badge)
        main_vbox.addLayout(header_layout)

        # ----------------- 2. TOP SECTION (2 CARDS) -----------------
        top_cards_layout = QHBoxLayout()
        top_cards_layout.setSpacing(18)

        # --- LEFT CARD: HÌNH ẢNH (~60%) ---
        left_card = QFrame()
        left_card.setObjectName("LeftCard")
        left_card.setStyleSheet("""
            QFrame#LeftCard {
                background-color: #ffffff;
                border: 1px solid #e2e8f0;
                border-radius: 12px;
            }
        """)
        left_layout = QVBoxLayout(left_card)
        left_layout.setContentsMargins(20, 18, 20, 18)
        left_layout.setSpacing(12)

        card_title = QLabel("Hình ảnh")
        card_title.setStyleSheet("font-size: 15px; font-weight: 700; color: #0f172a; border: none;")
        left_layout.addWidget(card_title)

        self.dropzone = DropZoneWidget()
        self.dropzone.files_dropped.connect(self.add_files)
        self.dropzone.browse_clicked.connect(self.browse_files)
        left_layout.addWidget(self.dropzone)

        self.status_bar_layout = QHBoxLayout()
        self.lbl_selected_count = QLabel("Đã chọn 0 ảnh")
        self.lbl_selected_count.setStyleSheet("font-size: 13px; font-weight: 600; color: #334155; border: none;")
        self.status_bar_layout.addWidget(self.lbl_selected_count)

        self.status_bar_layout.addStretch()

        self.btn_clear_all = QPushButton("  Xóa tất cả")
        self.btn_clear_all.setIcon(get_svg_icon(SVG_TRASH, "#ef4444", 14))
        self.btn_clear_all.setCursor(Qt.PointingHandCursor)
        self.btn_clear_all.setStyleSheet("""
            QPushButton {
                background: transparent;
                color: #ef4444;
                font-size: 12px;
                font-weight: 600;
                border: none;
            }
            QPushButton:hover {
                color: #dc2626;
                text-decoration: underline;
            }
        """)
        self.btn_clear_all.clicked.connect(self.clear_all_files)
        self.status_bar_layout.addWidget(self.btn_clear_all)
        left_layout.addLayout(self.status_bar_layout)

        # Thumbnails strip
        self.thumb_scroll = QScrollArea()
        self.thumb_scroll.setFixedHeight(88)
        self.thumb_scroll.setWidgetResizable(True)
        self.thumb_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.thumb_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.thumb_scroll.setStyleSheet("QScrollArea { background-color: transparent; border: none; }")
        self.thumb_container = QWidget()
        self.thumb_container.setStyleSheet("background-color: transparent;")
        self.thumb_layout = QHBoxLayout(self.thumb_container)
        self.thumb_layout.setContentsMargins(0, 0, 0, 0)
        self.thumb_layout.setSpacing(8)
        self.thumb_layout.addStretch()
        self.thumb_scroll.setWidget(self.thumb_container)
        left_layout.addWidget(self.thumb_scroll)

        action_layout = QHBoxLayout()
        action_layout.addStretch()

        self.btn_start = QPushButton("Bắt đầu nhận diện  →")
        self.btn_start.setCursor(Qt.PointingHandCursor)
        self.btn_start.setStyleSheet("""
            QPushButton {
                background-color: #2563eb;
                color: #ffffff;
                font-size: 14px;
                font-weight: 700;
                border: none;
                border-radius: 8px;
                padding: 10px 24px;
            }
            QPushButton:hover {
                background-color: #1d4ed8;
            }
            QPushButton:disabled {
                background-color: #94a3b8;
            }
        """)
        self.btn_start.clicked.connect(self.start_ocr_process)
        action_layout.addWidget(self.btn_start)

        self.btn_gemini = QPushButton("✨ Làm sạch bằng Gemini")
        self.btn_gemini.setCursor(Qt.PointingHandCursor)
        self.btn_gemini.setStyleSheet("""
            QPushButton {
                background-color: #f5f3ff;
                color: #4f46e5;
                font-size: 13.5px;
                font-weight: 700;
                border: 1.5px solid #c7d2fe;
                border-radius: 8px;
                padding: 10px 18px;
            }
            QPushButton:hover {
                background-color: #ede9fe;
                border-color: #818cf8;
            }
        """)
        self.btn_gemini.setToolTip("Xuất JSON cho Gemini làm sạch dữ liệu hoặc nạp kết quả đã làm sạch để chấm điểm bán")
        self.btn_gemini.clicked.connect(self.open_gemini_dialog)
        action_layout.addWidget(self.btn_gemini)

        left_layout.addLayout(action_layout)

        top_cards_layout.addWidget(left_card, 5)

        # --- RIGHT CARD: PHÂN TÍCH & BÁO CÁO KẾT QUẢ TRỰC TIẾP ---
        self.right_card = QFrame()
        self.right_card.setObjectName("RightCard")
        self.right_card.setStyleSheet("""
            QFrame#RightCard {
                background-color: #ffffff;
                border: 1px solid #e2e8f0;
                border-radius: 12px;
            }
        """)
        self.right_main_layout = QVBoxLayout(self.right_card)
        self.right_main_layout.setContentsMargins(18, 16, 18, 16)
        self.right_main_layout.setSpacing(10)

        # Thanh chuyển đổi chế độ xem & Header thao tác tích hợp 1 dòng
        self.right_tab_bar = QHBoxLayout()
        self.right_tab_bar.setSpacing(8)

        self.btn_tab_preview = QPushButton("◉ Xem trực quan OCR")
        self.btn_tab_report = QPushButton("≡ Báo cáo kết quả")

        _tab_active_style = """
            QPushButton {
                background-color: #064e3b; color: #a7f3d0;
                font-size: 12px; font-weight: 700;
                border: 1px solid #059669; border-radius: 6px;
                padding: 4px 12px;
            }
            QPushButton:hover { background-color: #047857; color: #ffffff; }
        """
        _tab_inactive_style = """
            QPushButton {
                background-color: #f1f5f9; color: #475569;
                font-size: 12px; font-weight: 600;
                border: 1px solid #cbd5e1; border-radius: 6px;
                padding: 4px 12px;
            }
            QPushButton:hover { background-color: #e2e8f0; }
        """
        self.btn_tab_preview.setStyleSheet(_tab_active_style)
        self.btn_tab_report.setStyleSheet(_tab_inactive_style)

        for b in [self.btn_tab_preview, self.btn_tab_report]:
            b.setCursor(Qt.PointingHandCursor)
            b.setFixedHeight(30)

        self.btn_tab_preview.clicked.connect(lambda: self.switch_right_tab("preview"))
        self.btn_tab_report.clicked.connect(lambda: self.switch_right_tab("report"))

        self.right_tab_bar.addWidget(self.btn_tab_preview)
        self.right_tab_bar.addWidget(self.btn_tab_report)

        # Cụm trạng thái tích hợp ngay trên thanh Header
        self.right_tab_bar.addSpacing(6)
        self.status_badge = QLabel("SẴN SÀNG")
        self.status_badge.setStyleSheet("""
            background-color: #f1f5f9; color: #475569;
            font-size: 11px; font-weight: 700;
            padding: 3px 8px; border-radius: 6px;
            border: 1px solid #cbd5e1;
        """)
        self.right_tab_bar.addWidget(self.status_badge)

        self.status_title = QLabel("Quá trình OCR trực quan")
        self.status_title.setStyleSheet("font-size: 12.5px; font-weight: 700; color: #0f172a; border: none;")
        self.right_tab_bar.addWidget(self.status_title)
        self.right_tab_bar.addStretch()

        # Cụm điều hướng & công cụ xem ảnh bên phải Header
        self.btn_toggle_zoom = QPushButton("🔍 Soi chữ Timemark")
        self.btn_toggle_zoom.setCursor(Qt.PointingHandCursor)
        self.btn_toggle_zoom.setFixedHeight(28)
        self.btn_toggle_zoom.setStyleSheet("""
            QPushButton {
                background-color: #f8fafc; color: #0f172a;
                border: 1px solid #cbd5e1; border-radius: 5px;
                font-size: 11.5px; font-weight: 600; padding: 0 10px;
            }
            QPushButton:hover { background-color: #e2e8f0; }
        """)
        self.btn_toggle_zoom.setToolTip("Phóng to cận cảnh 38% góc đáy ảnh để nhìn rõ từng nét chữ Timemark (Click ảnh để bật/tắt)")
        self.btn_toggle_zoom.clicked.connect(self.toggle_roi_zoom)
        self.right_tab_bar.addWidget(self.btn_toggle_zoom)

        self.btn_prev_img = QPushButton("‹")
        self.btn_prev_img.setCursor(Qt.PointingHandCursor)
        self.btn_prev_img.setFixedSize(26, 28)
        self.btn_next_img = QPushButton("›")
        self.btn_next_img.setCursor(Qt.PointingHandCursor)
        self.btn_next_img.setFixedSize(26, 28)
        for nb in [self.btn_prev_img, self.btn_next_img]:
            nb.setStyleSheet("""
                QPushButton {
                    background-color: #f8fafc; color: #334155;
                    border: 1px solid #cbd5e1; border-radius: 5px;
                    font-size: 13px; font-weight: 700;
                }
                QPushButton:hover { background-color: #e2e8f0; }
                QPushButton:disabled { color: #94a3b8; background-color: #f1f5f9; }
            """)
        self.lbl_preview_idx = QLabel("0/0")
        self.lbl_preview_idx.setStyleSheet("font-size: 11.5px; font-weight: 700; color: #64748b; padding: 0 2px;")
        self.right_tab_bar.addWidget(self.btn_prev_img)
        self.right_tab_bar.addWidget(self.lbl_preview_idx)
        self.right_tab_bar.addWidget(self.btn_next_img)
        self.btn_prev_img.clicked.connect(self.show_prev_preview)
        self.btn_next_img.clicked.connect(self.show_next_preview)

        self.btn_fullscreen_view = QPushButton("⛶")
        self.btn_fullscreen_view.setCursor(Qt.PointingHandCursor)
        self.btn_fullscreen_view.setFixedSize(28, 28)
        self.btn_fullscreen_view.setStyleSheet("""
            QPushButton {
                background-color: #eff6ff; color: #2563eb;
                border: 1px solid #bfdbfe; border-radius: 5px;
                font-size: 13px; font-weight: 700;
            }
            QPushButton:hover { background-color: #2563eb; color: #ffffff; }
        """)
        self.btn_fullscreen_view.setToolTip("Mở toàn màn hình xem ảnh gốc độ nét cao")
        self.btn_fullscreen_view.clicked.connect(self.open_current_fullscreen_preview)
        self.right_tab_bar.addWidget(self.btn_fullscreen_view)

        self.right_main_layout.addLayout(self.right_tab_bar)

        # 1. VIEW CHỜ & TIẾN TRÌNH QUÉT OCR TRỰC QUAN
        self.view_waiting = QWidget()
        vw_l = QVBoxLayout(self.view_waiting)
        vw_l.setContentsMargins(0, 0, 0, 0)
        vw_l.setSpacing(6)

        # Progress bar siêu mảnh (chỉ hiện khi đang xử lý OCR)
        self.progress_bar = QProgressBar()
        self.progress_bar.setFixedHeight(4)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                background-color: #e2e8f0;
                border: none;
                border-radius: 2px;
            }
            QProgressBar::chunk {
                background-color: #16a34a;
                border-radius: 2px;
            }
        """)
        self.progress_bar.setVisible(False)
        vw_l.addWidget(self.progress_bar)

        # Giữ widget status_desc ẩn để tương thích ngược với luồng worker
        self.status_desc = QLabel()
        self.status_desc.setVisible(False)

        # Khung căn giữa để tự động ôm sát tỉ lệ ảnh (9:16 hoặc 16:9), triệt tiêu hoàn toàn viền thừa 2 bên
        self.preview_align_layout = QHBoxLayout()
        self.preview_align_layout.setContentsMargins(0, 0, 0, 0)
        self.preview_align_layout.setAlignment(Qt.AlignCenter)

        # Khung Preview Canvas hiển thị hình ảnh (nền slate tối sang trọng, ôm sát tỉ lệ ảnh)
        self.preview_frame = QFrame()
        self.preview_frame.setMinimumHeight(380)
        self.preview_frame.setStyleSheet("""
            QFrame {
                background-color: #0f172a;
                border: 1px solid #334155;
                border-radius: 12px;
            }
        """)
        pf_layout = QVBoxLayout(self.preview_frame)
        pf_layout.setContentsMargins(4, 4, 4, 4)
        pf_layout.setAlignment(Qt.AlignCenter)

        # Hình ảnh được vẽ box xanh lá — Click để toggle Zoom cận cảnh Timemark
        self.preview_img_label = QLabel()
        self.preview_img_label.setAlignment(Qt.AlignCenter)
        self.preview_img_label.setStyleSheet("border: none; background: transparent;")
        self.preview_img_label.setVisible(False)
        self.preview_img_label.setMinimumSize(1, 1)
        self.preview_img_label.setCursor(Qt.PointingHandCursor)
        self.preview_img_label.setToolTip("Click vào ảnh để bật/tắt chế độ soi cận cảnh chữ Timemark")
        self.preview_img_label.mousePressEvent = lambda ev: self.toggle_roi_zoom()
        pf_layout.addWidget(self.preview_img_label, stretch=1)

        # Placeholder khi chưa chạy
        self.preview_placeholder = QWidget()
        ph_l = QVBoxLayout(self.preview_placeholder)
        ph_l.setAlignment(Qt.AlignCenter)
        ph_l.setSpacing(8)
        self.illust_label = QLabel()
        self.illust_label.setAlignment(Qt.AlignCenter)
        self.illust_label.setPixmap(get_svg_pixmap(SVG_EMPTY_ILLUST, "#3b82f6", 75, 75))
        self.illust_label.setStyleSheet("border: none; background: transparent;")
        ph_l.addWidget(self.illust_label)
        ph_txt = QLabel("Vùng hiển thị trực quan ROI & Track chữ Timemark")
        ph_txt.setStyleSheet("color: #94a3b8; font-size: 12px; font-weight: 500; border: none; background: transparent;")
        ph_l.addWidget(ph_txt, alignment=Qt.AlignCenter)
        pf_layout.addWidget(self.preview_placeholder)

        self.preview_align_layout.addWidget(self.preview_frame)
        vw_l.addLayout(self.preview_align_layout, stretch=1)

        # Khung Telemetry bóc tách thời gian thực — Tinh gọn thành 1 DÒNG DUY NHẤT
        self.telemetry_card = QFrame()
        self.telemetry_card.setFixedHeight(36)
        self.telemetry_card.setStyleSheet("""
            QFrame {
                background-color: #f8fafc;
                border: 1px solid #e2e8f0;
                border-radius: 8px;
            }
        """)
        tc_l = QHBoxLayout(self.telemetry_card)
        tc_l.setContentsMargins(12, 4, 12, 4)
        tc_l.setSpacing(10)

        self.lbl_tele_addr = QLabel("📍 Địa chỉ: --")
        self.lbl_tele_addr.setStyleSheet("font-size: 12px; font-weight: 700; color: #0f172a; border: none; background: transparent;")
        tc_l.addWidget(self.lbl_tele_addr, stretch=1)

        self.lbl_tele_time = QLabel("🕒 --")
        self.lbl_tele_time.setStyleSheet("font-size: 11.5px; font-weight: 600; color: #475569; border: none; background: transparent;")
        tc_l.addWidget(self.lbl_tele_time)

        self.lbl_tele_gps = QLabel("🌐 --")
        self.lbl_tele_gps.setStyleSheet("font-size: 11.5px; font-weight: 600; color: #475569; border: none; background: transparent;")
        tc_l.addWidget(self.lbl_tele_gps)

        self.lbl_tele_status = QLabel("Chờ quét")
        self.lbl_tele_status.setStyleSheet("background-color: #f1f5f9; color: #64748b; font-size: 10.5px; font-weight: 700; padding: 2px 8px; border-radius: 4px; border: 1px solid #cbd5e1;")
        tc_l.addWidget(self.lbl_tele_status)

        vw_l.addWidget(self.telemetry_card)
        self.right_main_layout.addWidget(self.view_waiting)

        # 2. VIEW BÁO CÁO TRỰC TIẾP (Hiển thị ngay khi phân tích hoàn tất!)
        self.view_report = QWidget()
        vr_l = QVBoxLayout(self.view_report)
        vr_l.setContentsMargins(0, 0, 0, 0)
        vr_l.setSpacing(12)

        # Header báo cáo
        top_rep_h = QHBoxLayout()
        top_rep_h.setSpacing(12)
        top_rep_h.setAlignment(Qt.AlignVCenter | Qt.AlignLeft)

        rep_icon = QLabel()
        rep_icon.setFixedSize(38, 38)
        rep_icon.setStyleSheet("background-color: #dcfce7; border-radius: 19px; border: 1px solid #bbf7d0;")
        rep_icon.setAlignment(Qt.AlignCenter)
        rep_icon.setPixmap(get_svg_pixmap(SVG_CHECK_CIRCLE, "#16a34a", 22, 22))
        top_rep_h.addWidget(rep_icon)

        rep_title_v = QVBoxLayout()
        rep_title_v.setSpacing(2)
        lbl_rep_title = QLabel("Phân tích hoàn tất!")
        lbl_rep_title.setStyleSheet("font-size: 16px; font-weight: 800; color: #0f172a; border: none;")
        rep_title_v.addWidget(lbl_rep_title)
        self.lbl_rep_desc = QLabel("AI đã nhận diện thông số & đối soát điểm bán thành công")
        self.lbl_rep_desc.setStyleSheet("font-size: 12px; color: #64748b; border: none;")
        rep_title_v.addWidget(self.lbl_rep_desc)
        top_rep_h.addLayout(rep_title_v)
        top_rep_h.addStretch()
        vr_l.addLayout(top_rep_h)

        # Khung 3 Mini KPI cards nằm ngang
        kpi_grid = QHBoxLayout()
        kpi_grid.setSpacing(10)

        # 1. Tổng ảnh nạp
        card_total = QFrame()
        card_total.setStyleSheet("background-color: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px;")
        ct_l = QVBoxLayout(card_total)
        ct_l.setContentsMargins(8, 10, 8, 10)
        ct_l.setSpacing(2)
        ct_l.setAlignment(Qt.AlignCenter)
        self.kpi_total_imgs = QLabel("0")
        self.kpi_total_imgs.setStyleSheet("font-size: 22px; font-weight: 800; color: #0f172a; border: none; background: transparent;")
        self.kpi_total_imgs.setAlignment(Qt.AlignCenter)
        ct_l.addWidget(self.kpi_total_imgs)
        lbl_ct = QLabel("Tổng ảnh nạp")
        lbl_ct.setStyleSheet("font-size: 11px; font-weight: 600; color: #64748b; border: none; background: transparent;")
        lbl_ct.setAlignment(Qt.AlignCenter)
        ct_l.addWidget(lbl_ct)
        kpi_grid.addWidget(card_total)

        # 2. Điểm hợp lệ
        card_valid = QFrame()
        card_valid.setStyleSheet("background-color: #f0fdf4; border: 1px solid #bbf7d0; border-radius: 8px;")
        cv_l = QVBoxLayout(card_valid)
        cv_l.setContentsMargins(8, 10, 8, 10)
        cv_l.setSpacing(2)
        cv_l.setAlignment(Qt.AlignCenter)
        self.kpi_valid_stores = QLabel("0")
        self.kpi_valid_stores.setStyleSheet("font-size: 22px; font-weight: 800; color: #16a34a; border: none; background: transparent;")
        self.kpi_valid_stores.setAlignment(Qt.AlignCenter)
        cv_l.addWidget(self.kpi_valid_stores)
        lbl_cv = QLabel("Điểm hợp lệ")
        lbl_cv.setStyleSheet("font-size: 11px; font-weight: 600; color: #15803d; border: none; background: transparent;")
        lbl_cv.setAlignment(Qt.AlignCenter)
        cv_l.addWidget(lbl_cv)
        kpi_grid.addWidget(card_valid)

        # 3. Trùng & Lỗi
        card_warn = QFrame()
        card_warn.setStyleSheet("background-color: #fffbeb; border: 1px solid #fde68a; border-radius: 8px;")
        cw_l = QVBoxLayout(card_warn)
        cw_l.setContentsMargins(8, 10, 8, 10)
        cw_l.setSpacing(2)
        cw_l.setAlignment(Qt.AlignCenter)
        self.kpi_warning_count = QLabel("0")
        self.kpi_warning_count.setStyleSheet("font-size: 22px; font-weight: 800; color: #d97706; border: none; background: transparent;")
        self.kpi_warning_count.setAlignment(Qt.AlignCenter)
        cw_l.addWidget(self.kpi_warning_count)
        lbl_cw = QLabel("Trùng & Lỗi")
        lbl_cw.setStyleSheet("font-size: 11px; font-weight: 600; color: #b45309; border: none; background: transparent;")
        lbl_cw.setAlignment(Qt.AlignCenter)
        cw_l.addWidget(lbl_cw)
        kpi_grid.addWidget(card_warn)

        vr_l.addLayout(kpi_grid)

        # Cụm nút Thao tác Báo cáo (Xuất Excel + Trợ lý Gemini)
        report_btn_row = QHBoxLayout()
        report_btn_row.setSpacing(8)

        self.btn_export = QPushButton("  Xuất báo cáo Excel")
        self.btn_export.setIcon(get_svg_icon(SVG_EXCEL, "#ffffff", 16))
        self.btn_export.setCursor(Qt.PointingHandCursor)
        self.btn_export.setFixedHeight(38)
        self.btn_export.setStyleSheet("""
            QPushButton {
                background-color: #16a34a;
                color: #ffffff;
                border: none;
                border-radius: 8px;
                font-size: 13px;
                font-weight: 700;
            }
            QPushButton:hover {
                background-color: #15803d;
            }
            QPushButton:disabled {
                background-color: #94a3b8;
            }
        """)
        self.btn_export.clicked.connect(self.export_to_excel)
        self.btn_export.setEnabled(False)
        report_btn_row.addWidget(self.btn_export, 6)

        self.btn_gemini_export = QPushButton("  Trợ lý Gemini")
        self.btn_gemini_export.setIcon(get_svg_icon(SVG_SPARKLE, "#4f46e5", 16))
        self.btn_gemini_export.setCursor(Qt.PointingHandCursor)
        self.btn_gemini_export.setFixedHeight(38)
        self.btn_gemini_export.setStyleSheet("""
            QPushButton {
                background-color: #f5f3ff;
                color: #4f46e5;
                border: 1.5px solid #c7d2fe;
                border-radius: 8px;
                font-size: 13px;
                font-weight: 700;
            }
            QPushButton:hover {
                background-color: #ede9fe;
            }
            QPushButton:disabled {
                color: #94a3b8;
                border-color: #e2e8f0;
                background-color: #f8fafc;
            }
        """)
        self.btn_gemini_export.clicked.connect(self.open_gemini_dialog)
        report_btn_row.addWidget(self.btn_gemini_export, 4)

        vr_l.addLayout(report_btn_row)

        self.view_report.setVisible(False)
        self.right_main_layout.addWidget(self.view_report)

        top_cards_layout.addWidget(self.right_card, 5)
        main_vbox.addLayout(top_cards_layout)

        main_vbox.addSpacing(6)

        # Subtitle: Chi tiết điểm bán
        lbl_detail = QLabel("Chi tiết điểm bán")
        lbl_detail.setStyleSheet("font-size: 15px; font-weight: 700; color: #0f172a; border: none;")
        main_vbox.addWidget(lbl_detail)

        # Quick Filter Tabs
        filter_layout = QHBoxLayout()
        filter_layout.setSpacing(8)

        self.btn_filter_all = QPushButton("Tất cả (0)")
        self.btn_filter_valid = QPushButton("Hợp lệ (0)")
        self.btn_filter_dup = QPushButton("Trùng lặp (0)")
        self.btn_filter_unrel = QPushButton("Không liên quan (0)")

        self.filter_buttons = [
            (self.btn_filter_all, "all"),
            (self.btn_filter_valid, "valid"),
            (self.btn_filter_dup, "duplicate"),
            (self.btn_filter_unrel, "unrelated")
        ]

        for btn, f_key in self.filter_buttons:
            btn.setCursor(Qt.PointingHandCursor)
            btn.setFixedHeight(32)
            btn.clicked.connect(lambda _, k=f_key: self.set_filter(k))
            filter_layout.addWidget(btn)

        self.current_filter_sr = "all"

        filter_layout.addStretch()

        # Dropdown Lọc Nhân Viên (SR)
        lbl_sr_icon = QLabel("👤 Nhân viên:")
        lbl_sr_icon.setStyleSheet("color: #475569; font-size: 12px; font-weight: 600; border: none; background: transparent;")
        filter_layout.addWidget(lbl_sr_icon)

        self.combo_filter_sr = QComboBox()
        self.combo_filter_sr.setFixedHeight(32)
        self.combo_filter_sr.setMinimumWidth(180)
        self.combo_filter_sr.setStyleSheet("""
            QComboBox {
                background-color: #ffffff;
                color: #0f172a;
                font-size: 12px;
                font-weight: 600;
                border: 1px solid #cbd5e1;
                border-radius: 6px;
                padding: 2px 10px;
            }
            QComboBox:hover {
                border-color: #2563eb;
            }
            QComboBox::drop-down {
                border: none;
                width: 20px;
            }
            QComboBox QAbstractItemView {
                background-color: #ffffff;
                color: #0f172a;
                selection-background-color: #eff6ff;
                selection-color: #1d4ed8;
                border: 1px solid #cbd5e1;
                border-radius: 6px;
                outline: none;
            }
        """)
        self.combo_filter_sr.addItem("Tất cả nhân viên", "all")
        self.combo_filter_sr.currentIndexChanged.connect(self.on_sr_filter_changed)
        filter_layout.addWidget(self.combo_filter_sr)

        main_vbox.addLayout(filter_layout)
        self.apply_filter_tab_styles()

        # Dải Thẻ Chip Nhân Viên (Bấm trực quan để lọc nhanh theo nhân viên)
        self.staff_chip_container = QWidget()
        self.staff_chip_container.setVisible(False)
        self.staff_chip_layout = QHBoxLayout(self.staff_chip_container)
        self.staff_chip_layout.setContentsMargins(0, 2, 0, 4)
        self.staff_chip_layout.setSpacing(6)
        self.staff_chip_layout.setAlignment(Qt.AlignLeft)
        main_vbox.addWidget(self.staff_chip_container)

        # Search Bar
        self.search_box = QLineEdit()
        self.search_box.setPlaceholderText("Tìm kiếm nhanh theo địa chỉ, nhân viên (SR), công ty, mã timecode...")
        self.search_box.setFixedHeight(42)
        self.search_box.setStyleSheet("""
            QLineEdit {
                background-color: #ffffff;
                border: 1px solid #cbd5e1;
                border-radius: 8px;
                padding: 0 16px;
                font-size: 13px;
                color: #0f172a;
            }
            QLineEdit:focus {
                border: 2px solid #2563eb;
                background-color: #ffffff;
            }
        """)
        self.search_box.textChanged.connect(self.filter_table)
        main_vbox.addWidget(self.search_box)

        # ----------------- 4. DATA TABLE (9 COLUMNS) -----------------
        self.table = QTableWidget()
        self.table.setColumnCount(9)
        self.table.setHorizontalHeaderLabels([
            "#", "Thời gian", "Nhân viên (SR)", "Công ty", "Địa chỉ điểm bán", "Mã Timemark", "Hình ảnh", "Trạng thái", "Thao tác"
        ])
        self.table.verticalHeader().setVisible(False)
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.NoSelection)
        self.table.setShowGrid(False)
        self.table.setFocusPolicy(Qt.NoFocus)
        self.table.cellClicked.connect(self.on_table_cell_clicked)
        self.table.cellDoubleClicked.connect(lambda r, c: self.on_table_row_double_clicked(r))

        self.table.verticalHeader().setDefaultSectionSize(62)
        self.table.verticalHeader().setSectionResizeMode(QHeaderView.Fixed)

        header = self.table.horizontalHeader()
        header.setFixedHeight(46)
        header.setSectionResizeMode(0, QHeaderView.Fixed)
        header.resizeSection(0, 46)    # STT
        header.setSectionResizeMode(1, QHeaderView.Fixed)
        header.resizeSection(1, 120)   # Thời gian
        header.setSectionResizeMode(2, QHeaderView.Fixed)
        header.resizeSection(2, 130)   # Nhân viên (SR)
        header.setSectionResizeMode(3, QHeaderView.Fixed)
        header.resizeSection(3, 140)   # Công ty
        header.setSectionResizeMode(4, QHeaderView.Stretch)           # Địa chỉ (Tự co giãn cân đối)
        header.setSectionResizeMode(5, QHeaderView.Fixed)
        header.resizeSection(5, 125)   # Mã Timemark (Timecode)
        header.setSectionResizeMode(6, QHeaderView.Fixed)
        header.resizeSection(6, 105)   # Ảnh
        header.setSectionResizeMode(7, QHeaderView.Fixed)
        header.resizeSection(7, 155)   # Trạng thái
        header.setSectionResizeMode(8, QHeaderView.Fixed)
        header.resizeSection(8, 80)    # Thao tác

        self.table.setStyleSheet("""
            QTableWidget {
                background-color: #ffffff;
                alternate-background-color: #fafbfc;
                border: 1px solid #e2e8f0;
                border-radius: 10px;
                font-size: 13px;
                outline: none;
            }
            QHeaderView::section {
                background-color: #f8fafc;
                color: #475569;
                font-weight: 700;
                font-size: 11.5px;
                border: none;
                border-bottom: 2px solid #e2e8f0;
                padding: 4px 6px;
            }
            QTableWidget::item {
                border-bottom: 1px solid #f1f5f9;
                color: #1e293b;
            }
            QTableWidget::item:hover {
                background-color: #f1f5f9;
            }
            QScrollBar:vertical {
                border: none;
                background: #f8fafc;
                width: 8px;
                border-radius: 4px;
            }
            QScrollBar::handle:vertical {
                background: #cbd5e1;
                border-radius: 4px;
                min-height: 24px;
            }
            QScrollBar::handle:vertical:hover {
                background: #94a3b8;
            }
        """)
        self.table.setMinimumHeight(320)
        main_vbox.addWidget(self.table)

        self.lbl_footer = QLabel("Chưa có dữ liệu phân tích")
        self.lbl_footer.setStyleSheet("font-size: 12px; color: #94a3b8; font-weight: 500; border: none;")
        main_vbox.addWidget(self.lbl_footer)

        self.update_file_selection_ui()

    # ----------------- UI UPDATES & EVENTS -----------------
    def apply_filter_tab_styles(self):
        active_style = """
            QPushButton {
                background-color: #2563eb;
                color: #ffffff;
                font-weight: 700;
                font-size: 12px;
                border-radius: 6px;
                padding: 0 14px;
                border: none;
            }
        """
        inactive_style = """
            QPushButton {
                background-color: #f1f5f9;
                color: #475569;
                font-weight: 600;
                font-size: 12px;
                border-radius: 6px;
                padding: 0 14px;
                border: 1px solid #e2e8f0;
            }
            QPushButton:hover {
                background-color: #e2e8f0;
            }
        """
        for btn, k in self.filter_buttons:
            if k == self.current_filter_status:
                btn.setStyleSheet(active_style)
            else:
                btn.setStyleSheet(inactive_style)

    def set_filter(self, filter_key: str):
        self.current_filter_status = filter_key
        self.apply_filter_tab_styles()
        self.filter_table(self.search_box.text())

    def add_files(self, file_paths: List[str]):
        added = 0
        for p in file_paths:
            if p not in self.selected_files:
                self.selected_files.append(p)
                added += 1
        if added > 0:
            self.refresh_thumbnails()
            self.update_file_selection_ui()

    def browse_files(self):
        files, _ = QFileDialog.getOpenFileNames(
            self,
            "Chọn ảnh Timemark",
            "",
            "Image Files (*.jpg *.jpeg *.png *.webp *.bmp)"
        )
        if files:
            self.add_files(files)

    def remove_file(self, file_path: str):
        if file_path in self.selected_files:
            self.selected_files.remove(file_path)
            self.refresh_thumbnails()
            self.update_file_selection_ui()

    def clear_all_files(self):
        self.selected_files.clear()
        self.refresh_thumbnails()
        self.update_file_selection_ui()
        self.view_report.setVisible(False)
        self.view_waiting.setVisible(True)
        self.status_title.setText("Sẵn sàng để bắt đầu")
        self.status_desc.setText("Vui lòng chọn ảnh và nhấn 'Bắt đầu nhận diện' để AI phân tích.")
        self.progress_bar.setVisible(False)
        self.btn_export.setEnabled(False)
        self.btn_gemini_export.setEnabled(False)
        self.last_raw_ocr_items.clear()
        self.table.setRowCount(0)
        self.btn_filter_all.setText("Tất cả (0)")
        self.btn_filter_valid.setText("Hợp lệ (0)")
        self.btn_filter_dup.setText("Trùng lặp (0)")
        self.btn_filter_unrel.setText("Không liên quan (0)")
        self.lbl_footer.setText("Chưa có dữ liệu phân tích")

    def refresh_thumbnails(self):
        while self.thumb_layout.count() > 0:
            item = self.thumb_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()

        for fp in self.selected_files:
            card = ThumbnailCard(fp)
            card.delete_clicked.connect(self.remove_file)
            self.thumb_layout.addWidget(card)

        self.thumb_layout.addStretch()

    def update_file_selection_ui(self):
        n = len(self.selected_files)
        self.lbl_selected_count.setText(f"Đã chọn {n} ảnh")
        has_files = (n > 0)
        self.btn_clear_all.setVisible(has_files)
        self.thumb_scroll.setVisible(has_files)
        self.btn_start.setEnabled(has_files)

    def switch_right_tab(self, tab_name: str):
        if tab_name == "preview":
            self.view_report.setVisible(False)
            self.view_waiting.setVisible(True)
            self.btn_tab_preview.setStyleSheet("""
                background-color: #064e3b;
                color: #a7f3d0;
                font-size: 12px;
                font-weight: 700;
                border: 1px solid #059669;
                border-radius: 6px;
                padding: 4px 12px;
            """)
            self.btn_tab_report.setStyleSheet("""
                background-color: #f1f5f9;
                color: #475569;
                font-size: 12px;
                font-weight: 600;
                border: 1px solid #cbd5e1;
                border-radius: 6px;
                padding: 4px 12px;
            """)
        else:
            self.view_waiting.setVisible(False)
            self.view_report.setVisible(True)
            self.btn_tab_report.setStyleSheet("""
                background-color: #2563eb;
                color: #ffffff;
                font-size: 12px;
                font-weight: 700;
                border: 1px solid #1d4ed8;
                border-radius: 6px;
                padding: 4px 12px;
            """)
            self.btn_tab_preview.setStyleSheet("""
                background-color: #f1f5f9;
                color: #475569;
                font-size: 12px;
                font-weight: 600;
                border: 1px solid #cbd5e1;
                border-radius: 6px;
                padding: 4px 12px;
            """)

    def toggle_roi_zoom(self):
        self.is_roi_zoom = not self.is_roi_zoom
        if self.current_preview_cv_img is not None:
            self.update_live_preview(self.current_preview_cv_img, self.current_preview_info or {}, self.current_preview_fn)

    def open_current_fullscreen_preview(self):
        if not self.current_preview_fn:
            return
        match_path = None
        for p in self.selected_files:
            if os.path.basename(p) == os.path.basename(self.current_preview_fn):
                match_path = p
                break
        if match_path and os.path.exists(match_path):
            self.open_full_image_viewer(match_path, self.current_preview_info)
        elif self.current_preview_cv_img is not None:
            dlg = ImageViewerDialog(self.current_preview_fn, annotated_img=self.current_preview_cv_img, info=self.current_preview_info, parent=self)
            dlg.exec()

    def adjust_preview_frame_aspect(self, cv_img: np.ndarray):
        """Tự động điều chỉnh chiều rộng của khung preview ôm sát tỉ lệ ảnh (9:16 hoặc 16:9), triệt tiêu hoàn toàn viền thừa 2 bên."""
        if cv_img is None:
            return
        h, w = cv_img.shape[:2]
        if self.is_roi_zoom:
            # Vùng crop chữ Timemark ở đáy có tỷ lệ ngang 16:9
            h_roi = max(int(h * 0.42), 1)
            aspect = w / h_roi
        else:
            aspect = w / max(h, 1)

        # Chiều cao khả dụng trong khung Right Card
        avail_h = self.preview_frame.height()
        if avail_h < 300:
            parent_h = self.view_waiting.height() if hasattr(self, 'view_waiting') else 460
            avail_h = max(parent_h - 48, 380)

        max_container_w = self.right_card.width() - 40 if hasattr(self, 'right_card') else 720
        target_w = int(avail_h * aspect) + 10

        # Khống chế kích thước để ôm sát ảnh, triệt tiêu 100% viền đen thừa 2 bên
        target_w = max(240, min(target_w, max_container_w))
        self.preview_frame.setFixedWidth(target_w)

    def update_live_preview(self, cv_img: np.ndarray, info: dict, fn: str = ""):
        if cv_img is None:
            return

        self.current_preview_cv_img = cv_img
        self.current_preview_info = info
        if fn:
            self.current_preview_fn = fn

        # Tự động co khung ôm sát tỉ lệ ảnh (9:16 cho ảnh dọc, 16:9 cho ảnh ngang)
        self.adjust_preview_frame_aspect(cv_img)

        # Xử lý chế độ Soi chữ Timemark (Crop 42% sát đáy ảnh) vs Xem toàn cảnh
        if self.is_roi_zoom:
            h, w = cv_img.shape[:2]
            roi_y = int(h * 0.58)
            crop_img = cv_img[roi_y:h, 0:w]
            pix = cv2_to_qpixmap(crop_img)
            self.btn_toggle_zoom.setText("🖼 Xem toàn cảnh")
            self.btn_toggle_zoom.setStyleSheet("""
                QPushButton {
                    background-color: #064e3b;
                    color: #a7f3d0;
                    border: 1px solid #059669;
                    border-radius: 5px;
                    font-size: 11px;
                    font-weight: 700;
                    padding: 0 10px;
                }
                QPushButton:hover { background-color: #047857; }
            """)
        else:
            pix = cv2_to_qpixmap(cv_img)
            self.btn_toggle_zoom.setText("🔍 Soi chữ Timemark")
            self.btn_toggle_zoom.setStyleSheet("""
                QPushButton {
                    background-color: #f8fafc;
                    color: #0f172a;
                    border: 1px solid #cbd5e1;
                    border-radius: 5px;
                    font-size: 11.5px;
                    font-weight: 600;
                    padding: 0 10px;
                }
                QPushButton:hover { background-color: #e2e8f0; }
            """)

        if not pix.isNull():
            self.preview_placeholder.setVisible(False)
            self.preview_img_label.setVisible(True)
            # Scale vừa khít khung đã ôm sát, không còn viền đen thừa
            frame_w = max(self.preview_frame.width() - 8, 200)
            frame_h = max(self.preview_frame.height() - 8, 300)
            scaled = pix.scaled(frame_w, frame_h, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            self.preview_img_label.setPixmap(scaled)

        self.status_badge.setText("▶ TRACKING")
        self.status_badge.setStyleSheet("""
            background-color: #ecfdf5;
            color: #047857;
            font-size: 11px;
            font-weight: 700;
            padding: 3px 8px;
            border-radius: 6px;
            border: 1px solid #a7f3d0;
        """)
        if fn:
            raw_base = os.path.basename(fn) if fn else ""
            display_fn = raw_base if len(raw_base) <= 24 else (raw_base[:10] + "..." + raw_base[-10:])
            self.status_title.setText(f"{display_fn}")
            self.status_title.setToolTip(f"Đang xem: {raw_base}\nClick ảnh để phóng to vùng chữ Timemark")

        addr = info.get("address") or "--"
        time_str = info.get("time") or "--:--"
        date_str = info.get("date") or "--/--/----"
        gps_str = info.get("gps_text") or "--"
        is_val = info.get("is_valid", False)

        # Cập nhật Telemetry 1 dòng tinh gọn
        disp_addr = addr if len(addr) <= 50 else (addr[:47] + "...")
        self.lbl_tele_addr.setText(f"📍 {disp_addr}")
        self.lbl_tele_addr.setToolTip(addr)
        self.lbl_tele_time.setText(f"🕒 {date_str} {time_str}")
        self.lbl_tele_gps.setText(f"🌐 {gps_str}")

        if is_val:
            self.lbl_tele_status.setText("Hợp lệ")
            self.lbl_tele_status.setStyleSheet("""
                background-color: #ecfdf5;
                color: #047857;
                font-size: 10.5px;
                font-weight: 700;
                padding: 2px 8px;
                border-radius: 4px;
                border: 1px solid #a7f3d0;
            """)
        else:
            self.lbl_tele_status.setText(info.get("reason") or "Không hợp lệ")
            self.lbl_tele_status.setStyleSheet("""
                background-color: #fef2f2;
                color: #b91c1c;
                font-size: 10.5px;
                font-weight: 700;
                padding: 2px 8px;
                border-radius: 4px;
                border: 1px solid #fecaca;
            """)

        n = len(self.analyzed_previews)
        if n > 0:
            self.lbl_preview_idx.setText(f"{self.current_preview_idx + 1}/{n}")
            self.btn_prev_img.setEnabled(self.current_preview_idx > 0)
            self.btn_next_img.setEnabled(self.current_preview_idx < n - 1)

    def show_prev_preview(self):
        if self.current_preview_idx > 0:
            self.current_preview_idx -= 1
            item = self.analyzed_previews[self.current_preview_idx]
            self.update_live_preview(item["img"], item["info"], item["fn"])

    def show_next_preview(self):
        if self.current_preview_idx < len(self.analyzed_previews) - 1:
            self.current_preview_idx += 1
            item = self.analyzed_previews[self.current_preview_idx]
            self.update_live_preview(item["img"], item["info"], item["fn"])

    def on_table_cell_clicked(self, row: int, col: int):
        if not hasattr(self, 'all_results') or not self.all_results:
            return
        details = self.all_results.get("details", [])
        if row < 0 or row >= len(details):
            return
        row_data = details[row]
        file_list = row_data.get("file_list", [])
        if not file_list:
            return

        target_fn = file_list[0]
        match_path = None
        for p in self.selected_files:
            if os.path.basename(p) == target_fn:
                match_path = p
                break

        # Nếu click vào cột Hình ảnh (cột 6), mở ngay ImageViewerDialog phóng to
        if col == 6 and match_path:
            self.open_full_image_viewer(match_path, row_data)
            return

        # Còn lại: hiển thị preview trên Right Card
        found_idx = -1
        for i, item in enumerate(self.analyzed_previews):
            if item["fn"] == target_fn:
                found_idx = i
                break

        if found_idx != -1:
            self.current_preview_idx = found_idx
            self.switch_right_tab("preview")
            item = self.analyzed_previews[found_idx]
            self.update_live_preview(item["img"], item["info"], item["fn"])
        elif match_path:
            engine = get_ocr_engine()
            ann = engine.get_annotated_preview(match_path)
            if ann is not None:
                self.switch_right_tab("preview")
                self.update_live_preview(ann, row_data, target_fn)

    def on_table_row_double_clicked(self, row: int):
        if not hasattr(self, 'all_results') or not self.all_results:
            return
        details = self.all_results.get("details", [])
        if row < 0 or row >= len(details):
            return
        row_data = details[row]
        file_list = row_data.get("file_list", [])
        if file_list:
            for p in self.selected_files:
                if os.path.basename(p) == file_list[0]:
                    self.open_full_image_viewer(p, row_data)
                    return

    def open_full_image_viewer(self, file_path: str, row_data: dict = None):
        if not file_path or not os.path.exists(file_path):
            QMessageBox.information(self, "Thông báo", "Không tìm thấy file ảnh gốc trên máy tính!")
            return
        engine = get_ocr_engine()
        ann = engine.get_annotated_preview(file_path)
        dlg = ImageViewerDialog(file_path, annotated_img=ann, info=row_data, parent=self)
        dlg.exec()

    def start_ocr_process(self):
        if not self.selected_files:
            QMessageBox.warning(self, "Thông báo", "Vui lòng chọn ít nhất 1 ảnh trước khi bắt đầu!")
            return

        self.btn_start.setEnabled(False)
        self.dropzone.setEnabled(False)
        self.btn_clear_all.setEnabled(False)
        self.btn_export.setEnabled(False)
        self.btn_gemini_export.setEnabled(False)

        # Chuyển sang giao diện tiến trình đang chạy & xem trực quan OCR
        self.analyzed_previews = []
        self.current_preview_idx = -1
        self.lbl_preview_idx.setText("0/0")
        self.btn_prev_img.setEnabled(False)
        self.btn_next_img.setEnabled(False)

        self.switch_right_tab("preview")
        self.status_badge.setText("ĐANG QUÉT")
        self.status_badge.setStyleSheet("""
            background-color: #ecfdf5;
            color: #047857;
            font-size: 11px;
            font-weight: 700;
            padding: 3px 8px;
            border-radius: 6px;
            border: 1px solid #a7f3d0;
        """)
        self.status_title.setText("Đang phân tích OCR trực quan...")
        self.status_desc.setText("Đang khởi động công cụ AI...")
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(10)

        self.worker_thread = OCRWorkerThread(self.selected_files)
        self.worker_thread.progress_update.connect(self.on_worker_progress)
        self.worker_thread.finished_success.connect(self.on_worker_success)
        self.worker_thread.finished_error.connect(self.on_worker_error)
        self.worker_thread.start()

    def on_worker_progress(self, data: dict):
        msg = data.get("message", "")
        self.status_desc.setText(msg)

        task_idx = data.get("task_index", 0)
        curr = data.get("progress_current", 0)
        tot = data.get("progress_total", 0)

        if task_idx == 2:
            if tot > 0:
                pct = 15 + int((curr / tot) * 70)
                self.progress_bar.setValue(min(pct, 85))
            else:
                self.progress_bar.setValue(40)

            # CẬP NHẬT PREVIEW TRỰC QUAN THỜI GIAN THỰC
            ann_img = data.get("annotated_image")
            fn = data.get("filename", "")
            info = data.get("info", {})
            if ann_img is not None:
                self.analyzed_previews.append({"fn": fn, "img": ann_img, "info": info})
                self.current_preview_idx = len(self.analyzed_previews) - 1
                self.update_live_preview(ann_img, info, fn=fn)

        elif task_idx == 3:
            self.progress_bar.setValue(90)
        elif task_idx == 4:
            self.progress_bar.setValue(100)

    def on_worker_success(self, results: dict):
        self.all_results = results
        self.last_raw_ocr_items = results.get("raw_ocr_results", [])
        self.btn_start.setEnabled(True)
        self.dropzone.setEnabled(True)
        self.btn_clear_all.setEnabled(True)
        self.btn_export.setEnabled(True)
        self.btn_gemini_export.setEnabled(True)

        self.status_badge.setText("HOÀN TẤT")
        self.status_badge.setStyleSheet("""
            background-color: #f0fdf4;
            color: #16a34a;
            font-size: 11px;
            font-weight: 700;
            padding: 3px 8px;
            border-radius: 6px;
            border: 1px solid #bbf7d0;
        """)
        self.status_title.setText("Đã hoàn tất phân tích OCR")
        self.status_desc.setText("AI đã track chính xác vùng chữ & đối soát điểm bán thành công.")
        self.progress_bar.setValue(100)

        # Mặc định hiển thị tab Báo cáo kết quả, nhưng người dùng có thể bấm sang Tab Preview bất cứ lúc nào
        self.switch_right_tab("report")

        summary = results.get("summary", {})
        total_imgs = summary.get("total_images", 0)
        valid_stores = summary.get("valid_stores", 0)
        warning_cnt = summary.get("warning_total", 0)

        self.kpi_total_imgs.setText(str(total_imgs))
        self.kpi_valid_stores.setText(str(valid_stores))
        self.kpi_warning_count.setText(str(warning_cnt))

        details = results.get("details", [])
        c_all = len(details)
        c_valid = sum(1 for d in details if d.get("status") in ("valid", "duplicate"))
        c_dup = sum(1 for d in details if d.get("status") == "duplicate")
        c_unrel = sum(1 for d in details if d.get("status") == "unrelated")

        self.btn_filter_all.setText(f"Tất cả ({c_all})")
        self.btn_filter_valid.setText(f"Hợp lệ ({c_valid})")
        self.btn_filter_dup.setText(f"Trùng lặp ({c_dup})")
        self.btn_filter_unrel.setText(f"Không liên quan ({c_unrel})")

        # Cập nhật danh sách Nhân viên vào Dropdown và Dải Thẻ Chip
        staff_summary = summary.get("staff_summary", {})
        self.combo_filter_sr.blockSignals(True)
        self.combo_filter_sr.clear()
        self.combo_filter_sr.addItem(f"Tất cả nhân viên ({valid_stores} điểm)", "all")

        # Xóa các chip cũ
        while self.staff_chip_layout.count():
            item = self.staff_chip_layout.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()

        self.staff_chips = []

        # Chip 'Tất cả'
        btn_chip_all = QPushButton(f"Tất cả ({valid_stores} điểm)")
        btn_chip_all.setCursor(Qt.PointingHandCursor)
        btn_chip_all.clicked.connect(lambda _, k="all": self.set_staff_filter_from_chip(k))
        self.staff_chip_layout.addWidget(btn_chip_all)
        self.staff_chips.append((btn_chip_all, "all"))

        for sr_name, s_data in staff_summary.items():
            st_cnt = s_data.get("total_stores", 0)
            p_cnt = s_data.get("total_photos", 0)
            self.combo_filter_sr.addItem(f"👤 {sr_name} ({st_cnt} điểm - {p_cnt} ảnh)", sr_name)

            btn_chip = QPushButton(f"👤 {sr_name}: {st_cnt} điểm ({p_cnt} ảnh)")
            btn_chip.setCursor(Qt.PointingHandCursor)
            btn_chip.clicked.connect(lambda _, k=sr_name: self.set_staff_filter_from_chip(k))
            self.staff_chip_layout.addWidget(btn_chip)
            self.staff_chips.append((btn_chip, sr_name))

        self.staff_chip_layout.addStretch()
        self.staff_chip_container.setVisible(len(staff_summary) > 0)
        self.combo_filter_sr.blockSignals(False)
        self.current_filter_sr = "all"
        self.update_staff_chips_style()

        self.populate_table(details)

    def on_worker_error(self, err_msg: str):
        self.btn_start.setEnabled(True)
        self.dropzone.setEnabled(True)
        self.btn_clear_all.setEnabled(True)
        self.view_report.setVisible(False)
        self.view_waiting.setVisible(True)
        self.status_title.setText("Có lỗi xảy ra")
        self.status_desc.setText(err_msg)
        self.progress_bar.setVisible(False)
        QMessageBox.critical(self, "Lỗi phân tích", f"Không thể xử lý ảnh:\n{err_msg}")

    def populate_table(self, rows: List[Dict[str, Any]]):
        self.table.setRowCount(len(rows))

        for r_idx, row_data in enumerate(rows):
            self.table.setRowHeight(r_idx, 62)

            stt = f"{row_data.get('stt', r_idx + 1):02d}"
            date_str = row_data.get("date", "--/--/----")
            time_str = row_data.get("time", "--:--")
            raw_address = row_data.get("address", "")
            address = format_clean_address(raw_address)
            sr = row_data.get("sr", "--")
            company = row_data.get("company", "--")
            tm_code = row_data.get("timemark_code", "--")
            count = row_data.get("count", 1)
            file_list = row_data.get("file_list", [])
            status = row_data.get("status", "valid")

            # Chuỗi tìm kiếm toàn diện cho dòng (bao gồm cả mã timecode)
            search_text = f"{address} {sr} {company} {tm_code} {date_str} {time_str}".lower()

            # 0. STT (Lưu UserRole cho lọc & tìm kiếm để tránh lỗi vẽ đè chữ của QTableWidget)
            stt_item = QTableWidgetItem(stt)
            stt_item.setTextAlignment(Qt.AlignCenter)
            stt_item.setForeground(QColor("#64748b"))
            stt_font = QFont("Segoe UI", 10)
            stt_font.setWeight(QFont.DemiBold)
            stt_item.setFont(stt_font)
            stt_item.setData(Qt.UserRole, status)
            stt_item.setData(Qt.UserRole + 1, search_text)
            stt_item.setData(Qt.UserRole + 2, sr)
            self.table.setItem(r_idx, 0, stt_item)

            # 1. Thời gian (Ngày + Giờ xếp tầng)
            self.table.setItem(r_idx, 1, QTableWidgetItem(""))
            time_widget = QWidget()
            tw_l = QVBoxLayout(time_widget)
            tw_l.setContentsMargins(4, 6, 4, 6)
            tw_l.setSpacing(2)
            tw_l.setAlignment(Qt.AlignCenter)

            d_lbl = QLabel(date_str)
            d_lbl.setStyleSheet("font-size: 11.5px; font-weight: 700; color: #1e293b; border: none; background: transparent;")
            d_lbl.setAlignment(Qt.AlignCenter)
            tw_l.addWidget(d_lbl)

            t_badge = QLabel(time_str)
            t_badge.setStyleSheet("""
                background-color: #f1f5f9;
                color: #475569;
                font-size: 10.5px;
                font-weight: 600;
                padding: 1px 8px;
                border-radius: 6px;
                border: 1px solid #e2e8f0;
            """)
            t_badge.setAlignment(Qt.AlignCenter)
            tw_l.addWidget(t_badge)
            self.table.setCellWidget(r_idx, 1, time_widget)

            # 2. Nhân viên SR (Tên nhân viên sạch, bỏ avatar tròn thừa)
            self.table.setItem(r_idx, 2, QTableWidgetItem(""))
            sr_widget = QWidget()
            sw_l = QHBoxLayout(sr_widget)
            sw_l.setContentsMargins(10, 6, 10, 6)
            sw_l.setAlignment(Qt.AlignVCenter | Qt.AlignLeft)

            if sr and sr != "--":
                name_lbl = QLabel(sr)
                name_lbl.setStyleSheet("font-size: 12px; font-weight: 600; color: #334155; border: none; background: transparent;")
                sw_l.addWidget(name_lbl)
            else:
                dash_lbl = QLabel("--")
                dash_lbl.setStyleSheet("color: #94a3b8; font-size: 12px; border: none; background: transparent;")
                sw_l.addWidget(dash_lbl)
            sw_l.addStretch()
            self.table.setCellWidget(r_idx, 2, sr_widget)

            # 3. Công ty (Badge doanh nghiệp thanh nhã)
            self.table.setItem(r_idx, 3, QTableWidgetItem(""))
            cp_widget = QWidget()
            cw_l = QHBoxLayout(cp_widget)
            cw_l.setContentsMargins(6, 6, 6, 6)
            cw_l.setSpacing(6)
            cw_l.setAlignment(Qt.AlignCenter)

            if company and company != "--":
                cp_badge = QLabel(company)
                cp_badge.setStyleSheet("""
                    background-color: #f8fafc;
                    color: #334155;
                    font-size: 11px;
                    font-weight: 600;
                    padding: 4px 10px;
                    border-radius: 6px;
                    border: 1px solid #e2e8f0;
                """)
                cp_badge.setAlignment(Qt.AlignCenter)
                cw_l.addWidget(cp_badge)
            else:
                dash_cp = QLabel("--")
                dash_cp.setStyleSheet("color: #94a3b8; font-size: 12px; border: none; background: transparent;")
                cw_l.addWidget(dash_cp)
            self.table.setCellWidget(r_idx, 3, cp_widget)

            # 4. Địa chỉ điểm bán (Chữ sạch, rõ nét, bỏ icon pin)
            self.table.setItem(r_idx, 4, QTableWidgetItem(""))
            addr_widget = QWidget()
            aw_l = QHBoxLayout(addr_widget)
            aw_l.setContentsMargins(12, 6, 12, 6)
            aw_l.setAlignment(Qt.AlignVCenter | Qt.AlignLeft)

            txt_addr = QLabel(address)
            txt_addr.setWordWrap(True)
            if status == "unrelated":
                txt_addr.setStyleSheet("font-size: 12px; color: #b91c1c; font-style: italic; font-weight: 500; border: none; background: transparent;")
            else:
                txt_addr.setStyleSheet("font-size: 12.5px; color: #0f172a; font-weight: 600; border: none; background: transparent;")
            txt_addr.setToolTip(address)
            aw_l.addWidget(txt_addr, stretch=1)
            self.table.setCellWidget(r_idx, 4, addr_widget)

            # 5. Mã Timemark / Timecode (Hiển thị trực tiếp ra bảng)
            self.table.setItem(r_idx, 5, QTableWidgetItem(""))
            tm_widget = QWidget()
            tm_l = QHBoxLayout(tm_widget)
            tm_l.setContentsMargins(4, 6, 4, 6)
            tm_l.setAlignment(Qt.AlignCenter)

            if tm_code and tm_code != "--":
                lbl_tm = QLabel(tm_code)
                lbl_tm.setStyleSheet("""
                    background-color: #eff6ff;
                    color: #1d4ed8;
                    font-size: 11px;
                    font-weight: 700;
                    padding: 3px 8px;
                    border-radius: 6px;
                    border: 1px solid #bfdbfe;
                """)
                lbl_tm.setAlignment(Qt.AlignCenter)
                tm_l.addWidget(lbl_tm)
            else:
                dash_tm = QLabel("--")
                dash_tm.setStyleSheet("color: #94a3b8; font-size: 12px; border: none; background: transparent;")
                dash_tm.setAlignment(Qt.AlignCenter)
                tm_l.addWidget(dash_tm)
            self.table.setCellWidget(r_idx, 5, tm_widget)

            # 6. Hình ảnh (Thumbnail bo góc & Pill số lượng ảnh)
            self.table.setItem(r_idx, 6, QTableWidgetItem(""))
            badge_widget = QWidget()
            bw_l = QHBoxLayout(badge_widget)
            bw_l.setContentsMargins(6, 6, 6, 6)
            bw_l.setSpacing(6)
            bw_l.setAlignment(Qt.AlignCenter)

            first_file = file_list[0] if file_list else ""
            match_path = None
            for p in self.selected_files:
                if os.path.basename(p) == first_file:
                    match_path = p
                    break

            thumb_lbl = QLabel()
            thumb_lbl.setFixedSize(40, 32)
            thumb_lbl.setCursor(Qt.PointingHandCursor)
            thumb_lbl.setStyleSheet("border-radius: 6px; border: 1px solid #cbd5e1; background-color: #f1f5f9;")
            thumb_lbl.setAlignment(Qt.AlignCenter)
            if match_path:
                pix = safe_load_pixmap(match_path, 38, 30)
                if not pix.isNull():
                    thumb_lbl.setPixmap(pix)
                thumb_lbl.mousePressEvent = lambda ev, p=match_path, d=row_data: self.open_full_image_viewer(p, d)
            bw_l.addWidget(thumb_lbl)

            if count > 1:
                cnt_style = """
                    background-color: #eff6ff;
                    color: #2563eb;
                    font-size: 11px;
                    font-weight: 700;
                    padding: 3px 8px;
                    border-radius: 10px;
                    border: 1px solid #bfdbfe;
                """
            else:
                cnt_style = """
                    background-color: #f1f5f9;
                    color: #475569;
                    font-size: 11px;
                    font-weight: 600;
                    padding: 3px 8px;
                    border-radius: 10px;
                    border: 1px solid #e2e8f0;
                """
            cnt_pill = QLabel(f"{count} ảnh")
            cnt_pill.setStyleSheet(cnt_style)
            bw_l.addWidget(cnt_pill)
            self.table.setCellWidget(r_idx, 6, badge_widget)

            # 7. Trạng thái (Pill status sạch, bỏ icon/emoji rác)
            self.table.setItem(r_idx, 7, QTableWidgetItem(""))
            status_container = QWidget()
            sc_l = QHBoxLayout(status_container)
            sc_l.setContentsMargins(4, 4, 4, 4)
            sc_l.setAlignment(Qt.AlignCenter)

            stat_lbl = QLabel()
            if status == "valid":
                stat_lbl.setText("Hợp lệ")
                stat_lbl.setStyleSheet("""
                    background-color: #ecfdf5;
                    color: #047857;
                    border: 1px solid #a7f3d0;
                    font-size: 11px;
                    font-weight: 700;
                    padding: 5px 12px;
                    border-radius: 12px;
                """)
            elif status == "duplicate":
                dup_cnt = max(1, count - 1)
                stat_lbl.setText(f"Hợp lệ (Trùng {dup_cnt} ảnh)")
                stat_lbl.setToolTip(f"Điểm bán này được tính 1 ảnh hợp lệ. Cảnh báo phát hiện {dup_cnt} ảnh chụp trùng.")
                stat_lbl.setStyleSheet("""
                    background-color: #fffbeb;
                    color: #b45309;
                    border: 1px solid #fde68a;
                    font-size: 11px;
                    font-weight: 700;
                    padding: 5px 12px;
                    border-radius: 12px;
                """)
            else:
                stat_lbl.setText("Không liên quan")
                stat_lbl.setStyleSheet("""
                    background-color: #fef2f2;
                    color: #b91c1c;
                    border: 1px solid #fecaca;
                    font-size: 11px;
                    font-weight: 700;
                    padding: 5px 12px;
                    border-radius: 12px;
                """)
            sc_l.addWidget(stat_lbl)
            self.table.setCellWidget(r_idx, 7, status_container)

            # 8. Nút Thao tác (Modern soft button)
            self.table.setItem(r_idx, 8, QTableWidgetItem(""))
            btn_container = QWidget()
            bc_l = QHBoxLayout(btn_container)
            bc_l.setContentsMargins(4, 4, 4, 4)
            bc_l.setAlignment(Qt.AlignCenter)

            btn_view = QPushButton("Chi tiết")
            btn_view.setCursor(Qt.PointingHandCursor)
            btn_view.setFixedSize(72, 28)
            btn_view.setStyleSheet("""
                QPushButton {
                    background-color: #ffffff;
                    color: #2563eb;
                    border: 1px solid #bfdbfe;
                    border-radius: 6px;
                    font-size: 11.5px;
                    font-weight: 600;
                }
                QPushButton:hover {
                    background-color: #2563eb;
                    color: #ffffff;
                    border-color: #2563eb;
                }
            """)
            btn_view.clicked.connect(lambda _, d=row_data: self.show_detail(d))
            bc_l.addWidget(btn_view)
            self.table.setCellWidget(r_idx, 8, btn_container)

        self.filter_table(self.search_box.text())

    def show_detail(self, row_data: dict):
        dlg = StoreDetailDialog(row_data, self.selected_files, self)
        dlg.exec()

    def on_sr_filter_changed(self):
        self.current_filter_sr = self.combo_filter_sr.currentData() or "all"
        self.update_staff_chips_style()
        self.filter_table(self.search_box.text())

    def update_staff_chips_style(self):
        if not hasattr(self, 'staff_chips'):
            return
        for btn, sr_val in self.staff_chips:
            is_active = (self.current_filter_sr == sr_val)
            if is_active:
                btn.setStyleSheet("""
                    QPushButton {
                        background-color: #1d4ed8;
                        color: #ffffff;
                        font-size: 11.5px;
                        font-weight: 700;
                        border: 1px solid #1e40af;
                        border-radius: 6px;
                        padding: 3px 10px;
                    }
                """)
            else:
                btn.setStyleSheet("""
                    QPushButton {
                        background-color: #f1f5f9;
                        color: #334155;
                        font-size: 11.5px;
                        font-weight: 600;
                        border: 1px solid #cbd5e1;
                        border-radius: 6px;
                        padding: 3px 10px;
                    }
                    QPushButton:hover {
                        background-color: #e2e8f0;
                        color: #0f172a;
                    }
                """)

    def set_staff_filter_from_chip(self, sr_key: str):
        # Đồng bộ chuyển index của combo_filter_sr
        for i in range(self.combo_filter_sr.count()):
            if self.combo_filter_sr.itemData(i) == sr_key:
                self.combo_filter_sr.setCurrentIndex(i)
                return
        self.current_filter_sr = sr_key
        self.update_staff_chips_style()
        self.filter_table(self.search_box.text())

    def filter_table(self, query: str):
        q = query.strip().lower()
        visible_count = 0
        total = self.table.rowCount()

        for row in range(total):
            item_meta = self.table.item(row, 0)
            if not item_meta:
                self.table.setRowHidden(row, False)
                visible_count += 1
                continue

            row_status = item_meta.data(Qt.UserRole)
            text_all = (item_meta.data(Qt.UserRole + 1) or "").lower()
            row_sr = (item_meta.data(Qt.UserRole + 2) or "").strip()

            # 1. Khớp trạng thái (Tất cả / Hợp lệ / Trùng lặp / Không liên quan)
            if self.current_filter_status == "all":
                status_match = True
            elif self.current_filter_status == "valid":
                status_match = (row_status in ("valid", "duplicate"))
            elif self.current_filter_status == "duplicate":
                status_match = (row_status == "duplicate")
            elif self.current_filter_status == "unrelated":
                status_match = (row_status == "unrelated")
            else:
                status_match = True

            # 2. Khớp từ khóa tìm kiếm
            text_match = (q in text_all) if q else True

            # 3. Khớp Nhân viên (SR)
            if self.current_filter_sr == "all":
                sr_match = True
            else:
                sr_match = (row_sr == self.current_filter_sr)

            matched = status_match and text_match and sr_match
            self.table.setRowHidden(row, not matched)
            if matched:
                visible_count += 1

        self.lbl_footer.setText(f"Hiển thị {visible_count} trong tổng số {total} kết quả")

    def export_to_excel(self):
        details = self.all_results.get("details", [])
        if not details:
            QMessageBox.information(self, "Thông báo", "Chưa có kết quả để xuất file!")
            return

        default_name = f"diem_ban_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
        save_path, _ = QFileDialog.getSaveFileName(
            self,
            "Lưu báo cáo Excel",
            default_name,
            "Excel Workbook (*.xlsx)"
        )
        if not save_path:
            return

        try:
            # Điểm bán hợp lệ bao gồm cả điểm trùng ảnh (tính 1 ảnh)
            valid_list = [d for d in details if d.get("status") in ("valid", "duplicate")]
            warn_list = [d for d in details if d.get("status") in ("duplicate", "unrelated")]

            def build_valid_df(items):
                rows = []
                for idx, it in enumerate(items, 1):
                    cnt = it.get("count", 1)
                    st = it.get("status", "valid")
                    if st == "duplicate":
                        dup_cnt = max(1, cnt - 1)
                        st_label = f"Hợp lệ (Trùng {dup_cnt} ảnh)"
                        note = f"Tính 1 ảnh hợp lệ, cảnh báo có {dup_cnt} ảnh trùng"
                    else:
                        st_label = "Hợp lệ"
                        note = ""

                    rows.append({
                        "STT": idx,
                        "Ngày": it.get("date", "--"),
                        "Giờ": it.get("time", "--"),
                        "Nhân viên (SR)": it.get("sr", "--"),
                        "Công ty": it.get("company", "--"),
                        "Địa chỉ điểm bán": format_clean_address(it.get("address", "")),
                        "Mã Timemark": it.get("timemark_code", "--"),
                        "Trạng thái": st_label,
                        "Số ảnh chụp": cnt,
                        "Số ảnh tính": 1,
                        "Danh sách file ảnh": it.get("files", ""),
                        "Ghi chú": note
                    })
                return pd.DataFrame(rows)

            def build_warn_df(items):
                rows = []
                for idx, it in enumerate(items, 1):
                    cnt = it.get("count", 1)
                    st = it.get("status", "valid")
                    if st == "duplicate":
                        dup_cnt = max(1, cnt - 1)
                        st_label = f"Trùng {dup_cnt} ảnh (Đã tính 1)"
                        note = f"Phát hiện {dup_cnt} ảnh trùng lặp. Đã ghi nhận 1 ảnh vào sheet Điểm Bán Hợp Lệ."
                        dup_col = dup_cnt
                    else:
                        st_label = "Không liên quan"
                        note = it.get("reason", "Ảnh không hợp lệ")
                        dup_col = 0

                    rows.append({
                        "STT": idx,
                        "Ngày": it.get("date", "--"),
                        "Giờ": it.get("time", "--"),
                        "Nhân viên (SR)": it.get("sr", "--"),
                        "Công ty": it.get("company", "--"),
                        "Địa chỉ": format_clean_address(it.get("address", "")),
                        "Mã Timemark": it.get("timemark_code", "--"),
                        "Trạng thái": st_label,
                        "Số ảnh chụp": cnt,
                        "Số ảnh trùng": dup_col,
                        "Danh sách file ảnh": it.get("files", ""),
                        "Chi tiết cảnh báo": note
                    })
                return pd.DataFrame(rows)

            def build_kpi_df(items):
                staff_stats = {}
                for it in items:
                    if it.get("status") == "unrelated":
                        continue
                    sr = (it.get("sr") or "--").strip()
                    if sr not in staff_stats:
                        staff_stats[sr] = {
                            "total_stores": 0,
                            "standard_stores": 0,
                            "single_stores": 0,
                            "dup_stores": 0,
                            "total_photos": 0
                        }
                    staff_stats[sr]["total_stores"] += 1
                    c = it.get("count", 1)
                    staff_stats[sr]["total_photos"] += c
                    if c == 2:
                        staff_stats[sr]["standard_stores"] += 1
                    elif c > 2:
                        staff_stats[sr]["dup_stores"] += 1
                    else:
                        staff_stats[sr]["single_stores"] += 1

                rows = []
                for idx, (sr, s) in enumerate(staff_stats.items(), 1):
                    rate = f"{(s['standard_stores'] / s['total_stores'] * 100):.1f}%" if s['total_stores'] > 0 else "0%"
                    rows.append({
                        "STT": idx,
                        "Nhân viên (SR)": sr,
                        "Tổng điểm bán": s["total_stores"],
                        "Đạt chuẩn (2 ảnh)": s["standard_stores"],
                        "Thiếu ảnh (1 ảnh)": s["single_stores"],
                        "Chụp dư (>2 ảnh)": s["dup_stores"],
                        "Tổng số ảnh chụp": s["total_photos"],
                        "Tỷ lệ đạt chuẩn": rate
                    })
                return pd.DataFrame(rows)

            df_valid = build_valid_df(valid_list)
            df_kpi = build_kpi_df(details)
            df_warn = build_warn_df(warn_list)

            with pd.ExcelWriter(save_path, engine='openpyxl') as writer:
                df_valid.to_excel(writer, index=False, sheet_name="Điểm Bán Hợp Lệ")
                df_kpi.to_excel(writer, index=False, sheet_name="KPI Nhân Viên")
                df_warn.to_excel(writer, index=False, sheet_name="Trùng Lặp & Cảnh Báo")

                from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
                header_font = Font(name="Segoe UI", size=11, bold=True, color="FFFFFF")
                header_fill_blue = PatternFill(start_color="1E293B", end_color="1E293B", fill_type="solid")
                header_fill_green = PatternFill(start_color="15803D", end_color="15803D", fill_type="solid")
                header_fill_amber = PatternFill(start_color="9A3412", end_color="9A3412", fill_type="solid")
                cell_font = Font(name="Segoe UI", size=10)
                thin_border = Border(
                    left=Side(style='thin', color='CBD5E1'),
                    right=Side(style='thin', color='CBD5E1'),
                    top=Side(style='thin', color='CBD5E1'),
                    bottom=Side(style='thin', color='CBD5E1')
                )

                sheet_configs = [
                    ("Điểm Bán Hợp Lệ", header_fill_blue),
                    ("KPI Nhân Viên", header_fill_green),
                    ("Trùng Lặp & Cảnh Báo", header_fill_amber)
                ]

                for sheet_name, fill in sheet_configs:
                    ws = writer.sheets[sheet_name]
                    for col_idx, col in enumerate(ws.columns, start=1):
                        max_len = 0
                        for r_idx, cell in enumerate(col, start=1):
                            cell.border = thin_border
                            if r_idx == 1:
                                cell.font = header_font
                                cell.fill = fill
                                cell.alignment = Alignment(horizontal="center", vertical="center")
                            else:
                                cell.font = cell_font
                                if col_idx in (1, 2, 3, 5, 7, 8, 9, 10):
                                    cell.alignment = Alignment(horizontal="center", vertical="center")
                                else:
                                    cell.alignment = Alignment(horizontal="left", vertical="center")

                            v_str = str(cell.value or "")
                            if len(v_str) > max_len:
                                max_len = len(v_str)

                        col_letter = ws.cell(row=1, column=col_idx).column_letter
                        ws.column_dimensions[col_letter].width = max(max_len + 4, 14)

            QMessageBox.information(self, "Thành công", f"Đã xuất file Excel thành công tại:\n{save_path}")
        except Exception as e:
            QMessageBox.critical(self, "Lỗi xuất Excel", f"Không thể lưu file:\n{str(e)}")

    def open_gemini_dialog(self, initial_tab: int = 0):
        engine = get_ocr_engine()
        raw_records = []

        if self.last_raw_ocr_items:
            raw_records = engine.format_gemini_export_records(self.last_raw_ocr_items)
        elif self.all_results and self.all_results.get("details"):
            # Lấy thông tin từ bảng details nếu không có raw_ocr_items
            details = self.all_results.get("details", [])
            for d in details:
                fl = d.get("file_list") or [d.get("files", "")]
                for f in fl:
                    f_name = os.path.basename(f) if f else ""
                    raw_records.append({
                        "id": len(raw_records) + 1,
                        "filename": f_name,
                        "sr": d.get("sr", "--"),
                        "company": d.get("company", "--"),
                        "address": d.get("address", ""),
                        "gps": d.get("gps", ""),
                        "date": d.get("date", "--/--/----"),
                        "time": d.get("time", "--:--"),
                        "raw_text": d.get("address", "")
                    })
        elif self.selected_files:
            # Chưa chạy OCR trước đó: thực hiện trích xuất nhanh các trường từ các ảnh đã chọn
            prog = QProgressDialog("Đang trích xuất dữ liệu nhanh từ ảnh để chuẩn bị xuất JSON...", "Hủy", 0, len(self.selected_files), self)
            prog.setWindowTitle("Trích xuất thông tin OCR")
            prog.setWindowModality(Qt.WindowModal)
            prog.show()
            QApplication.processEvents()

            quick_items = []
            for idx, path in enumerate(self.selected_files):
                if prog.wasCanceled():
                    break
                prog.setValue(idx)
                QApplication.processEvents()
                img = safe_read_cv2(path)
                if img is not None:
                    fn = os.path.basename(path)
                    info = engine.extract_timemark_info(img)
                    info["filename"] = fn
                    info["filepath"] = path
                    quick_items.append(info)
            prog.setValue(len(self.selected_files))
            if quick_items:
                self.last_raw_ocr_items = quick_items
                raw_records = engine.format_gemini_export_records(quick_items)

        # Mở hộp thoại Gemini Assistant Dialog
        dlg = GeminiAssistantDialog(
            raw_records=raw_records,
            on_apply=self.apply_gemini_cleaned_data,
            initial_tab=initial_tab if raw_records else 1,
            parent=self
        )
        dlg.exec()

    def apply_gemini_cleaned_data(self, cleaned_data: list):
        if not cleaned_data:
            return
        try:
            engine = get_ocr_engine()
            results = engine.group_from_cleaned_records(cleaned_data, existing_items=self.last_raw_ocr_items)
            self.on_worker_success(results)
            self.status_title.setText("Đã chấm điểm bán thành công từ dữ liệu làm sạch bởi Gemini")
            self.status_desc.setText(f"Dữ liệu được chuẩn hóa bởi Gemini ({len(cleaned_data)} ảnh, {results['summary']['valid_stores']} điểm bán).")
            QMessageBox.information(
                self,
                "Chấm điểm thành công",
                f"Đã đối soát và chấm điểm bán thành công từ dữ liệu làm sạch bởi Gemini!\n\n"
                f"• Tổng số ảnh: {len(cleaned_data)}\n"
                f"• Số điểm bán hợp lệ: {results['summary']['valid_stores']}\n"
                f"• Điểm bán đạt chuẩn (2 ảnh): {results['summary']['standard_stores']}\n"
                f"• Điểm thiếu / trùng: {results['summary']['warning_total']}\n\n"
                f"Dữ liệu địa chỉ, tên SR đã được cập nhật chuẩn đẹp vào bảng bên dưới!"
            )
        except Exception as e:
            QMessageBox.critical(self, "Lỗi chấm điểm", f"Không thể xử lý dữ liệu JSON đã làm sạch:\n{str(e)}")

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, 'current_preview_cv_img') and self.current_preview_cv_img is not None:
            self.adjust_preview_frame_aspect(self.current_preview_cv_img)
            pix = self.preview_img_label.pixmap()
            if pix and not pix.isNull():
                frame_w = max(self.preview_frame.width() - 8, 200)
                frame_h = max(self.preview_frame.height() - 8, 300)
                scaled = pix.scaled(frame_w, frame_h, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                self.preview_img_label.setPixmap(scaled)


def main():
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()


