// content/flow_controller.js
console.log("VQPVEO3PRO - Flow Content Script đã được tiêm (injected).");

// Helpers
const sleep = ms => new Promise(r => setTimeout(r, ms));

// Lấy CSS path chuẩn xác (loại bỏ các ID động của Angular)
function getCssSelector(el) {
    if (!(el instanceof Element)) return;
    const path = [];
    while (el.nodeType === Node.ELEMENT_NODE) {
        let selector = el.nodeName.toLowerCase();
        // Bỏ qua các ID động của Angular Material
        if (el.id && !el.id.match(/mat-|cdk-|aria-/i)) {
            selector += '#' + el.id;
            path.unshift(selector);
            break;
        } else {
            let sib = el, nth = 1;
            while (sib = sib.previousElementSibling) {
                if (sib.nodeName.toLowerCase() == selector) nth++;
            }
            if (nth != 1) selector += `:nth-of-type(${nth})`;
        }
        path.unshift(selector);
        el = el.parentNode;
    }
    return path.join(' > ');
}

// Cấu trúc lưu trữ chi tiết
let vqConfig = {
    project: null,
    ratio: null,
    model: null,
    prompt: null,
    generate: null,
    menu_download: null,
    hover_download: null,
    download_normal: null,
    download_hd: null,
    custom_clicks: [],
    wait_time: 40 // Mặc định đợi 40 giây
};

let recordingMode = 'NONE'; // Chứa ID của nút đang record

// Khôi phục cấu hình từ bộ nhớ
let isPanelMinimized = false;

chrome.storage.local.get(['vqConfig'], (result) => {
    if (result.vqConfig) {
        vqConfig = Object.assign(vqConfig, result.vqConfig);
        if (!vqConfig.custom_clicks) vqConfig.custom_clicks = [];
        if (!vqConfig.wait_time) vqConfig.wait_time = 40;
        if (typeof vqConfig.use_hd === 'undefined') vqConfig.use_hd = true; // Bật tải HD mặc định
        
        // Nếu đã cấu hình ít nhất prompt và generate, tự động ẩn giao diện
        if (vqConfig.prompt && vqConfig.generate) {
            isPanelMinimized = true;
        }
    }
});

