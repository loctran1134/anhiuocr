document.addEventListener('DOMContentLoaded', () => {
  const txtJson = document.getElementById('txtJson');
  const btnPaste = document.getElementById('btnPaste');
  const btnOpenFile = document.getElementById('btnOpenFile');
  const fileInput = document.getElementById('fileInput');
  const btnClear = document.getElementById('btnClear');
  const chkAutoSubmit = document.getElementById('chkAutoSubmit');
  const cboMode = document.getElementById('cboMode');
  const btnSend = document.getElementById('btnSendToGemini');
  const statusBox = document.getElementById('statusBox');

  function showStatus(text, isError = false) {
    statusBox.textContent = text;
    statusBox.classList.remove('hidden');
    statusBox.style.background = isError ? '#fef2f2' : '#eff6ff';
    statusBox.style.color = isError ? '#991b1b' : '#1e40af';
    statusBox.style.borderColor = isError ? '#fecaca' : '#bfdbfe';
  }

  function hideStatus() {
    statusBox.classList.add('hidden');
  }

  // Tự động kiểm tra clipboard khi mở popup
  navigator.clipboard.readText().then(clipText => {
    if (clipText && (clipText.trim().startsWith('[') || clipText.trim().startsWith('{')) && !txtJson.value) {
      txtJson.value = clipText.trim();
      showStatus("Đã tự động dán dữ liệu JSON từ bộ nhớ tạm!");
    }
  }).catch(() => {});

  btnPaste.addEventListener('click', async () => {
    try {
      const text = await navigator.clipboard.readText();
      if (text) {
        txtJson.value = text.trim();
        showStatus("Đã dán từ Clipboard!");
      }
    } catch (e) {
      showStatus("Không thể truy cập Clipboard. Hãy dùng Ctrl+V vào ô bên dưới.", true);
    }
  });

  btnOpenFile.addEventListener('click', () => fileInput.click());

  fileInput.addEventListener('change', (e) => {
    const file = e.target.files[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = (evt) => {
      txtJson.value = evt.target.result;
      showStatus(`Đã tải file: ${file.name}`);
    };
    reader.readAsText(file);
  });

  btnClear.addEventListener('click', () => {
    txtJson.value = '';
    hideStatus();
  });

  // Bấm Mở Web Gemini & Chấm điểm bán
  btnSend.addEventListener('click', async () => {
    hideStatus();
    const rawVal = txtJson.value.trim();
    if (!rawVal) {
      showStatus("Vui lòng dán hoặc mở file JSON OCR trước khi chấm điểm!", true);
      return;
    }

    // Kiểm tra định dạng JSON
    let parsedData = null;
    let jsonToInclude = rawVal;
    try {
      // Bỏ qua markdown nếu có
      let cleanVal = rawVal;
      if (cleanVal.includes('```')) {
        const m = cleanVal.match(/```(?:json)?\s*([\s\S]*?)\s*```/);
        if (m) cleanVal = m[1].trim();
      }
      parsedData = JSON.parse(cleanVal);
      jsonToInclude = JSON.stringify(parsedData, null, 2);
    } catch (err) {
      showStatus("Dữ liệu trong ô không phải là JSON hợp lệ: " + err.message, true);
      return;
    }

    const mode = cboMode.value;
    const autoSubmit = chkAutoSubmit.checked;

    // Soạn thảo Prompt chuyên sâu cho Gemini
    const fullPrompt = buildAuditPrompt(jsonToInclude, mode);

    btnSend.disabled = true;
    btnSend.textContent = "Đang kết nối Gemini...";

    try {
      // 1. Kiểm tra xem đã có tab Gemini đang mở sẵn không
      const tabs = await chrome.tabs.query({ url: "*://gemini.google.com/*" });
      
      if (tabs && tabs.length > 0) {
        // Có tab Gemini sẵn -> Kích hoạt tab đó và gửi lệnh
        const targetTab = tabs[0];
        await chrome.tabs.update(targetTab.id, { active: true });
        
        chrome.tabs.sendMessage(targetTab.id, {
          action: "INJECT_AND_SUBMIT",
          prompt: fullPrompt,
          autoSubmit: autoSubmit
        }, (resp) => {
          btnSend.disabled = false;
          btnSend.textContent = "Mở Web Gemini & Chấm điểm bán";
          if (chrome.runtime.lastError) {
            // Có thể tab đang mở nhưng chưa inject content script -> lưu storage và reload
            savePendingAndReload(targetTab.id, fullPrompt, autoSubmit);
          } else {
            showStatus("Đã gửi dữ liệu sang tab Gemini thành công!");
          }
        });
      } else {
        // Chưa có tab Gemini -> Lưu vào storage và mở tab mới
        await chrome.storage.local.set({
          pending_gemini_prompt: fullPrompt,
          auto_submit: autoSubmit
        });

        await chrome.tabs.create({ url: "https://gemini.google.com/app" });
        btnSend.disabled = false;
        btnSend.textContent = "Mở Web Gemini & Chấm điểm bán";
        showStatus("Đang mở trang Gemini. Hệ thống sẽ tự động điền prompt và chấm điểm!");
      }
    } catch (e) {
      btnSend.disabled = false;
      btnSend.textContent = "Mở Web Gemini & Chấm điểm bán";
      showStatus("Lỗi kết nối: " + e.message, true);
    }
  });

  async function savePendingAndReload(tabId, prompt, autoSubmit) {
    await chrome.storage.local.set({
      pending_gemini_prompt: prompt,
      auto_submit: autoSubmit
    });
    await chrome.tabs.reload(tabId);
    showStatus("Đang tải lại tab Gemini và tự động gửi dữ liệu!");
  }

  function buildAuditPrompt(jsonStr, mode) {
    const isStrict = mode === 'strict';

    return `Bạn là Chuyên viên Kiểm toán & Đối soát Hoạt động Bán hàng Thực địa (Field Sales Auditor).

Dưới đây là toàn bộ dữ liệu JSON được trích xuất bằng OCR từ ảnh chụp check-in watermark Timemark của nhân viên bán hàng:

\`\`\`json
${jsonStr}
\`\`\`

YÊU CẦU ĐỐI SOÁT & CHẤM ĐIỂM BÁN HÀNG:
1. Đếm chính xác nhân viên này đã đi thực tế BAO NHIÊU ĐIỂM BÁN (Cửa hàng / Đại lý / Tạp hóa riêng biệt) trong ngày.
2. Quy tắc đối soát & gom nhóm điểm bán:
   - Gom nhóm: Các ảnh chụp có cùng địa chỉ (hoặc sai khác nhỏ do chính tả/số nhà gần kề) và thời gian chụp liên tiếp trong vòng 1-15 phút tại cùng vị trí phải được GOM CHUNG LÀ 1 ĐIỂM BÁN DUY NHẤT.
   - Loại trừ trùng lặp: Nếu nhân viên chụp nhiều ảnh (quầy kệ, mặt tiền, tủ tiền, sản phẩm) ở cùng 1 cửa hàng, chỉ tính là 1 điểm bán hợp lệ.
   ${isStrict ? '- Kiểm tra khoảng cách & thời gian: Phát hiện các bất thường (ví dụ 2 điểm cách xa nhau 5km nhưng thời gian check-in chỉ cách nhau 1-2 phút; hoặc check-in cùng tọa độ GPS nhưng ghi 2 tên tiệm khác nhau).' : ''}
   - Loại trừ ảnh lỗi: Ảnh không có biển hiệu, không có địa chỉ, ảnh phong cảnh ngoài đường hoặc không liên quan đến việc bán hàng.

3. HÃY TRÌNH BÀY KẾT QUẢ THEO BẢNG SAU:
| STT | Tên Điểm Bán / Biển Hiệu | Địa Chỉ Chi Tiết | Thời Gian | Tọa Độ GPS | Số Ảnh | Trạng Thái (Hợp Lệ / Trùng / Nghi Vấn) | Nhận Xét Đối Soát |

4. BẢNG TỔNG KẾT ĐÁNH GIÁ:
- Tổng số ảnh đã quét: ...
- Tổng số điểm bán thực tế đã ghé: ...
- Số lượt check-in vi phạm / trùng lặp: ...
- Đánh giá chất lượng thực thi: ĐẠT / KHÔNG ĐẠT KPI.`;
  }
});
