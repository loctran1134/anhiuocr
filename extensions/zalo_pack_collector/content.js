/**
 * Zalo Image Pack Collector - Content Script (V2 Upgrade)
 * Hỗ trợ tự động mở đúng đoạn chat, trích xuất chính xác ảnh check-in và gom Pack chuẩn theo thời gian.
 */

(() => {
  // Tránh inject trùng lặp nhưng cho phép cập nhật listener
  window.__zpc_injected = true;

  // Lắng nghe lệnh từ Extension Popup
  chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
    if (request.action === "GET_STATE") {
      const convList = getConversationsList();
      const activeName = getActiveConversationName();
      const members = getChatMembers();
      sendResponse({ success: true, conversations: convList, activeConversation: activeName, members });
      return false;
    } 
    
    if (request.action === "SWITCH_CONVERSATION") {
      const ok = openConversationByName(request.conversationName);
      // Đợi Zalo cập nhật DOM của đoạn chat mới
      setTimeout(() => {
        const activeName = getActiveConversationName();
        const members = getChatMembers();
        sendResponse({ success: ok, activeConversation: activeName, members });
      }, 700);
      return true; // async
    } 
    
    if (request.action === "SCAN_PACKS" || request.action === "SCAN_IMAGES") {
      // Đợi 200ms cho ổn định rồi quét
      setTimeout(() => {
        const result = scanAndGroupPacks(request.filter || {});
        sendResponse({ success: true, result });
      }, 200);
      return true; // async
    } 
    
    if (request.action === "AUTO_SCROLL_UP") {
      autoScrollHistory(request.times || 8).then(() => {
        sendResponse({ success: true });
      });
      return true; // async
    } 
    
    if (request.action === "DOWNLOAD_ZIP") {
      downloadPacksAsZip(request.packs, request.employeeName, request.date)
        .then(() => sendResponse({ success: true }))
        .catch(err => sendResponse({ success: false, error: err.message }));
      return true; // async
    }

    if (request.action === "GET_CHAT_MEMBERS") {
      getChatMembersAsync().then(res => {
        sendResponse({
          success: true,
          members: res.members,
          targetCount: res.targetCount,
          isGroup: res.isGroup
        });
      }).catch(err => {
        sendResponse({ success: false, error: err.message, members: [] });
      });
      return true; // async response
    }
  });

  // 1. LẤY DANH SÁCH CUỘC TRÒ CHUYỆN Ở THANH BÊN TRÁI
  function getConversationsList() {
    const list = [];

    // Tìm các phần tử cuộc trò chuyện
    const convItems = Array.from(document.querySelectorAll(
      '.conv-item, [id^="conv_"], [class*="conv-item"], [class*="conversation-item"], [data-id*="conv"], .chat-item'
    ));

    // Fallback: nếu selector chuẩn không ra, tìm trong cột bên trái (left < 400px)
    let candidateEls = convItems;
    if (candidateEls.length === 0) {
      const leftCol = document.querySelector('#conversationList, [class*="conv-list"], [class*="chat-list"], aside, nav') || document.body;
      candidateEls = Array.from(leftCol.querySelectorAll('div, li, [role="button"]')).filter(el => {
        const rect = el.getBoundingClientRect();
        return rect.left < 380 && rect.width > 120 && rect.height >= 40 && rect.height <= 90;
      });
    }

    candidateEls.forEach(item => {
      const titleEl = item.querySelector('.conv-item-title, [class*="title"], [class*="name"]');
      let name = '';
      if (titleEl && titleEl.innerText) {
        name = titleEl.innerText.trim();
      } else if (item.innerText) {
        name = item.innerText.split('\n')[0].trim();
      }

      const lower = name.toLowerCase();
      const isSystem = ['tìm kiếm', 'tất cả', 'chưa đọc', 'phân loại', 'đăng xuất', 'cài đặt', 'cloud của tôi'].includes(lower);

      if (name && name.length >= 2 && name.length <= 60 && !list.includes(name) && !isSystem) {
        list.push(name);
      }
    });

    return list;
  }

  // 2. LẤY TÊN CUỘC TRÒ CHUYỆN ĐANG MỞ
  function getActiveConversationName() {
    // Header chính của khung chat
    const headerTitle = document.querySelector(
      '.header-title, [class*="header__title"], [class*="conversation-title"], .chat-header-title, [data-id="chat-header-title"], .chat-box-header .title'
    );
    if (headerTitle && headerTitle.innerText) {
      const t = headerTitle.innerText.split('\n')[0].trim();
      if (t) return t;
    }

    // Hoặc item đang active ở sidebar
    const activeItem = document.querySelector(
      '.conv-item.active, [class*="conv-item"][class*="active"], [class*="selected"], [aria-selected="true"]'
    );
    if (activeItem) {
      const titleEl = activeItem.querySelector('[class*="title"], [class*="name"]') || activeItem;
      const t = titleEl.innerText.split('\n')[0].trim();
      if (t) return t;
    }

    return '';
  }

  // 3. TỰ ĐỘNG BẤM MỞ ĐOẠN CHAT THEO TÊN
  function openConversationByName(targetName) {
    if (!targetName) return false;
    const norm = targetName.trim().toLowerCase();

    // Tìm trong danh sách item ở sidebar
    const candidates = Array.from(document.querySelectorAll(
      '.conv-item, [id^="conv_"], [class*="conv-item"], [class*="conversation-item"], [data-id*="conv"], div, li'
    )).filter(el => {
      const rect = el.getBoundingClientRect();
      return rect.left < 400 && rect.width > 100 && rect.height >= 30;
    });

    for (const item of candidates) {
      const text = (item.innerText || '').toLowerCase();
      const firstLine = text.split('\n')[0].trim();

      if (firstLine === norm || firstLine.includes(norm) || (text.includes(norm) && item.clientHeight < 100)) {
        triggerSimulatedClick(item);
        return true;
      }
    }
    return false;
  }

  function triggerSimulatedClick(el) {
    el.scrollIntoView({ block: 'nearest', behavior: 'instant' });
    const rect = el.getBoundingClientRect();
    const clickTarget = el.querySelector('div, a, span') || el;
    const opts = {
      bubbles: true,
      cancelable: true,
      view: window,
      clientX: rect.left + rect.width / 2,
      clientY: rect.top + rect.height / 2
    };

    el.dispatchEvent(new MouseEvent('mouseenter', opts));
    el.dispatchEvent(new MouseEvent('mousedown', opts));
    el.dispatchEvent(new MouseEvent('mouseup', opts));
    el.dispatchEvent(new MouseEvent('click', opts));
    if (typeof clickTarget.click === 'function') {
      clickTarget.click();
    }
  }

  // 4. LẤY DANH SÁCH THÀNH VIÊN TRONG CHAT HIỆN TẠI
  // 4. LÀM SẠCH VÀ CHUẨN HÓA TÊN THÀNH VIÊN (TRÁNH LỖI AVATAR, ICON KEY/ADMIN)
  function cleanMemberName(str) {
    if (!str) return '';
    // Tách theo dòng để tìm dòng tên người thực tế
    const lines = str.split('\n').map(l => l.trim()).filter(l => l.length > 0);
    let candidate = '';

    for (const line of lines) {
      let l = line.replace(/^[\uE000-\uF8FF\u2000-\u206F\u2E00-\u2E7F\u00A0\s]+/, '').trim();
      // Bỏ qua dòng chỉ có 1 ký tự (VD: "a", icon glyph, chữ cái avatar)
      if (l.length <= 1) continue;
      // Bỏ qua dòng vai trò hoặc nhãn hệ thống
      const lower = l.toLowerCase();
      if (['trưởng nhóm', 'phó nhóm', 'admin', 'chủ phòng', 'thành viên', 'hôm nay', 'hôm qua'].includes(lower)) continue;
      // Bỏ qua mốc giờ (VD: 08:26)
      if (/^\d{1,2}:\d{2}$/.test(l)) continue;
      // Bỏ qua link / file / tags
      if (lower.startsWith('http') || lower.startsWith('link') || lower.startsWith('file')) continue;
      if (lower.startsWith('hd') || lower.startsWith('sale') || /^(\d+k|\d+h\d*)/i.test(lower)) continue;

      candidate = l;
      break;
    }

    if (!candidate && lines.length > 0) {
      candidate = lines[0];
    }

    // Bỏ tiền tố lỗi như "a " do icon admin/phó nhóm hoặc thẻ <a>
    if (/^[a-zA-Z]\s+[\p{L}0-9]/u.test(candidate)) {
      candidate = candidate.replace(/^[a-zA-Z]\s+/, '').trim();
    }
    // Bỏ tiền tố @ nếu là mention
    if (candidate.startsWith('@')) {
      candidate = candidate.substring(1).trim();
    }
    // Bỏ dấu hai chấm ở cuối nếu có (VD "Trần Phước Lộc:")
    if (candidate.endsWith(':')) {
      candidate = candidate.slice(0, -1).trim();
    }

    return candidate;
  }

  function extractCleanSenderText(el) {
    if (!el) return '';
    const attr = el.getAttribute('data-sender-name') || el.getAttribute('data-user-name');
    if (attr) return cleanMemberName(attr);

    // 1. Thử tìm thẻ con chứa text tên riêng biệt (loại trừ avatar)
    const specificNameEl = el.querySelector('.card-sender-name, [class*="sender-name"], [class*="author-name"], [class*="display-name"], [class*="user-name"], .truncate, span[title]');
    if (specificNameEl && specificNameEl !== el) {
      const t = specificNameEl.getAttribute('title') || specificNameEl.innerText || specificNameEl.textContent || '';
      const c = cleanMemberName(t);
      if (c && c.length >= 2) return c;
    }

    // 2. Dùng textContent trên bản clone đã bỏ avatar/icon (textContent luôn hoạt động chuẩn trên detached node)
    try {
      const clone = el.cloneNode(true);
      const toRemove = clone.querySelectorAll('.avatar, [class*="avatar"], i, [class*="icon"], [class*="badge"], svg, [class*="admin"], [class*="time"], .tag');
      toRemove.forEach(r => r.remove());
      const txt = (clone.textContent || '').trim();
      const c = cleanMemberName(txt);
      if (c && c.length >= 2) return c;
    } catch (e) {}

    // 3. Fallback dùng innerText của phần tử gốc
    const raw = el.innerText || el.textContent || '';
    return cleanMemberName(raw);
  }

  function isValidMemberName(name, activeConv, isGroup) {
    if (!name || name.length < 2 || name.length > 60) return false;
    const lower = name.toLowerCase();
    // Bỏ tên nhóm nếu là chat nhóm
    if (isGroup && activeConv && lower === activeConv.toLowerCase()) return false;
    // Bỏ các từ hệ thống trong Zalo
    const banned = [
      'tin nhắn', 'tìm kiếm', 'tất cả', 'chưa đọc', 'phân loại', 'cài đặt',
      'ghim', 'trưởng nhóm', 'phó nhóm', 'thành viên', 'hôm nay', 'hôm qua',
      'link', 'file', 'ảnh', 'nhóm', 'cloud của tôi'
    ];
    if (banned.includes(lower)) return false;
    if (lower.endsWith(' thành viên')) return false;
    return true;
  }

  // LẤY MỤC TIÊU SỐ LƯỢNG THÀNH VIÊN TỪ HEADER (VD: "5 thành viên")
  function getGroupMemberCountTarget() {
    const candidates = Array.from(document.querySelectorAll(
      '.header-subtitle, [class*="subtitle"], [class*="header__subtitle"], [data-id*="subtitle"], .chat-box-header div, .chat-box-header span, .header div, .header span, [class*="sub-title"]'
    ));
    for (const el of candidates) {
      const txt = (el.innerText || '').trim();
      const m = txt.match(/(\d+)\s*thành viên/i);
      if (m && el.clientHeight > 0) {
        return { el: el, count: parseInt(m[1], 10) };
      }
    }
    return null;
  }

  function simulateClick(el) {
    if (!el) return;
    const opts = { bubbles: true, cancelable: true, view: window };
    el.dispatchEvent(new MouseEvent('mouseenter', opts));
    el.dispatchEvent(new MouseEvent('mousedown', opts));
    el.dispatchEvent(new MouseEvent('mouseup', opts));
    el.dispatchEvent(new MouseEvent('click', opts));
    if (typeof el.click === 'function') {
      try { el.click(); } catch (e) {}
    }
  }

  function closeMemberModal() {
    document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', code: 'Escape', keyCode: 27, which: 27, bubbles: true }));
    document.dispatchEvent(new KeyboardEvent('keyup', { key: 'Escape', code: 'Escape', keyCode: 27, which: 27, bubbles: true }));

    setTimeout(() => {
      const closeButtons = document.querySelectorAll(
        '.modal [class*="close"], [role="dialog"] [class*="close"], [class*="modal"] .close, [aria-label*="Đóng"], [aria-label*="Close"], [data-id*="close"], i.fa-times'
      );
      closeButtons.forEach(btn => simulateClick(btn));
    }, 100);
  }

  function scanMembersFromModalOrPanel(rawNames) {
    const modals = Array.from(document.querySelectorAll(
      '.modal, [class*="modal"], [role="dialog"], .portal, [class*="portal"], [class*="dialog"], [class*="popover"], [class*="member-list"], div[style*="z-index"]'
    )).filter(m => m.clientHeight > 80);

    modals.forEach(modal => {
      const avs = modal.querySelectorAll('.avatar[title], [class*="avatar"][title], img[title], img[alt]');
      avs.forEach(a => {
        const t = a.getAttribute('title') || a.getAttribute('alt') || '';
        const c = cleanMemberName(t);
        if (c && c.length >= 2) rawNames.add(c);
      });

      const rows = modal.querySelectorAll(
        '.member-item, [class*="member-item"], [class*="member-row"], [class*="user-item"], [class*="member_item"], [class*="member-info"], div, li'
      );
      rows.forEach(r => {
        if (r.clientHeight >= 24 && r.clientHeight <= 90) {
          const txt = r.innerText || r.textContent || '';
          const c = cleanMemberName(txt);
          if (c && c.length >= 2) rawNames.add(c);
        }
      });
    });
  }

  function scanMembersFromVisibleDOM(rawNames) {
    const scrollContainer = getChatScrollContainer();

    // 1. Tên người gửi trong tin nhắn
    const senderEls = scrollContainer.querySelectorAll(
      '.card-sender-name, [class*="sender-name"], [class*="author"], .msg-info__sender, [data-sender-name], [class*="chat-message-sender"], .chat-item__sender, [class*="user-name"], [class*="display-name"]'
    );
    senderEls.forEach(el => {
      const clean = extractCleanSenderText(el);
      if (clean) rawNames.add(clean);
    });

    // 2. Avatar title & alt
    const avatars = scrollContainer.querySelectorAll(
      '.avatar[title], [class*="avatar"][title], [data-avatar][title], .avatar img[title], [class*="avatar"] img[title], .avatar img[alt], [class*="avatar"] img[alt]'
    );
    avatars.forEach(av => {
      const t = (av.getAttribute('title') || av.getAttribute('alt') || '').trim();
      const clean = cleanMemberName(t);
      if (clean) rawNames.add(clean);
    });

    // 3. Mentions (@...)
    const mentionEls = scrollContainer.querySelectorAll(
      '.mention, [class*="mention"], [data-user-name], [data-uid], [data-user-id], span[data-c-id], a[href*="user"]'
    );
    mentionEls.forEach(m => {
      let txt = (m.getAttribute('data-user-name') || m.innerText || m.textContent || '').trim();
      const clean = cleanMemberName(txt);
      if (clean) rawNames.add(clean);
    });

    // 4. Quotes / replies
    const quoteEls = scrollContainer.querySelectorAll(
      '.chat-item-quote, [class*="quote"], .rel-pos [class*="quote"]'
    );
    quoteEls.forEach(q => {
      const lines = (q.innerText || q.textContent || '').split('\n');
      lines.forEach(l => {
        const clean = cleanMemberName(l);
        if (clean && clean.length >= 2) rawNames.add(clean);
      });
    });

    // 5. Panel / sidebar bên phải nếu có sẵn trong DOM (Zalo Web hiển thị thông tin nhóm ở cột bên phải)
    const rightSidebars = document.querySelectorAll(
      '#conversationInfo, [id*="conversationInfo"], [class*="conv-info"], [class*="chat-info"], [class*="group-member"], [class*="layout-info"], aside, [class*="sidebar-right"], .right-sidebar'
    );
    rightSidebars.forEach(sidebar => {
      sidebar.querySelectorAll('img[title], img[alt], [title]').forEach(el => {
        const t = el.getAttribute('title') || el.getAttribute('alt') || '';
        const clean = cleanMemberName(t);
        if (clean && clean.length >= 2) rawNames.add(clean);
      });
      sidebar.querySelectorAll('[class*="member-item"], [class*="member-name"], [class*="user-name"], li, div, span, p').forEach(el => {
        const txt = (el.innerText || el.textContent || '').trim();
        const lines = txt.split('\n').map(l => l.trim()).filter(Boolean);
        if (lines.length > 0) {
          const clean = cleanMemberName(lines[0]);
          if (clean && clean.length >= 2 && clean.length <= 40 && !clean.includes(':')) {
            rawNames.add(clean);
          }
        }
      });
    });
  }

  // TỰ ĐỘNG LẤY ĐẦY ĐỦ 100% THÀNH VIÊN TRONG ĐOẠN CHAT (BẤT ĐỒNG BỘ)
  async function getChatMembersAsync() {
    const rawNames = new Set();
    const groupTarget = getGroupMemberCountTarget();
    const targetCount = groupTarget ? groupTarget.count : 0;
    const isGroup = Boolean(groupTarget);
    const activeConv = getActiveConversationName();

    // 1. Quét nhanh từ DOM hiện diện
    scanMembersFromVisibleDOM(rawNames);

    // 2. Nếu là nhóm và số người quét được chưa đủ số lượng mục tiêu:
    // Tự động kích hoạt mở modal "Thành viên nhóm" bằng cách click vào header subtitle "X thành viên"
    if (groupTarget && targetCount > 0 && rawNames.size < targetCount) {
      try {
        const clickTarget = groupTarget.el.closest('[class*="subtitle"], [class*="header"]') || groupTarget.el;
        simulateClick(groupTarget.el);
        if (clickTarget !== groupTarget.el) {
          simulateClick(clickTarget);
        }

        // Đợi 350ms cho modal Zalo mở ra
        await new Promise(r => setTimeout(r, 350));

        // Quét danh sách thành viên trong modal
        scanMembersFromModalOrPanel(rawNames);

        // Đóng modal lại ngay
        closeMemberModal();
        await new Promise(r => setTimeout(r, 100));
      } catch (e) {
        console.warn("Lỗi auto mở modal thành viên:", e);
      }
    }

    // 3. Nếu là chat 1-1 thì lấy tên cuộc trò chuyện
    if (activeConv && !isGroup) {
      const clean = cleanMemberName(activeConv);
      if (clean) rawNames.add(clean);
    }

    // 4. Chuẩn hóa và làm sạch
    const finalSet = new Set();
    rawNames.forEach(name => {
      const norm = cleanMemberName(name);
      if (isValidMemberName(norm, activeConv, isGroup)) {
        finalSet.add(norm);
      }
    });

    return {
      members: Array.from(finalSet),
      targetCount: targetCount,
      isGroup: isGroup
    };
  }

  // 5. TÌM KHUNG CHỨA TIN NHẮN CHAT CHÍNH
  function getChatScrollContainer() {
    return document.querySelector(
      '#messageViewScroll, [id="messageViewScroll"], [class*="message-view__scroll"], .chat-message-list, [class*="chat-scroll"]'
    ) || document.body;
  }

  // TÌM CONTAINER TIN NHẮN CHUẨN XÁC
  // Leo lên cây DOM để tìm dòng tin nhắn cấp cao nhất (trực thuộc scroll container hoặc message list)
  function findMessageCard(el) {
    if (!el) return null;
    const scrollContainer = getChatScrollContainer();

    let curr = el;
    let candidate = null;

    while (curr && curr !== scrollContainer && curr !== document.body) {
      const cl = (typeof curr.className === 'string') ? curr.className : '';
      const id = curr.id || '';
      const dataId = curr.getAttribute('data-id') || '';

      // Chỉ khớp các selector message thực thụ (KHÔNG dùng [data-id] chung chung)
      if (
        cl.includes('chat-item') ||
        cl.includes('msg-item') ||
        cl.includes('chat-message') ||
        cl.includes('card--group') ||
        cl.includes('message-item') ||
        id.startsWith('msg_') ||
        id.startsWith('msg-') ||
        dataId.startsWith('msg_') ||
        dataId.startsWith('msg-') ||
        dataId.startsWith('chat_')
      ) {
        candidate = curr;
      }

      // Nếu curr có chứa avatar hoặc sender, khả năng cao là card tin nhắn
      if (!candidate && curr.querySelector && curr.querySelector('.avatar, [class*="avatar"], .card-sender-name, [class*="sender"], [class*="author"]')) {
        candidate = curr;
      }

      // Nếu phần tử cha của curr là scrollContainer hoặc list tin nhắn, thì curr chính là card tin nhắn hoàn chỉnh
      if (
        curr.parentElement === scrollContainer ||
        (curr.parentElement && (
          curr.parentElement.id === 'messageViewScroll' ||
          curr.parentElement.classList.contains('chat-message-list')
        ))
      ) {
        return curr;
      }

      curr = curr.parentElement;
    }

    if (candidate) return candidate;

    return el.closest('.chat-item, .msg-item, [id^="msg_"], [class*="card--group"], [class*="message-item"], [class*="chat-message"]') || el.parentElement;
  }

  // TRÍCH XUẤT TÊN NGƯỜI GỬI TỪ MESSAGE CARD HOẶC CỤM TIN NHẮN PHÍA TRƯỚC
  function extractSenderFromMessageCard(msgCard, targetEmployee = '') {
    if (!msgCard) return '';

    // 0. Nếu người dùng chọn đích danh tên nhân viên (VD: "Anh Nguyen"), kiểm tra trực tiếp
    if (targetEmployee) {
      const normEmp = cleanMemberName(targetEmployee).toLowerCase();
      if (normEmp && !normEmp.includes('tất cả') && !normEmp.includes('mọi người')) {
        const rawText = (msgCard.innerText || msgCard.textContent || '').toLowerCase();
        if (rawText.includes(normEmp)) {
          return targetEmployee;
        }
        const avImgs = msgCard.querySelectorAll('.avatar, [class*="avatar"], img[title], img[alt]');
        for (const av of avImgs) {
          const t = (av.getAttribute('title') || av.getAttribute('alt') || '').toLowerCase();
          if (t.includes(normEmp)) {
            return targetEmployee;
          }
        }
      }
    }

    // 1. Tìm trực tiếp bằng tất cả các class author / sender / name
    const senderEl = msgCard.querySelector(
      '.card-sender-name, [class*="sender-name"], [class*="author-name"], [class*="author"], .msg-info__sender, [data-sender-name], [class*="chat-message-sender"], .chat-item__sender, [class*="user-name"], [class*="display-name"], [class*="chat-item__author"]'
    );
    if (senderEl) {
      const s = extractCleanSenderText(senderEl);
      if (s) return s;
    }

    // 2. Tìm avatar title & alt
    const av = msgCard.querySelector('.avatar, [class*="avatar"]');
    if (av) {
      const t = av.getAttribute('title') || av.getAttribute('data-title') || '';
      if (t) {
        const s = cleanMemberName(t);
        if (s) return s;
      }
      const imgInAv = av.querySelector('img');
      if (imgInAv) {
        const alt = imgInAv.getAttribute('title') || imgInAv.getAttribute('alt') || '';
        if (alt) {
          const s = cleanMemberName(alt);
          if (s) return s;
        }
      }
      let next = av.nextElementSibling;
      while (next) {
        const txt = (next.innerText || next.textContent || '').trim();
        const s = cleanMemberName(txt);
        if (s && s.length >= 2 && s.length <= 40 && !s.includes(':')) {
          return s;
        }
        next = next.nextElementSibling;
      }
    }

    // 3. Phân tích trực tiếp từ các dòng text đầu tiên của msgCard
    const cardText = (msgCard.innerText || msgCard.textContent || '').trim();
    if (cardText) {
      const lines = cardText.split('\n').map(l => l.trim()).filter(Boolean);
      for (const line of lines) {
        const s = cleanMemberName(line);
        if (
          s && s.length >= 2 && s.length <= 40 &&
          !s.includes(':') &&
          !/^(hd|sale|\d+|\d+k|\d+h\d*)/i.test(s) &&
          !s.toLowerCase().includes('thành viên')
        ) {
          return s;
        }
      }
    }

    // 4. Nếu nằm trong cụm tin nhắn liên tiếp: duyệt ngược lại các tin trước đó (tối đa 25 tin)
    let cur = msgCard.previousElementSibling;
    let steps = 0;
    while (cur && steps < 25) {
      if (isDateSeparatorElement(cur)) {
        break;
      }

      if (targetEmployee) {
        const normEmp = cleanMemberName(targetEmployee).toLowerCase();
        if (normEmp && !normEmp.includes('tất cả')) {
          const rawText = (cur.innerText || cur.textContent || '').toLowerCase();
          if (rawText.includes(normEmp)) {
            return targetEmployee;
          }
        }
      }

      const prevSenderEl = cur.querySelector(
        '.card-sender-name, [class*="sender-name"], [class*="author-name"], [class*="author"], .msg-info__sender, [data-sender-name], [class*="chat-message-sender"], .chat-item__sender, [class*="user-name"]'
      );
      if (prevSenderEl) {
        const s = extractCleanSenderText(prevSenderEl);
        if (s) return s;
      }
      const prevAv = cur.querySelector('.avatar, [class*="avatar"]');
      if (prevAv) {
        const t = prevAv.getAttribute('title') || '';
        if (t) {
          const s = cleanMemberName(t);
          if (s) return s;
        }
        const img = prevAv.querySelector('img');
        if (img) {
          const alt = img.getAttribute('title') || img.getAttribute('alt') || '';
          const s = cleanMemberName(alt);
          if (s) return s;
        }
        let next = prevAv.nextElementSibling;
        while (next) {
          const txt = (next.innerText || next.textContent || '').trim();
          const s = cleanMemberName(txt);
          if (s && s.length >= 2 && s.length <= 40) return s;
          next = next.nextElementSibling;
        }
      }

      const prevText = (cur.innerText || cur.textContent || '').trim();
      if (prevText) {
        const lines = prevText.split('\n').map(l => l.trim()).filter(Boolean);
        for (const line of lines) {
          const s = cleanMemberName(line);
          if (
            s && s.length >= 2 && s.length <= 40 &&
            !s.includes(':') &&
            !/^(hd|sale|\d+|\d+k|\d+h\d*)/i.test(s) &&
            !s.toLowerCase().includes('thành viên')
          ) {
            return s;
          }
        }
      }

      cur = cur.previousElementSibling;
      steps++;
    }

    return '';
  }

  // KIỂM TRA TÊN NGƯỜI GỬI KHỚP VỚI BỘ LỌC
  function isSenderMatching(sender, employeeName) {
    if (!employeeName) return true;
    const normFilter = cleanMemberName(employeeName).toLowerCase();
    if (
      !normFilter ||
      normFilter === 'tất cả' ||
      normFilter === 'all' ||
      normFilter.includes('tất cả') ||
      normFilter.includes('mọi người')
    ) {
      return true;
    }

    if (!sender) return false;
    const normSender = cleanMemberName(sender).toLowerCase();

    // Bỏ dấu ba chấm '...' hoặc icon ở đuôi
    const sClean = normSender.replace(/\.{2,}$/, '').replace(/[\uE000-\uF8FF]/g, '').trim();
    const fClean = normFilter.replace(/\.{2,}$/, '').replace(/[\uE000-\uF8FF]/g, '').trim();

    // Khớp chính xác hoặc khớp chứa
    if (sClean === fClean) return true;
    if (sClean.includes(fClean) || fClean.includes(sClean)) return true;

    // Khớp tiền tố (trong chat Zalo tên dài thường bị cắt ngắn, VD: "Hải Sport Cầu Lông Pickleball Chín...")
    if (sClean.length >= 6 && fClean.startsWith(sClean)) return true;
    if (fClean.length >= 6 && sClean.startsWith(fClean)) return true;

    // Khớp không dấu (accent insensitive)
    const removeAccents = (str) => (str || '').normalize("NFD").replace(/[\u0300-\u036f]/g, "").replace(/đ/g, "d").replace(/Đ/g, "D");
    const noAccF = removeAccents(fClean);
    const noAccS = removeAccents(sClean);
    if (noAccS === noAccF) return true;
    if (noAccS.includes(noAccF) || noAccF.includes(noAccS)) return true;
    if (noAccS.length >= 6 && noAccF.startsWith(noAccS)) return true;
    if (noAccF.length >= 6 && noAccS.startsWith(noAccF)) return true;

    return false;
  }

  // QUÉT TẤT CẢ ẢNH CHAT (CẢ <img> VÀ BACKGROUND-IMAGE GRID)
  function findAllChatPhotos(scrollContainer) {
    const candidates = [];
    const seenElements = new Set();

    // 1. Thẻ <img>
    const imgEls = Array.from(scrollContainer.querySelectorAll('img'));
    imgEls.forEach(img => {
      if (seenElements.has(img)) return;
      seenElements.add(img);

      const src = img.currentSrc || img.src || img.getAttribute('data-original') || img.getAttribute('data-url') || img.getAttribute('data-src');
      if (isValidChatPhoto(img, src)) {
        candidates.push({ el: img, src: cleanZaloImgUrl(src) });
      }
    });

    // 2. Thẻ có style background-image (Zalo layout lưới album ảnh)
    const bgEls = Array.from(scrollContainer.querySelectorAll(
      '[style*="background-image"], [class*="picture"], [class*="photo"], [class*="thumb"]'
    ));
    bgEls.forEach(el => {
      if (seenElements.has(el)) return;
      seenElements.add(el);

      const style = el.getAttribute('style') || '';
      const m = style.match(/background-image:\s*url\(['"]?(.*?)['"]?\)/i);
      if (m && m[1]) {
        const src = m[1];
        if (isValidChatPhoto(el, src)) {
          candidates.push({ el: el, src: cleanZaloImgUrl(src) });
        }
      }
    });

    return candidates;
  }

  // KIỂM TRA ẢNH CHỤP CHECK-IN HỢP LỆ (KHÔNG BỎ SÓT LƯỚI ẢNH 3 CỘT, LOẠI BỎ AVT VÀ ICON)
  function isValidChatPhoto(el, src) {
    if (!el || !src) return false;

    // 1. LOẠI BỎ AVATAR
    if (
      el.closest('.avatar, [class*="avatar"], .conv-item, [class*="conv-item"], .header, [class*="header"], [class*="sidebar"]') ||
      src.includes('avatar') ||
      src.includes('/avt/') ||
      src.includes('default-avatar') ||
      src.includes('s120-ava') ||
      src.includes('ava_')
    ) {
      return false;
    }

    // 2. LOẠI BỎ LOGO, TUTORIAL GRAPHIC, ICON, STICKER, EMOJI
    if (
      src.includes('zalo.me/images') ||
      src.includes('/icon/') ||
      src.includes('emoji') ||
      src.includes('sticker') ||
      src.includes('.svg') ||
      src.includes('data:image/svg') ||
      src.includes('chat_onboard') ||
      src.includes('welcome')
    ) {
      return false;
    }

    // 3. Phải nằm trong khung chat
    const scrollContainer = getChatScrollContainer();
    if (scrollContainer && !scrollContainer.contains(el)) {
      return false;
    }

    // 4. Kích thước thật: Chỉ loại bỏ icon/reaction siêu nhỏ (< 35px), không loại bỏ ảnh lưới 3 cột (~80-90px)
    const w = el.naturalWidth || el.clientWidth || 0;
    const h = el.naturalHeight || el.clientHeight || 0;
    if (w > 0 && h > 0 && (w < 35 || h < 35)) {
      return false;
    }

    // 5. CDN Zalo (zadn.vn, zdn.vn, blob) hoặc thuộc bubble ảnh
    const isZaloCdn = src.includes('zadn.vn') || src.includes('zdn.vn') || src.startsWith('blob:') || src.includes('photo') || src.includes('zalo');
    const isImageBubble = el.closest(
      '.img-bubble, .image-temp, [class*="image"], [class*="photo"], [class*="media"], [class*="thumb"], [class*="picture"], [class*="card--picture"]'
    );
    const hasHdBadge = Boolean(el.parentElement && el.parentElement.querySelector('[class*="hd"], .tag-hd'));

    return isZaloCdn || Boolean(isImageBubble) || hasHdBadge;
  }

  function isDateSeparatorElement(el) {
    if (!el) return false;
    // Nếu có avatar hoặc bong bóng tin nhắn/ảnh thì chắc chắn KHÔNG PHẢI vạch ngày
    if (el.querySelector && el.querySelector('.avatar, [class*="avatar"], .card-sender-name, [class*="sender"], [class*="author"], img[src*="photo"], [class*="picture"]')) {
      return false;
    }

    const raw = (el.innerText || el.textContent || '').trim();
    if (!raw || raw.length > 50) return false;

    const txt = raw.toLowerCase().replace(/[\u00A0\r\n\t]/g, ' ').replace(/\s+/g, ' ');

    // 1. Chứa từ khóa hôm nay, hôm qua
    if (txt.includes('hôm nay') || txt.includes('hôm qua') || txt.includes('today') || txt.includes('yesterday')) {
      return true;
    }

    // 2. Chứa thứ trong tuần (T2..T7, CN, Thứ 2..Thứ 7, Chủ nhật) kèm mốc ngày
    if (/(?:t[2-7]|thứ\s*[2-7]|cn|chủ\s*nhật)/i.test(txt) && /\d{1,2}[\/\-\.]\d{1,2}/.test(txt)) {
      return true;
    }

    // 3. Chứa định dạng ngày DD/MM hoặc DD/MM/YYYY (VD: "08/10", "08/10/2026", "T5, 08/10")
    if (/\b\d{1,2}[\/\-\.]\d{1,2}(?:[\/\-\.]\d{2,4})?\b/.test(txt)) {
      return true;
    }

    // 4. Các class định danh ngày của Zalo
    if (el.querySelector && el.querySelector('.chat-date, .date-separator, [class*="date"], [class*="timeline"], [class*="divider"]')) {
      return true;
    }

    return false;
  }

  // TRÍCH XUẤT NGÀY CỦA TIN NHẮN (DD/MM/YYYY)
  function extractDateFromMessageCard(msgCard) {
    if (!msgCard) return getTodayFormatted();

    // 1. Duyệt ngược lên qua các sibling để tìm vạch ngăn ngày gần nhất phía trên
    let cur = msgCard.previousElementSibling;
    let steps = 0;
    while (cur && steps < 250) {
      if (isDateSeparatorElement(cur)) {
        const curTxt = (cur.innerText || cur.textContent || '').trim().toLowerCase();
        if (curTxt.includes('hôm qua')) {
          const yest = new Date();
          yest.setDate(yest.getDate() - 1);
          return formatDate(yest);
        }
        if (curTxt.includes('hôm nay')) {
          return getTodayFormatted();
        }

        const pCur = parseDateFromText(curTxt);
        if (pCur) return pCur;

        if (cur.querySelector) {
          const dateEl = cur.querySelector('.chat-date, .date-separator, [class*="divider-date"], [class*="timeline"], [class*="date"]');
          if (dateEl) {
            const parsed = parseDateFromText(dateEl.innerText || dateEl.textContent || '');
            if (parsed) return parsed;
          }
        }
      }
      cur = cur.previousElementSibling;
      steps++;
    }

    // 2. Nếu không tìm thấy vạch phía trên, kiểm tra xem phía dưới có vạch "Hôm nay" không
    // (Nếu phía dưới có "Hôm nay" thì các tin phía trên vạch đó là "Hôm qua")
    let nextCur = msgCard.nextElementSibling;
    let nextSteps = 0;
    while (nextCur && nextSteps < 100) {
      if (isDateSeparatorElement(nextCur)) {
        const nTxt = (nextCur.innerText || nextCur.textContent || '').trim().toLowerCase();
        if (nTxt.includes('hôm nay')) {
          const yest = new Date();
          yest.setDate(yest.getDate() - 1);
          return formatDate(yest);
        }
        break;
      }
      nextCur = nextCur.nextElementSibling;
      nextSteps++;
    }

    return getTodayFormatted();
  }

  // 1. TÌM TOÀN BỘ CÁC VẠCH NGÀY TRONG KHUNG CHAT (THEO THỨ TỰ TÀI LIỆU DOM)
  function getAllChatDateDividers() {
    const scrollContainer = getChatScrollContainer();
    const candidateEls = Array.from(scrollContainer.querySelectorAll(
      '.chat-date, .date-separator, [class*="divider"], [class*="timeline"], [class*="date"], div, span, p'
    ));

    const dividers = [];

    for (const el of candidateEls) {
      // Bỏ qua các thẻ chứa ảnh, avatar, tên người gửi, hoặc thẻ quá lớn
      if (
        el.clientHeight === 0 ||
        el.querySelector('.avatar, [class*="avatar"], img, [style*="background-image"], .card-sender-name')
      ) {
        continue;
      }

      const raw = (el.innerText || el.textContent || '').trim();
      if (!raw || raw.length > 40) continue;

      const dateStr = parseDateFromText(raw);
      if (dateStr) {
        // Chỉ lấy phần tử lá nhất (leaf node) hoặc phần tử không có con chứa date
        const hasChildWithDate = Array.from(el.children).some(c => parseDateFromText((c.innerText || c.textContent || '').trim()));
        if (!hasChildWithDate) {
          dividers.push({ el, dateStr, text: raw });
        }
      }
    }

    return dividers;
  }

  // 2. LẤY NGÀY CỦA ẢNH DỰA TRÊN VỊ TRÍ SO VỚI CÁC VẠCH NGÀY (CHÍNH XÁC 100%)
  function getPhotoDate(photoEl, dividers, msgCard) {
    if (dividers && dividers.length > 0) {
      // Tìm divider gần nhất nằm PHÍA TRƯỚC photoEl trong cây DOM
      let lastDividerBefore = null;
      for (const d of dividers) {
        const pos = d.el.compareDocumentPosition(photoEl);
        if (pos & Node.DOCUMENT_POSITION_FOLLOWING) {
          lastDividerBefore = d;
        }
      }

      if (lastDividerBefore) {
        return lastDividerBefore.dateStr;
      }

      // Nếu ảnh nằm trước vạch ngày đầu tiên:
      const firstD = dividers[0];
      const lower = firstD.text.toLowerCase();
      if (lower.includes('hôm nay')) {
        const yest = new Date();
        yest.setDate(yest.getDate() - 1);
        return formatDate(yest);
      }
      return firstD.dateStr;
    }

    // Fallback nếu không quét được divider nào: duyệt ngược thẻ cha
    return extractDateFromMessageCard(msgCard);
  }

  function parseDateFromText(txt) {
    if (!txt) return null;
    txt = txt.trim().toLowerCase().replace(/[\u00A0\r\n\t]/g, ' ');
    const today = new Date();
    if (txt.includes('hôm nay')) {
      return formatDate(today);
    }
    if (txt.includes('hôm qua')) {
      const yest = new Date();
      yest.setDate(yest.getDate() - 1);
      return formatDate(yest);
    }

    // Khớp DD/MM/YYYY hoặc DD/MM (VD: "T5 08/10", "T5, 08/10, 2026", "08/10/2026", "8/10")
    const m = txt.match(/(\d{1,2})[\/\-\.](\d{1,2})(?:[,\s\/\-\.]+(\d{2,4}))?/);
    if (m) {
      const d = m[1].padStart(2, '0');
      const mo = m[2].padStart(2, '0');
      let y = String(today.getFullYear());
      if (m[3]) {
        y = m[3].length === 2 ? `20${m[3]}` : m[3];
      }
      return `${d}/${mo}/${y}`;
    }

    return null;
  }

  function formatDate(d) {
    const day = String(d.getDate()).padStart(2, '0');
    const mo = String(d.getMonth() + 1).padStart(2, '0');
    const y = d.getFullYear();
    return `${day}/${mo}/${y}`;
  }

  function getTodayFormatted() {
    return formatDate(new Date());
  }

  function parseDateParts(str) {
    if (!str) return null;
    // Dạng YYYY-MM-DD từ <input type="date">
    if (/^\d{4}-\d{1,2}-\d{1,2}$/.test(str)) {
      const parts = str.split('-');
      return {
        year: parseInt(parts[0], 10),
        month: parseInt(parts[1], 10),
        day: parseInt(parts[2], 10)
      };
    }
    // Dạng DD/MM/YYYY hoặc MM/DD/YYYY (VD: "08/10/2026", "08/10")
    const m = str.match(/(\d{1,2})[\/\-\.](\d{1,2})(?:[,\s\/\-\.]+(\d{2,4}))?/);
    if (m) {
      let y = new Date().getFullYear();
      if (m[3]) {
        y = m[3].length === 2 ? 2000 + parseInt(m[3], 10) : parseInt(m[3], 10);
      }
      return {
        day: parseInt(m[1], 10),
        month: parseInt(m[2], 10),
        year: y
      };
    }
    return null;
  }

  function isDateMatching(photoDate, targetDate) {
    if (!targetDate) return true;
    const pPhoto = parseDateParts(photoDate);
    const pTarget = parseDateParts(targetDate);
    if (!pPhoto || !pTarget) return photoDate === targetDate;

    // So sánh năm
    if (pPhoto.year !== pTarget.year) return false;

    // Khớp chuẩn: Day == Day && Month == Month
    if (pPhoto.day === pTarget.day && pPhoto.month === pTarget.month) return true;

    // Khớp đảo do locale trình duyệt (US MM/DD/YYYY vs VN DD/MM/YYYY)
    if (pPhoto.day === pTarget.month && pPhoto.month === pTarget.day) return true;

    return false;
  }

  function normalizeTargetDate(targetDate) {
    if (!targetDate) return '';
    // Nếu là dạng YYYY-MM-DD từ <input type="date">
    const parts = targetDate.split('-');
    if (parts.length === 3) {
      return `${parts[2].padStart(2, '0')}/${parts[1].padStart(2, '0')}/${parts[0]}`;
    }
    return parseDateFromText(targetDate) || targetDate;
  }

  // 6. QUÉT VÀ NHÓM ẢNH THÀNH PACK CHUẨN XÁC
  function scanAndGroupPacks(filter) {
    const {
      employeeName = '',
      targetDate = '',
      timeGapMinutes = 5,
      useDateFilter = false
    } = filter;

    const scrollContainer = getChatScrollContainer();
    const photoItems = findAllChatPhotos(scrollContainer);
    const dividers = getAllChatDateDividers();

    const rawPhotos = [];
    const seenUrls = new Set();
    const diag = {
      totalCandidates: photoItems.length,
      filteredBySender: 0,
      filteredByDate: 0,
      matched: 0
    };

    photoItems.forEach(({ el, src }, idx) => {
      if (seenUrls.has(src)) return;
      seenUrls.add(src);

      const msgCard = findMessageCard(el);
      let sender = extractSenderFromMessageCard(msgCard, employeeName);
      if (!sender) {
        sender = getActiveConversationName() || 'Nhân viên';
      }

      // Lọc người gửi
      if (!isSenderMatching(sender, employeeName)) {
        diag.filteredBySender++;
        return;
      }

      // Trích xuất ngày gửi dựa trên vạch ngày trong chat
      const dateStr = getPhotoDate(el, dividers, msgCard);

      // Lọc theo ngày nếu người dùng kích hoạt
      if (useDateFilter && targetDate) {
        if (!isDateMatching(dateStr, targetDate)) {
          diag.filteredByDate++;
          return;
        }
      }

      // Trích xuất thời gian (giờ:phút)
      let timeStr = '';
      if (msgCard) {
        timeStr = extractTimeFromElement(msgCard);
      }
      if (!timeStr) {
        timeStr = extractTimeFromElement(el.parentElement) || getCurrentTimeString();
      }

      const minutes = parseTimeToMinutes(timeStr);
      const blockId = msgCard ? (msgCard.id || msgCard.getAttribute('data-id') || `msg_${idx}`) : `img_${idx}`;

      diag.matched++;
      rawPhotos.push({
        blockId: blockId,
        sender: sender,
        date: dateStr,
        timeStr: timeStr,
        minutes: minutes,
        src: src
      });
    });

    // Gom thành PACK theo thời gian
    rawPhotos.sort((a, b) => a.minutes - b.minutes);

    const packs = [];
    let curPack = null;
    let packIdx = 1;

    rawPhotos.forEach((item) => {
      if (!curPack) {
        curPack = createNewPack(packIdx, item);
      } else {
        const diffMinutes = Math.abs(item.minutes - curPack.lastMinutes);
        const isSameBlock = (item.blockId === curPack.lastBlockId);
        const isSameSender = (cleanMemberName(item.sender) === cleanMemberName(curPack.sender));

        if (isSameBlock || (isSameSender && diffMinutes <= timeGapMinutes)) {
          curPack.images.push(item.src);
          curPack.lastMinutes = item.minutes;
          curPack.lastBlockId = item.blockId;
        } else {
          packs.push(curPack);
          packIdx++;
          curPack = createNewPack(packIdx, item);
        }
      }
    });

    if (curPack) {
      packs.push(curPack);
    }

    return {
      activeConversation: getActiveConversationName(),
      totalImages: rawPhotos.length,
      totalPacks: packs.length,
      employeeName: employeeName || 'Tất cả',
      date: targetDate || getTodayFormatted(),
      packs: packs,
      diag: diag
    };
  }


  function createNewPack(idx, item) {
    const cleanSender = cleanMemberName(item.sender);
    const safeSender = cleanSender ? `_${cleanSender.replace(/[^a-zA-Z0-9_\u00C0-\u024F\u1EA0-\u1EF9]/g, '')}` : '';
    return {
      id: idx,
      name: `Pack_${String(idx).padStart(2, '0')}_${item.timeStr.replace(':', 'h')}${safeSender}`,
      time: item.timeStr,
      date: item.date,
      sender: cleanSender || item.sender,
      firstMinutes: item.minutes,
      lastMinutes: item.minutes,
      lastBlockId: item.blockId,
      images: [item.src]
    };
  }

  // Trích xuất giờ:phút từ phần tử tin nhắn Zalo
  function extractTimeFromElement(el) {
    if (!el) return '';

    const timeEl = el.querySelector('.card-time, .msg-info__time, [class*="bubble-time"], [class*="time"], [data-translate-inner*="time"]');
    if (timeEl && timeEl.innerText) {
      const m = timeEl.innerText.match(/(\d{1,2}:\d{2})/);
      if (m) return formatHHMM(m[1]);
    }

    const attrTime = el.getAttribute('data-time') || el.getAttribute('title');
    if (attrTime) {
      const m = attrTime.match(/(\d{1,2}:\d{2})/);
      if (m) return formatHHMM(m[1]);
    }

    const text = el.innerText || '';
    const m = text.match(/\b([01]?\d|2[0-3]):([0-5]\d)\b/);
    if (m) return `${m[1].padStart(2, '0')}:${m[2]}`;

    return '';
  }

  function formatHHMM(str) {
    const parts = str.split(':');
    return `${parts[0].padStart(2, '0')}:${parts[1].padStart(2, '0')}`;
  }

  function getCurrentTimeString() {
    const now = new Date();
    return `${String(now.getHours()).padStart(2, '0')}:${String(now.getMinutes()).padStart(2, '0')}`;
  }

  function cleanZaloImgUrl(url) {
    if (!url) return url;
    try {
      const u = new URL(url);
      if (u.hostname.includes('zadn.vn') || u.hostname.includes('zdn.vn')) {
        u.searchParams.delete('w');
        u.searchParams.delete('h');
        return u.toString();
      }
    } catch (e) {}
    return url;
  }

  function parseTimeToMinutes(tStr) {
    if (!tStr) return 0;
    const parts = tStr.split(':');
    const h = parseInt(parts[0], 10) || 0;
    const m = parseInt(parts[1], 10) || 0;
    return h * 60 + m;
  }

  // TỰ ĐỘNG CUỘN NGƯỢC LÊN ĐỂ TẢI LỊCH SỬ TIN NHẮN CŨ
  async function autoScrollHistory(scrollCount = 8) {
    const scrollEl = getChatScrollContainer();
    if (!scrollEl) return;

    for (let i = 0; i < scrollCount; i++) {
      scrollEl.scrollTop = 0;
      await new Promise(r => setTimeout(r, 650));
    }
  }

  // TẢI FILE ZIP
  async function downloadPacksAsZip(packs, employeeName = 'nhan_vien', date = '') {
    if (!window.JSZip) {
      throw new Error("Thư viện JSZip chưa được tải!");
    }

    const zip = new JSZip();
    const safeEmp = (employeeName || 'nhan_vien').replace(/[^a-zA-Z0-9_\u00C0-\u024F\u1EA0-\u1EF9]/g, '_');
    const safeDate = (date || getTodayString()).replace(/[\/\-\.]/g, '_');
    const rootFolder = zip.folder(`Zalo_${safeEmp}_${safeDate}`);

    let totalImgCount = 0;

    for (const pack of packs) {
      const packFolder = rootFolder.folder(pack.name);
      for (let idx = 0; idx < pack.images.length; idx++) {
        const imgUrl = pack.images[idx];
        const fileName = `anh_${String(idx + 1).padStart(2, '0')}.jpg`;

        try {
          const resp = await fetch(imgUrl, { mode: 'cors' });
          if (resp.ok) {
            const blob = await resp.blob();
            packFolder.file(fileName, blob);
            totalImgCount++;
          }
        } catch (e) {
          console.warn(`Không thể tải ảnh: ${imgUrl}`, e);
        }
      }
    }

    rootFolder.file('metadata_packs.json', JSON.stringify({
      employee: employeeName,
      date: date || getTodayString(),
      totalPacks: packs.length,
      totalImages: totalImgCount,
      packs: packs
    }, null, 2));

    const content = await zip.generateAsync({ type: 'blob' });
    const url = URL.createObjectURL(content);

    const a = document.createElement('a');
    a.href = url;
    a.download = `Zalo_${safeEmp}_${safeDate}_${packs.length}_Packs.zip`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  }
})();
