# Hướng dẫn VOICEVOX cho VQPVEO3PRO trên Windows

Ứng dụng đã cài và tích hợp VOICEVOX Engine qua HTTP API. Bạn không cần mở
VOICEVOX Editor hoặc xuất WAV bằng tay. Mở VQPVEO3PRO rồi chọn giọng trong tab
**KÊNH NHẬT → Tài sản kênh**.

## 1. Cài VOICEVOX

Ứng dụng hiện dùng VOICEVOX Engine 0.25.2 bản Windows CPU đặt trong
`D:\Flow\.runtime\voicevox_engine`. Khi mở VQPVEO3PRO, engine tự khởi động ẩn
ở `127.0.0.1:50021` và tự dừng khi thoát ứng dụng.

Nếu cần cài thủ công trên máy khác:

1. Mở trang chính thức: https://voicevox.hiroshiba.jp/
2. Bấm **ダウンロード / Download** và chọn bản Windows. Với người mới, dùng bản CPU trước vì tương thích rộng; có thể đổi GPU sau.
3. Chạy bộ cài. Nếu Windows SmartScreen hiện cảnh báo, tài liệu chính thức yêu cầu mở **More info / 詳細情報**, kiểm tra nhà phát hành là **Kazuyuki Hiroshiba**, rồi mới chọn Run.
4. Mở VOICEVOX và chờ giao diện nạp xong. Khi editor mở, engine HTTP thường chạy cùng tại `127.0.0.1:50021`.

Không cần mở cổng router hoặc tắt tường lửa Internet. VQPVEO3PRO và VOICEVOX nói chuyện trong chính máy tính qua địa chỉ loopback.

## 2. Khởi động và kiểm tra engine

VQPVEO3PRO tự khởi động engine khi mở. Trong **Tài sản kênh**, nút **Khởi động
VOICEVOX Engine** dùng để chạy lại thủ công; nút **Dừng engine do app mở** chỉ
dừng tiến trình do VQPVEO3PRO tạo. Nếu bạn tự chạy một engine khác, app sẽ dùng
engine đó và không tắt nó.

Khi engine đang chạy, có thể kiểm tra bằng trình duyệt:

- http://127.0.0.1:50021/version — phải hiện chuỗi phiên bản.
- http://127.0.0.1:50021/docs — tài liệu API của engine đang chạy.

Nếu trình duyệt báo không kết nối được, vào **Tài sản kênh** và bấm **Khởi động
VOICEVOX Engine**. Log kỹ thuật nằm tại `D:\Flow\logs\voicevox_engine.log`.

## 3. Chọn và nghe thử giọng trong ứng dụng

1. Chạy `start_app.bat`.
2. Mở **KÊNH NHẬT → Tài sản kênh**.
3. Giữ địa chỉ `http://127.0.0.1:50021`.
4. App tự tải danh sách sau khi engine sẵn sàng. Có thể bấm **Kiểm tra & tải giọng** để làm mới; ứng dụng đọc `/version` và `/speakers`, sau đó hiện tên nhân vật, style và ID.
5. Chọn một giọng trong danh sách, rồi bấm **Nghe thử**. Câu thử là tiếng Nhật của kênh và dùng tốc độ `0.95`, giống pipeline thật.
6. Khi đã chọn đúng giọng, bấm **Lưu tài sản kênh**.

Với kênh tài chính điềm tĩnh, hãy nghe thử các giọng nam trầm hoặc ổn định. Danh sách thực tế phụ thuộc phiên bản và thư viện VOICEVOX bạn cài; ứng dụng lấy danh sách trực tiếp nên không gắn cứng ID.

## 4. Tạo giọng đọc cho một tập

Sau khi có kịch bản hợp lệ, bấm **3 · Tạo giọng đọc**. Ứng dụng sẽ:

1. Chia lời đọc theo câu.
2. Gọi `/audio_query` để VOICEVOX phân tích cách đọc.
3. Đặt tốc độ `0.95`, WAV mono 24 kHz.
4. Gọi `/synthesis` và cache từng câu để chạy lại nhanh hơn.
5. Ghép thành `audio/merged.wav`, chèn sting hai giây trước mỗi item.
6. Sinh ASS và SRT theo ranh giới thời gian thật của từng câu.

Bạn có thể nghe `merged.wav` trong thư mục tập. Nếu đổi giọng rồi lưu lại, trạng thái Voice và các bước phụ thuộc bị vô hiệu hóa để tránh dùng nhầm bản cũ.

## 5. Credit và điều khoản sử dụng

VOICEVOX yêu cầu credit thể hiện việc sử dụng phần mềm. Pipeline tự thêm một dòng dạng:

```text
音声：VOICEVOX：<tên nhân vật>（<style>）
```

Mỗi nhân vật có thể có điều khoản riêng. Trước khi đăng hoặc kiếm tiền, mở trang nhân vật từ https://voicevox.hiroshiba.jp/ và kiểm tra cách ghi credit, nội dung thương mại và giới hạn riêng. Quy định phần mềm: https://voicevox.hiroshiba.jp/term/

## 6. Lỗi thường gặp

- **Connection refused / không kết nối 50021:** bấm **Khởi động VOICEVOX Engine**, chờ khoảng 5–30 giây và xem log nếu vẫn lỗi.
- **Danh sách giọng trống:** bấm **Kiểm tra & tải giọng**; thử `http://127.0.0.1:50021/speakers` trong trình duyệt.
- **Nghe thử không phát:** kiểm tra loa Windows và volume mixer; file thử nằm trong thư mục Temp của Windows.
- **Giọng khác sau khi cập nhật:** bấm lại **Kiểm tra & tải giọng**, chọn theo tên, nghe thử rồi lưu. Ứng dụng lưu style ID của bản đang dùng.
- **Tên riêng/thuật ngữ tài chính đọc sai:** trước mắt sửa cách viết trong lời thoại bằng kana. VOICEVOX editor cũng cho phép sửa cách đọc và accent; pipeline hiện chưa đồng bộ từ điển người dùng của editor.
- **Tạo cả tập chậm:** lần đầu một speaker có thể nạp lâu hơn. CPU vẫn hoạt động; GPU chỉ là lựa chọn tăng tốc.

## 7. FlowKit và UUID

UUID ở đây là UUID project Google Flow mà FlowKit dùng. Khi FlowKit tạo/liên kết project, nó lưu chính UUID này làm `project_id` cục bộ. VQPVEO3PRO giờ gọi:

1. `GET /health` để kiểm tra Chrome Extension.
2. `GET /api/active-project` để lấy project đang chọn; nếu chưa chọn rõ, FlowKit trả project gần nhất.
3. `GET /api/flow/status` làm phương án dự phòng cho project UUID đã pin.
4. `POST /api/flow/generate-image` để tạo ảnh 16:9 qua kết nối Google Flow sẵn có.

Vì vậy bạn có thể để ô UUID trống. Nút **Tự lấy từ FlowKit** giúp kiểm tra project trước khi chạy; nếu trạng thái ghi `fallback_most_recent`, hãy nhìn tên project để chắc chắn đúng dự án.