function renderPanel() {
    let panel = document.getElementById('vq-panel');
    if (!panel) {
        panel = document.createElement('div');
        panel.id = 'vq-panel';
        document.body.appendChild(panel);
    }
    
    if (isPanelMinimized) {
        panel.innerHTML = `
            <div id="btn-maximize" style="position:fixed; bottom:20px; right:20px; z-index:999999; background:#3b82f6; color:white; padding:10px 15px; border-radius:20px; cursor:pointer; font-weight:bold; box-shadow:0 4px 10px rgba(0,0,0,0.5); font-family:sans-serif;">
                ⚙️ VQPVEO3PRO (Sẵn sàng)
            </div>
        `;
        document.getElementById('btn-maximize').onclick = () => {
            isPanelMinimized = false;
            renderPanel();
        };
        return;
    }

    const getStatus = (key) => vqConfig[key] ? '✅' : '❌';
    
    panel.innerHTML = `
        <div style="padding:15px; background:#1e293b; color:white; border-radius:8px; border:2px solid #3b82f6; position:fixed; bottom:20px; right:20px; z-index:999999; font-family:sans-serif; width:300px; box-shadow: 0 10px 25px rgba(0,0,0,0.8); max-height: 80vh; overflow-y: auto;">
            <div style="display:flex; justify-content:space-between; align-items:center; border-bottom:1px solid #475569; margin-bottom:10px; padding-bottom:5px;">
                <h3 style="margin:0; font-size:15px; color:#f59e0b;">CẤU HÌNH GOOGLE FLOW</h3>
                <button id="btn-minimize" style="background:none; border:none; color:white; cursor:pointer; font-size:16px;" title="Thu nhỏ">➖</button>
            </div>
            
            <div style="font-size:12px; margin-bottom:10px; color:#9ca3af;">Click vào nút bên dưới, sau đó giữ phím <b>ALT + Click</b> vào phần tử trên trang để ghi nhớ. (Click thường để mở menu)</div>
            
            <button id="btn-project" class="vq-btn" style="width:100%; margin-bottom:5px; padding:6px; background:#475569; color:white; border:none; border-radius:4px; cursor:pointer; text-align:left;">
                ${getStatus('project')} 1. Nút Tạo Project mới
            </button>
            <button id="btn-ratio" class="vq-btn" style="width:100%; margin-bottom:5px; padding:6px; background:#475569; color:white; border:none; border-radius:4px; cursor:pointer; text-align:left;">
                ${getStatus('ratio')} 2. Nút Chọn Tỷ lệ
            </button>
            <button id="btn-model" class="vq-btn" style="width:100%; margin-bottom:5px; padding:6px; background:#475569; color:white; border:none; border-radius:4px; cursor:pointer; text-align:left;">
                ${getStatus('model')} 3. Nút Chọn Model
            </button>
            <button id="btn-prompt" class="vq-btn" style="width:100%; margin-bottom:5px; padding:6px; background:#475569; color:white; border:none; border-radius:4px; cursor:pointer; text-align:left;">
                ${getStatus('prompt')} 4. Ô Điền Prompt
            </button>
            <button id="btn-generate" class="vq-btn" style="width:100%; margin-bottom:5px; padding:6px; background:#475569; color:white; border:none; border-radius:4px; cursor:pointer; text-align:left;">
                ${getStatus('generate')} 5. Nút Tạo Hình Ảnh
            </button>
            
            <div style="margin-top:10px; margin-bottom:10px; font-size:12px; background:#334155; padding:5px; border-radius:4px; display:flex; justify-content:space-between; align-items:center;">
                <label style="color:white;">⏳ Đợi sinh ảnh (giây):</label>
                <input type="number" id="inp-wait-time" value="${vqConfig.wait_time}" style="width:50px; padding:2px; border-radius:3px; border:1px solid #64748b; background:#0f172a; color:white; text-align:center;">
            </div>

            <div style="border-top:1px solid #475569; margin:10px 0; padding-top:5px; color:#f59e0b; font-size:11px; text-align:center;">--- Thao tác khi tải ảnh ---</div>
            <button id="btn-menu_download" class="vq-btn" style="width:100%; margin-bottom:5px; padding:6px; background:#475569; color:white; border:none; border-radius:4px; cursor:pointer; text-align:left;">
                ${getStatus('menu_download')} 6. Nút Dấu 3 chấm (Nếu có)
            </button>
            <button id="btn-hover_download" class="vq-btn" style="width:100%; margin-bottom:5px; padding:6px; background:#475569; color:white; border:none; border-radius:4px; cursor:pointer; text-align:left;">
                ${getStatus('hover_download')} 7. Hover chữ "Tải xuống"
            </button>
            
            <div style="margin-bottom:10px; padding:8px; background:#334155; border-radius:4px;">
                <label style="color:white; font-size:12px; display:flex; align-items:center; cursor:pointer;">
                    <input type="checkbox" id="chk-use-hd" style="margin-right:8px;" ${vqConfig.use_hd ? 'checked' : ''}>
                    Ưu tiên tải Ảnh HD (Nếu tắt sẽ tải Thường)
                </label>
            </div>

            <button id="btn-download_normal" class="vq-btn" style="width:100%; margin-bottom:5px; padding:6px; background:#475569; color:white; border:none; border-radius:4px; cursor:pointer; text-align:left; opacity: ${vqConfig.use_hd ? '0.5' : '1'};">
                ${getStatus('download_normal')} 8. Nút Tải Ảnh Thường (1K)
            </button>
            <button id="btn-download_hd" class="vq-btn" style="width:100%; margin-bottom:10px; padding:6px; background:#475569; color:white; border:none; border-radius:4px; cursor:pointer; text-align:left; opacity: ${vqConfig.use_hd ? '1' : '0.5'};">
                ${getStatus('download_hd')} 9. Nút Tải Ảnh HD (2K/4K)
            </button>
            
            <div style="border-top:1px solid #475569; margin-top:10px; padding-top:10px;">
                <button id="btn-custom_clicks" class="vq-btn" style="width:100%; margin-bottom:10px; padding:6px; background:#6366f1; color:white; border:none; border-radius:4px; cursor:pointer;">
                    + Thêm Thao Tác Click Phụ (${vqConfig.custom_clicks.length})
                </button>
            </div>
            
            <div id="vq-status" style="font-size:12px; color:#fbbf24; margin-bottom:10px; min-height:35px; text-align:center; font-weight:bold;">Sẵn sàng.</div>
            
            <button id="btn-clear" style="width:100%; padding:6px; background:#ef4444; color:white; border:none; border-radius:4px; font-weight:bold; cursor:pointer;">XÓA TẤT CẢ</button>
        </div>
    `;

    const setMode = (mode, text) => {
        if (recordingMode !== 'NONE') return;
        recordingMode = mode;
        document.getElementById('vq-status').innerText = "Đang chờ: Giữ phím ALT + CLICK vào " + text + "...";
        document.getElementById('btn-' + mode).style.backgroundColor = '#fbbf24';
    };

    document.getElementById('btn-minimize').onclick = () => {
        isPanelMinimized = true;
        renderPanel();
    };

    document.getElementById('inp-wait-time').addEventListener('change', (e) => {
        vqConfig.wait_time = parseInt(e.target.value) || 40;
        saveConfig();
    });

    document.getElementById('chk-use-hd').addEventListener('change', (e) => {
        vqConfig.use_hd = e.target.checked;
        saveConfig();
        renderPanel();
    });

    document.getElementById('btn-project').onclick = () => setMode('project', 'Tạo Project');
    document.getElementById('btn-ratio').onclick = () => setMode('ratio', 'Chọn Tỷ lệ');
    document.getElementById('btn-model').onclick = () => setMode('model', 'Chọn Model');
    document.getElementById('btn-prompt').onclick = () => setMode('prompt', 'Ô Nhập chữ');
    document.getElementById('btn-generate').onclick = () => setMode('generate', 'Nút Tạo ảnh');
    document.getElementById('btn-menu_download').onclick = () => setMode('menu_download', 'Dấu 3 chấm');
    document.getElementById('btn-hover_download').onclick = () => setMode('hover_download', 'Chữ Tải xuống');
    document.getElementById('btn-download_normal').onclick = () => setMode('download_normal', 'Tải ảnh 1K');
    document.getElementById('btn-download_hd').onclick = () => setMode('download_hd', 'Tải ảnh HD');
    document.getElementById('btn-custom_clicks').onclick = () => setMode('custom_clicks', 'Click phụ (ESC để dừng)');
    
    document.getElementById('btn-clear').onclick = () => {
        if(confirm("Bạn có chắc chắn muốn xóa toàn bộ cấu hình?")) {
            vqConfig = { project: null, ratio: null, model: null, prompt: null, generate: null, menu_download: null, hover_download: null, download_normal: null, download_hd: null, custom_clicks: [], wait_time: 40 };
            saveConfig();
            renderPanel();
        }
    };
}

