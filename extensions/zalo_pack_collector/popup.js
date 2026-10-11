document.addEventListener('DOMContentLoaded', () => {
  const elEmp = document.getElementById('employeeName');
  const elDate = document.getElementById('targetDate');
  const chkDate = document.getElementById('chkDateFilter');
  const elGap = document.getElementById('timeGap');
  const elList = document.getElementById('memberList');
  const btnFetch = document.getElementById('btnFetchMembers');
  const btnScan = document.getElementById('btnScan');
  const btnScroll = document.getElementById('btnScrollUp');
  const btnZip = document.getElementById('btnDownloadZip');
  const msgBox = document.getElementById('statusMessage');
  const resArea = document.getElementById('resultsArea');
  const txtTotalImgs = document.getElementById('txtTotalImages');
  const txtTotalPacks = document.getElementById('txtTotalPacks');
  const btnDateToday = document.getElementById('btnDateToday');
  const btnDateYesterday = document.getElementById('btnDateYesterday');
  const btnDateAll = document.getElementById('btnDateAll');

  // Mặc định ngày hôm nay
  const today = new Date().toISOString().split('T')[0];
  elDate.value = today;

  function setDatePreset(type) {
    const d = new Date();
    if (type === 'today') {
      elDate.value = d.toISOString().split('T')[0];
      if (chkDate) chkDate.checked = true;
      btnDateToday?.classList.add('active');
      btnDateYesterday?.classList.remove('active');
      btnDateAll?.classList.remove('active');
    } else if (type === 'yesterday') {
      d.setDate(d.getDate() - 1);
      elDate.value = d.toISOString().split('T')[0];
      if (chkDate) chkDate.checked = true;
      btnDateToday?.classList.remove('active');
      btnDateYesterday?.classList.add('active');
      btnDateAll?.classList.remove('active');
    } else if (type === 'all') {
      if (chkDate) chkDate.checked = false;
      btnDateToday?.classList.remove('active');
      btnDateYesterday?.classList.remove('active');
      btnDateAll?.classList.add('active');
    }
  }

  btnDateToday?.addEventListener('click', () => setDatePreset('today'));
  btnDateYesterday?.addEventListener('click', () => setDatePreset('yesterday'));
  btnDateAll?.addEventListener('click', () => setDatePreset('all'));

  elDate?.addEventListener('change', () => {
    btnDateToday?.classList.remove('active');
    btnDateYesterday?.classList.remove('active');
    btnDateAll?.classList.remove('active');
  });

  chkDate?.addEventListener('change', () => {
    if (!chkDate.checked) {
      btnDateToday?.classList.remove('active');
      btnDateYesterday?.classList.remove('active');
      btnDateAll?.classList.add('active');
    } else {
      btnDateAll?.classList.remove('active');
    }
  });

  let currentScanResult = null;

  function showStatus(text, isError = false) {
    msgBox.textContent = text;
    msgBox.classList.remove('hidden');
    msgBox.style.background = isError ? '#fef2f2' : '#eff6ff';
    msgBox.style.color = isError ? '#991b1b' : '#1e40af';
    msgBox.style.borderColor = isError ? '#fecaca' : '#bfdbfe';
  }

  function hideStatus() {
    msgBox.classList.add('hidden');
  }

  async function getActiveZaloTab() {
    const tabs = await chrome.tabs.query({ active: true, currentWindow: true });
    if (!tabs || tabs.length === 0) return null;
    const tab = tabs[0];
    if (tab.url && tab.url.includes('chat.zalo.me')) {
      return tab;
    }
    return null;
  }

  // Tự động quét tên thành viên khi mở popup
  async function fetchMembers() {
    const tab = await getActiveZaloTab();
    if (!tab) {
      showStatus("Vui lòng mở trang chat.zalo.me trước khi dùng tiện ích!", true);
      return;
    }

    chrome.tabs.sendMessage(tab.id, { action: "GET_CHAT_MEMBERS" }, (resp) => {
      if (chrome.runtime.lastError) {
        showStatus("Chưa kết nối được với Zalo Web. Hãy F5 tải lại tab Zalo!", true);
        return;
      }
      elList.innerHTML = '';

      // Tùy chọn 1: Tất cả thành viên
      const optAll = document.createElement('option');
      optAll.value = 'Tất cả (Mọi người)';
      elList.appendChild(optAll);

      if (resp && resp.members && resp.members.length > 0) {
        resp.members.forEach(m => {
          const opt = document.createElement('option');
          opt.value = m;
          elList.appendChild(opt);
        });
        const totalStr = resp.targetCount ? `${resp.members.length}/${resp.targetCount}` : `${resp.members.length}`;
        elEmp.placeholder = `Tất cả hoặc bấm chọn (${totalStr} thành viên)...`;
        showStatus(`Đã tìm thấy ${totalStr} thành viên trong nhóm. Bấm mũi tên để chọn!`);
      } else {
        elEmp.placeholder = "Tất cả (Mọi người) hoặc tự gõ tên...";
        showStatus("Đang ở chế độ 'Tất cả (Mọi người)'. Bạn có thể tự gõ tên cụ thể.");
      }
    });
  }

  // Tự động xóa chữ khi click vào để hiện toàn bộ danh sách dropdown
  elEmp.addEventListener('focus', () => {
    if (elEmp.value === 'Tất cả (Mọi người)') {
      elEmp.value = '';
    }
  });

  btnFetch.addEventListener('click', () => {
    elEmp.value = '';
    fetchMembers();
  });
  fetchMembers();

  // Bấm Quét & Chia Pack
  btnScan.addEventListener('click', async () => {
    hideStatus();
    const tab = await getActiveZaloTab();
    if (!tab) {
      showStatus("Vui lòng mở trang chat.zalo.me!", true);
      return;
    }

    const empName = elEmp.value.trim();
    const targetDate = elDate.value; // YYYY-MM-DD
    const gap = parseInt(elGap.value, 10) || 5;
    const useDate = chkDate ? chkDate.checked : false;

    btnScan.disabled = true;
    btnScan.textContent = "Đang quét...";

    chrome.tabs.sendMessage(tab.id, {
      action: "SCAN_IMAGES",
      filter: {
        employeeName: empName,
        targetDate: targetDate,
        timeGapMinutes: gap,
        useDateFilter: useDate
      }
    }, (resp) => {
      btnScan.disabled = false;
      btnScan.textContent = "Quét & Chia Pack";

      if (chrome.runtime.lastError) {
        showStatus("Lỗi kết nối tới tab Zalo. Hãy tải lại trang Zalo (F5)!", true);
        return;
      }

      if (resp && resp.success && resp.result) {
        currentScanResult = resp.result;
        renderResults(resp.result);
      } else {
        showStatus("Không tìm thấy ảnh nào khớp với bộ lọc!", true);
      }
    });
  });

  // Nút Cuộn lấy tin cũ
  btnScroll.addEventListener('click', async () => {
    const tab = await getActiveZaloTab();
    if (!tab) {
      showStatus("Vui lòng mở trang chat.zalo.me!", true);
      return;
    }
    btnScroll.disabled = true;
    btnScroll.textContent = "Đang cuộn...";
    showStatus("Đang tự động cuộn lên để Zalo nạp tin nhắn cũ...");

    chrome.tabs.sendMessage(tab.id, { action: "AUTO_SCROLL_UP", times: 8 }, (resp) => {
      btnScroll.disabled = false;
      btnScroll.textContent = "Cuộn lấy tin cũ";
      showStatus("Đã cuộn xong lịch sử. Bấm 'Quét & Chia Pack' để cập nhật!");
    });
  });

  // Hiển thị danh sách Pack
  function renderResults(res) {
    txtTotalImgs.textContent = res.totalImages;
    txtTotalPacks.textContent = res.totalPacks;
    packsList.innerHTML = '';

    if (res.packs.length === 0) {
      let msg = "Không tìm thấy ảnh nào phù hợp!";
      if (res.diag && res.diag.totalCandidates > 0) {
        msg = `Tìm thấy ${res.diag.totalCandidates} ảnh trong chat, nhưng: `;
        const reasons = [];
        if (res.diag.filteredBySender > 0) {
          reasons.push(`${res.diag.filteredBySender} ảnh người gửi không khớp '${res.employeeName}'`);
        }
        if (res.diag.filteredByDate > 0) {
          reasons.push(`${res.diag.filteredByDate} ảnh khác ngày chọn`);
        }
        msg += reasons.join(', ') + ". ";
        msg += "Mẹo: Thử bấm nút 'Tất cả ngày' hoặc chọn 'Tất cả (Mọi người)'.";
      } else {
        msg = "Chưa tìm thấy ảnh nào trong khung chat. Mẹo: Hãy bấm 'Cuộn lấy tin cũ' để Zalo tải thêm ảnh, hoặc chọn 'Tất cả ngày'.";
      }
      showStatus(msg, true);
      resArea.classList.add('hidden');
      return;
    }

    resArea.classList.remove('hidden');

    res.packs.forEach((p) => {
      const card = document.createElement('div');
      card.className = 'pack-card';

      const top = document.createElement('div');
      top.className = 'pack-card-top';

      const title = document.createElement('span');
      title.className = 'pack-title';
      const senderDisplay = p.sender || 'Nhân viên';
      const timeDisplay = (p.time || '').replace(':', 'h');
      title.textContent = `Pack ${p.id}: [${senderDisplay}] • [${p.images.length} ảnh] • [${timeDisplay}]`;

      const timeBadge = document.createElement('span');
      timeBadge.className = 'pack-time-badge';
      timeBadge.textContent = `${p.time} • ${p.date || 'Hôm nay'}`;

      top.appendChild(title);
      top.appendChild(timeBadge);
      card.appendChild(top);

      const thumbs = document.createElement('div');
      thumbs.className = 'pack-thumbs';
      p.images.forEach(imgUrl => {
        const img = document.createElement('img');
        img.className = 'pack-thumb-img';
        img.src = imgUrl;
        img.title = "Click để xem";
        img.onclick = () => window.open(imgUrl, '_blank');
        thumbs.appendChild(img);
      });
      card.appendChild(thumbs);

      packsList.appendChild(card);
    });
  }

  // Tải file ZIP
  btnZip.addEventListener('click', async () => {
    if (!currentScanResult || !currentScanResult.packs || currentScanResult.packs.length === 0) {
      showStatus("Chưa có danh sách pack nào để tải!", true);
      return;
    }

    const tab = await getActiveZaloTab();
    if (!tab) {
      showStatus("Vui lòng giữ mở tab chat.zalo.me để tải ảnh!", true);
      return;
    }

    btnZip.disabled = true;
    btnZip.textContent = "Đang nén ZIP...";
    showStatus("Đang tải từng ảnh từ Zalo và nén vào file ZIP...");

    chrome.tabs.sendMessage(tab.id, {
      action: "DOWNLOAD_ZIP",
      packs: currentScanResult.packs,
      employeeName: currentScanResult.employeeName,
      date: currentScanResult.date
    }, (resp) => {
      btnZip.disabled = false;
      btnZip.textContent = "Tải file ZIP";
      if (resp && resp.success) {
        showStatus("Đã tải xong file ZIP về máy của bạn!");
      } else {
        showStatus("Lỗi khi tải hoặc nén ZIP: " + (resp ? resp.error : "Không rõ lỗi"), true);
      }
    });
  });
});
