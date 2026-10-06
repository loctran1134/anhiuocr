import os
import sys
import re
import cv2
import numpy as np
from rapidfuzz import fuzz

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

# Ensure torch lib is in dll search path on Windows Python 3.13 and imported first
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

# Patch PaddleStaticRunner to avoid Windows PIR/onednn bug on Paddle 3.x
import paddle.inference as paddle_inference

orig_create_predictor = paddle_inference.create_predictor

def patched_create_predictor(config):
    if hasattr(config, "disable_onednn"):
        config.disable_onednn()
    if hasattr(config, "disable_mkldnn"):
        config.disable_mkldnn()
    if hasattr(config, "enable_new_ir"):
        config.enable_new_ir(False)
    return orig_create_predictor(config)

paddle_inference.create_predictor = patched_create_predictor

from paddleocr import PaddleOCR


class TimemarkOCREngine:
    def __init__(self):
        self.ocr = PaddleOCR(lang='vi', use_textline_orientation=True)

    def extract_timemark_info(self, image: np.ndarray) -> dict:
        """
        Nhận diện đầy đủ 6 thông số Timemark theo ảnh mẫu:
        1. Giờ chụp (17:49)
        2. Ngày chụp (01/10/2026)
        3. Địa chỉ điểm bán (Ấp Phú Cường, Chợ Vàm, An Giang)
        4. Nhân viên tiếp thị SR (Hồ Tứ Giang)
        5. Công ty (SABECO AN GIANG)
        6. Mã xác thực Timemark Verified (RPUKLDDDDMU2RK)
        """
        h, w = image.shape[:2]

        # 1. OCR Vùng Watermark bên trái: Y (45% -> 100%), X (0% -> 65%)
        roi_left = image[int(h * 0.45):h, 0:int(w * 0.65)]
        pred_left = self.ocr.predict(roi_left)

        raw_lines = []
        for item in pred_left:
            for t in item.get('rec_texts', []):
                cleaned = t.strip()
                if cleaned:
                    raw_lines.append(cleaned)

        # 2. OCR Mã Timemark mép phải (X: 88% -> 100%, Y: 5% -> 100%)
        # Trải dài toàn bộ chiều cao mép phải để không bị cắt xén chuỗi ký tự xác thực
        roi_right = image[int(h * 0.05):h, int(w * 0.88):w]
        rot_right = cv2.rotate(roi_right, cv2.ROTATE_90_CLOCKWISE)
        pred_right = self.ocr.predict(rot_right)

        timemark_code = ""
        is_verified = False
        for item in pred_right:
            for t in item.get('rec_texts', []):
                cleaned_t = t.strip()
                if 'verified' in cleaned_t.lower() or 'timemark' in cleaned_t.lower():
                    is_verified = True
                m = re.search(r'\b([A-Z0-9]{8,22})\b', cleaned_t)
                if m:
                    cand = m.group(1).upper()
                    if cand not in ('TIMEMARK', 'VERIFIED'):
                        timemark_code = cand

        # Fallback 1: Thử xoay ngược chiều kim đồng hồ nếu máy chụp ngược hướng
        if not timemark_code:
            rot_ccw = cv2.rotate(roi_right, cv2.ROTATE_90_COUNTERCLOCKWISE)
            pred_ccw = self.ocr.predict(rot_ccw)
            for item in pred_ccw:
                for t in item.get('rec_texts', []):
                    cleaned_t = t.strip()
                    if 'verified' in cleaned_t.lower() or 'timemark' in cleaned_t.lower():
                        is_verified = True
                    m = re.search(r'\b([A-Z0-9]{8,22})\b', cleaned_t)
                    if m:
                        cand = m.group(1).upper()
                        if cand not in ('TIMEMARK', 'VERIFIED'):
                            timemark_code = cand

        # Fallback 2: Kiểm tra trong danh sách text vùng watermark bên trái
        if not timemark_code:
            for line in raw_lines:
                if 'verified' in line.lower() or 'timemark' in line.lower():
                    is_verified = True
                m = re.search(r'\b([A-Z0-9]{8,22})\b', line)
                if m:
                    cand = m.group(1).upper()
                    if cand not in ('TIMEMARK', 'VERIFIED') and not re.match(r'^\d{1,4}$', cand):
                        timemark_code = cand

        # 3. Trích xuất từng trường thông tin từ danh sách dòng bên trái
        time_val = ""
        date_val = ""
        sr_val = ""
        company_val = ""
        address_lines = []

        admin_keywords = [
            "ấp", "khóm", "thôn", "xóm", "tổ", "tổ dân phố", "khu phố", "kp",
            "xã", "phường", "thị trấn", "tt.", "tt",
            "huyện", "thị xã", "tx.", "tx", "quận", "q.",
            "tỉnh", "thành phố", "tp.", "tp",
            "đường", "phố", "ngõ", "hẻm", "số", "việt nam"
        ]

        for line in raw_lines:
            lower = line.lower()

            # Giờ chụp: HH:MM
            m_time = re.search(r'\b(\d{1,2}:\d{2}(?::\d{2})?)\b', line)
            if m_time and not time_val:
                time_val = m_time.group(1)
                continue

            # Ngày chụp: DD/MM/YYYY
            m_date = re.search(r'\b(\d{1,2}[/\-\.]\d{1,2}[/\-\.]\d{2,4})\b', line)
            if m_date and not date_val:
                date_val = m_date.group(1)
                continue

            # Bỏ qua ngày trong tuần hoặc thời tiết
            if re.search(r'^(thứ\s+|chủ\s+nhật|nhiều\s+mây|nắng|mưa|\d+°|độ\s*cao)', lower):
                continue

            # Nhân viên SR
            m_sr = re.search(r'^(?:sr|nv|nhân viên)\s*[:\-\s]\s*(.+)', line, re.IGNORECASE)
            if m_sr:
                sr_val = m_sr.group(1).strip()
                continue

            # Công ty
            m_cp = re.search(r'^(?:công ty|cty|c\.ty|company)\s*[:\-\s]\s*(.+)', line, re.IGNORECASE)
            if m_cp:
                company_val = m_cp.group(1).strip()
                continue

            # Địa chỉ hành chính
            if any(kw in lower for kw in admin_keywords) or "," in line:
                cleaned_line = re.sub(r'^[a-zA-Z0-9][\.\,]\s*', '', line.strip())
                address_lines.append(cleaned_line)

        if address_lines:
            address_val = ", ".join(address_lines)
        else:
            leftovers = [
                l for l in raw_lines
                if not any(kw in l.lower() for kw in ['sr:', 'công ty:', 'cty:', 'thứ ', 'nhiều mây', '°c', 'timemark'])
                and len(l) > 6
            ]
            if leftovers:
                address_val = leftovers[0]
            else:
                address_val = "Không tìm thấy địa chỉ Timemark"

        address_val = re.sub(r'^[a-zA-Z0-9][\.\,]\s*', '', address_val.strip())
        address_val = re.sub(r'\s*,\s*', ', ', address_val)
        address_val = re.sub(r'(,\s*){2,}', ', ', address_val)

        # Xác định tính hợp lệ
        has_time_or_date = bool(time_val or date_val)
        has_address = (address_val != "Không tìm thấy địa chỉ Timemark" and len(address_val) >= 6)
        is_valid = (has_time_or_date or is_verified) and has_address

        reason = ""
        if not is_valid:
            if not has_address:
                reason = "Không trích xuất được địa chỉ"
            elif not has_time_or_date and not is_verified:
                reason = "Không có dấu Timemark"
            else:
                reason = "Ảnh không hợp lệ"

        return {
            "time": time_val or "--:--",
            "date": date_val or "--/--/----",
            "address": address_val,
            "sr": sr_val or "--",
            "company": company_val or "--",
            "timemark_code": timemark_code or "--",
            "is_verified": is_verified,
            "is_valid": is_valid,
            "reason": reason
        }

    def group_addresses(self, ocr_results: list, similarity_threshold: float = 90.0) -> list:
        valid_items = [x for x in ocr_results if x.get("is_valid", True)]
        unrelated_items = [x for x in ocr_results if not x.get("is_valid", True)]

        store_groups = []

        for item in valid_items:
            filename = item["filename"]
            address = item["address"]

            matched_store = None
            best_score = 0.0

            for store in store_groups:
                score = fuzz.token_sort_ratio(address, store["address"])
                if score >= similarity_threshold and score > best_score:
                    best_score = score
                    matched_store = store

            if matched_store is not None:
                matched_store["count"] += 1
                matched_store["files"].append(filename)
                if len(address) > len(matched_store["address"]):
                    matched_store["address"] = address
                # Cập nhật thông tin nếu store trước đó chưa có
                if not matched_store.get("sr") or matched_store["sr"] == "--":
                    matched_store["sr"] = item.get("sr", "--")
                if not matched_store.get("company") or matched_store["company"] == "--":
                    matched_store["company"] = item.get("company", "--")
                if not matched_store.get("timemark_code") or matched_store["timemark_code"] == "--":
                    matched_store["timemark_code"] = item.get("timemark_code", "--")
            else:
                store_groups.append({
                    "address": address,
                    "time": item.get("time", "--:--"),
                    "date": item.get("date", "--/--/----"),
                    "sr": item.get("sr", "--"),
                    "company": item.get("company", "--"),
                    "timemark_code": item.get("timemark_code", "--"),
                    "is_verified": item.get("is_verified", False),
                    "count": 1,
                    "files": [filename],
                    "status": "valid"
                })

        for s in store_groups:
            if s["count"] > 1:
                s["status"] = "duplicate"
            else:
                s["status"] = "valid"

        for u in unrelated_items:
            store_groups.append({
                "address": u["address"],
                "time": u.get("time", "--:--"),
                "date": u.get("date", "--/--/----"),
                "sr": u.get("sr", "--"),
                "company": u.get("company", "--"),
                "timemark_code": u.get("timemark_code", "--"),
                "is_verified": u.get("is_verified", False),
                "count": 1,
                "files": [u["filename"]],
                "status": "unrelated",
                "reason": u.get("reason", "Ảnh không hợp lệ")
            })

        return store_groups

    def process_images(self, image_items: list, progress_callback=None) -> dict:
        n_files = len(image_items)

        ocr_results = []
        for idx, item in enumerate(image_items):
            fn = item["filename"]
            img_bgr = item["image"]

            info = self.extract_timemark_info(img_bgr)
            info["filename"] = fn
            ocr_results.append(info)

            if progress_callback:
                progress_callback({
                    "step": 2,
                    "task_index": 2,
                    "task_total": 4,
                    "progress_current": idx + 1,
                    "progress_total": n_files,
                    "message": f"Đang đọc ảnh {idx + 1}/{n_files} ({fn})"
                })

        if progress_callback:
            progress_callback({
                "step": 2,
                "task_index": 3,
                "task_total": 4,
                "message": "Phân loại trùng lặp & đối chiếu thông số..."
            })

        grouped_stores = self.group_addresses(ocr_results, similarity_threshold=90.0)

        table_rows = []
        valid_cnt = 0
        dup_stores = 0
        dup_imgs = 0
        unrelated_cnt = 0

        for idx, store in enumerate(grouped_stores, start=1):
            st = store.get("status", "valid")
            cnt = store.get("count", 1)

            if st == "valid":
                valid_cnt += 1
                status_label = "Hợp lệ"
                reason_str = store.get("reason", "")
            elif st == "duplicate":
                # Tính 1 ảnh hợp lệ, cảnh báo (cnt - 1) ảnh trùng
                valid_cnt += 1
                dup_stores += 1
                dup_imgs += (cnt - 1)
                status_label = f"Hợp lệ (Trùng {cnt - 1} ảnh)"
                reason_str = f"Tính 1 ảnh hợp lệ, cảnh báo có {cnt - 1} ảnh chụp trùng"
            else:
                unrelated_cnt += 1
                status_label = "Không liên quan"
                reason_str = store.get("reason", "Ảnh không hợp lệ")

            table_rows.append({
                "stt": idx,
                "date": store.get("date", "--/--/----"),
                "time": store.get("time", "--:--"),
                "address": store["address"],
                "sr": store.get("sr", "--"),
                "company": store.get("company", "--"),
                "timemark_code": store.get("timemark_code", "--"),
                "is_verified": store.get("is_verified", False),
                "count": cnt,
                "duplicate_count": max(0, cnt - 1) if st == "duplicate" else 0,
                "files": ", ".join(store["files"]),
                "file_list": store["files"],
                "status": st,
                "status_label": status_label,
                "reason": reason_str
            })

        summary = {
            "total_images": n_files,
            "valid_stores": valid_cnt,
            "duplicate_stores": dup_stores,
            "duplicate_images": dup_imgs,
            "unrelated_images": unrelated_cnt,
            "warning_total": dup_imgs + unrelated_cnt
        }

        final_result = {
            "summary": summary,
            "details": table_rows
        }

        if progress_callback:
            progress_callback({
                "step": 2,
                "task_index": 4,
                "task_total": 4,
                "message": "Hoàn tất!",
                "result": final_result
            })

        return final_result
