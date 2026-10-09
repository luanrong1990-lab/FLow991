document.addEventListener('DOMContentLoaded', () => {
    const statusText = document.getElementById('status-text');
    const statusIndicator = document.getElementById('status-indicator');

    function updateStatus(status) {
        if (status === 'connected') {
            statusIndicator.className = 'status connected';
            statusText.innerText = 'Connected';
        } else {
            statusIndicator.className = 'status disconnected';
            statusText.innerText = 'Disconnected';
        }
    }

    // Lấy trạng thái ban đầu
    chrome.storage.local.get(['bridge_status'], (result) => {
        updateStatus(result.bridge_status || 'disconnected');
    });

    // Lắng nghe thay đổi
    chrome.storage.onChanged.addListener((changes, namespace) => {
        if (namespace === 'local' && changes.bridge_status) {
            updateStatus(changes.bridge_status.newValue);
        }
    });
});
