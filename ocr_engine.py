import os
import sys
import re
import math
import json
import unicodedata
from typing import Any, List, Dict, Optional
import cv2
import numpy as np
import yaml
from PIL import Image
from rapidfuzz import fuzz, process

if hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except Exception:
        pass

# 1. Cấu hình thư mục models nội bộ cho ứng dụng độc lập 100% Offline (Hỗ trợ PyInstaller .exe)
if getattr(sys, 'frozen', False):
    candidates = [
        getattr(sys, '_MEIPASS', ''),
        os.path.join(os.path.dirname(sys.executable), '_internal'),
        os.path.dirname(sys.executable)
    ]
else:
    candidates = [os.path.dirname(os.path.abspath(__file__))]

MODEL_DIR = None
for c in candidates:
    if c:
        m_dir = os.path.join(c, 'models')
        if os.path.exists(m_dir):
            MODEL_DIR = m_dir
            os.environ["PADDLE_PDX_CACHE_HOME"] = m_dir
            break

if not MODEL_DIR:
    MODEL_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'models')

# 2. Giới hạn số luồng CPU (Ngăn chặn 100% CPU lockup và chống nóng máy hiệu quả)
NUM_THREADS = "4"
os.environ["OMP_NUM_THREADS"] = NUM_THREADS
os.environ["MKL_NUM_THREADS"] = NUM_THREADS
os.environ["OPENBLAS_NUM_THREADS"] = NUM_THREADS
os.environ["VECLIB_MAXIMUM_THREADS"] = NUM_THREADS
os.environ["NUMEXPR_NUM_THREADS"] = NUM_THREADS

try:
    import torch
    torch.set_num_threads(4)
    torch_lib = os.path.join(os.path.dirname(torch.__file__), 'lib')
    if os.path.exists(torch_lib):
        try:
            os.add_dll_directory(torch_lib)
        except Exception:
            pass
except Exception:
    pass

from rapidocr_onnxruntime import RapidOCR
from vietocr.tool.predictor import Predictor
from vietocr.tool.config import Cfg

# Danh bạ 63 Tỉnh / Thành phố Việt Nam chuẩn hóa chính tả
PROVINCES_VN = [
    "An Giang", "Bà Rịa - Vũng Tàu", "Bắc Giang", "Bắc Kạn", "Bạc Liêu", "Bắc Ninh",
    "Bến Tre", "Bình Định", "Bình Dương", "Bình Phước", "Bình Thuận", "Cà Mau",
    "Cần Thơ", "Cao Bằng", "Đà Nẵng", "Đắk Lắk", "Đắk Nông", "Điện Biên", "Đồng Nai",
    "Đồng Tháp", "Gia Lai", "Hà Giang", "Hà Nam", "Hà Nội", "Hà Tĩnh", "Hải Dương",
    "Hải Phòng", "Hậu Giang", "Hòa Bình", "Hưng Yên", "Khánh Hòa", "Kiên Giang",
    "Kon Tum", "Lai Châu", "Lâm Đồng", "Lạng Sơn", "Lào Cai", "Long An", "Nam Định",
    "Nghệ An", "Ninh Bình", "Ninh Thuận", "Phú Thọ", "Phú Yên", "Quảng Bình",
    "Quảng Nam", "Quảng Ngãi", "Quảng Ninh", "Quảng Trị", "Sóc Trăng", "Sơn La",
    "Tây Ninh", "Thái Bình", "Thái Nguyên", "Thanh Hóa", "Thừa Thiên Huế", "Tiền Giang",
    "TP. Hồ Chí Minh", "Trà Vinh", "Tuyên Quang", "Vĩnh Long", "Vĩnh Phúc", "Yên Bái"
]

# Ánh xạ các huyện/thị đặc thù sang tỉnh để tự động sửa các lỗi OCR tỉnh bị cụt như 'Anh', 'An g'
DISTRICT_PROVINCE_MAP = {
    "thoại sơn": "An Giang",
    "chợ mới": "An Giang",
    "phú tân": "An Giang",
    "tri tôn": "An Giang",
    "tịnh biên": "An Giang",
    "châu thành": "An Giang",
    "châu đốc": "An Giang",
    "long xuyên": "An Giang",
    "an phú": "An Giang",
    "tân châu": "An Giang",
    "chợ vàm": "An Giang",
    "châu phú": "An Giang"
}

