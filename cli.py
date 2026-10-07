import os
import sys
import argparse
import glob

if hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except Exception:
        pass

import cv2
import numpy as np
import pandas as pd
from datetime import datetime
from ocr_engine import TimemarkOCREngine

def load_image_unicode(file_path: str):
    try:
        from PIL import Image, ImageOps
        pil_img = Image.open(file_path)
        pil_img = ImageOps.exif_transpose(pil_img)
        return cv2.cvtColor(np.array(pil_img.convert("RGB")), cv2.COLOR_RGB2BGR)
    except Exception:
        pass
    try:
        with open(file_path, "rb") as f:
            file_bytes = np.frombuffer(f.read(), dtype=np.uint8)
            img = cv2.imdecode(file_bytes, cv2.IMREAD_COLOR)
            if img is not None:
                return img
    except Exception:
        pass
    return None

def main():
    parser = argparse.ArgumentParser(description="Anhiu - Đếm điểm bán tự động")
    parser.add_argument("--folder", type=str, help="Đường dẫn thư mục chứa ảnh Timemark")
    parser.add_argument("--files", nargs="+", help="Danh sách các file ảnh")
    parser.add_argument("--output", type=str, default="ket_qua_diem_ban.xlsx", help="Tên file Excel xuất ra")
    parser.add_argument("--export-json", type=str, help="Xuất dữ liệu OCR thô ra file JSON + Prompt cho Gemini")
    parser.add_argument("--import-json", type=str, help="Nạp file JSON đã được Gemini làm sạch để chấm điểm bán ngay")
    args = parser.parse_args()

    engine = TimemarkOCREngine()

    # Nạp trực tiếp từ JSON đã làm sạch bởi Gemini nếu có
    if args.import_json:
        import json
        if not os.path.exists(args.import_json):
            print(f"Lỗi: Không tìm thấy file JSON: {args.import_json}")
            sys.exit(1)
        with open(args.import_json, 'r', encoding='utf-8') as f:
            cleaned_data = json.load(f)
        print(f"\n[GEMINI IMPORT] Đang chấm điểm bán từ {len(cleaned_data)} bản ghi JSON đã làm sạch...")
        result = engine.group_from_cleaned_records(cleaned_data)
        summary = result["summary"]
        details = result["details"]
        print("\n-------------------------------------------------------")
        print("### BÁO CÁO KẾT QUẢ TỪ JSON ĐÃ LÀM SẠCH (GEMINI)")
        print(f"- Tổng số ảnh: {summary.get('total_images', 0)}")
        print(f"- TỔNG SỐ ĐIỂM BÁN HỢP LỆ: {summary.get('valid_stores', 0)} điểm")
        print(f"  + Số điểm đạt chuẩn (2 ảnh): {summary.get('standard_stores', 0)}")
        print(f"  + Số điểm thiếu/dư/cảnh báo: {summary.get('warning_total', 0)}")
        print("-------------------------------------------------------\n")
        df = pd.DataFrame(details)
        if not df.empty:
            df = df.rename(columns={"stt": "STT", "address": "Địa chỉ", "count": "Số ảnh", "files": "Danh sách file"})
            print(df.to_string(index=False))
            df.to_excel(args.output, index=False)
            print(f"\n[XUẤT FILE] Đã lưu kết quả Excel vào file: {os.path.abspath(args.output)}")
        sys.exit(0)

    file_paths = []
    if args.folder:
        exts = ["*.jpg", "*.jpeg", "*.png", "*.JPG", "*.JPEG", "*.PNG"]
        for ext in exts:
            file_paths.extend(glob.glob(os.path.join(args.folder, ext)))
    elif args.files:
        file_paths = args.files
    else:
        print("Vui lòng chỉ định --folder, --files hoặc --import-json. Ví dụ: python cli.py --folder ./data")
        sys.exit(1)

    if not file_paths:
        print("Không tìm thấy file ảnh nào hợp lệ!")
        sys.exit(1)

    print(f"\n=======================================================")
    print(f"            ANHIU - ĐẾM ĐIỂM BÁN TỰ ĐỘNG")
    print(f"=======================================================\n")


    image_items = []
    for fp in file_paths:
        img = load_image_unicode(fp)
        if img is not None:
            image_items.append({
                "filename": os.path.basename(fp),
                "image": img
            })

    engine = TimemarkOCREngine()

    def print_progress(p):
        step = p.get("step")
        msg = p.get("message", "")
        if step == 1:
            print("\n-------------------------------------------------------")
            print("### BÁO CÁO TIỀN XỬ LÝ")
            rep = p.get("report", {})
            print(f"- Số lượng ảnh đầu vào: {rep.get('num_files')} file")
            print(f"- Vùng cắt (ROI Crop): {rep.get('roi_crop')}")
            print(f"- Công nghệ OCR: {rep.get('ocr_technology')}")
            print(f"- Thuật toán so sánh: {rep.get('similarity_algorithm')}")
            print(f"- Ngưỡng tương đồng: {rep.get('similarity_threshold')}")
            print("-------------------------------------------------------\n")
        else:
            print(f"[TIẾN TRÌNH] {msg}")

    result = engine.process_images(image_items, progress_callback=print_progress)

    summary = result["summary"]
    details = result["details"]

    print("\n-------------------------------------------------------")
    print("### BÁO CÁO KẾT QUẢ TÓM TẮT CHẤM CÔNG")
    print(f"- Tổng số ảnh đã xử lý: {summary.get('total_images', 0)}")
    print(f"- TỔNG SỐ ĐIỂM BÁN THỰC TẾ (ĐÃ TÍNH): {summary.get('valid_stores', 0)} điểm bán")
    print(f"  + Số điểm đạt chuẩn (đủ 2 ảnh): {summary.get('standard_stores', 0)}")
    if summary.get('duplicate_stores', 0) > 0:
        print(f"  + Số điểm chụp dư (>2 ảnh): {summary.get('duplicate_stores', 0)} (dư {summary.get('duplicate_images', 0)} ảnh)")
    if summary.get('single_stores', 0) > 0:
        print(f"  + Số điểm thiếu ảnh (chỉ 1 ảnh): {summary.get('single_stores', 0)}")
    if summary.get('unrelated_images', 0) > 0:
        print(f"- Ảnh không liên quan / lỗi loại bỏ: {summary.get('unrelated_images')} ảnh")
    print("-------------------------------------------------------\n")

    print("### BẢNG CHI TIẾT")
    df = pd.DataFrame(details)
    if not df.empty:
        df = df.rename(columns={
            "stt": "STT",
            "address": "Địa chỉ điểm bán",
            "count": "Số ảnh chụp",
            "files": "Danh sách file ảnh"
        })
        print(df.to_string(index=False))

        output_file = args.output
        df.to_excel(output_file, index=False)
        print(f"\n[XUẤT FILE] Đã lưu kết quả chi tiết vào file: {os.path.abspath(output_file)}")

    if args.export_json:
        raw_results = result.get("raw_ocr_results", [])
        engine.export_to_gemini_json(raw_results, args.export_json, include_prompt_file=True)
        print(f"\n[GEMINI EXPORT] Đã xuất file JSON thô cho Gemini tại: {os.path.abspath(args.export_json)}")
        print(f"[GEMINI EXPORT] Kèm theo file Prompt: {os.path.abspath(os.path.splitext(args.export_json)[0] + '_prompt_gemini.txt')}")
    else:
        if df.empty:
            print("Không có kết quả nào.")

if __name__ == "__main__":
    main()
