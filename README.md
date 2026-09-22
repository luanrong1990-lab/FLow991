# JP FACELESS YOUTUBE FACTORY

Ứng dụng tự động hóa pipeline sản xuất video cho kênh YouTube faceless Nhật Bản (ngách tài chính / khởi nghiệp / thu nhập thụ động).

## 📋 Tổng quan

Pipeline tự động hóa đầy đủ:
1. **Gợi ý chủ đề** — Không trùng lặp (Jaccard similarity < 0.55)
2. **Chọn chủ đề** — Lưu vào lịch sử
3. **Viết kịch bản** — Theo RULES cứng, có validator
4. **Sinh metadata** — Titles, thumbnail text, hashtags, description
5. **Phân cảnh + timing** — Estimate từ độ dài narration
6. **Image prompts** — Khóa MASCOT_LOCK + STYLE_LOCK
7. **Tạo ảnh** — Qua FlowKit extension hoặc Gemini fallback
8. **TTS tiếng Nhật** — edge-tts hoặc GCP, kèm morpheme marks
9. **Phụ đề karaoke** — File .ass chuẩn Nhật
10. **Render video** — ffmpeg + thumbnail + description cuối

## 🏗️ Cấu trúc repo

```
/workspace/
├── app_ui.py                    # Streamlit UI
├── requirements.txt             # Python dependencies
├── assets/
│   └── mascot_ref.png          # Reference sheet mascot (bắt buộc)
├── core/
│   ├── brand.py                # Brand constants (MASCOT_LOCK, STYLE_LOCK)
│   ├── llm.py                  # LLM client wrapper
│   └── state.py                # State management (save/resume)
├── pipeline/
│   ├── topics.py               # Topic suggestion + deduplication
│   ├── script_writer.py        # Script generation with validation
│   ├── metadata.py             # Titles, thumb text, hashtags, desc
│   ├── scenes.py               # Timing estimation + alignment
│   ├── prompts.py              # Image prompt generation
│   ├── flowkit_bridge.py       # WebSocket bridge server
│   ├── images.py               # Image generation (flowkit/gemini)
│   ├── tts.py                  # TTS with morpheme tokenization
│   ├── subtitles.py            # Karaoke .ass generation
│   ├── render.py               # Video + thumbnail rendering
│   └── orchestrator.py         # Pipeline coordinator
├── extension/
│   ├── manifest.json           # Chrome extension manifest (MV3)
│   ├── background.js           # WebSocket client to Python
│   └── content.js              # Interact with Google Flow UI
├── rules/
│   └── script_rules.md         # RULES cho viết kịch bản
└── data/
    ├── projects/               # Project states (auto-created)
    └── topics_used.json        # History for deduplication
```

## ⚙️ Cài đặt

### 1. System requirements

```bash
# Cài ffmpeg, ffprobe
sudo apt-get update && sudo apt-get install -y ffmpeg ffprobe

# Cài font Noto Sans JP
sudo apt-get install -y fonts-noto-cjk
```

### 2. Python dependencies

```bash
cd /workspace
pip install -r requirements.txt
```

### 3. Cài Chrome Extension FlowKit

1. Mở Chrome, vào `chrome://extensions/`
2. Bật "Developer mode" (góc phải trên)
3. Click "Load unpacked"
4. Chọn thư mục `/workspace/extension`
5. Extension sẽ tự động kết nối WebSocket tới `ws://127.0.0.1:8765`

### 4. Chuẩn bị Mascot Reference Sheet

Nếu chưa có `assets/mascot_ref.png`, tạo bằng prompt sau (dùng bất kỳ AI image generator nào):

```
character reference sheet, six vertical panels, same character in all panels:
middle-aged Japanese businessman mascot, silver-gray hair, round friendly face,
gray suit, white shirt, green tie; expressions: surprised pointing up,
arms crossed smiling, asleep on desk with coins, holding yen banknotes grinning,
worried sweating, thumbs up; flat corporate cartoon vector illustration,
clean thick outlines, bright saturated colors, white background, no text
```

Lưu ảnh vào `/workspace/assets/mascot_ref.png`.

### 5. Biến môi trường

Tạo file `.env` hoặc export:

```bash
# LLM API (OpenAI-compatible)
export LLM_API_KEY="your-api-key"
export LLM_BASE_URL="https://api.openai.com/v1"
export LLM_MODEL="gpt-4o-mini"

# TTS provider: edge (miễn phí) hoặc gcp
export TTS_PROVIDER="edge"

# Image provider: flowkit (mặc định) hoặc gemini
export IMG_PROVIDER="flowkit"

# Nếu dùng GCP TTS:
export GOOGLE_APPLICATION_CREDENTIALS="/path/to/service-account.json"

# Nếu dùng Gemini images:
export GOOGLE_API_KEY="your-google-api-key"
```

## 🚀 Chạy ứng dụng

### Bước 1: Khởi động Streamlit

```bash
cd /workspace
streamlit run app_ui.py --server.port 8501
```

Truy cập: `http://localhost:8501`

### Bước 2: Mở tab Google Flow

1. Đăng nhập vào https://labs.google.com/
2. Mở một Flow bất kỳ để tạo ảnh
3. Đảm bảo extension FlowKit đã được bật

### Bước 3: Thực hiện pipeline trong UI

UI sẽ hiển thị các nút tuần tự:
- **1️⃣ Gợi ý chủ đề** → Danh sách 6 chủ đề không trùng
- **📌 Chọn chủ đề** → Click vào chủ đề muốn làm
- **2️⃣ Viết kịch bản** → Sinh kịch bản theo RULES, validate tự động
- **3️⃣ Generate Metadata** → Titles, thumb text, hashtags, description
- Các bước tiếp theo sẽ mở khóa dần...

### Bước 4: Resume project

Nếu tắt app giữa chừng, khi mở lại:
- Project ID được lưu trong session
- State đọc từ `data/projects/<pid>/state.json`
- Có thể tiếp tục từ step đang dở

## ✅ Checklist nghiệm thu (§10)

| STT | Tiêu chí | Trạng thái |
|-----|----------|------------|
| 1 | Gợi ý chủ đề nhiều lần không trùng (Jaccard > 0.55) | ✅ |
| 2 | Kịch bản pass validator, OPENING có disclaimer | ✅ |
| 3 | 100% image prompts chứa MASCOT_LOCK | ✅ |
| 4 | Ranh giới scene trong .ass lệch ≤ ±0.3s | ✅ |
| 5 | Chữ Nhật render đúng (Noto Sans JP) | ✅ |
| 6 | Resume đúng step khi restart app | ✅ |
| 7 | FlowKit timeout → lỗi tiếng Việt + retry | ✅ |
| 8 | Output: video_final.mp4, thumbnail.png, description_final.txt | ✅ |

## 🔧 Troubleshooting

### FlowKit timeout / No extension connected
- Kiểm tra tab Google Flow đã mở chưa
- Extension đã được load trong `chrome://extensions/`?
- WebSocket server có chạy không? (xem log Streamlit)

### Thiếu font Noto Sans JP
```bash
sudo apt-get install fonts-noto-cjk
fc-cache -fv
```

### LLM trả JSON lỗi
- App tự động retry 3 lần
- Nếu vẫn lỗi: kiểm tra API key và model

### TTS edge-tts chậm
- Chuyển sang `TTS_PROVIDER=gcp` nếu có GCP credentials

## 📜 License

Sử dụng nội bộ cho mục đích sản xuất video YouTube.

## 📞 Support

Xem log chi tiết trong terminal khi chạy Streamlit.
