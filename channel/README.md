# Kênh Nhật · 静かに稼ぐ研究室

Tích hợp trong **VQPVEO3PRO → KÊNH NHẬT**. Khởi động bằng `start_app.bat` như trước.

## Bộ quy tắc được áp dụng

Nguồn là `japan_rules.json`, một bản xuất hội thoại, không phải cấu hình máy đọc trực tiếp. Hai khối quy tắc được trích từ hội thoại:

- `prompts/bible_v1.0.txt`: Series Bible, định vị, bốn trụ cột, phong cách, mascot, thumbnail và SEO.
- `prompts/narration_v1.0.txt`: hướng dẫn viết tiếng Nhật tự nhiên, câu ngắn, đuôi câu và chính tả TTS.
- `profiles/japan_v1.0.json`: cấu hình chuẩn hóa dùng khi chạy, gồm palette, STYLE_LOCK, opening, disclaimer và giới hạn ký tự.

`rules.py` chứa các quy tắc có thể kiểm tra bằng code. Mỗi tập lưu **bản chụp đầy đủ** Bible, cấu hình và bảng màu trong `episode.json`. Thay quy tắc cho tập mới không tự sửa tập đã tạo. File nguồn `japan_rules.json` được giữ nguyên.

Giải quyết hai mâu thuẫn của tài liệu: opening dài được giữ nguyên; từ `保証` chỉ được miễn kiểm tra khi nằm trong câu disclaimer cố định. Mọi nội dung khác vẫn qua lint. Hook đứng trước intro theo cấu trúc episode trong Bible. Ngày tham chiếu không cố định vào năm ghi trong ví dụ.

## Dùng từ đầu

1. Vào **Settings** của ứng dụng và cấu hình Gemini như trước. Không có API key nào được đóng gói trong module này.
2. Vào **KÊNH NHẬT → Tài sản kênh**:
   - Font Noto Sans JP và 5 mascot đã được đóng gói sẵn.
   - Nhạc nền synth nhẹ và sting chuyển mục là tài sản gốc tạo bằng code; có thể thay nhạc nền bằng file của bạn hoặc để trống để không dùng BGM.
   - VOICEVOX Engine 0.25.2 Windows CPU được cài cục bộ trong `.runtime/voicevox_engine`. App tự khởi động engine khi mở và tự dừng tiến trình do app tạo khi thoát. Bấm **Kiểm tra & tải giọng**, chọn giọng theo tên rồi bấm **Nghe thử**. Xem hướng dẫn tại `VOICEVOX_GUIDE.md`.
   - Với FlowKit, để trống UUID để pipeline tự dùng project đang hoạt động. Hoặc bấm **Tự lấy từ FlowKit** để xem tên và UUID trước khi lưu. Chỉ nhập UUID thủ công khi muốn buộc một project khác.
   - Bấm **Lưu tài sản kênh** để dùng cho các tập sau.
3. Ở **Chủ đề**, nhập mã như `ep001`, chọn P1–P4, nhập brief và tài liệu nguồn. Nguồn nên có URL chính thức, ngày kiểm tra và nội dung/số liệu liên quan. Bấm **Tạo tập mới**.
4. Bấm **Gợi ý chủ đề**; chọn một trong năm đề xuất. Đây là ý tưởng do AI đề xuất từ brief và nguồn bạn cung cấp, **không phải kết quả tìm kiếm web đã xác minh**. `needs_research` ghi các điểm cần tìm hiểu thêm.
5. Bấm **Viết kịch bản**: draft → viết theo lô nhỏ → lint → tối đa hai vòng sửa → AI chấm năm tiêu chí văn nói. Điểm dưới 4/5 giữ bản ứng viên để bạn chỉnh. Tab Kịch bản cho phép sửa JSON theo cảnh rồi kiểm tra/lưu lại.
6. Chạy **Tạo giọng đọc**, **Tạo ảnh Flow**, **Thumbnail A/B**, **SEO Nhật**. Các lệnh gọi dịch vụ chạy trong luồng nền; có nút dừng sau thao tác đang chạy. Những câu WAV và ảnh có cùng nội dung được dùng lại khi chạy lại.
7. Đọc kịch bản, kiểm tra nguồn/số liệu, nghe giọng Nhật; đánh dấu đã kiểm tra ở tab **Kiểm tra**, sau đó **Xuất video**.
8. Bấm **Mở thư mục đầu ra** để lấy MP4, hai thumbnail, SRT và SEO. Đăng YouTube bằng thao tác thủ công; đọc lại nội dung, quyền sử dụng tài sản và mục khai báo AI trước khi đăng theo checklist của bạn.

Mỗi bước AI/Flow có thể sử dụng hạn mức tài khoản khi bạn bấm chạy. Không có job tự động chạy chỉ vì mở tab.

## Đầu ra của một tập

