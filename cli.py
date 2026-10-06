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
        with open(file_path, "rb") as f:
            file_bytes = np.frombuffer(f.read(), dtype=np.uint8)
            img = cv2.imdecode(file_bytes, cv2.IMREAD_COLOR)
            if img is not None:
                return img
    except Exception:
        pass
    try:
        from PIL import Image
        pil_img = Image.open(file_path).convert("RGB")
        return cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGB2BGR)
    except Exception:
        pass
    return None

def main():
    parser = argparse.ArgumentParser(description="Anhiu - Đếm điểm bán tự động")
    parser.add_argument("--folder", type=str, help="Đường dẫn thư mục chứa ảnh Timemark")
    parser.add_argument("--files", nargs="+", help="Danh sách các file ảnh")
    parser.add_argument("--output", type=str, default="ket_qua_diem_ban.xlsx", help="Tên file Excel xuất ra")
    args = parser.parse_args()

    file_paths = []
    if args.folder:
        exts = ["*.jpg", "*.jpeg", "*.png", "*.JPG", "*.JPEG", "*.PNG"]
        for ext in exts:
            file_paths.extend(glob.glob(os.path.join(args.folder, ext)))
    elif args.files:
        file_paths = args.files
    else:
        print("Vui lòng chỉ định --folder hoặc --files. Ví dụ: python cli.py --folder ./data")
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
    print("### BÁO CÁO KẾT QUẢ TÓM TẮT")
    print(f"- Tổng số ảnh đã xử lý: {summary.get('total_images', 0)}")
    print(f"- TỔNG SỐ ĐIỂM BÁN HỢP LỆ (ĐÃ TÍNH): {summary.get('valid_stores', 0)}")
    if summary.get('duplicate_images', 0) > 0:
        print(f"- CẢNH BÁO ẢNH TRÙNG: {summary.get('duplicate_images')} ảnh trùng (thuộc {summary.get('duplicate_stores')} điểm bán; mỗi điểm đã tính 1 ảnh hợp lệ)")
    if summary.get('unrelated_images', 0) > 0:
        print(f"- Ảnh không liên quan / lỗi: {summary.get('unrelated_images')}")
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
    else:
        print("Không có kết quả nào.")

if __name__ == "__main__":
    main()
