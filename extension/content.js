// content.js - Interact with Google Flow UI
// TODO: Adjust selectors based on actual FlowKit/Google Flow UI structure

const SEL = {
  prompt: 'textarea[placeholder*="prompt"], input[type="text"][placeholder*="prompt"], #prompt',
  generate: 'button:contains("Generate"), button:contains("生成"), [role="button"]:has-text("Generate")',
  result: 'img[result], .generated-image, [data-testid="result-image"]'
};

// Helper to wait for element
function waitFor(selector, timeout = 30000) {
  return new Promise((resolve, reject) => {
    const el = document.querySelector(selector);
    if (el) return resolve(el);
    
    const observer = new MutationObserver(() => {
      const el = document.querySelector(selector);
      if (el) {
        observer.disconnect();
        resolve(el);
      }
    });
    
    observer.observe(document.body, { childList: true, subtree: true });
    setTimeout(() => {
      observer.disconnect();
      reject(new Error(`Timeout waiting for ${selector}`));
    }, timeout);
  });
}

// Helper to dispatch input event
function setInputValue(el, value) {
  el.value = value;
  el.dispatchEvent(new Event('input', { bubbles: true }));
  el.dispatchEvent(new Event('change', { bubbles: true }));
}

// Convert blob to base64
function blobToBase64(blob) {
  return new Promise((resolve) => {
    const reader = new FileReader();
    reader.onloadend = () => resolve(reader.result.split(',')[1]);
    reader.readAsDataURL(blob);
  });
}

// Listen for jobs from background script
chrome.runtime.onMessage.addListener(async (msg, sender, sendResponse) => {
  if (msg.type !== "job") return;
  
  const { job_id, prompt, ref, n } = msg;
  
  try {
    // Step 1: Find and fill prompt input
    // TODO: Adjust selector for your FlowKit flow
    const promptEl = await waitFor(SEL.prompt);
    setInputValue(promptEl, prompt);
    
    // Step 2: Attach reference image if provided
    // TODO: Implement reference sheet upload based on your Flow's input mechanism
    if (ref) {
      // Example: find file input and trigger upload
      // const fileInput = document.querySelector('input[type="file"]');
      // const blob = await fetch('data:image/png;base64,' + ref).then(r => r.blob());
      // ... upload logic
      console.log("Reference sheet provided (upload not implemented - TODO)");
    }
    
    // Step 3: Click generate button
    // TODO: Adjust selector
    const genBtn = await waitFor(SEL.generate, 5000);
    genBtn.click();
    
    // Step 4: Wait for result image
    // TODO: Adjust selector and timeout
    const resultImg = await waitFor(SEL.result, 180000);
    
    // Step 5: Extract image as base64
    // Try to get from src or canvas
    let images = [];
    
    if (resultImg.tagName === 'CANVAS') {
      const dataUrl = resultImg.toDataURL('image/png');
      images.push(dataUrl.split(',')[1]);
    } else if (resultImg.src) {
      // Fetch to handle CORS
      const response = await fetch(resultImg.src);
      const blob = await response.blob();
      const base64 = await blobToBase64(blob);
      images.push(base64);
    }
    
    // Send result back to background
    chrome.runtime.sendMessage({
      type: "result",
      job_id: job_id,
      images: images
    });
    
  } catch (err) {
    console.error("FlowKit content script error:", err);
    chrome.runtime.sendMessage({
      type: "error",
      job_id: job_id,
      message: err.message
    });
  }
});

console.log("FlowKit content script loaded");
