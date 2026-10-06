import os
import sys
import re
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
torch_lib = r'D:\python\Lib\site-packages\torch\lib'
if os.path.exists(torch_lib):
    try:
        os.add_dll_directory(torch_lib)
    except Exception:
        pass
try:
    import torch
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
    QProgressBar, QDialog, QAbstractItemView, QGridLayout
)
from PySide6.QtSvg import QSvgRenderer

# ----------------- VECTOR SVG ICONS (NO EMOJIS) -----------------
SVG_CAMERA = '''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M14.5 4h-5L7 7H4a2 2 0 0 0-2 2v9a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2V9a2 2 0 0 0-2-2h-3l-2.5-3z"/><circle cx="12" cy="13" r="3"/></svg>'''

SVG_CLOUD_UPLOAD = '''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M4 14.899A7 7 0 1 1 15.71 8h1.79a4.5 4.5 0 0 1 2.5 8.242"/><path d="M12 12v9"/><path d="m16 16-4-4-4 4"/></svg>'''

SVG_IMAGE = '''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect width="18" height="18" x="3" y="3" rx="2" ry="2"/><circle cx="9" cy="9" r="2"/><path d="m21 15-3.086-3.086a2 2 0 0 0-2.828 0L6 21"/></svg>'''

SVG_CHECK_CIRCLE = '''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/><polyline points="22 4 12 14.01 9 11.01"/></svg>'''

SVG_ALERT_TRIANGLE = '''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3Z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg>'''

SVG_MAP_PIN = '''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M20 10c0 6-8 12-8 12s-8-6-8-12a8 8 0 0 1 16 0Z"/><circle cx="12" cy="10" r="3"/></svg>'''

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

def safe_read_cv2(file_path: str):
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
    cleaned = re.sub(r'^[a-zA-Z0-9][\.\,]\s*', '', addr.strip())
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
    def __init__(self, image_path: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"Xem ảnh: {os.path.basename(image_path)}")
        self.resize(960, 720)
        self.setMinimumSize(700, 500)
        self.setStyleSheet("""
            QDialog {
                background-color: #0f172a;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 14, 18, 16)
        layout.setSpacing(12)

        # Top Bar
        top_bar = QHBoxLayout()
        top_bar.setSpacing(10)

        lbl_fname = QLabel(os.path.basename(image_path))
        lbl_fname.setStyleSheet("color: #f8fafc; font-size: 14px; font-weight: 700; border: none; background: transparent;")
        top_bar.addWidget(lbl_fname)

        top_bar.addStretch()

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
                border: 1px solid #1e293b;
                border-radius: 8px;
                background-color: #020617;
            }
        """)

        container = QWidget()
        container.setStyleSheet("background-color: transparent;")
        c_layout = QVBoxLayout(container)
        c_layout.setContentsMargins(10, 10, 10, 10)
        c_layout.setAlignment(Qt.AlignCenter)

        img_label = QLabel()
        img_label.setAlignment(Qt.AlignCenter)
        img_label.setStyleSheet("border: none; background: transparent;")

        pix = safe_load_pixmap(image_path, 1600, 1200)
        if not pix.isNull():
            img_label.setPixmap(pix)
        else:
            img_label.setText("Không thể tải hình ảnh này")
            img_label.setStyleSheet("color: #94a3b8; font-size: 14px; border: none;")

        c_layout.addWidget(img_label)
        scroll.setWidget(container)
        layout.addWidget(scroll, stretch=1)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape:
            self.accept()
        else:
            super().keyPressEvent(event)


