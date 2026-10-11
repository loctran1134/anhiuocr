/**
 * Gemini Store Visit Scorer - Content Script
 * Tự động nạp dữ liệu OCR JSON và Prompt chấm điểm vào ô nhập của Google Gemini
 * và tự động bấm gửi để Gemini phân tích số lượng điểm bán.
 */

(() => {
  if (window.__ge_injected) return;
  window.__ge_injected = true;

  // Lắng nghe message trực tiếp từ extension popup nếu tab đang mở sẵn
  chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
    if (request.action === "INJECT_AND_SUBMIT") {
      injectPromptIntoGemini(request.prompt, request.autoSubmit)
        .then(res => sendResponse({ success: true }))
        .catch(err => sendResponse({ success: false, error: err.message }));
      return true; // async
    }
  });

  // Kiểm tra xem có tác vụ chấm điểm đang chờ trong storage không (khi tab vừa mở mới)
  function checkPendingTask() {
    chrome.storage.local.get(['pending_gemini_prompt', 'auto_submit'], (data) => {
      if (data && data.pending_gemini_prompt) {
        const prompt = data.pending_gemini_prompt;
        const autoSubmit = data.auto_submit !== false;

        // Xóa storage để không bị lặp
        chrome.storage.local.remove(['pending_gemini_prompt', 'auto_submit']);

        showBanner("Đang chuẩn bị gửi dữ liệu chấm điểm bán...");
        injectPromptIntoGemini(prompt, autoSubmit);
      }
    });
  }

  // Chờ và tìm ô nhập prompt của Gemini
  async function waitForGeminiInput(maxAttempts = 35) {
    for (let i = 0; i < maxAttempts; i++) {
      const inputEl = findGeminiInputElement();
      if (inputEl) return inputEl;
      await new Promise(r => setTimeout(r, 600));
    }
    return null;
  }

  function findGeminiInputElement() {
    return document.querySelector(
      '.ql-editor[contenteditable="true"], ' +
      'div[contenteditable="true"][role="textbox"], ' +
      'rich-textarea div[contenteditable="true"], ' +
      'div[contenteditable="true"], ' +
      'textarea'
    );
  }

  function findGeminiSendButton() {
    // Tìm các nút gửi tin nhắn đặc trưng của Gemini
    const selectors = [
      'button[aria-label*="Send message"]',
      'button[aria-label*="Gửi tin nhắn"]',
      'button[aria-label*="Send prompt"]',
      'button[aria-label*="Send"]',
      'button[aria-label*="Gửi"]',
      'button.send-button',
      'div[role="button"][aria-label*="Send"]',
      'button[mat-icon-button]'
    ];

    for (const sel of selectors) {
      const btns = document.querySelectorAll(sel);
      for (const btn of btns) {
        if (!btn.disabled && btn.offsetParent !== null) {
          return btn;
        }
      }
    }
    return null;
  }

  async function injectPromptIntoGemini(promptText, autoSubmit = true) {
    showBanner("Đang tìm ô nhập của Google Gemini...");
    const inputEl = await waitForGeminiInput();

    if (!inputEl) {
      showBanner("Không tìm thấy ô nhập tin nhắn trên trang Gemini!", "error");
      throw new Error("Không tìm thấy ô nhập prompt trên Gemini.");
    }

    inputEl.focus();

    // Điền nội dung vào ô nhập (hỗ trợ cả contenteditable và textarea)
    if (inputEl.tagName === 'TEXTAREA') {
      inputEl.value = promptText;
      inputEl.dispatchEvent(new Event('input', { bubbles: true }));
      inputEl.dispatchEvent(new Event('change', { bubbles: true }));
    } else {
      // Dành cho contenteditable div
      inputEl.innerHTML = '';
      
      // Sử dụng execCommand hoặc chèn Paragraph để giữ định dạng dòng
      const lines = promptText.split('\n');
      const htmlContent = lines.map(line => `<p>${escapeHtml(line) || '<br>'}</p>`).join('');
      inputEl.innerHTML = htmlContent;

      // Kích hoạt các sự kiện input để framework (Angular/Lit/React) ghi nhận
      inputEl.dispatchEvent(new InputEvent('input', {
        bubbles: true,
        cancelable: true,
        inputType: 'insertFromPaste'
      }));
      inputEl.dispatchEvent(new Event('change', { bubbles: true }));
      inputEl.dispatchEvent(new KeyboardEvent('keyup', { bubbles: true, key: 'a' }));
    }

    showBanner("Đã nạp toàn bộ dữ liệu JSON & Prompt!");

    if (autoSubmit) {
      showBanner("Đang chuẩn bị bấm Gửi...");
      // Đợi 1s để Gemini kích hoạt trạng thái nút Send
      await new Promise(r => setTimeout(r, 1200));

      const sendBtn = findGeminiSendButton();
      if (sendBtn) {
        sendBtn.click();
        showBanner("Đã gửi thành công! Gemini đang tiến hành chấm điểm bán...", "success");
      } else {
        // Fallback: Giả lập nhấn phím Enter
        const enterEvt = new KeyboardEvent('keydown', {
          bubbles: true,
          cancelable: true,
          key: 'Enter',
          code: 'Enter',
          keyCode: 13
        });
        inputEl.dispatchEvent(enterEvt);
        showBanner("Đã kích hoạt gửi! Hãy kiểm tra kết quả phân tích phía trên.", "success");
      }
    }
  }

  function escapeHtml(text) {
    if (!text) return '';
    const map = { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#039;' };
    return text.replace(/[&<>"']/g, m => map[m]);
  }

  function showBanner(text, type = 'info') {
    let banner = document.getElementById('ge-status-banner');
    if (!banner) {
      banner = document.createElement('div');
      banner.id = 'ge-status-banner';
      document.body.appendChild(banner);
    }

    banner.className = type;
    banner.textContent = text;
    banner.style.display = 'flex';

    if (type === 'success') {
      setTimeout(() => {
        if (banner) banner.style.display = 'none';
      }, 6000);
    }
  }

  // Khởi động kiểm tra khi trang tải xong
  setTimeout(checkPendingTask, 1500);
})();