def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Tính khoảng cách địa lý giữa 2 tọa độ GPS theo mét (Haversine formula)."""
    R = 6371000.0  # mét
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2.0) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2.0) ** 2
    return 2.0 * R * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))

def extract_gps_coordinates(text: str):
    """Trích xuất cặp tọa độ GPS (Vĩ độ, Kinh độ) từ chuỗi văn bản Timemark."""
    if not text:
        return None
    m = re.search(r'(\d{1,2}\.\d{4,8})[\s\?°]*[nN]?[\,\s]+(\d{2,3}\.\d{4,8})[\s\?°\-]*[eE]?', text)
    if m:
        try:
            lat = float(m.group(1))
            lon = float(m.group(2))
            if 8.0 <= lat <= 24.0 and 102.0 <= lon <= 110.0:
                return lat, lon
        except ValueError:
            pass
    return None

def extract_house_number(addr: str):
    """Trích xuất số nhà chính xác (ví dụ: 804, 804/2, 12A), loại trừ số đường/ấp/khóm."""
    if not addr:
        return None
    # 1. Dạng có từ 'Số' đứng trước: 'số 804', 'Số 12A/3'
    m_so = re.search(r'\bs[ốo]\s*(\d+[a-zA-Z]?(?:/\d+[a-zA-Z]?)*)\b', addr, flags=re.IGNORECASE)
    if m_so:
        return m_so.group(1).upper()

    # 2. Xóa các danh xưng có số (Quốc lộ, Tỉnh lộ, ĐT, Đường 30/4, Khóm 1, Ấp 2, Phường 3) để tránh nhận nhầm thành số nhà
    clean = re.sub(r'\b(?:ql|tl|đt|đh|quốc\s*lộ|tỉnh\s*lộ|huyện\s*lộ)\s*\d+[a-zA-Z]?\b', '', addr, flags=re.IGNORECASE)
    clean = re.sub(r'\bđường\s*(?:30/4|3/2|19/5|2/9|26/3)\b', '', clean, flags=re.IGNORECASE)
    clean = re.sub(r'\b(?:ấp|khóm|thôn|tổ|khu\s*phố|kp|phường|quận|q\.)\s*\d+\b', '', clean, flags=re.IGNORECASE)

    # 3. Dạng đứng trước tên đường: '804 Đường Nguyễn Huệ', '12/4 Trần Hưng Đạo'
    m_front = re.search(r'(?:^|[,\s])(\d+[a-zA-Z]?(?:/\d+[a-zA-Z]?)*)\s+(?:đường|phố|ngõ|hẻm|[A-ZÀ-Ỹ])', clean, flags=re.IGNORECASE)
    if m_front:
        return m_front.group(1).upper()

    # 4. Dạng số đứng ở đầu địa chỉ (bao gồm cả OCR đọc nhầm số 1 thành T, I, l: vd 'T02' -> '102')
    m_ocr_one = re.match(r'^\s*([TIli|])(\d{2,4}[a-zA-Z]?)\b', clean)
    if m_ocr_one:
        return f"1{m_ocr_one.group(2)}".upper()

    m_start = re.match(r'^\s*(\d+[a-zA-Z]?(?:/\d+[a-zA-Z]?)*)\b', clean)
    if m_start:
        return m_start.group(1).upper()

    return None

def extract_hamlet(addr: str):
    """Trích xuất tên Ấp/Khóm/Thôn/Tổ dân phố đặc trưng (ví dụ: Ấp Tây -> tây, Khóm 2 -> 2, Ap Bắc Sơn -> bắc sơn)."""
    if not addr:
        return None
    m = re.search(r'\b((?:[aáàảãạâấầẩẫậăắằẳẵặ]p|kh[oóòỏõọôốồổỗộơớờởỡợ]m|thôn|t[ổoòóỏõọôốồổỗộ]|khu\s*ph[ốoòóỏõọôốồổỗộ]|kp)\s+[^,]+)', addr, flags=re.IGNORECASE)
    if m:
        h = m.group(1).strip()
        h = re.sub(r'^(?:[aáàảãạâấầẩẫậăắằẳẵặ]p|kh[oóòỏõọôốồổỗộơớờởỡợ]m|thôn|t[ổoòóỏõọôốồổỗộ]|khu\s*ph[ốoòóỏõọôốồổỗộ]|kp)\s*', '', h, flags=re.IGNORECASE).strip()
        return h.lower()
    return None

def extract_street_name(addr: str):
    """Trích xuất tên đường/tuyến đường lõi (Đường Nguyễn Huệ, QL91, TL943, Đường 30/4)."""
    if not addr:
        return None
    # Cắt trước các tên huyện/thị dính liền nếu có
    clean_st_addr = re.sub(r'[\,\s]+\b(thoại\s*sơn|núi\s*sập|chợ\s*mới|tri\s*tôn|tịnh\s*biên|châu\s*đốc|long\s*xuyên|phú\s*tân|châu\s*thành|an\s*phú|tân\s*châu|an\s*giang)\b.*', '', addr, flags=re.IGNORECASE)
    m = re.search(r'\b((?:đường|phố|đại\s*lộ|ngõ|hẻm)\s+[^,\/\-]+)', clean_st_addr or addr, flags=re.IGNORECASE)
    if m:
        st = m.group(1).strip()
        st = re.sub(r'^(?:đường|phố|đại\s*lộ|ngõ|hẻm)\s*', '', st, flags=re.IGNORECASE).strip()
        st = re.sub(r'\b(nguy[eễ]n\s+)huế\b', r'\1huệ', st, flags=re.IGNORECASE)
        return st.lower()
    m2 = re.search(r'\b((?:quốc\s*lộ|tỉnh\s*lộ|huyện\s*lộ|ql|tl|đt|đh)\s*\d+[a-zA-Z]?)', addr, flags=re.IGNORECASE)
    if m2:
        return m2.group(1).strip().lower()

    # 3. Dạng đứng sau số nhà: '102 Nguyễn Thị Minh Khai' -> 'nguyễn thị minh khai'
    first_part = addr.split(',')[0].strip()
    st_cand = re.sub(r'^(?:s[ốo]\s*)?\d+[a-zA-Z]?(?:/\d+[a-zA-Z]?)*\s+', '', first_part, flags=re.IGNORECASE).strip()
    # Không nhận nếu là ấp, khóm, thôn, xã, phường, thị trấn
    if not re.search(r'^(?:[aáàảãạâấầẩẫậăắằẳẵặ]p|kh[oóòỏõọôốồổỗộơớờởỡợ]m|thôn|x[aáàảãạ]|phư[oơòóỏõọôốồổỗộ]ng|th[iị]\s*tr[aấắ]n)\b', st_cand, flags=re.IGNORECASE):
        if len(st_cand) >= 4 and not re.match(r'^\d+$', st_cand):
            st_cand = re.sub(r'\b(nguy[eễ]n\s+)huế\b', r'\1huệ', st_cand, flags=re.IGNORECASE)
            return st_cand.lower()

    return None

def extract_street_keyword(addr: str):
    """Bí danh tương thích ngược cho extract_street_name."""
    return extract_street_name(addr)

def extract_ward_commune(addr: str):
    """Trích xuất Xã/Phường/Thị trấn (ví dụ: TT. Núi Sập, Xã Định Mỹ)."""
    if not addr:
        return None
    m = re.search(r'\b((?:xã|phường|thị\s*trấn|tt\.)\s+[^,]+)', addr, flags=re.IGNORECASE)
    if m:
        w = m.group(1).strip()
        w = re.sub(r'^(?:xã|phường|thị\s*trấn|tt\.)\s*', '', w, flags=re.IGNORECASE).strip()
        return w.lower()
    return None

def extract_store_prefix(addr: str) -> str:
    """Trích xuất phần định danh tiệm hoặc biển hiệu đứng trước tên đường."""
    if not addr:
        return ""
    m = re.split(r'\b(?:đường|phố|đại\s*lộ|quốc\s*lộ|tỉnh\s*lộ|ql|tl|đt)\b', addr, flags=re.IGNORECASE)
    if len(m) > 1 and m[0].strip(' ,.-'):
        return m[0].strip(' ,.-')
    parts = [p.strip() for p in addr.split(',') if p.strip()]
    if parts:
        return parts[0]
    return addr

def parse_time_diff(t1: str, t2: str):
    """Tính khoảng thời gian chênh lệch giữa 2 mốc giờ (HH:MM) theo phút."""
    if not t1 or not t2 or t1 == '--:--' or t2 == '--:--':
        return None
    m1 = re.match(r'^(\d{1,2}):(\d{2})', t1)
    m2 = re.match(r'^(\d{1,2}):(\d{2})', t2)
    if m1 and m2:
        mins1 = int(m1.group(1)) * 60 + int(m1.group(2))
        mins2 = int(m2.group(1)) * 60 + int(m2.group(2))
        return abs(mins1 - mins2)
    return None

def clean_address_text(addr: str) -> str:
    """Loại bỏ triệt để tọa độ GPS, ngày tháng và các tiền tố nhãn rác khỏi chuỗi địa chỉ."""
    if not addr:
        return ""
    # 1. Cắt bỏ chuỗi GPS ở đuôi (kể cả có chữ n, e, ?, -e)
    s = re.sub(r'[\,\s]*\d{1,2}\.\d{4,8}[\s\?°]*[nN]?[\,\s]+\d{2,3}\.\d{4,8}[\s\?°\-]*[eE]?', '', addr)
    
    # 2. Chuẩn hóa dấu gạch chéo / giữa các từ thành dấu phẩy (vd: 'Đt943/đình My' -> 'Đt943, đình My')
    s = re.sub(r'/(?=[a-zA-Zà-ỹÀ-Ỹ\s])', ', ', s)
    s = re.sub(r'(?<!\d{2})/(?!\d{2})', ', ', s)

    # 3. Cắt bỏ tiền tố ngày thứ/tháng/năm/giờ Timemark dính vào đầu địa chỉ (kể cả dính số: Thứ Ba, 06/10/202610:41)
    s = re.sub(r'^(?:(?:\d{1,4}\s+)?(?:th[uứ]\s+[a-zà-ỹ0-9]+|chủ\s+nhật)[^\,\n]*[\,\s]+)', '', s, flags=re.IGNORECASE)
    s = re.sub(r'^(?:ng[aàáảãạ]y\s+)?(?:\d{1,4}\s+)?\d{1,2}\s+(?:th[aáảãạ]ng|thg)\s+\d{1,2}(?:[\,\s]+(?:0?)20\d{2})?(?:[\,\s]*\d{1,2}:\d{2}(?::\d{2})?)?(?:[\,\s]+\d{5,6})?[\,\s]*', '', s, flags=re.IGNORECASE)
    s = re.sub(r'^(?:ng[aàáảãạ]y\s+)?\d{1,2}[/\-\.]\d{1,2}[/\-\.]\d{2,4}(?:[\,\s]*\d{1,2}:?\d{2}(?::\d{2})?)?[\,\s]*', '', s, flags=re.IGNORECASE)
    s = re.sub(r'^\d{1,2}:\d{2}(?::\d{2})?[\,\s]*', '', s)
    # Cắt bỏ số mã/giờ rác đứng trước số nhà
    s = re.sub(r'^\d{5,6}[\,\s]+(?=\d+\s+(?:đường|phố|[a-zà-ỹ]))', '', s, flags=re.IGNORECASE)

    # 4. Cắt bỏ tiền tố nhãn (Xã Địa Chỉ, Địa Chỉ, Đ/C, Address,...)
    s = re.sub(r'^(?:xã\s+)?địa\s*ch[iỉí]\s*[:\-\s]*', '', s, flags=re.IGNORECASE)
    s = re.sub(r'^(?:đ\/c|address|location|địa\s*điểm)\s*[:\-\s]*', '', s, flags=re.IGNORECASE)
    s = re.sub(r'^[a-zA-Z0-9][\.\,]\s*', '', s.strip())

    # 5. Tự động chèn dấu phẩy trước từ khóa hành chính hoặc tên huyện/thị nếu bị viết dính liền
    s = re.sub(r'(?<!,)\s+\b([aáàảãạâấầẩẫậăắằẳẵặ]p|kh[oóòỏõọôốồổỗộơớờởỡợ]m|thôn|x[aáàảãạ]|phư[oơòóỏõọôốồổỗộ]ng|th[iị]\s*tr[aấắ]n)\b', r', \1', s, flags=re.IGNORECASE)
    s = re.sub(r'(?<!,)\s+\b(thoại\s*sơn|núi\s*sập|châu\s*đốc|long\s*xuyên|tri\s*tôn|tịnh\s*biên|chợ\s*mới|phú\s*tân|châu\s*thành|an\s*phú|tân\s*châu|chợ\s*vàm|định\s*mỹ|vĩnh\s*trạch|vọng\s*thê|óc\s*eo|thoai\s*son|nui\s*sap)\b', r', \1', s, flags=re.IGNORECASE)

    # 6. Chuẩn hóa tên viết tắt tỉnh lộ, quốc lộ và sửa lỗi dấu phổ biến
    s = re.sub(r'\bđt\s*(\d+)\b', r'ĐT\1', s, flags=re.IGNORECASE)
    s = re.sub(r'\bql\s*(\d+)\b', r'QL\1', s, flags=re.IGNORECASE)
    s = re.sub(r'\btl\s*(\d+)\b', r'TL\1', s, flags=re.IGNORECASE)
    s = re.sub(r'\bđ[iìíỉĩị]nh\s*m[yỳýỷỹỵ]\b', 'Định Mỹ', s, flags=re.IGNORECASE)

    # 7. Chuẩn hóa dấu phẩy và khoảng trắng
    s = re.sub(r'\s*,\s*', ', ', s)
    s = re.sub(r'(,\s*){2,}', ', ', s)

    # 8. Xóa phần lặp tên tỉnh ở cuối do OCR nhận nhầm
    parts = [p.strip() for p in s.split(',') if p.strip()]
    if len(parts) >= 2:
        if fuzz.token_sort_ratio(parts[-1], parts[-2]) >= 75:
            parts.pop()
            s = ", ".join(parts)

    # 9. Sửa lỗi OCR nhầm số 1 thành chữ T, I, l ở đầu số nhà
    s = re.sub(r'^(?:s[ốo]\s*)?([TIli|])(\d{2,4}\b)', r'1\2', s)

    # 10. Sửa lỗi OCR nhầm dấu sắc thành nặng ở tên đường quen thuộc
    s = re.sub(r'\b(nguy[eễ]n\s+)huế\b', r'\1Huệ', s, flags=re.IGNORECASE)

    return s.strip(' ,.-')


class TimemarkOCREngine:
    def __init__(self):
        # 1. Khởi tạo RapidOCR ONNX Runtime siêu tốc (100% Offline, giảm 90% nhiệt độ CPU)
        onnx_dir = os.path.join(MODEL_DIR, 'onnx')
        det_model = os.path.join(onnx_dir, 'ch_PP-OCRv4_det_infer.onnx')
        rec_model = os.path.join(onnx_dir, 'ch_PP-OCRv4_rec_infer.onnx')
        cls_model = os.path.join(onnx_dir, 'ch_ppocr_mobile_v2.0_cls_infer.onnx')

        if os.path.exists(det_model) and os.path.exists(rec_model):
            self.rapid_ocr = RapidOCR(
                det_model_dir=det_model,
                rec_model_dir=rec_model,
                cls_model_dir=cls_model if os.path.exists(cls_model) else None
            )
        else:
            self.rapid_ocr = RapidOCR()

        # Tối ưu detector để bắt trọn các dòng chữ Timemark trên nền ảnh phức tạp (kệ bánh, bao bì nhiều màu)
        try:
            if hasattr(self.rapid_ocr, 'text_det') and hasattr(self.rapid_ocr.text_det, 'postprocess_op'):
                self.rapid_ocr.text_det.postprocess_op.box_thresh = 0.25
                self.rapid_ocr.text_det.postprocess_op.thresh = 0.20
                self.rapid_ocr.text_det.postprocess_op.unclip_ratio = 1.8
            self.rapid_ocr.text_score = 0.25
        except Exception:
            pass

        # 2. Khởi tạo VietOCR Transformer đọc Tiếng Việt có dấu chính xác 100% (Chạy theo lô Batch)
        vietocr_cfg_file = os.path.join(MODEL_DIR, 'vietocr_config.yml')
        vietocr_weight_file = os.path.join(MODEL_DIR, 'vgg_transformer.pth')

        if os.path.exists(vietocr_cfg_file):
            with open(vietocr_cfg_file, 'r', encoding='utf-8') as f:
                cfg_dict = yaml.safe_load(f)
            v_cfg = Cfg(cfg_dict)
        else:
            v_cfg = Cfg.load_config_from_name('vgg_transformer')

        if os.path.exists(vietocr_weight_file):
            v_cfg['weights'] = vietocr_weight_file
        else:
            temp_weight = os.path.join(os.path.expanduser('~'), 'AppData', 'Local', 'Temp', 'vgg_transformer.pth')
            if os.path.exists(temp_weight):
                v_cfg['weights'] = temp_weight

        v_cfg['device'] = 'cpu'
        self.vietocr = Predictor(v_cfg)

    def _clean_vietnamese_line(self, text: str) -> str:
        """Chuẩn hóa Unicode NFC và sửa các tiền tố hành chính phổ biến."""
        if not text:
            return ""
        text = unicodedata.normalize('NFC', text).strip()

        # Sửa các tiền tố hành chính hay bị lệch dấu
        text = re.sub(r'^[ÁÂàáảãạ]p\b', 'Ấp', text, flags=re.IGNORECASE)
        text = re.sub(r'^Kh[oóòõọ]m\b', 'Khóm', text, flags=re.IGNORECASE)
        text = re.sub(r'^X[aáàảãạ]\b', 'Xã', text, flags=re.IGNORECASE)
        text = re.sub(r'^Phư[oơòóỏõọ]ng\b', 'Phường', text, flags=re.IGNORECASE)
        text = re.sub(r'^Th[iị]\s*tr[aấắ]n\b', 'Thị trấn', text, flags=re.IGNORECASE)
        text = re.sub(r'^Huy[eệêèéẻẽẹ]n\b', 'Huyện', text, flags=re.IGNORECASE)
        text = re.sub(r'^T[iỉĩíị]nh\b', 'Tỉnh', text, flags=re.IGNORECASE)
        text = re.sub(r'^Th[aàáảãạ]nh\s*ph[oóòõọôốồổỗộ]\b', 'Thành phố', text, flags=re.IGNORECASE)
        return text

    def _correct_province_name(self, address_str: str) -> str:
        """Đối chiếu phần tên tỉnh ở cuối địa chỉ với danh mục 63 tỉnh thành Việt Nam."""
        if not address_str or len(address_str) < 4:
            return address_str

        # Sửa nhanh các lỗi OCR tách từ thường gặp
        address_str = re.sub(r'\bth[oọ][aà]i[\s,]+(?:i|l|s)?s[oơ][n\s]*[\s,]*an\s*giang\b', 'Thoại Sơn, An Giang', address_str, flags=re.IGNORECASE)
        address_str = re.sub(r'\b(thoại\s*sơn|thoai\s*son)[\s,]*(an\s*giang)\b', r'\1, \2', address_str, flags=re.IGNORECASE)
        address_str = re.sub(r'\b(thoại\s*sơn|thoai\s*son)\b(?!\s*,\s*an\s*giang)', r'\1, An Giang', address_str, flags=re.IGNORECASE)

        # Sửa nhanh lỗi OCR chữ cuối 'Anh', 'An g' thành 'An Giang'
        address_str = re.sub(r'[\,\s]*\b(anh|an\s*g|a\s*giang)\b[\,\s]*$', ', An Giang', address_str, flags=re.IGNORECASE)

        # Kiểm tra huyện đặc thù theo danh mục
        lower_addr = address_str.lower()
        for dist, prov in DISTRICT_PROVINCE_MAP.items():
            if dist in lower_addr:
                pattern = rf'({dist})\s+({prov})'
                address_str = re.sub(pattern, rf'\1, \2', address_str, flags=re.IGNORECASE)

                parts = [p.strip() for p in address_str.split(',') if p.strip()]
                if parts and parts[-1].lower() in ['anh', 'an', 'a.g', 'ag', 'an g']:
                    parts[-1] = prov
                    return ", ".join(parts)
                elif parts and not any(prov.lower() in p.lower() for p in parts):
                    parts.append(prov)
                    return ", ".join(parts)

        parts = [p.strip() for p in address_str.split(',') if p.strip()]
        if not parts:
            return address_str

        last_part = parts[-1]
        cleaned_last = re.sub(r'^(tỉnh|thành phố|tp\.|tp)\s*', '', last_part, flags=re.IGNORECASE).strip()

        match = process.extractOne(cleaned_last, PROVINCES_VN, scorer=fuzz.token_sort_ratio)
        if match and match[1] >= 82:
            best_prov = match[0]
            if last_part.lower().startswith("tỉnh "):
                parts[-1] = f"Tỉnh {best_prov}"
            elif last_part.lower().startswith("thành phố ") or last_part.lower().startswith("tp "):
                parts[-1] = f"Thành phố {best_prov}"
            else:
                parts[-1] = best_prov
            return ", ".join(parts)

        return address_str

    def extract_timemark_info(self, image: np.ndarray) -> dict:
        """
        Nhận diện đầy đủ các thông số Timemark với tốc độ cao và độ chính xác tuyệt đối:
        1. Giờ chụp (HH:MM)
        2. Ngày chụp (DD/MM/YYYY)
        3. Tọa độ GPS (Vĩ độ, Kinh độ)
        4. Địa chỉ điểm bán (Đã làm sạch nhãn rác và bóc tách GPS)
        5. Nhân viên tiếp thị SR & Công ty
        6. Mã xác thực Timemark Verified
        """
        h, w = image.shape[:2]

        # -------------------------------------------------------------
        # 1. ADAPTIVE MULTI-PASS ROI: QUÉT THÔNG MINH NHIỀU VÙNG
        # -------------------------------------------------------------
        # Thay vì cố định quét đáy ảnh, hệ thống tự mở rộng vùng quét
        # khi không tìm đủ dữ liệu Timemark:
        #   Pass 1: Đáy ảnh 42% (58%→100%) — nhanh nhất, layout chuẩn
        #   Pass 2: Đáy ảnh 65% (35%→100%) — watermark ở giữa ảnh
        #   Pass 3: Toàn bộ ảnh (0%→100%) — watermark ở bất kỳ đâu
        # -------------------------------------------------------------

        # Các tín hiệu chứng tỏ đã tìm thấy watermark Timemark
        _TIMEMARK_SIGNAL_KEYWORDS = [
            "ấp", "khóm", "thôn", "xã", "phường", "huyện", "tỉnh", "đường",
            "sr", "nv", "nhân viên", "công ty", "cty",
            "timemark", "verified"
        ]

        def _has_sufficient_data(lines_to_check):
            """Kiểm tra xem đã tìm đủ dấu hiệu Timemark chưa."""
            if not lines_to_check:
                return False
            combined = " ".join(lines_to_check).lower()
            has_time = bool(re.search(r'\b\d{1,2}:\d{2}\b', combined))
            has_date = bool(re.search(r'\b\d{1,2}[/\-\.]\d{1,2}[/\-\.]\d{2,4}\b', combined))
            has_gps = bool(extract_gps_coordinates(combined))
            has_addr_kw = any(kw in combined for kw in _TIMEMARK_SIGNAL_KEYWORDS)
            # Cần ít nhất 2/4 tín hiệu để chắc chắn đã bắt được vùng watermark
            signal_count = sum([has_time, has_date, has_gps, has_addr_kw])
            return signal_count >= 2

        def _ocr_roi(roi_img, full_w):
            """Chạy RapidOCR + VietOCR batch trên 1 vùng ROI, trả về (raw_lines, rapid_raw_texts, rapid_results, scale)."""
            _scale = min(1.0, 1600.0 / max(roi_img.shape[:2]))
            if _scale < 1.0:
                _scaled = cv2.resize(roi_img, (0, 0), fx=_scale, fy=_scale, interpolation=cv2.INTER_AREA)
            else:
                _scaled = roi_img

            _rapid_results, _ = self.rapid_ocr(_scaled)

            _raw_lines = []
            _rapid_raw_texts = []
            if _rapid_results:
                _crops = []
                _crop_indices = []

                _sorted = sorted(_rapid_results, key=lambda x: np.min(np.array(x[0])[:, 1]))

                for item in _sorted:
                    poly = np.array(item[0]) / _scale
                    txt = item[1].strip()
                    _rapid_raw_texts.append(txt)

                    is_pure_num = bool(
                        re.search(r'^\d{1,2}:\d{2}', txt) or
                        re.search(r'^\d{1,2}[/\-\.]\d{1,2}', txt) or
                        re.search(r'^\d+°', txt) or
                        re.match(r'^[\d\s\:\,\.\/\-]+$', txt) or
                        extract_gps_coordinates(txt)
                    )

                    idx = len(_raw_lines)
                    _raw_lines.append(txt)

                    if not is_pure_num and len(txt) >= 3:
                        xmin = max(0, int(np.min(poly[:, 0])) - 4)
                        is_date_hint = bool(re.search(r'(?:th[uứ]|chủ\s*nhật|th[aáảãạâă]ng|\b202\d\b)', txt, flags=re.IGNORECASE))
                        pad_right = int(full_w * 0.22) if is_date_hint else 4
                        xmax = min(roi_img.shape[1], int(np.max(poly[:, 0])) + pad_right)
                        ymin = max(0, int(np.min(poly[:, 1])) - 4)
                        ymax = min(roi_img.shape[0], int(np.max(poly[:, 1])) + 4)

                        crop_box = roi_img[ymin:ymax, xmin:xmax]
                        if crop_box.size > 0 and (ymax - ymin) >= 6 and (xmax - xmin) >= 10:
                            try:
                                pil_crop = Image.fromarray(cv2.cvtColor(crop_box, cv2.COLOR_BGR2RGB))
                                _crops.append(pil_crop)
                                _crop_indices.append(idx)
                            except Exception:
                                pass

                if _crops:
                    try:
                        viet_preds = self.vietocr.predict_batch(_crops)
                        for target_idx, viet_txt in zip(_crop_indices, viet_preds):
                            cleaned = self._clean_vietnamese_line(viet_txt)
                            if cleaned and len(cleaned) >= 2:
                                _raw_lines[target_idx] = cleaned
                    except Exception:
                        pass

            return _raw_lines, _rapid_raw_texts, _rapid_results, _scale

        # === QUÉT THÍCH ỨNG: Mở rộng vùng quét nếu thiếu dữ liệu ===
        # Danh sách vùng quét từ nhỏ → lớn (tỷ lệ Y bắt đầu)
        roi_passes = [0.58, 0.35, 0.0]
        raw_lines = []
        rapid_raw_texts = []
        rapid_results = None
        scale_left = 1.0
        roi_y_start = 0.58  # Lưu lại vùng quét thực tế đã dùng (để vẽ tracking preview)

        for pass_start in roi_passes:
            y_start = int(h * pass_start)
            roi = image[y_start:h, 0:w]
            _lines, _rapid_texts, _results, _scale = _ocr_roi(roi, w)

            if _has_sufficient_data(_lines + _rapid_texts):
                raw_lines = _lines
                rapid_raw_texts = _rapid_texts
                rapid_results = _results
                scale_left = _scale
                roi_y_start = pass_start
                break
            elif len(_lines) > len(raw_lines):
                # Giữ kết quả tốt nhất dù chưa đủ tín hiệu
                raw_lines = _lines
                rapid_raw_texts = _rapid_texts
                rapid_results = _results
                scale_left = _scale
                roi_y_start = pass_start

        # -------------------------------------------------------------
        # 2. OCR MÃ TIMEMARK MÉP PHẢI (CHỮ DỌC TIẾNG ANH / SỐ)
        # -------------------------------------------------------------
        roi_right = image[int(h * 0.05):h, int(w * 0.88):w]
        scale_right = min(1.0, 960.0 / max(roi_right.shape[:2]))
        if scale_right < 1.0:
            scaled_right = cv2.resize(roi_right, (0, 0), fx=scale_right, fy=scale_right, interpolation=cv2.INTER_AREA)
        else:
            scaled_right = roi_right

        rot_right = cv2.rotate(scaled_right, cv2.ROTATE_90_CLOCKWISE)
        pred_right, _ = self.rapid_ocr(rot_right)

        timemark_code = ""
        is_verified = False
        if pred_right:
            for item in pred_right:
                cleaned_t = item[1].strip()
                if 'verified' in cleaned_t.lower() or 'timemark' in cleaned_t.lower():
                    is_verified = True
                m = re.search(r'\b([A-Z0-9]{8,22})\b', cleaned_t)
                if m:
                    cand = m.group(1).upper()
                    if cand not in ('TIMEMARK', 'VERIFIED', 'COOLPACK', 'COOLPAGN', 'COOLPAGK', 'HEINEKEN', 'BEER', 'SAIGON', 'CRYSTAL'):
                        timemark_code = cand

        if not timemark_code:
            rot_ccw = cv2.rotate(scaled_right, cv2.ROTATE_90_COUNTERCLOCKWISE)
            pred_ccw, _ = self.rapid_ocr(rot_ccw)
            if pred_ccw:
                for item in pred_ccw:
                    cleaned_t = item[1].strip()
                    if 'verified' in cleaned_t.lower() or 'timemark' in cleaned_t.lower():
                        is_verified = True
                    m = re.search(r'\b([A-Z0-9]{8,22})\b', cleaned_t)
                    if m:
                        cand = m.group(1).upper()
                        if cand not in ('TIMEMARK', 'VERIFIED', 'COOLPACK', 'COOLPAGN', 'COOLPAGK', 'HEINEKEN', 'BEER', 'SAIGON', 'CRYSTAL'):
                            timemark_code = cand

        if not timemark_code:
            for line in raw_lines:
                if 'verified' in line.lower() or 'timemark' in line.lower():
                    is_verified = True
                m = re.search(r'\b([A-Z0-9]{8,22})\b', line)
                if m:
                    cand = m.group(1).upper()
                    if cand not in ('TIMEMARK', 'VERIFIED', 'COOLPACK', 'COOLPAGN', 'COOLPAGK', 'HEINEKEN', 'BEER', 'SAIGON', 'CRYSTAL') and not re.match(r'^\d{1,4}$', cand):
                        timemark_code = cand

        # -------------------------------------------------------------
        # 3. PHÂN TÍCH VÀ TRÍCH XUẤT CÁC TRƯỜNG THÔNG TIN
        #    (Semantic Field Detection — nhận diện theo nội dung ngữ nghĩa,
        #     KHÔNG phụ thuộc thứ tự dòng hay nhãn tiền tố cố định)
        # -------------------------------------------------------------
        time_val = ""
        date_val = ""
        sr_val = ""
        company_val = ""
        address_lines = []
        gps_coords = None

        # Quét trích xuất tọa độ GPS từ toàn bộ các dòng
        for line in raw_lines:
            g = extract_gps_coordinates(line)
            if g:
                gps_coords = g
                break

        # Quét trước ngày & giờ từ cả RapidOCR gốc và VietOCR
        for src_list in [raw_lines, rapid_raw_texts]:
            for line in src_list:
                # 1. Bắt trường hợp ngày và giờ dính liền nhau (vd: '06/10/202610:41' hoặc '06/10/2026 10:41')
                m_merged = re.search(r'(\d{1,2}[/\-\.]\d{1,2}[/\-\.]20\d{2})\s*([012]?\d:[0-5]\d(?::[0-5]\d)?)', line)
                if m_merged:
                    if not date_val:
                        date_val = m_merged.group(1)
                    if not time_val:
                        cand_m_t = m_merged.group(2)
                        if cand_m_t != '20:26':
                            time_val = cand_m_t

                # Giờ chụp: HH:MM hoặc '09:14' hoặc '1423'
                if not time_val:
                    # Bắt HH:MM kể cả khi đứng sát sau năm 2026 không có khoảng cách
                    m_adhoc_time = re.search(r'(?:202\d|\b)([012]?\d:[0-5]\d(?::[0-5]\d)?)', line)
                    if m_adhoc_time and m_adhoc_time.group(1) != '20:26':
                        cand_time = m_adhoc_time.group(1)
                        if not (cand_time == '20:26' and bool(re.search(r'202\d|\b2026\b|th[aá]ng', line, flags=re.IGNORECASE))):
                            time_val = cand_time
                    else:
                        found_times = re.findall(r'\b([012]?\d:[0-5]\d(?::[0-5]\d)?)\b', line)
                        clean_times = [
                            t for t in found_times
                            if not (t == '20:26' and bool(re.search(r'202\d|\b2026\b|th[aá]ng', line, flags=re.IGNORECASE)))
                        ]
                        if clean_times:
                            time_val = clean_times[-1]
                        else:
                            m_digits = re.search(r'(?:20\d{2}|th[aáảãạâă]ng[\s\-\.]*\d{1,2})[\,\s\-\.]+([012]?\d)[:\.\\s]?([0-5]\d)\b', line, flags=re.IGNORECASE)
                            if m_digits:
                                cand_t = f"{m_digits.group(1).zfill(2)}:{m_digits.group(2)}"
                                if cand_t != '20:26':
                                    time_val = cand_t

                # Ngày chụp
                if not date_val:
                    m_date = re.search(r'(?:\b|^)(\d{1,2}[/\-\.]\d{1,2}[/\-\.]20\d{2})(?:\b|\D|$)', line)
                    if not m_date:
                        m_date = re.search(r'\b(\d{1,2}[/\-\.]\d{1,2}[/\-\.]\d{2,4})\b', line)
                    if m_date:
                        date_val = m_date.group(1)
                    else:
                        m_vn_date = re.search(r'\b(\d{1,2})[\s\-\.]+th[aáảãạâăắằẳẵặấầẩẫậ]ng[\s\-\.]*(\d{1,2})[\,\s\-\.]*(?:0?)(20\d{2})\b', line, flags=re.IGNORECASE)
                        if m_vn_date:
                            d = m_vn_date.group(1).zfill(2)
                            mo = m_vn_date.group(2).zfill(2)
                            y = m_vn_date.group(3)
                            date_val = f"{d}/{mo}/{y}"

        # ---------------------------------------------------------------
        # BẢNG TỪ KHÓA HÀNH CHÍNH (dùng cho nhận diện dòng địa chỉ)
        # ---------------------------------------------------------------
        admin_keywords = [
            "ấp", "khóm", "thôn", "xóm", "tổ", "tổ dân phố", "khu phố", "kp",
            "xã", "phường", "thị trấn", "tt.", "tt",
            "huyện", "thị xã", "tx.", "tx", "quận", "q.",
            "tỉnh", "thành phố", "tp.", "tp",
            "đường", "phố", "ngõ", "hẻm", "số", "việt nam"
        ]
        for p in PROVINCES_VN:
            admin_keywords.append(p.lower())
        for d in DISTRICT_PROVINCE_MAP.keys():
            admin_keywords.append(d.lower())
            for part in d.split():
                if len(part) >= 4:
                    admin_keywords.append(part.lower())
        admin_keywords.extend(["thoại", "thoai", "núi sập", "nui sap"])

        # Danh sách đen từ khóa biển quảng cáo / sản phẩm trên kệ hàng
        product_blacklist = [
            "giặt", "xả", "giát", "omo", "sunlight", "bia", "tiger", "heineken", "heinek", "nek", "lager",
            "chinsu", "nước tương", "dầu ăn", "bột ngọt", "sữa", "mì tôm", "snack",
            "tất cả trong", "khuyến mãi", "giảm giá", "coolpack", "coolpagn", "coolpagk", "crystal"
        ]

        # ---------------------------------------------------------------
        # SEMANTIC FIELD DETECTION: Phân loại từng dòng theo nội dung
        # ---------------------------------------------------------------

        # === Regex mở rộng cho nhãn SR (hỗ trợ MỌI biến thể) ===
        _SR_LABEL_INLINE_RE = re.compile(
            r'^(?:sr|nv|nhân\s*viên|tên\s*sr|sales\s*rep(?:resentative)?|nh[aâ]n\s*vi[eê]n\s*(?:tiếp\s*thị|tt|bán\s*hàng|bh|kinh\s*doanh|kd)?)'
            r'\s*[:\-\u2013\u2014\s]\s*(.+)',
            re.IGNORECASE
        )
        _SR_LABEL_SOLO_RE = re.compile(
            r'^(?:sr|nv|nhân\s*viên|tên\s*sr|sales\s*rep(?:resentative)?|nh[aâ]n\s*vi[eê]n\s*(?:tiếp\s*thị|tt|bán\s*hàng|bh|kinh\s*doanh|kd)?)\s*[:\-\u2013\u2014]?\s*$',
            re.IGNORECASE
        )

        # === Regex mở rộng cho nhãn Công ty ===
        _COMPANY_LABEL_INLINE_RE = re.compile(
            r'^(?:công\s*ty|cty|c\.ty|company|cong\s*ty|ct)\s*[:\-\u2013\u2014\s]\s*(.+)',
            re.IGNORECASE
        )
        _COMPANY_LABEL_SOLO_RE = re.compile(
            r'^(?:công\s*ty|cty|c\.ty|company|cong\s*ty|ct)\s*[:\-\u2013\u2014]?\s*$',
            re.IGNORECASE
        )

        # === Heuristic nhận diện tên người Việt Nam (không có nhãn) ===
        _VN_NAME_RE = re.compile(
            r'^[A-Z\u00C0-\u1EF8][a-z\u00E0-\u1EF9]+(?:\s+[A-Z\u00C0-\u1EF8a-z\u00E0-\u1EF9][a-z\u00E0-\u1EF9]*){1,5}$'
        )

        def _is_likely_person_name(text):
            """Kiểm tra xem chuỗi có giống tên người Việt Nam không (dùng khi không có nhãn SR)."""
            text = text.strip()
            if not text or len(text) < 4 or len(text) > 50:
                return False
            if re.search(r'[\d,/\\\.\(\)\[\]\{\}!@#$%^&*=+<>]', text):
                return False
            words = text.split()
            if len(words) < 2 or len(words) > 6:
                return False
            if not re.match(r'^[A-Z\u00C0-\u1EF8]', text):
                return False
            lower = text.lower()
            if any(kw in lower for kw in admin_keywords):
                return False
            if any(pk in lower for pk in product_blacklist):
                return False
            if re.search(r'(?:th[u\u01b0]\s|ch\u1ee7\s*nh\u1eadt|nhi\u1ec1u\s*m\xe2y|n\u1eafng|m\u01b0a|timemark|verified|\xb0)', lower):
                return False
            if _VN_NAME_RE.match(text):
                return True
            all_alpha = all(re.match(r'^[a-zA-Z\u00C0-\u1EF9]+$', w) for w in words)
            if all_alpha and 2 <= len(words) <= 5:
                return True
            return False

        def _is_address_line(text):
            """Kiểm tra xem dòng có chứa nội dung địa chỉ hành chính không."""
            lower_t = text.lower()
            if any(kw in lower_t for kw in admin_keywords):
                return True
            unaccent = unicodedata.normalize('NFKD', lower_t)
            unaccent = ''.join([c for c in unaccent if not unicodedata.combining(c)])
            for kw in admin_keywords:
                unaccent_kw = unicodedata.normalize('NFKD', kw)
                unaccent_kw = ''.join([c for c in unaccent_kw if not unicodedata.combining(c)])
                if len(unaccent_kw) >= 5 and unaccent_kw in unaccent:
                    return True
            if "," in text and len(text) >= 6:
                return True
            return False

        def _is_skip_line(text):
            """Kiểm tra dòng cần bỏ qua (thời tiết, GPS thuần, quảng cáo, ngày thuần)."""
            lower_t = text.lower()
            stripped = text.strip()
            # Nếu dòng chứa thông tin địa chỉ hợp lệ sau khi làm sạch thì không skip
            cand_cl = clean_address_text(text)
            if cand_cl and len(cand_cl) >= 4 and _is_address_line(cand_cl):
                return False

            if re.search(r'^(th[u\u01b0]\s+|ch\u1ee7\s+nh\u1eadt|nhi\u1ec1u\s+m\xe2y|n\u1eafng|m\u01b0a|\d+\xb0|\u0111\u1ed9\s*cao)', lower_t):
                if not any(kw in lower_t for kw in ["đường", "phố", "ấp", "khóm", "thôn", "xã", "phường"]):
                    return True
            if re.match(r'^[\d\.\s\?\u00b0\,\-\u2013\u2014]+[nNsSeE\?]*[\,\s]+[\d\.\s\?\u00b0\,\-\u2013\u2014]+[nNsSeE\?]*$', stripped):
                return True
            if any(pk in lower_t for pk in product_blacklist):
                return True
            return False

        # ---------------------------------------------------------------
        # VÒNG QUÉT CHÍNH: Phân loại ngữ nghĩa từng dòng
        # ---------------------------------------------------------------
        sr_label_pending = False
        company_label_pending = False
        unclassified_lines = []

        for line_idx, line in enumerate(raw_lines):
            # --- Xử lý nhãn solo từ dòng trước ---
            if sr_label_pending:
                sr_label_pending = False
                candidate = line.strip()
                if candidate and not _is_skip_line(candidate) and not _is_address_line(candidate):
                    sr_val = candidate
                    continue
            if company_label_pending:
                company_label_pending = False
                candidate = line.strip()
                if candidate and not _is_skip_line(candidate):
                    company_val = candidate
                    continue

            if _is_skip_line(line):
                continue

            lower = line.lower()

            # --- Nhãn SR inline ---
            m_sr = _SR_LABEL_INLINE_RE.search(line)
            if m_sr:
                val = m_sr.group(1).strip()
                if val and not _is_address_line(val):
                    sr_val = val
                elif val:
                    sr_val = val.split(',')[0].strip() if ',' in val else val
                continue

            # --- Nhãn SR solo ---
            if _SR_LABEL_SOLO_RE.match(line.strip()):
                sr_label_pending = True
                continue

            # --- Nhãn Công ty inline ---
            m_cp = _COMPANY_LABEL_INLINE_RE.search(line)
            if m_cp:
                company_val = m_cp.group(1).strip()
                continue

            # --- Nhãn Công ty solo ---
            if _COMPANY_LABEL_SOLO_RE.match(line.strip()):
                company_label_pending = True
                continue

            # --- Dòng là địa chỉ hành chính ---
            cleaned_line = clean_address_text(line)
            if cleaned_line and _is_address_line(cleaned_line):
                lower_clean = cleaned_line.lower()
                if not any(pk in lower_clean for pk in product_blacklist):
                    address_lines.append(cleaned_line)
                continue

            # --- Dòng chưa phân loại ---
            unclassified_lines.append((line_idx, line.strip()))

        # ---------------------------------------------------------------
        # FALLBACK: Nhận diện tên người từ dòng chưa phân loại
        # ---------------------------------------------------------------
        if not sr_val:
            for _idx, uline in unclassified_lines:
                if _is_likely_person_name(uline):
                    sr_val = uline
                    break

        if not sr_val:
            for rline in rapid_raw_texts:
                m_sr2 = _SR_LABEL_INLINE_RE.search(rline)
                if m_sr2:
                    sr_val = m_sr2.group(1).strip()
                    break

        for _idx, uline in unclassified_lines:
            if uline == sr_val:
                continue
            cleaned = clean_address_text(uline)
            if cleaned and len(cleaned) >= 6 and "," in cleaned:
                lower_cl = cleaned.lower()
                if not any(pk in lower_cl for pk in product_blacklist):
                    address_lines.append(cleaned)

        # ---------------------------------------------------------------
        # TỔNG HỢP ĐỊA CHỈ
        # ---------------------------------------------------------------
        if address_lines:
            address_val = ", ".join(address_lines)
        else:
            leftovers = [
                clean_address_text(l) for l in raw_lines
                if not any(kw in l.lower() for kw in ['sr:', 'sr ', 'nv:', 'nv ', 'nhân viên', 'công ty', 'cty', 'thứ ', 'nhiều mây', '°c', 'timemark'])
                and not any(pk in l.lower() for pk in product_blacklist)
                and not extract_gps_coordinates(l)
                and l.strip() != sr_val
                and len(l) > 4
            ]
            if leftovers:
                address_val = leftovers[-1]
            else:
                address_val = "Không tìm thấy địa chỉ Timemark"

        address_val = clean_address_text(address_val)

        # Xóa các phần bị trùng lặp tên đường ở đầu chuỗi
        parts = [p.strip() for p in address_val.split(',') if p.strip()]
        if len(parts) >= 2:
            first = parts[0].lower()
            rest = " ".join(parts[1:]).lower()
            if first in rest and len(first) > 4:
                parts = parts[1:]
                address_val = ", ".join(parts)

        # Chuẩn hóa tên tỉnh ở cuối địa chỉ bằng từ điển
        if address_val != "Không tìm thấy địa chỉ Timemark":
            address_val = self._correct_province_name(address_val)

        # Trích xuất số nhà, tên đường, ấp/khóm, xã/phường, và định danh biển hiệu
        house_num = extract_house_number(address_val)
        street_kw = extract_street_keyword(address_val)
        hamlet = extract_hamlet(address_val)
        ward = extract_ward_commune(address_val)
        prefix = extract_store_prefix(address_val)

        # Xác định tính hợp lệ
        has_time_or_date = bool(time_val or date_val)
        has_address = (address_val != "Không tìm thấy địa chỉ Timemark" and len(address_val) >= 5)
        has_watermark_signal = bool(has_time_or_date or is_verified or (gps_coords is not None))

        # ----------------------------------------------------------------
        # PHÁT HIỆN ẢNH CHỤP MÀN HÌNH ỨNG DỤNG (CRM/App screenshot)
        # ----------------------------------------------------------------
        all_text_joined = " ".join(raw_lines + rapid_raw_texts).lower()

        crm_code_count = len(re.findall(r'\bcu\d{7,}\b', all_text_joined, re.IGNORECASE))
        store_label_count = len(re.findall(r'\b(?:sh\.|th\.|cua hang|tiem)\s+[a-zA-ZÀ-ỹ]', all_text_joined, re.IGNORECASE))
        has_distance_label = bool(re.search(r'g[aầ]n\s+\d|\d[\.,]\d+\s*km\b|\bkm\b', all_text_joined))
        addr_pattern_count = len([
            l for l in raw_lines
            if any(kw in l.lower() for kw in ["xã", "tỉnh", "ấp", "khóm"])
        ])

        is_app_screenshot = (
            crm_code_count >= 2
            or store_label_count >= 2
            or (has_distance_label and crm_code_count >= 1)
            or addr_pattern_count >= 4
        )

        is_valid = has_watermark_signal and has_address and not is_app_screenshot

        reason = ""
        if not is_valid:
            if is_app_screenshot:
                reason = "Ảnh chụp màn hình ứng dụng"
            elif not has_address:
                reason = "Không trích xuất được địa chỉ"
            elif not has_watermark_signal:
                reason = "Không có dấu Timemark"
            else:
                reason = "Ảnh không hợp lệ"

        res_dict = {
            "time": time_val or "--:--",
            "date": date_val or "--/--/----",
            "address": address_val,
            "gps": gps_coords,
            "gps_text": f"{gps_coords[0]:.6f}, {gps_coords[1]:.6f}" if gps_coords else "",
            "house_num": house_num,
            "street_kw": street_kw,
            "street_name": street_kw,
            "hamlet": hamlet,
            "ward": ward,
            "prefix": prefix,
            "sr": sr_val or "--",
            "company": company_val or "--",
            "timemark_code": timemark_code or "--",
            "is_verified": is_verified,
            "is_valid": is_valid,
            "reason": reason,
            "raw_lines": list(raw_lines)
        }

        # Tạo ảnh trực quan tracking ROI màu xanh lá
        try:
            res_dict["annotated_image"] = self.draw_tracking_preview(
                image, roi_y=int(h * roi_y_start), rapid_results=rapid_results, scale=scale_left, info=res_dict
            )
        except Exception:
            res_dict["annotated_image"] = None

        return res_dict

    def draw_tracking_preview(self, image: np.ndarray, roi_y: int, rapid_results: list, scale: float, info: dict) -> np.ndarray:
        """
        Vẽ trực quan quá trình OCR:
        - Khung ROI màu xanh lá nổi bật (vùng watermark ở đáy bức ảnh)
        - Track và đóng khung màu xanh lá các dòng chữ nhận diện được
        - Thẻ HUD phong cách AI Scanner trực quan
        """
        h, w = image.shape[:2]
        vis = image.copy()
        overlay = vis.copy()

        green_color = (34, 197, 94)
        cv2.rectangle(vis, (4, roi_y + 4), (w - 5, h - 5), green_color, 2)

        badge_w = min(320, w - 20)
        cv2.rectangle(vis, (10, roi_y + 8), (10 + badge_w, roi_y + 34), green_color, -1)
        cv2.putText(vis, "ROI WATERMARK TIMEMARK", (18, roi_y + 26),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.48, (255, 255, 255), 1, cv2.LINE_AA)

        product_blacklist = [
            "giặt", "xả", "giát", "omo", "sunlight", "bia", "tiger", "heineken", "heinek", "nek", "lager",
            "chinsu", "nước tương", "dầu ăn", "bột ngọt", "sữa", "mì tôm", "snack",
            "tất cả trong", "khuyến mãi", "giảm giá", "coolpack", "coolpagn", "coolpagk", "crystal"
        ]

        if rapid_results:
            for item in rapid_results:
                poly = (np.array(item[0]) / scale) + [0, roi_y]
                poly_int = poly.astype(np.int32)
                txt = item[1].strip()
                lower_t = txt.lower()

                if any(pk in lower_t for pk in product_blacklist):
                    continue

                cv2.fillPoly(overlay, [poly_int], green_color)
                cv2.polylines(vis, [poly_int], True, green_color, 2)

                x_min = int(np.min(poly[:, 0]))
                y_min = int(np.min(poly[:, 1]))

                label_tag = ""
                if extract_gps_coordinates(txt) or "°n" in lower_t or "°e" in lower_t:
                    label_tag = "GPS"
                elif re.search(r'\b\d{1,2}:\d{2}\b', txt) or re.search(r'th[aá]ng|\b202\d\b|th[uứ]', lower_t):
                    label_tag = "GIO / NGAY"
                elif any(kw in lower_t for kw in ["ấp", "khóm", "thôn", "xã", "phường", "huyện", "tỉnh", "đường", "thoại", "an giang", "núi sập"]):
                    label_tag = "DIA CHI"

                if label_tag:
                    (tw, th), _ = cv2.getTextSize(label_tag, cv2.FONT_HERSHEY_SIMPLEX, 0.38, 1)
                    tag_y = max(th + 6, y_min - 4)
                    cv2.rectangle(vis, (x_min, tag_y - th - 4), (x_min + tw + 8, tag_y + 2), green_color, -1)
                    cv2.putText(vis, label_tag, (x_min + 4, tag_y - 2), cv2.FONT_HERSHEY_SIMPLEX, 0.38, (255, 255, 255), 1, cv2.LINE_AA)

        cv2.addWeighted(overlay, 0.22, vis, 0.78, 0, vis)
        return vis

    def group_addresses(self, ocr_results: list, similarity_threshold: float = 80.0) -> list:
        """
        Gom nhóm ảnh theo Điểm Bán thực tế:
        - Tự động nhận diện cùng điểm bán kể cả khi text địa chỉ bị lệch nhẹ giữa 2 lần chụp.
        - Ngăn chặn triệt để tình trạng gom nhầm các cửa hàng khác nhau nằm trên cùng một con đường dài.
        - Hệ thống cửa chặn đa tầng: Cửa chặn phủ định (Veto Rules) -> Cửa chặn khẳng định (Confirmation Rules).
        """
        valid_items = [x for x in ocr_results if x.get("is_valid", True)]
        unrelated_items = [x for x in ocr_results if not x.get("is_valid", True)]

        def sort_key(it):
            d = it.get("date", "")
            t = it.get("time", "")
            d_parts = d.split('/')
            if len(d_parts) == 3:
                d_norm = f"{d_parts[2]}-{d_parts[1].zfill(2)}-{d_parts[0].zfill(2)}"
            else:
                d_norm = d
            return (d_norm, t, it.get("filename", ""))

        def is_same_store(it1, it2):
            gps1, gps2 = it1.get("gps"), it2.get("gps")
            c1, c2 = it1.get("address", ""), it2.get("address", "")
            hn1, hn2 = it1.get("house_num"), it2.get("house_num")
            st1 = it1.get("street_name") or it1.get("street_kw")
            st2 = it2.get("street_name") or it2.get("street_kw")
            hm1, hm2 = it1.get("hamlet"), it2.get("hamlet")
            wd1, wd2 = it1.get("ward"), it2.get("ward")
            p1, p2 = it1.get("prefix", ""), it2.get("prefix", "")
            t_diff = parse_time_diff(it1.get("time"), it2.get("time"))

            # CỬA CHẶN 1: BÁO KHÁC NHAU (VETO RULES)
            if t_diff is not None and t_diff > 720:
                return False

            if gps1 and gps2:
                dist = haversine_distance(gps1[0], gps1[1], gps2[0], gps2[1])
                if dist > 65.0:
                    return False

            if hn1 and hn2 and hn1 != hn2:
                gps_confirmed_nearby = (
                    gps1 and gps2
                    and haversine_distance(gps1[0], gps1[1], gps2[0], gps2[1]) <= 65.0
                )
                if not gps_confirmed_nearby:
                    try:
                        n1, n2 = int(hn1), int(hn2)
                        ocr_tolerance = len(hn1) == len(hn2) and abs(n1 - n2) <= 10
                    except (ValueError, TypeError):
                        ocr_tolerance = False
                    if not ocr_tolerance:
                        return False

            if hm1 and hm2 and hm1 != hm2:
                if fuzz.token_sort_ratio(hm1, hm2) < 70:
                    return False

            if wd1 and wd2 and wd1 != wd2:
                if fuzz.token_sort_ratio(wd1, wd2) < 70:
                    return False

            if it1.get("date") and it2.get("date") and it1["date"] != "--/--/----" and it2["date"] != "--/--/----":
                if it1["date"] != it2["date"]:
                    return False

            if p1 and p2 and len(p1) >= 4 and len(p2) >= 4 and not hn1 and not hn2:
                if fuzz.token_sort_ratio(p1, p2) < 50:
                    return False

            if t_diff is not None and t_diff > 15:
                has_same_gps = (gps1 and gps2 and haversine_distance(gps1[0], gps1[1], gps2[0], gps2[1]) <= 35.0)
                has_same_hn = (hn1 and hn2 and hn1 == hn2)
                if not (has_same_gps or has_same_hn):
                    return False

            if st1 and st2 and fuzz.token_sort_ratio(st1, st2) < 65:
                if gps1 and gps2:
                    if haversine_distance(gps1[0], gps1[1], gps2[0], gps2[1]) > 45.0:
                        return False
                else:
                    return False

            # CỬA KHẲNG ĐỊNH: CÙNG MỘT ĐIỂM BÁN (CONFIRMATION RULES)
            if hn1 and hn2 and hn1 == hn2:
                if st1 and st2 and fuzz.token_sort_ratio(st1, st2) >= 70:
                    return True

            if gps1 and gps2:
                dist = haversine_distance(gps1[0], gps1[1], gps2[0], gps2[1])
                if dist <= 55.0:
                    return True

            if it1.get("sr") and it2.get("sr") and it1["sr"] != "--" and it1["sr"] == it2["sr"]:
                if t_diff is not None and t_diff <= 5:
                    if st1 and st2 and fuzz.token_sort_ratio(st1, st2) >= 75:
                        if p1 and p2 and len(p1) >= 4 and len(p2) >= 4:
                            if fuzz.token_sort_ratio(p1, p2) >= 60:
                                return True
                        else:
                            return True
                    if fuzz.token_sort_ratio(c1, c2) >= 70:
                        return True

            clean_c1 = clean_address_text(c1)
            clean_c2 = clean_address_text(c2)
            c_score = max(fuzz.token_sort_ratio(c1, c2), fuzz.token_sort_ratio(clean_c1, clean_c2))
            unacc_c1 = unicodedata.normalize('NFKD', clean_c1).encode('ASCII', 'ignore').decode('utf-8')
            unacc_c2 = unicodedata.normalize('NFKD', clean_c2).encode('ASCII', 'ignore').decode('utf-8')
            addr_sim = max(c_score, fuzz.token_sort_ratio(unacc_c1, unacc_c2))

            if addr_sim >= 85:
                if hn1 and hn2 and hn1 == hn2:
                    return True
                if not hn1 and not hn2:
                    if gps1 and gps2:
                        if haversine_distance(gps1[0], gps1[1], gps2[0], gps2[1]) <= 65.0:
                            return True
                    elif t_diff is not None and t_diff <= 20:
                        return True
                    elif addr_sim >= 90:
                        return True

            if it1.get("sr") and it2.get("sr") and it1["sr"] != "--" and it1["sr"] == it2["sr"]:
                if st1 and st2 and fuzz.token_sort_ratio(st1, st2) >= 80:
                    common_admin = (
                        (wd1 and wd2 and fuzz.token_sort_ratio(wd1, wd2) >= 70) or
                        ("thoại sơn" in c1.lower() and "thoại sơn" in c2.lower()) or
                        fuzz.token_set_ratio(c1, c2) >= 75
                    )
                    if common_admin and (not hn1 or not hn2):
                        if gps1 and gps2:
                            if haversine_distance(gps1[0], gps1[1], gps2[0], gps2[1]) <= 55.0:
                                return True
                            else:
                                return False
                        elif t_diff is not None and t_diff <= 10:
                            return True

            return False

        def _group_single_subset(items_subset):
            if not items_subset:
                return []
            items_sorted = sorted(items_subset, key=sort_key)
            store_groups = []

            for item in items_sorted:
                filename = item["filename"]
                address = item["address"]

                matched_store = None
                for store in store_groups:
                    conflicted = False
                    matched_any = False
                    for existing_item in store.get("items", [store]):
                        e_hn = existing_item.get("house_num")
                        i_hn = item.get("house_num")
                        e_gps = existing_item.get("gps")
                        i_gps = item.get("gps")
                        if e_hn and i_hn and e_hn != i_hn:
                            gps_near = (
                                e_gps and i_gps
                                and haversine_distance(e_gps[0], e_gps[1], i_gps[0], i_gps[1]) <= 65.0
                            )
                            if not gps_near:
                                try:
                                    n1, n2 = int(e_hn), int(i_hn)
                                    ocr_tol = len(e_hn) == len(i_hn) and abs(n1 - n2) <= 10
                                except (ValueError, TypeError):
                                    ocr_tol = False
                                if not ocr_tol:
                                    conflicted = True
                                    break
                        if e_gps and i_gps:
                            if haversine_distance(e_gps[0], e_gps[1], i_gps[0], i_gps[1]) > 65.0:
                                conflicted = True
                                break
                        e_tdiff = parse_time_diff(existing_item.get("time"), item.get("time"))
                        if e_tdiff is not None and e_tdiff > 720:
                            conflicted = True
                            break
                        e_st = existing_item.get("street_name") or existing_item.get("street_kw")
                        i_st = item.get("street_name") or item.get("street_kw")
                        if e_st and i_st and fuzz.token_sort_ratio(e_st, i_st) < 65:
                            if e_gps and i_gps:
                                if haversine_distance(e_gps[0], e_gps[1], i_gps[0], i_gps[1]) > 45.0:
                                    conflicted = True
                                    break
                            else:
                                conflicted = True
                                break
                        if is_same_store(item, existing_item):
                            matched_any = True

                    if matched_any and not conflicted:
                        matched_store = store
                        break

                clean_addr = clean_address_text(address)
                if matched_store is not None:
                    matched_store["count"] += 1
                    matched_store["files"].append(filename)
                    matched_store.setdefault("items", []).append(item)

                    cur_clean = clean_address_text(matched_store.get("address", ""))
                    if len(clean_addr) > len(cur_clean):
                        matched_store["address"] = clean_addr
                        if item.get("house_num"):
                            matched_store["house_num"] = item["house_num"]
                        if item.get("street_name"):
                            matched_store["street_name"] = item["street_name"]
                            matched_store["street_kw"] = item["street_name"]
                        if item.get("hamlet"):
                            matched_store["hamlet"] = item["hamlet"]
                        if item.get("ward"):
                            matched_store["ward"] = item["ward"]
                    if not matched_store.get("gps") and item.get("gps"):
                        matched_store["gps"] = item["gps"]
                        matched_store["gps_text"] = item.get("gps_text", "")
                    if not matched_store.get("sr") or matched_store["sr"] == "--":
                        matched_store["sr"] = item.get("sr", "--")
                    if not matched_store.get("company") or matched_store["company"] == "--":
                        matched_store["company"] = item.get("company", "--")
                    if not matched_store.get("timemark_code") or matched_store["timemark_code"] == "--":
                        matched_store["timemark_code"] = item.get("timemark_code", "--")
                else:
                    store_entry = {
                        "address": clean_addr,
                        "gps": item.get("gps"),
                        "gps_text": item.get("gps_text", ""),
                        "house_num": item.get("house_num"),
                        "street_kw": item.get("street_kw") or item.get("street_name"),
                        "street_name": item.get("street_name") or item.get("street_kw"),
                        "hamlet": item.get("hamlet"),
                        "ward": item.get("ward"),
                        "prefix": item.get("prefix"),
                        "time": item.get("time", "--:--"),
                        "date": item.get("date", "--/--/----"),
                        "sr": item.get("sr", "--"),
                        "company": item.get("company", "--"),
                        "timemark_code": item.get("timemark_code", "--"),
                        "is_verified": item.get("is_verified", False),
                        "count": 1,
                        "files": [filename],
                        "status": "valid"
                    }
                    store_entry["items"] = [item]
                    store_groups.append(store_entry)

            # Phân loại trạng thái điểm bán chuẩn xác theo quy chuẩn 2 ảnh/điểm
            for s in store_groups:
                cnt = s["count"]
                if cnt == 2:
                    s["status"] = "valid"
                    s["status_label"] = "Đạt chuẩn (2 ảnh)"
                    s["reason"] = "Đủ 2 ảnh theo quy định"
                elif cnt > 2:
                    s["status"] = "duplicate"
                    s["status_label"] = f"Chụp dư ({cnt} ảnh)"
                    s["reason"] = f"Tính 1 điểm bán (Nhân viên chụp thừa {cnt - 2} ảnh)"
                else:
                    # cnt == 1: Vẫn tính 1 điểm bán hợp lệ, nhưng gắn nhãn thiếu ảnh
                    s["status"] = "valid"
                    s["status_label"] = "Thiếu ảnh (1 ảnh)"
                    s["reason"] = "Mới chụp 1 ảnh, thiếu 1 ảnh đối chứng thứ hai"

            return store_groups

        # Tách danh sách theo từng Nhân viên SR để đối soát độc lập
        sr_buckets = {}
        for x in valid_items:
            sr_name = (x.get("sr") or "").strip()
            if not sr_name or sr_name == "--":
                sr_name = "Chưa xác định"
            sr_buckets.setdefault(sr_name, []).append(x)

        all_grouped_stores = []
        for sr_name, items_subset in sr_buckets.items():
            all_grouped_stores.extend(_group_single_subset(items_subset))

        for u in unrelated_items:
            all_grouped_stores.append({
                "address": u["address"],
                "gps": u.get("gps"),
                "gps_text": u.get("gps_text", ""),
                "house_num": u.get("house_num"),
                "street_kw": u.get("street_kw"),
                "street_name": u.get("street_name") or u.get("street_kw"),
                "hamlet": u.get("hamlet"),
                "ward": u.get("ward"),
                "prefix": u.get("prefix"),
                "time": u.get("time", "--:--"),
                "date": u.get("date", "--/--/----"),
                "sr": u.get("sr", "--"),
                "company": u.get("company", "--"),
                "timemark_code": u.get("timemark_code", "--"),
                "is_verified": u.get("is_verified", False),
                "count": 1,
                "files": [u["filename"]],
                "status": "unrelated",
                "status_label": "Không liên quan",
                "reason": u.get("reason", "Ảnh không hợp lệ")
            })

        return all_grouped_stores

    def process_images(self, image_items: list, progress_callback=None) -> dict:
        n_files = len(image_items)

        if progress_callback:
            progress_callback({
                "step": 1,
                "report": {
                    "num_files": n_files,
                    "roi_crop": "Watermark trái (45%-100%) & Timemark phải (88%-100%)",
                    "ocr_technology": "RapidOCR ONNX Runtime + VietOCR Batch Transformer",
                    "similarity_algorithm": "Multi-tier Matching (GPS Buffer 55m, House Number, Token Set)",
                    "similarity_threshold": "80%"
                }
            })

        ocr_results = []
        if not hasattr(self, 'preview_cache'):
            self.preview_cache = {}

        for idx, item in enumerate(image_items):
            fn = item["filename"]
            fp = item.get("filepath", "")
            img_bgr = item["image"]

            info = self.extract_timemark_info(img_bgr)
            info["filename"] = fn
            info["filepath"] = fp
            ocr_results.append(info)

            ann = info.get("annotated_image")
            if ann is not None:
                self.preview_cache[fn] = ann
                if fp:
                    self.preview_cache[fp] = ann

            if progress_callback:
                short_display_fn = fn if len(fn) <= 26 else (fn[:11] + "..." + fn[-11:])
                progress_callback({
                    "step": 2,
                    "task_index": 2,
                    "task_total": 4,
                    "progress_current": idx + 1,
                    "progress_total": n_files,
                    "filename": fn,
                    "filepath": fp,
                    "info": info,
                    "annotated_image": ann,
                    "message": f"Đang đọc ảnh {idx + 1}/{n_files} ({short_display_fn})"
                })

        if progress_callback:
            progress_callback({
                "step": 2,
                "task_index": 3,
                "task_total": 4,
                "message": "Phân loại trùng lặp & đối chiếu thông số..."
            })

        grouped_stores = self.group_addresses(ocr_results, similarity_threshold=80.0)
        final_result = self._build_final_result(grouped_stores, n_files, ocr_results)

        if progress_callback:
            progress_callback({
                "step": 2,
                "task_index": 4,
                "task_total": 4,
                "message": "Hoàn tất!",
                "result": final_result
            })

        return final_result

    def _build_final_result(self, grouped_stores: list, n_files: int, ocr_results: list = None) -> dict:
        table_rows = []
        valid_cnt = 0
        standard_stores = 0
        single_stores = 0
        dup_stores = 0
        dup_imgs = 0
        unrelated_cnt = 0

        for idx, store in enumerate(grouped_stores, start=1):
            st = store.get("status", "valid")
            cnt = store.get("count", 1)
            status_label = store.get("status_label", "Hợp lệ")
            reason_str = store.get("reason", "")

            if st == "unrelated":
                unrelated_cnt += 1
            else:
                valid_cnt += 1
                if cnt == 2:
                    standard_stores += 1
                elif cnt > 2:
                    dup_stores += 1
                    dup_imgs += (cnt - 2)
                else:
                    single_stores += 1

            table_rows.append({
                "stt": idx,
                "date": store.get("date", "--/--/----"),
                "time": store.get("time", "--:--"),
                "address": store["address"],
                "gps": store.get("gps_text", ""),
                "sr": store.get("sr", "--"),
                "company": store.get("company", "--"),
                "timemark_code": store.get("timemark_code", "--"),
                "is_verified": store.get("is_verified", False),
                "count": cnt,
                "duplicate_count": max(0, cnt - 2) if cnt > 2 else 0,
                "files": ", ".join(store["files"]),
                "file_list": store["files"],
                "status": st,
                "status_label": status_label,
                "reason": reason_str
            })

        # Thống kê chi tiết theo từng nhân viên (SR)
        staff_summary = {}
        for row in table_rows:
            if row.get("status") == "unrelated":
                continue
            sr_name = (row.get("sr") or "--").strip()
            if sr_name not in staff_summary:
                staff_summary[sr_name] = {
                    "sr": sr_name,
                    "total_stores": 0,
                    "standard_stores": 0,
                    "single_stores": 0,
                    "dup_stores": 0,
                    "total_photos": 0
                }
            staff_summary[sr_name]["total_stores"] += 1
            c = row.get("count", 1)
            staff_summary[sr_name]["total_photos"] += c
            if c == 2:
                staff_summary[sr_name]["standard_stores"] += 1
            elif c > 2:
                staff_summary[sr_name]["dup_stores"] += 1
            else:
                staff_summary[sr_name]["single_stores"] += 1

        summary = {
            "total_images": n_files,
            "valid_stores": valid_cnt,
            "standard_stores": standard_stores,
            "single_stores": single_stores,
            "duplicate_stores": dup_stores,
            "duplicate_images": dup_imgs,
            "unrelated_images": unrelated_cnt,
            "warning_total": dup_stores + single_stores + unrelated_cnt,
            "staff_summary": staff_summary
        }

        final_result = {
            "summary": summary,
            "details": table_rows
        }
        if ocr_results is not None:
            final_result["raw_ocr_results"] = ocr_results
        return final_result

    def format_gemini_export_records(self, ocr_results: list) -> list:
        """Định dạng danh sách dữ liệu OCR thành JSON sạch đẹp chuẩn bị gửi cho Gemini làm sạch."""
        records = []
        for idx, item in enumerate(ocr_results, start=1):
            gps = item.get("gps")
            gps_str = ""
            if gps and len(gps) == 2:
                gps_str = f"{gps[0]:.6f}, {gps[1]:.6f}"
            elif item.get("gps_text"):
                gps_str = str(item.get("gps_text"))

            raw_lines = item.get("raw_lines") or []
            records.append({
                "id": idx,
                "filename": item.get("filename", ""),
                "sr": item.get("sr", "--"),
                "company": item.get("company", "--"),
                "address": item.get("address", ""),
                "gps": gps_str,
                "date": item.get("date", "--/--/----"),
                "time": item.get("time", "--:--"),
                "raw_text": " | ".join(raw_lines) if raw_lines else item.get("address", "")
            })
        return records

    @staticmethod
    def get_gemini_cleaning_prompt(records_or_json: Any) -> str:
        """Tạo prompt chuẩn để dán vào Gemini kèm dữ liệu JSON."""
        if not isinstance(records_or_json, str):
            json_str = json.dumps(records_or_json, ensure_ascii=False, indent=2)
        else:
            json_str = records_or_json

        return f"""Bạn là trợ lý AI chuyên chuẩn hóa dữ liệu địa chỉ và thông tin bán hàng (Sales Rep) cho hệ thống Anhiu OCR.