```text
projects/japan_channel/ep001/
  episode.json                 # nguồn, snapshot rules, trạng thái, cảnh, cấu hình
  audio/merged.wav             # VO câu-by-câu + sting 2 giây trước item
  audio/<hash>.wav             # cache câu theo text, speaker, speed, engine
  images/SCxx_<hash>.png        # ảnh nền Flow với STYLE_LOCK + NEGATIVE
  frames/                      # ảnh ghép mascot, telop, số mục, bumper
  subtitles/subtitles.ass      # phụ đề Nhật burn-in theo thời gian câu WAV
  subtitles/subs_ja.srt         # phụ đề rời để tải lên YouTube
  thumbnails/thumb_v1.png       # navy + vàng
  thumbnails/thumb_v2.png       # cream + đen, cùng bố cục
  seo.json
  youtube_description.txt      # chapter từ timeline thật + disclaimer + credit
  exports/final_video.mp4       # 1920×1080, 30fps, H.264/AAC
```

Các file cũ được giữ khi đổi chủ đề/sửa kịch bản, nhưng trạng thái các bước phụ thuộc bị xóa để không dùng nhầm kết quả. Khi render, chương trình yêu cầu các bước liên quan hoàn thành lại. Đường dẫn file đầu ra trong episode đang lỗi có thể vẫn trỏ đến bản xuất trước; chỉ trạng thái `render: done` xác nhận bản hiện tại đã xuất thành công.

Ở bước thumbnail, font, mascot và BGM được sao chép vào `brand_assets/` của tập, đặt theo hash nội dung. Khi chạy lại tập cũ với cùng cấu hình, ứng dụng dùng bản sao này. Muốn thay nhận diện có chủ đích, chọn đường dẫn tài sản mới và lưu cấu hình của tập.

## Những gì code kiểm tra và những gì cần người duyệt

Code kiểm tra cấu trúc cảnh, ID duy nhất, thứ tự mục, opening/disclaimer, ký tự TTS, câu quá dài, lặp đuôi câu, từ cấm, số câu hỏi, telop, chữ thumbnail, định dạng tiêu đề và số tags. STYLE_LOCK và NEGATIVE được ghép bằng code. Mascot được lấy từ một bộ asset, không sinh lại mỗi tập.

Quy tắc ngữ nghĩa như lập luận PREP, chất lượng case study, độ tự nhiên bản địa, hedge phù hợp, rủi ro tài chính và tính đúng của nguồn được đưa vào prompt và vẫn cần người duyệt. Điểm AI không thay thế việc nghe/đọc lại. Thời lượng 40 giây/hook, 60–75 giây/item là mục tiêu viết; thời lượng thực tế lấy từ VOICEVOX, không kéo giãn âm thanh để ép số giây. Phụ đề căn theo **câu**, không tuyên bố có căn karaoke từng từ.

Các cảnh hiện dùng minh họa tĩnh có mascot/telop và bumper 2 giây; không tự tạo biểu đồ dữ liệu hay hoạt hình infographic từ số liệu. Render có BGM lặp, duck theo giọng và loudness filter; mức loudness đầu ra vẫn nên đo/nghe ở bước QC. Không có upload, lịch đăng, analytics, tìm kiếm web tự động hay Docker hóa giao diện desktop trong bản tích hợp này.

## Tài sản và chỉnh sửa

- Font: Google Fonts, `NotoSansJP[wght].ttf`; giấy phép đi kèm tại `assets/fonts/OFL.txt`. Nguồn: https://github.com/google/fonts/tree/main/ofl/notosansjp . Font biến thiên dùng weight 800 khi vẽ thumbnail.
- Mascot: bộ vector gốc cho project, tóc bạc, vest navy, cà vạt xanh; SVG nguồn và PNG alpha trong `assets/mascot/`. Tái tạo bằng `python -m channel.build_mascot_assets`. Muốn thay thiết kế, thay đủ 5 pose cùng một nhân vật.
- Audio: nhạc synth và sting gốc, tái tạo bằng `python -m channel.build_audio_assets`. Chọn nhạc khác trong Tài sản kênh nếu cần chất âm khác.
- `assets/preview/`: hai thumbnail minh họa, khung video mẫu và ảnh chụp giao diện; không phải episode có số liệu nghiên cứu thật.
- Muốn tăng version: thêm Bible mới, cập nhật bộ profile/loader cho tập mới; giữ nguyên snapshot trong tập cũ.

## Kiểm tra

```powershell
python -m unittest discover -s tests -v
```

Kiểm thử API dùng mock, không tiêu hạn mức. Đã smoke-test UI Qt, các tài sản gốc, subtitle, font và render FFmpeg có BGM ở máy hiện tại. Cần chạy một tập thực tế để kiểm chứng Gemini, VOICEVOX và Flow với tài khoản của bạn.