function injectVQPanel() {
    renderPanel();
}

// Bơm giao diện ngay khi trang load xong
if (document.readyState === 'complete') {
    injectVQPanel();
} else {
    window.addEventListener('load', injectVQPanel);
}

// Lắng nghe phím ESC để hủy
document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape' && recordingMode !== 'NONE') {
        recordingMode = 'NONE';
        renderPanel();
    }
});

function saveConfig() {
    chrome.storage.local.set({ vqConfig });
    if (socket && socket.readyState === WebSocket.OPEN) {
        socket.send(JSON.stringify({ type: 'SAVE_CONFIG', config: vqConfig }));
    }
}

// Lắng nghe Click với phím ALT để record
document.addEventListener('click', (e) => {
    if (recordingMode === 'NONE') return;

    if (!e.altKey) {
        return;
    }

    e.preventDefault();
    e.stopPropagation();
    
    const selector = getCssSelector(e.target);
    const elementText = e.target.innerText.substring(0, 30).trim() || e.target.tagName;
    
    // Hiệu ứng nháy nháy
    const originalOutline = e.target.style.outline;
    e.target.style.outline = "3px solid red";
    
    setTimeout(() => {
        const isOk = window.confirm(`Bạn có muốn lưu thao tác:\nClick vào nút [ ${elementText} ] không?`);
        e.target.style.outline = originalOutline;
        
        if (isOk) {
            if (recordingMode === 'custom_clicks') {
                vqConfig.custom_clicks.push(selector);
                saveConfig();
                renderPanel();
                document.getElementById('vq-status').innerText = `Đã lưu thao tác phụ (${vqConfig.custom_clicks.length}). Giữ ALT + CLICK tiếp hoặc ESC để dừng.`;
            } else {
                vqConfig[recordingMode] = selector;
                saveConfig();
                recordingMode = 'NONE';
                renderPanel();
            }
        }
    }, 50);
}, true);