Dưới đây là danh sách dữ liệu thô (JSON) vừa đọc từ ảnh chụp watermark Timemark của nhân viên thị trường.

NHIỆM VỤ CỦA BẠN:
1. Chuẩn hóa địa chỉ ("address"):
   - Viết hoa đúng chính tả địa chỉ hành chính Việt Nam có dấu (ví dụ: "Đt943/đình My An Giang" -> "ĐT943, Định Mỹ, Thoại Sơn, An Giang").
   - Tên đường/tỉnh lộ/quốc lộ viết chuẩn: ĐT (Đường Tỉnh), QL (Quốc Lộ), ĐL (Đại Lộ)...
   - Giữ nguyên số nhà (nếu có).
2. Chuẩn hóa tên nhân viên ("sr"):
   - Viết hoa chữ cái đầu (Title Case: "Nguyễn Văn A").
   - Xóa các tiền tố thừa ("SR:", "NV:", "Nhân viên:").
   - Nếu không có tên người, để "--".
3. Chuẩn hóa công ty ("company"):
   - Chuẩn hóa tên công ty, nếu không có để "--".
4. Chuẩn hóa tọa độ ("gps"):
   - Định dạng chuẩn "vĩ_độ, kinh_độ" (ví dụ: "10.293456, 105.342189"). Nếu không có để "".
