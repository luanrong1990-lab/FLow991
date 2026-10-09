// background/service_worker.js - VQPVEO3PRO v2.0
// Tham khảo kiến trúc VEO Automation để xử lý download chính xác
console.log("VQPVEO3PRO - Background Service Worker v2.0");

// === DOWNLOAD TRACKING ===
// Mỗi Chrome Profile chạy extension riêng biệt, nên Map này chỉ chứa 1 entry tại 1 thời điểm
const pendingDownloads = new Map(); // tabId -> { seg_id, downloadId? }

chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {
    const tabId = sender.tab?.id;
    const windowId = sender.tab?.windowId;
    
    switch (msg.action) {
        // === WINDOW MANAGEMENT ===
        case 'MINIMIZE_WINDOW':
            if (windowId) chrome.windows.update(windowId, { state: 'minimized' });
            break;
            
        case 'MAXIMIZE_WINDOW':
            if (windowId) chrome.windows.update(windowId, { state: 'maximized', focused: true });
            break;
        
        // === DOWNLOAD: Chuẩn bị tracking trước khi click nút download ===
        case 'PREPARE_DOWNLOAD':
            if (tabId && msg.seg_id) {
                pendingDownloads.set(tabId, { seg_id: msg.seg_id });
                console.log(`📋 Prepared download tracking: ${msg.seg_id} → tab ${tabId}`);
            }
            break;
            
        // === DOWNLOAD: Tải trực tiếp bằng URL (học từ VEO Automation) ===
        case 'DOWNLOAD_IMAGE':
            {
                const { url, seg_id } = msg;
                const ext = (url.match(/\.(png|jpg|jpeg|webp)/i) || [, 'png'])[1];
                const filename = `Flow_Images/${seg_id}.${ext}`;
                
                chrome.downloads.download({
                    url: url,
                    filename: filename,
                    saveAs: false
                }, (downloadId) => {
                    if (chrome.runtime.lastError) {
                        console.error('❌ Direct download failed:', chrome.runtime.lastError.message);
                        sendResponse({ success: false, error: chrome.runtime.lastError.message });
                    } else {
                        console.log(`✅ Direct download started: ${filename} (ID: ${downloadId})`);
                        // Track download for completion notification
                        if (tabId) {
                            pendingDownloads.set(tabId, { seg_id, downloadId });
                        }
                        sendResponse({ success: true, downloadId, filename });
                    }
                });
                return true; // async sendResponse
            }
    }
});

// === DOWNLOAD COMPLETION TRACKING ===
// Khi file tải xong, gửi filepath chính xác về đúng tab đã yêu cầu
chrome.downloads.onChanged.addListener((delta) => {
    if (!delta.state || delta.state.current !== 'complete') return;
    
    chrome.downloads.search({ id: delta.id }, (results) => {
        if (!results || !results.length) return;
        const item = results[0];
        if (!item.filename) return;
        
        // Chỉ xử lý file ảnh
        if (!/\.(jpg|jpeg|png|webp)$/i.test(item.filename)) return;
        
        console.log(`📥 Download completed: ${item.filename} (ID: ${delta.id})`);
        
        // Tìm tab đang chờ download này
        for (const [tabId, pending] of pendingDownloads.entries()) {
            // Match bằng downloadId (direct download) hoặc lấy pending đầu tiên (click download)
            if (pending.downloadId === delta.id || !pending.downloadId) {
                pendingDownloads.delete(tabId);
                console.log(`📨 Sending filepath to tab ${tabId} for ${pending.seg_id}: ${item.filename}`);
                
                chrome.tabs.sendMessage(tabId, {
                    action: 'DOWNLOAD_COMPLETED',
                    seg_id: pending.seg_id,
                    filepath: item.filename
                }).catch(() => {}); // Tab có thể đã đóng
                break;
            }
        }
    });
});

// === FILE RENAMING (Học từ VEO Automation: onDeterminingFilename) ===
// Đổi tên file TRƯỚC KHI Chrome lưu, để file có tên chứa seg_id
try {
    if (chrome.downloads && chrome.downloads.onDeterminingFilename) {
        chrome.downloads.onDeterminingFilename.addListener((downloadItem, suggest) => {
            // Chỉ xử lý file ảnh từ Google
            if (!/\.(jpg|jpeg|png|webp)$/i.test(downloadItem.filename)) return;
            if (!downloadItem.url.includes('google')) return;
            
            // Tìm pending download chưa có downloadId (click-based download)
            for (const [tabId, pending] of pendingDownloads.entries()) {
                if (pending.seg_id && !pending.downloadId) {
                    const ext = downloadItem.filename.split('.').pop();
                    const newFilename = `Flow_Images/${pending.seg_id}.${ext}`;
                    pending.downloadId = downloadItem.id; // Gắn ID để track completion
                    console.log(`✏️ Renamed download: ${downloadItem.filename} → ${newFilename}`);
                    suggest({ filename: newFilename });
                    return;
                }
            }
        });
        console.log("✅ onDeterminingFilename registered successfully");
    }
} catch(e) {
    console.log("⚠️ onDeterminingFilename not available (Chrome 130+), using fallback tracking");
}