let socket = null;
let reconnectInterval = 3000;

function connectWebSocket() {
    if (socket) {
        socket.close();
    }
    
    console.log("Đang kết nối tới Local Bridge từ trang web...");
    socket = new WebSocket('ws://127.0.0.1:8765');
    
    socket.onopen = () => {
        console.log("Đã kết nối thành công với Local Bridge.");
        chrome.storage.local.set({ bridge_status: 'connected' });
        
        // Ẩn trình duyệt ngay khi kết nối (chạy nền)
        try { chrome.runtime.sendMessage({ action: 'MINIMIZE_WINDOW' }); } catch(e) {}
        
        socket.send(JSON.stringify({
            type: 'HANDSHAKE',
            client: 'flow_content_script',
            version: '1.0'
        }));
        
        // Yêu cầu tải cấu hình toàn cục từ Python Desktop
        socket.send(JSON.stringify({ type: 'GET_CONFIG' }));
    };
    
    socket.onmessage = async (event) => {
        try {
            const data = JSON.parse(event.data);
            console.log("Nhận lệnh từ Desktop App:", data);
            
            if (data.type === 'PING') {
                socket.send(JSON.stringify({ type: 'PONG' }));
            }
            else if (data.type === 'LOAD_CONFIG' && data.config) {
                console.log("Đã đồng bộ cấu hình từ Desktop App", data.config);
                vqConfig = Object.assign(vqConfig, data.config);
                chrome.storage.local.set({ vqConfig });
                if (vqConfig.prompt && vqConfig.generate) {
                    isPanelMinimized = true;
                }
                renderPanel();
            }
            else if (data.type === 'GENERATE_IMAGE') {
                await handleGenerateImage(data);
            }
        } catch (e) {
            console.error("Lỗi khi xử lý tin nhắn:", e);
        }
    };
    
    socket.onclose = () => {
        console.log("Mất kết nối Local Bridge. Thử lại sau 3s...");
        chrome.storage.local.set({ bridge_status: 'disconnected' });
        setTimeout(connectWebSocket, reconnectInterval);
    };
    
    socket.onerror = (err) => {
        console.error("Lỗi WebSocket:", err);
    };
}