5. Chuẩn hóa ngày ("date") & giờ ("time"):
   - "date": DD/MM/YYYY (ví dụ: "06/10/2026").
   - "time": HH:MM (ví dụ: "10:41").
   - Nếu bị dính số (ví dụ: 06/10/202610:41) hãy tách chuẩn date và time.

YÊU CẦU ĐẦU RA BẮT BUỘC:
- Giữ nguyên "id" và "filename" để đối soát ảnh gốc.
- CHỈ TRẢ VỀ DUY NHẤT một khối mã JSON hợp lệ (mảng các object [ {{ ... }}, {{ ... }} ]), KHÔNG viết thêm bất kỳ lời chào hay giải thích nào khác.

DỮ LIỆU CẦN LÀM SẠCH:
```json
{json_str}
```"""

    def export_to_gemini_json(self, ocr_results: list, json_path: str, include_prompt_file: bool = True) -> str:
        """Xuất danh sách kết quả OCR ra file JSON cho Gemini và tạo file prompt mẫu đi kèm."""
        records = self.format_gemini_export_records(ocr_results)
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(records, f, ensure_ascii=False, indent=2)

        if include_prompt_file:
            prompt_path = os.path.splitext(json_path)[0] + "_prompt_gemini.txt"
            prompt_content = self.get_gemini_cleaning_prompt(records)
            with open(prompt_path, 'w', encoding='utf-8') as f:
                f.write(prompt_content)
        return json_path

    def group_from_cleaned_records(self, cleaned_records: list, existing_items: list = None) -> dict:
        """
        Nhận vào danh sách JSON đã được Gemini làm sạch và thực hiện gom nhóm điểm bán.
        `existing_items`: danh sách ocr_results gốc (để giữ preview ảnh và filepath).
        """
        existing_map = {}
        if existing_items:
            for it in existing_items:
                fn = it.get("filename", "")
                if fn:
                    existing_map[fn] = it

        mapped_ocr_results = []
        for rec in cleaned_records:
            fn = rec.get("filename", "")
            orig = existing_map.get(fn, {})

            addr = str(rec.get("address", "")).strip()
            sr = str(rec.get("sr", "--")).strip()
            company = str(rec.get("company", "--")).strip()
            date = str(rec.get("date", "--/--/----")).strip()
            time = str(rec.get("time", "--:--")).strip()
            gps_raw = rec.get("gps")

            # Parse GPS
            gps_coords = None
            gps_text = ""
            if isinstance(gps_raw, (list, tuple)) and len(gps_raw) == 2:
                try:
                    gps_coords = (float(gps_raw[0]), float(gps_raw[1]))
                    gps_text = f"{gps_coords[0]:.6f}, {gps_coords[1]:.6f}"
                except Exception:
                    pass
            elif isinstance(gps_raw, str) and gps_raw.strip():
                g = extract_gps_coordinates(gps_raw)
                if g:
                    gps_coords = g
                    gps_text = f"{g[0]:.6f}, {g[1]:.6f}"
                else:
                    gps_text = gps_raw.strip()

            if not gps_coords and orig.get("gps"):
                gps_coords = orig.get("gps")
                gps_text = orig.get("gps_text", "")

            # Trích xuất các trường phụ từ địa chỉ đã làm sạch
            h_num = extract_house_number(addr)
            st_name = extract_street_name(addr)
            hamlet = extract_hamlet(addr)
            ward = extract_ward_commune(addr)
            prefix = ""
            if addr:
                p_parts = addr.split(',')
                if p_parts:
                    prefix = p_parts[0].strip()

            item_dict = {
                "filename": fn,
                "filepath": orig.get("filepath", ""),
                "address": addr,
                "sr": sr or "--",
                "company": company or "--",
                "date": date or "--/--/----",
                "time": time or "--:--",
                "gps": gps_coords,
                "gps_text": gps_text,
                "house_num": h_num,
                "street_name": st_name,
                "street_kw": st_name,
                "hamlet": hamlet,
                "ward": ward,
                "prefix": prefix,
                "is_verified": orig.get("is_verified", False),
                "is_valid": bool(addr and addr != "Không tìm thấy địa chỉ Timemark"),
                "reason": "" if (addr and addr != "Không tìm thấy địa chỉ Timemark") else "Không tìm thấy địa chỉ",
                "timemark_code": orig.get("timemark_code", "--"),
                "raw_lines": orig.get("raw_lines", [])
            }
            mapped_ocr_results.append(item_dict)

        # Chạy gom nhóm điểm bán
        grouped_stores = self.group_addresses(mapped_ocr_results, similarity_threshold=80.0)

        n_files = len(mapped_ocr_results)
        final_result = self._build_final_result(grouped_stores, n_files, mapped_ocr_results)
        return final_result

    def get_annotated_preview(self, key: str):
        """Lấy ảnh preview trực quan ROI màu xanh lá từ bộ nhớ đệm cache."""
        if not hasattr(self, 'preview_cache'):
            self.preview_cache = {}
        if key in self.preview_cache:
            return self.preview_cache[key]
        bname = os.path.basename(key)
        for k, v in self.preview_cache.items():
            if os.path.basename(k) == bname:
                return v
        return None