# ----------------- DETAIL MODAL DIALOG -----------------
class StoreDetailDialog(QDialog):
    def __init__(self, data: dict, all_selected_files: List[str] = None, parent=None):
        super().__init__(parent)
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
        dlg = ImageViewerDialog(file_path, self)
        dlg.exec()


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
        left_layout.addLayout(action_layout)

        top_cards_layout.addWidget(left_card, 6)

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
        self.right_main_layout.setContentsMargins(22, 20, 22, 20)
        self.right_main_layout.setSpacing(10)

        # 1. VIEW CHỜ & TIẾN TRÌNH (Khi chưa chạy hoặc đang chạy)
        self.view_waiting = QWidget()
        vw_l = QVBoxLayout(self.view_waiting)
        vw_l.setContentsMargins(0, 10, 0, 10)
        vw_l.setSpacing(10)
        vw_l.setAlignment(Qt.AlignCenter)

        self.illust_label = QLabel()
        self.illust_label.setAlignment(Qt.AlignCenter)
        self.illust_label.setStyleSheet("border: none; background: transparent;")
        self.illust_label.setPixmap(get_svg_pixmap(SVG_EMPTY_ILLUST, "#2563eb", 85, 85))
        vw_l.addWidget(self.illust_label)

        self.status_title = QLabel("Sẵn sàng để bắt đầu")
        self.status_title.setAlignment(Qt.AlignCenter)
        self.status_title.setStyleSheet("font-size: 16px; font-weight: 700; color: #0f172a; border: none;")
        vw_l.addWidget(self.status_title)

        self.status_desc = QLabel("Vui lòng chọn ảnh và nhấn 'Bắt đầu nhận diện' để AI phân tích.")
        self.status_desc.setWordWrap(True)
        self.status_desc.setAlignment(Qt.AlignCenter)
        self.status_desc.setStyleSheet("font-size: 13px; color: #64748b; line-height: 1.4; border: none;")
        vw_l.addWidget(self.status_desc)

        self.progress_bar = QProgressBar()
        self.progress_bar.setFixedHeight(8)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                background-color: #e2e8f0;
                border: none;
                border-radius: 4px;
            }
            QProgressBar::chunk {
                background-color: #2563eb;
                border-radius: 4px;
            }
        """)
        self.progress_bar.setVisible(False)
        vw_l.addWidget(self.progress_bar)
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

        # Nút Xuất Excel trực tiếp tại đây
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
        vr_l.addWidget(self.btn_export)

        self.view_report.setVisible(False)
        self.right_main_layout.addWidget(self.view_report)

        top_cards_layout.addWidget(self.right_card, 4)
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

        filter_layout.addStretch()
        main_vbox.addLayout(filter_layout)
        self.apply_filter_tab_styles()

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

    def start_ocr_process(self):
        if not self.selected_files:
            QMessageBox.warning(self, "Thông báo", "Vui lòng chọn ít nhất 1 ảnh trước khi bắt đầu!")
            return

        self.btn_start.setEnabled(False)
        self.dropzone.setEnabled(False)
        self.btn_clear_all.setEnabled(False)
        self.btn_export.setEnabled(False)

        # Chuyển sang giao diện tiến trình đang chạy
        self.view_report.setVisible(False)
        self.view_waiting.setVisible(True)
        self.status_title.setText("Đang phân tích...")
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
        elif task_idx == 3:
            self.progress_bar.setValue(90)
        elif task_idx == 4:
            self.progress_bar.setValue(100)

    def on_worker_success(self, results: dict):
        self.all_results = results
        self.btn_start.setEnabled(True)
        self.dropzone.setEnabled(True)
        self.btn_clear_all.setEnabled(True)
        self.btn_export.setEnabled(True)

        # Hiển thị trực tiếp Báo cáo kết quả tại Right Card
        self.view_waiting.setVisible(False)
        self.view_report.setVisible(True)

        summary = results.get("summary", {})
        total_imgs = summary.get("total_images", 0)
        valid_stores = summary.get("valid_stores", 0)
        warning_cnt = summary.get("warning_total", 0)

        self.kpi_total_imgs.setText(str(total_imgs))
        self.kpi_valid_stores.setText(str(valid_stores))
        self.kpi_warning_count.setText(str(warning_cnt))

        details = results.get("details", [])
        c_all = len(details)
        # Các điểm có ảnh trùng vẫn được tính 1 ảnh hợp lệ
        c_valid = sum(1 for d in details if d.get("status") in ("valid", "duplicate"))
        c_dup = sum(1 for d in details if d.get("status") == "duplicate")
        c_unrel = sum(1 for d in details if d.get("status") == "unrelated")

        self.btn_filter_all.setText(f"Tất cả ({c_all})")
        self.btn_filter_valid.setText(f"Hợp lệ ({c_valid})")
        self.btn_filter_dup.setText(f"Trùng lặp ({c_dup})")
        self.btn_filter_unrel.setText(f"Không liên quan ({c_unrel})")

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
            thumb_lbl.setStyleSheet("border-radius: 6px; border: 1px solid #cbd5e1; background-color: #f1f5f9;")
            thumb_lbl.setAlignment(Qt.AlignCenter)
            if match_path:
                pix = safe_load_pixmap(match_path, 38, 30)
                if not pix.isNull():
                    thumb_lbl.setPixmap(pix)
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
            text_match = (q in text_all) if q else True

            matched = status_match and text_match
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

            df_valid = build_valid_df(valid_list)
            df_warn = build_warn_df(warn_list)

            with pd.ExcelWriter(save_path, engine='openpyxl') as writer:
                df_valid.to_excel(writer, index=False, sheet_name="Điểm Bán Hợp Lệ")
                df_warn.to_excel(writer, index=False, sheet_name="Trùng Lặp & Cảnh Báo")

                from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
                header_font = Font(name="Segoe UI", size=11, bold=True, color="FFFFFF")
                header_fill_blue = PatternFill(start_color="1E293B", end_color="1E293B", fill_type="solid")
                header_fill_amber = PatternFill(start_color="9A3412", end_color="9A3412", fill_type="solid")
                cell_font = Font(name="Segoe UI", size=10)
                thin_border = Border(
                    left=Side(style='thin', color='CBD5E1'),
                    right=Side(style='thin', color='CBD5E1'),
                    top=Side(style='thin', color='CBD5E1'),
                    bottom=Side(style='thin', color='CBD5E1')
                )

                for sheet_name, fill in [("Điểm Bán Hợp Lệ", header_fill_blue), ("Trùng Lặp & Cảnh Báo", header_fill_amber)]:
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


def main():
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