async function handleGenerateImage(payload) {
    try {
        // Ẩn trình duyệt khi bắt đầu chạy macro
        try { chrome.runtime.sendMessage({ action: 'MINIMIZE_WINDOW' }); } catch(e) {}
        
        const promptText = typeof payload === 'string' ? payload : payload.prompt;
        const seg_id = payload.seg_id || 'unknown';
        console.log(`Bắt đầu chạy Macro cho phân đoạn: ${seg_id}`);
        
        const clickSelector = async (selector, delay = 500) => {
            if (!selector) return;
            const el = document.querySelector(selector);
            if (el) {
                try {
                    el.click();
                } catch (e) {
                    try {
                        // Fallback: dispatch custom MouseEvent if click() fails
                        el.dispatchEvent(new MouseEvent('click', {
                            view: window,
                            bubbles: true,
                            cancelable: true
                        }));
                    } catch (e2) {
                        console.warn("Lỗi click phần tử:", selector, e2);
                    }
                }
                await sleep(delay);
            } else {
                console.warn("Không tìm thấy phần tử (bỏ qua):", selector);
            }
        };

const getVisibleElement = (selector) => {
            if (!selector) return null;
            // 1. Loại bỏ các ID động của Angular (mat-menu-panel-13, cdk-overlay-2...)
            let safeSelector = selector.replace(/#mat-menu-panel-\d+/g, '');
            safeSelector = safeSelector.replace(/#cdk-overlay-\d+/g, '');
            
            try {
                // 2. Thử tìm chính xác (nhưng đã bỏ ID động)
                let els = Array.from(document.querySelectorAll(safeSelector));
                let visibleEls = els.filter(e => e.offsetWidth > 0 || e.offsetHeight > 0 || e.getClientRects().length > 0);
                if (visibleEls.length > 0) return visibleEls[0];

                // 3. Fallback: Bỏ qua nth-of-type cứng nhắc (rất hiệu quả với danh sách ảnh bị đẩy lùi)
                let fuzzySelector = safeSelector.replace(/:nth-of-type\(\d+\)/g, '');
                els = Array.from(document.querySelectorAll(fuzzySelector));
                visibleEls = els.filter(e => e.offsetWidth > 0 || e.offsetHeight > 0 || e.getClientRects().length > 0);
                if (visibleEls.length > 0) {
                    return visibleEls[0]; 
                }
            } catch (err) {
                console.warn("Lỗi phân tích selector:", err);
            }
            return null;
        };
        
        const smartClickText = async (text, maxWait = 5000) => {
            if (!text || text === 'default' || text === 'Mặc định') return true;
            console.log(`Đang tìm chữ [${text}] để bấm...`);
            const start = Date.now();
            while (Date.now() - start < maxWait) {
                // Sử dụng XPath để tìm phần tử chứa text chính xác
                const xpath = `//span[normalize-space(text())='${text}'] | //div[normalize-space(text())='${text}'] | //button[normalize-space(text())='${text}']`;
                const iterator = document.evaluate(xpath, document, null, XPathResult.ORDERED_NODE_ITERATOR_TYPE, null);
                let el = iterator.iterateNext();
                
                while (el) {
                    if (el.offsetWidth > 0 || el.offsetHeight > 0 || el.getClientRects().length > 0) {
                        try { el.click(); } catch(e) {
                            el.dispatchEvent(new MouseEvent('click', { bubbles: true, cancelable: true }));
                        }
                        console.log(`Đã bấm thành công vào chữ: ${text}`);
                        return true;
                    }
                    el = iterator.iterateNext();
                }
                await sleep(500);
            }
            console.warn(`Không tìm thấy tùy chọn có chữ: ${text}`);
            return false;
        };

        const smartClick = async (selector, maxWait = 25000) => {
            if (!selector) return false;
            console.log(`Đang chờ phần tử [${selector}] xuất hiện (tối đa ${maxWait}ms)...`);
            const start = Date.now();
            while (Date.now() - start < maxWait) {
                let el = getVisibleElement(selector);

                if (el) {
                    try { el.click(); } catch(e) {
                        el.dispatchEvent(new MouseEvent('click', { bubbles: true, cancelable: true }));
                    }
                    console.log(`Đã click thành công: ${selector}`);
                    return true;
                }
                await sleep(1000);
            }
            console.warn(`Timeout: Không tìm thấy nút [${selector}]`);
            throw new Error("UI bị thay đổi hoặc Timeout: Không tìm thấy nút - " + selector);
        };

        const smartHover = async (selector, maxWait = 10000) => {
            if (!selector) return false;
            console.log(`Đang chờ để hover: [${selector}]...`);
            const start = Date.now();
            while (Date.now() - start < maxWait) {
                let el = getVisibleElement(selector);
                
                if (el) {
                    el.dispatchEvent(new MouseEvent('mouseover', { view: window, bubbles: true, cancelable: true }));
                    el.dispatchEvent(new MouseEvent('mouseenter', { view: window, bubbles: true, cancelable: true }));
                    el.dispatchEvent(new MouseEvent('mousemove', { view: window, bubbles: true, cancelable: true }));
                    try { el.click(); } catch(e) {}
                    console.log(`Đã hover thành công: ${selector}`);
                    return true;
                }
                await sleep(1000);
            }
            return false;
        };

        // Chờ trang web tải xong (Chờ TextArea hoặc nút Project xuất hiện, tối đa 15 giây)
        console.log("Đợi trang web tải giao diện...");
        for (let i = 0; i < 15; i++) {
            let found = document.querySelector('textarea');
            if (vqConfig.project && getVisibleElement(vqConfig.project)) found = true;
            if (found) break;
            await sleep(1000);
        }

        // 1. Nếu không thấy TextArea (đang ở trang chủ), cố gắng click Tạo Project
        if (!document.querySelector('textarea')) {
            console.log("Không thấy TextArea, thử click Tạo Dự Án Mới...");
            if (vqConfig.project) {
                await clickSelector(vqConfig.project, 1000);
            }
            // Fallback bấm theo chữ nếu config bị sai selector
            try { await smartClickText("+ Dự án mới", 1000); } catch(e) {}
            try { await smartClickText("Dự án mới", 1000); } catch(e) {}
            try { await smartClickText("New project", 1000); } catch(e) {}
        }
        
        // 2. Chờ và tìm ô nhập Prompt (Đảm bảo Workspace đã load xong)
        let promptInput = null;
        console.log("Đang tìm ô nhập Prompt...");
        for (let attempt = 0; attempt < 25; attempt++) {
            if (vqConfig.prompt) {
                promptInput = document.querySelector(vqConfig.prompt);
            }
            
            if (!promptInput) {
                let textareas = Array.from(document.querySelectorAll('textarea'));
                promptInput = textareas.find(ta => 
                    (ta.getAttribute('placeholder') || '').toLowerCase().includes('tạo những gì') ||
                    (ta.getAttribute('placeholder') || '').toLowerCase().includes('prompt') ||
                    (ta.getAttribute('aria-label') || '').toLowerCase().includes('prompt')
                );
                if (!promptInput) {
                    promptInput = textareas.find(ta => ta.offsetParent !== null && window.getComputedStyle(ta).visibility === 'visible');
                }
            }
            
            if (promptInput) {
                break;
            }
            await sleep(1000); // Chờ 1 giây rồi thử lại
        }

        if (!promptInput) {
            throw new Error("Không tìm thấy ô nhập chữ (TextArea) trên trang web này. (Đã chờ 25s)");
        }
        
        // 3. Setup các thông số (Tỉ lệ, Model, Số lượng ảnh) - Giờ workspace chắc chắn đã render!
        await clickSelector(vqConfig.ratio, 500);
        if (payload.ratio) await smartClickText(payload.ratio, 3000);
        else await sleep(500);
        
        await clickSelector(vqConfig.model, 500);
        if (payload.model) await smartClickText(payload.model, 3000);
        else await sleep(500);
        
        if (vqConfig.num_images) {
            await clickSelector(vqConfig.num_images, 500);
            if (payload.num_images) await smartClickText(payload.num_images, 3000);
            else await sleep(500);
        }
        
        if (vqConfig.custom_clicks && vqConfig.custom_clicks.length > 0) {
            for (let i = 0; i < vqConfig.custom_clicks.length; i++) {
                await clickSelector(vqConfig.custom_clicks[i], 500);
            }
        }

        // Gửi phím Escape để đóng tất cả các popup/menu đang mở
        document.body.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', bubbles: true, cancelable: true }));
        await sleep(300);

        // 4. Điền Prompt và Tạo ảnh

        try {
            promptInput.focus();
            promptInput.click();
            await sleep(200);

            if (typeof promptInput.select === 'function') {
                try { promptInput.select(); } catch(e) {}
            }
            
            // Cách 1: Gán value trực tiếp
            try { promptInput.value = promptText; } catch(e) {}
            try { promptInput.innerText = promptText; } catch(e) {}
            
            // Cách 2: execCommand
            try { document.execCommand('insertText', false, promptText); } catch(e) {}

            // Cách 3: Native Setter (Angular/React)
            try {
                const tagName = promptInput.tagName.toLowerCase();
                if (tagName === 'textarea') {
                    const nativeSetter = Object.getOwnPropertyDescriptor(window.HTMLTextAreaElement.prototype, "value")?.set;
                    if (nativeSetter) nativeSetter.call(promptInput, promptText);
                } else if (tagName === 'input') {
                    const nativeSetter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, "value")?.set;
                    if (nativeSetter) nativeSetter.call(promptInput, promptText);
                }
            } catch(e) {
                console.warn("Native setter failed", e);
            }

            // Kích hoạt Event
            promptInput.dispatchEvent(new Event('input', { bubbles: true, cancelable: true }));
            promptInput.dispatchEvent(new Event('change', { bubbles: true, cancelable: true }));
            promptInput.dispatchEvent(new KeyboardEvent('keyup', { key: ' ', bubbles: true }));
            
        } catch (injectionError) {
            console.error("Lỗi khi điền text:", injectionError);
            // Dù lỗi điền text cũng ráng đi tiếp
        }

        await sleep(500);

        // 3. Bấm Tạo Ảnh
        let genButton = null;
        if (vqConfig.generate) {
            genButton = document.querySelector(vqConfig.generate);
        }
        
        if (!genButton) {
            const buttons = Array.from(document.querySelectorAll('button, div[role="button"]'));
            genButton = buttons.find(b => {
                const txt = b.innerText.toLowerCase();
                return txt.includes('generate') || txt.includes('tạo') || txt.includes('create') || txt.includes('submit');
            });

            if (!genButton) {
                genButton = document.querySelector('button[aria-label*="generate" i], button[aria-label*="create" i], button[aria-label*="gửi" i], button[aria-label*="send" i], button[aria-label*="tạo" i], button svg');
                if (genButton && genButton.tagName.toLowerCase() === 'svg') {
                    genButton = genButton.closest('button, div[role="button"]');
                }
            }
        }

        if (!genButton) {
            throw new Error("Không tìm thấy nút Tạo ảnh/Gửi (Generate/Send).");
        }

        try { genButton.click(); } catch (e) {
            genButton.dispatchEvent(new MouseEvent('click', { bubbles: true, cancelable: true }));
        }

        

        // --- CHỜ ẢNH HOÀN THÀNH ---
        const waitTimeMs = (vqConfig.wait_time || 40) * 1000;
        console.log(`Đã bấm Tạo, chờ ${waitTimeMs}ms để Google Flow render xong ảnh...`);
        await sleep(waitTimeMs); 

        // === PHƯƠNG ÁN 1: Tải trực tiếp bằng URL (Học từ VEO Automation) ===
        // Tìm ảnh vừa tạo trong DOM và tải bằng chrome.downloads API
        let directDownloadSuccess = false;
        try {
            // Tìm ảnh mới nhất trong khu vực kết quả
            const allImages = Array.from(document.querySelectorAll('img'));
            const resultImages = allImages.filter(img => {
                const src = img.src || '';
                return (src.includes('googleusercontent') || src.includes('ggpht') || src.includes('lh3.google')) 
                    && img.offsetWidth > 100 && img.offsetHeight > 100;
            });
            
            if (resultImages.length > 0) {
                // Lấy ảnh cuối cùng (mới nhất)
                const latestImg = resultImages[resultImages.length - 1];
                const imageUrl = latestImg.src;
                console.log(`🎯 Tìm thấy ảnh trong DOM: ${imageUrl.substring(0, 80)}...`);
                
                // Gửi cho Background tải trực tiếp với tên file = seg_id
                const result = await new Promise((resolve) => {
                    chrome.runtime.sendMessage({
                        action: 'DOWNLOAD_IMAGE',
                        url: imageUrl,
                        seg_id: seg_id
                    }, (response) => resolve(response || { success: false }));
                });
                
                if (result.success) {
                    console.log(`✅ Direct download thành công: ${result.filename}`);
                    directDownloadSuccess = true;
                } else {
                    console.warn(`⚠️ Direct download thất bại: ${result.error}, chuyển sang click download...`);
                }
            } else {
                console.log("⚠️ Không tìm thấy ảnh trong DOM, chuyển sang click download...");
            }
        } catch(e) {
            console.warn("⚠️ Lỗi khi thử direct download:", e);
        }
        
        // === PHƯƠNG ÁN 2: Click nút Download (Fallback) ===
        if (!directDownloadSuccess) {
            // Báo cho Background chuẩn bị tracking download cho seg_id này
            try { chrome.runtime.sendMessage({ action: 'PREPARE_DOWNLOAD', seg_id: seg_id }); } catch(e) {}
            
            // 3.5 Bấm Menu Dấu 3 chấm
            if (vqConfig.menu_download) {
                const clickedMenu = await smartClick(vqConfig.menu_download, 30000);
                if (clickedMenu) {
                    console.log("Đã mở menu 3 chấm, chờ hiển thị dropdown...");
                    await sleep(1000);
                }
            }

            // 3.6 Hover vào nút Tải xuống
            if (vqConfig.hover_download) {
                const hovered = await smartHover(vqConfig.hover_download, 5000);
                if (hovered) {
                    console.log("Đã hover/click vào nút Tải xuống, chờ menu con...");
                    await sleep(1000);
                }
            }

            // 4. Bấm Tải ảnh HD
            if (vqConfig.download_hd && vqConfig.use_hd !== false) {
                const clicked = await smartClick(vqConfig.download_hd, 10000);
                if (clicked) {
                    console.log("Đã bấm Tải ảnh HD, chờ quá trình xử lý...");
                    await sleep(15000);
                }
            }
            // 5. Bấm Tải ảnh Thường
            else if (vqConfig.download_normal) {
                const clicked = await smartClick(vqConfig.download_normal, 10000);
                if (clicked) {
                    console.log("Đã bấm Tải ảnh Thường...");
                    await sleep(3000);
                }
            }
        }

        // === CHỜ FILEPATH TỪ BACKGROUND (áp dụng cho cả 2 phương án) ===
        let downloadedFilepath = null;
        try {
            downloadedFilepath = await new Promise((resolve, reject) => {
                const timeout = setTimeout(() => {
                    chrome.runtime.onMessage.removeListener(listener);
                    reject(new Error("Timeout chờ file download"));
                }, 30000); // 30s timeout
                
                function listener(message) {
                    if (message.action === "DOWNLOAD_COMPLETED" && message.filepath) {
                        clearTimeout(timeout);
                        chrome.runtime.onMessage.removeListener(listener);
                        console.log(`📥 Nhận filepath: ${message.filepath}`);
                        resolve(message.filepath);
                    }
                }
                chrome.runtime.onMessage.addListener(listener);
            });
        } catch(e) {
            console.warn("⚠️ Không nhận được filepath từ background (fallback scan)", e);
        }

        // === GỬI KẾT QUẢ VỀ PYTHON ===
        if (socket && socket.readyState === WebSocket.OPEN) {
            const completionMsg = {
                type: 'GENERATION_COMPLETED',
                seg_id: seg_id
            };
            if (downloadedFilepath) {
                completionMsg.filepath = downloadedFilepath;
            }
            socket.send(JSON.stringify(completionMsg));
            console.log(`✅ Hoàn thành ${seg_id}, filepath: ${downloadedFilepath || '(fallback scan)'}`);
        }
        
    } catch (error) {
        console.error("Lỗi trong quá trình sinh ảnh:", error);
        
        // Auto-check mechanism: nếu có lỗi nghĩa là UI của Flow có thể đã thay đổi
        if (isPanelMinimized) {
            isPanelMinimized = false;
            renderPanel();
        }
        
        // Hiện lại trình duyệt nếu có lỗi
        try { chrome.runtime.sendMessage({ action: 'MAXIMIZE_WINDOW' }); } catch(e) {}
        
        alert("🚨 VQPVEO3PRO: Đã xảy ra lỗi khi điều khiển giao diện.\n\nCó thể Google Flow đã thay đổi cấu trúc web, hoặc mạng quá chậm.\nVui lòng kiểm tra lại cấu hình các nút (đặc biệt là nút bị ❌ hoặc nút đang gây lỗi).\n\nChi tiết lỗi: " + error.message);

        if (socket && socket.readyState === WebSocket.OPEN) {
            socket.send(JSON.stringify({
                type: 'GENERATION_ERROR',
                seg_id: seg_id,
                error: error.stack ? error.stack.toString() : error.message
            }));
        }
    }
}

// Khởi động kết nối khi trang được load
connectWebSocket();
