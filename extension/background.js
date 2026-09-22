// background.js - WebSocket bridge to Python server
const WS_URL = "ws://127.0.0.1:8765";
let ws = null;
let currentJob = null;

function connect() {
  ws = new WebSocket(WS_URL);
  
  ws.onopen = () => {
    console.log("FlowKit Bridge: Connected to Python server");
  };
  
  ws.onclose = () => {
    console.log("FlowKit Bridge: Disconnected, reconnecting in 3s...");
    setTimeout(connect, 3000);
  };
  
  ws.onerror = (err) => {
    console.error("FlowKit Bridge: WebSocket error", err);
  };
  
  ws.onmessage = (event) => {
    const msg = JSON.parse(event.data);
    
    if (msg.type === "job") {
      currentJob = msg;
      // Forward job to content script in labs.google tab
      chrome.tabs.query({ url: "https://labs.google/*" }, (tabs) => {
        if (tabs.length > 0) {
          chrome.tabs.sendMessage(tabs[0].id, msg);
        } else {
          console.error("FlowKit Bridge: No Google Flow tab found");
          // Send error back to server
          ws.send(JSON.stringify({
            type: "error",
            job_id: msg.job_id,
            message: "No Google Flow tab open"
          }));
        }
      });
    }
  };
}

// Poll server every 1.5s to maintain connection
setInterval(() => {
  if (ws && ws.readyState === WebSocket.OPEN) {
    ws.send(JSON.stringify({ type: "poll" }));
  }
}, 1500);

// Listen for results from content script
chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {
  if (msg.type === "result" && ws && ws.readyState === WebSocket.OPEN) {
    ws.send(JSON.stringify(msg));
  }
});

// Initial connection
connect();
