# VQPVEO3PRO STUDIO - AI Video Automation Pipeline
> **Japan Market Edition** | Chuyên biệt hóa cho quy trình sản xuất video tự động (Faceless YouTube / TikTok Nhật Bản).

---

## 🌟 Giới Thiệu (Overview)

**VQPVEO3PRO STUDIO** là giải pháp phần mềm chuyên nghiệp tự động hóa 100% quy trình sản xuất video ngắn và dài dạng **Faceless Video cho thị trường Nhật Bản**, tích hợp từ khâu viết kịch bản AI, lồng tiếng Voicevox (Zundamon), tạo phụ đề Karaoke chuẩn ASR, sinh ảnh phân cảnh AI đồng nhất nhân vật tham chiếu, đến dựng và xuất video MP4 hoàn chỉnh.

![Studio Preview](ui_studio_preview.html)

---

## 🚀 Các Tính Năng Nổi Bật (Key Features)

### 1. Quy Trình Studio Stepper 5 Bước Trực Quan
- **Bước 1 - Khởi tạo Dự án:** Quản lý workspace riêng biệt, lưu trữ tài nguyên hình ảnh, âm thanh, phụ đề cho từng video.
- **Bước 2 - Kịch bản AI & Tối ưu SEO:** Tuân thủ chuẩn mực **Japanese Faceless Rules** (Hook 3 giây đầu kích thích tò mò -> Thân bài ngắn gọn chuẩn ngữ pháp bản địa -> CTA kêu gọi đăng ký tự nhiên), tự động sinh bộ thẻ SEO YouTube (5 Tiêu đề viral, Mô tả, Tags & Hashtags tiếng Nhật).
- **Bước 3 - Âm thanh & Phụ đề Karaoke:** Tích hợp Voicevox Engine (giọng đọc Zundamon, Yukkuri...) và Faster-Whisper ASR bóc tách thời gian từng từ để sinh phụ đề Karaoke `.ass` chuẩn xác.
- **Bước 4 - Lưới Phân Cảnh & Flowkit:** Tạo prompt hình ảnh tự động, đồng nhất nhân vật tham chiếu xuyên suốt video (Ref Character ID), sinh ảnh đa luồng qua Flowkit Bridge.
- **Bước 5 - Dựng & Xuất Video:** Ghép nối timeline, chuyển cảnh, phụ đề Karaoke vàng viền đen, xuất video Full HD 1080p (16:9 Landscape hoặc 9:16 Shorts).

### 2. Màn Hình Live Preview 16:9 Thời Gian Thực
- Xem trước từng phân cảnh kèm phụ đề Karaoke nổi và watermark nhân vật tham chiếu.
- Bảng theo dõi tiến độ dự án cập nhật tự động: Kịch bản, Số lượng ảnh đã tạo, Tình trạng âm thanh, Trạng thái đồng nhất nhân vật.

### 3. Cơ Chế Chống Quá Tải API Thông Minh (Resilient AI Provider)
- Tự động xoay vòng nhiều API Key (Key Rotation).
- Cơ chế tự động phát hiện mã lỗi `503` (Server quá tải) hoặc `429` (Hết quota) để đổi key và tự động fallback sang các model ổn định (`gemini-2.5-flash`, `gemini-3.5-flash`).

---

## 🛠️ Cài Đặt & Khởi Chạy (Installation & Setup)

### 1. Yêu Cầu Hệ Thống (Prerequisites)
- Hệ điều hành: Windows 10 / 11 (64-bit).
- Python: Phiên bản 3.10 trở lên.
- [FFmpeg](https://ffmpeg.org/): Đã được cấu hình trong `PATH` hệ thống.
- [VOICEVOX Engine](https://voicevox.hiroshiba.jp/): Chạy cục bộ tại cổng `http://127.0.0.1:50021`.

### 2. Cài Đặt Thư Viện Python
Mở Command Prompt hoặc PowerShell tại thư mục dự án:
```bash
pip install -r requirements.txt
```

### 3. Thiết Lập Cấu Hình API Key
Tạo file cấu hình cá nhân từ file mẫu:
1. Sao chép file `config/user_settings.example.json` thành `config/user_settings.json`.
2. Điền Google Gemini API Key hoặc Groq API Key vào file:
```json
{
    "DEFAULT_AI_PROVIDER": "Gemini (Google)",
    "Gemini (Google)_API_KEYS": "AIzaSy...",
    "Gemini (Google)_MODEL": "models/gemini-2.5-flash"
}
```
*(Lưu ý: File `config/user_settings.json` đã được đưa vào `.gitignore` để bảo mật tuyệt đối các API Key của bạn).*

### 4. Khởi Chạy Ứng Dụng
Nhấp đúp chuột vào file:
```bash
start_app.bat
```
Hoặc chạy lệnh:
```bash
python app/main.py
```

---

## 📁 Cấu Trúc Thư Mục (Project Structure)

```text
Flow/
├── app/                  # Entrypoint chính của ứng dụng PySide6
│   └── main.py
├── ui/                   # Giao diện người dùng chuẩn Studio Stepper
│   ├── main_window.py    # Cửa sổ chính, Header, Stepper Bar, Live Preview
│   ├── project_panel.py  # Bước 1: Quản lý Dự án
│   ├── script_panel.py   # Bước 2: Kịch bản AI & Tối ưu SEO
│   ├── voice_panel.py    # Bước 3: Voicevox & Subtitle Karaoke
│   ├── visual_grid.py    # Bước 4: Storyboard & Quản lý Phân cảnh
│   ├── timeline.py       # Bước 5: Dựng & Xuất Video
│   └── settings_panel.py # Cài đặt hệ thống & API Keys
├── ai/                   # AI Providers (Gemini, OpenAI, Voicevox Engine)
│   ├── gemini_provider.py
│   └── voicevox_engine.py
├── audio/                # Xử lý âm thanh & Faster-Whisper ASR
├── config/               # Cấu hình dự án & thư viện phong cách
│   ├── user_settings.example.json
│   └── character_library.json
├── utils/                # Tiện ích bổ trợ (Logger, Dependency Manager, JSON Store)
├── japan_rules.json      # Bộ quy chuẩn video thị trường Nhật Bản
├── start_app.bat         # File kích hoạt phần mềm 1-click
└── README.md
```

---

## 📄 License
Phát triển và bảo vệ bản quyền bởi **VQPVEO3PRO Studio**.
Mọi quyền được bảo lưu.
