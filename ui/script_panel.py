"""
ui/script_panel.py - Giao diện tạo Kịch bản AI chuẩn Studio Stepper (Phase 2).

Thiết kế hiện đại chuẩn Studio:
- Bố cục responsive hài hòa: Giới hạn chiều rộng hợp lý, không bị giãn bè ngang khi phóng to màn hình.
- Phù hợp hoàn hảo với Japan Faceless Video Rules (Hook 3s, Zundamon Storytelling, 1-Click Generation).
- Hiển thị thông minh: Khi chưa tạo kịch bản, hiển thị bảng hướng dẫn cấu trúc chuẩn;
  khi đã tạo xong, hiển thị bảng Review Kịch bản & Bộ thẻ SEO chuyên nghiệp kèm nút Sao chép.
"""

import json
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, 
    QTextEdit, QProgressBar, QMessageBox, QSplitter, QFrame, 
    QComboBox, QGridLayout, QLineEdit, QApplication, QScrollArea
)
from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QFont

from ai.factory import get_current_ai_provider
from utils.logger import app_logger


class ScriptGeneratorWorker(QThread):
    """Luồng nền để gọi AI API sinh kịch bản & SEO."""
    success_signal = Signal(dict)
    error_signal = Signal(str)
    
    def __init__(self, topic, audience, style, language, duration):
        super().__init__()
        self.topic = topic
        self.audience = audience
        self.style = style
        self.language = language
        self.duration = duration
        
    def run(self):
        try:
            provider = get_current_ai_provider()
            script_json_str = provider.generate_script(
                self.topic, self.audience, self.style, self.language, self.duration
            )
            try:
                data = json.loads(script_json_str)
                self.success_signal.emit(data)
            except json.JSONDecodeError:
                self.error_signal.emit("Lỗi: AI không trả về chuẩn định dạng JSON.")
        except Exception as e:
            self.error_signal.emit(str(e))


class ScriptPanel(QWidget):
    def __init__(self):
        super().__init__()
        self._init_ui()

    def _init_ui(self):
        # Layout ngoài cùng dạng ScrollArea để đảm bảo không bao giờ bị cắt vỡ trên màn hình nhỏ
        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(0, 0, 0, 0)
        outer_layout.setSpacing(0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setStyleSheet("QScrollArea { background-color: transparent; border: none; }")

        container = QWidget()
        container.setStyleSheet("background-color: transparent;")
        
        # Responsive wrapper: Giới hạn chiều rộng tối đa 1100px và căn giữa khi phóng to
        center_h_layout = QHBoxLayout(container)
        center_h_layout.setContentsMargins(16, 16, 16, 16)
        
        self.content_box = QWidget()
        self.content_box.setMaximumWidth(1100) # Khắc phục triệt để lỗi giãn bè ngang trên màn hình 1080p/2K/4K
        content_layout = QVBoxLayout(self.content_box)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(16)

        center_h_layout.addWidget(self.content_box)

        scroll.setWidget(container)
        outer_layout.addWidget(scroll)

        # ========================================================
        # 1. HEADER SECTION (Tiêu đề + Badges + Nút Đổi cấu hình)
        # ========================================================
        header_widget = QWidget()
        header_layout = QHBoxLayout(header_widget)
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(12)

        title_box = QHBoxLayout()
        title_box.setSpacing(10)
        
        lbl_icon = QLabel("✍️")
        lbl_icon.setStyleSheet("font-size: 18px;")
        title_box.addWidget(lbl_icon)

        lbl_title = QLabel("Kịch bản AI & Tối ưu SEO")
        lbl_title.setStyleSheet("font-size: 17px; font-weight: 800; color: #f8fafc; letter-spacing: 0.3px;")
        title_box.addWidget(lbl_title)
        
        header_layout.addLayout(title_box)

        # Japanese Rules Badge
        lbl_badge = QLabel("Japanese Rules Active")
        lbl_badge.setStyleSheet("""
            background-color: rgba(168, 85, 247, 0.15);
            color: #d8b4fe;
            border: 1px solid rgba(168, 85, 247, 0.4);
            border-radius: 12px;
            padding: 4px 12px;
            font-size: 11px;
            font-weight: 700;
        """)
        header_layout.addWidget(lbl_badge)

        header_layout.addStretch()

        # Nút chuyển đổi xem lại cấu hình nhập / kết quả
        self.btn_toggle_view = QPushButton("🔄 Sửa cấu hình / Tạo lại")
        self.btn_toggle_view.setStyleSheet("""
            QPushButton {
                background-color: #1e293b;
                color: #e2e8f0;
                border: 1px solid #334155;
                border-radius: 8px;
                padding: 6px 14px;
                font-size: 12px;
                font-weight: 600;
            }
            QPushButton:hover {
                background-color: #334155;
                color: #ffffff;
            }
        """)
        self.btn_toggle_view.clicked.connect(self._toggle_input_view)
        self.btn_toggle_view.setVisible(False)
        header_layout.addWidget(self.btn_toggle_view)

        content_layout.addWidget(header_widget)

        # ========================================================
        # 2. MAIN INPUT CARD (Khung nhập liệu Studio chuyên nghiệp)
        # ========================================================
        self.card_input = QFrame()
        self.card_input.setStyleSheet("""
            QFrame#cardInput {
                background-color: #0d1322;
                border: 1px solid #1e293b;
                border-radius: 14px;
            }
        """)
        self.card_input.setObjectName("cardInput")

        card_layout = QVBoxLayout(self.card_input)
        card_layout.setContentsMargins(20, 20, 20, 20)
        card_layout.setSpacing(16)

        # Row 1: Chủ đề video / Bài viết gốc
        topic_box = QVBoxLayout()
        topic_box.setSpacing(6)
        lbl_topic = QLabel("Chủ đề video / Bài viết gốc:")
        lbl_topic.setStyleSheet("color: #cbd5e1; font-weight: 600; font-size: 12px;")
        topic_box.addWidget(lbl_topic)

        self.txt_topic = QTextEdit()
        self.txt_topic.setPlaceholderText("Ví dụ: Bí ẩn thế giới ngầm Tokyo và những truyền thuyết đô thị, hoặc dán URL bài báo cần tóm tắt...")
        self.txt_topic.setFixedHeight(64)
        self.txt_topic.setStyleSheet("""
            QTextEdit {
                background-color: #070b14;
                color: #f8fafc;
                border: 1px solid #222f47;
                border-radius: 8px;
                padding: 8px 12px;
                font-size: 13px;
                line-height: 1.4;
            }
            QTextEdit:focus {
                border: 1px solid #3b82f6;
                background-color: #0a0f1d;
            }
        """)
        topic_box.addWidget(self.txt_topic)
        card_layout.addLayout(topic_box)

        # Row 2: Grid 3 cột cấu hình thông số
        grid_opts = QGridLayout()
        grid_opts.setHorizontalSpacing(16)
        grid_opts.setVerticalSpacing(8)

        # Cột 1: Ngôn ngữ
        lbl_lang = QLabel("Ngôn ngữ:")
        lbl_lang.setStyleSheet("color: #94a3b8; font-size: 11px; font-weight: 600;")
        self.combo_language = QComboBox()
        self.combo_language.addItems([
            "Tiếng Nhật (Native JP)", "Tiếng Việt", "English (US)", "English (UK)", 
            "Tiếng Hàn (한국어)", "Tiếng Trung (中文)", "Spanish (Español)", "French (Français)"
        ])
        self.combo_language.setFixedHeight(36)
        grid_opts.addWidget(lbl_lang, 0, 0)
        grid_opts.addWidget(self.combo_language, 1, 0)

        # Cột 2: Phong cách
        lbl_style = QLabel("Phong cách:")
        lbl_style.setStyleSheet("color: #94a3b8; font-size: 11px; font-weight: 600;")
        self.combo_style = QComboBox()
        self.combo_style.addItems([
            "Zundamon Storytelling (Faceless Nhật)",
            "Kể chuyện & Bí ẩn (Storytelling)",
            "Hài hước & Châm biếm (Humorous)",
            "Giáo dục & Học thuật (Educational)",
            "Nghiêm túc & Chuyên nghiệp (Professional)",
            "Kịch tính & Hồi hộp (Dramatic)",
            "Truyền cảm hứng (Inspirational)"
        ])
        self.combo_style.setFixedHeight(36)
        grid_opts.addWidget(lbl_style, 0, 1)
        grid_opts.addWidget(self.combo_style, 1, 1)

        # Cột 3: Thời lượng
        lbl_dur = QLabel("Thời lượng:")
        lbl_dur.setStyleSheet("color: #94a3b8; font-size: 11px; font-weight: 600;")
        self.combo_duration = QComboBox()
        self.combo_duration.setEditable(True)
        self.combo_duration.addItems([
            "3 - 5 phút (Chuẩn YouTube)",
            "1 - 3 phút (Ngắn gọn)",
            "< 1 phút (Shorts/Reels/TikTok)",
            "5 - 8 phút (Chuyên sâu)",
            "8 - 12 phút (Dài)"
        ])
        self.combo_duration.setFixedHeight(36)
        grid_opts.addWidget(lbl_dur, 0, 2)
        grid_opts.addWidget(self.combo_duration, 1, 2)

        # Cột 4: Đối tượng khán giả
        lbl_aud = QLabel("Đối tượng:")
        lbl_aud.setStyleSheet("color: #94a3b8; font-size: 11px; font-weight: 600;")
        self.combo_audience = QComboBox()
        self.combo_audience.addItems([
            "Tất cả lứa tuổi (General)",
            "Giới trẻ & Gen Z (Teens)",
            "Người lớn & Dân văn phòng (Adults)",
            "Otaku & Anime fans",
            "Người cao tuổi (Seniors)"
        ])
        self.combo_audience.setFixedHeight(36)
        grid_opts.addWidget(lbl_aud, 0, 3)
        grid_opts.addWidget(self.combo_audience, 1, 3)

        card_layout.addLayout(grid_opts)

        # Row 3: Action Button (Căn chỉnh cân đối, không kéo dãn vô tận)
        btn_box = QHBoxLayout()
        btn_box.setContentsMargins(0, 8, 0, 0)
        btn_box.addStretch()

        self.btn_generate = QPushButton("✨ Tạo Kịch Bản 1-Click (Tuân thủ Rules Nhật)")
        self.btn_generate.setFixedHeight(44)
        self.btn_generate.setMinimumWidth(380)
        self.btn_generate.setMaximumWidth(520)
        self.btn_generate.setCursor(Qt.PointingHandCursor)
        self.btn_generate.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #2563eb, stop:1 #4f46e5);
                color: #ffffff;
                font-weight: 700;
                font-size: 13px;
                border-radius: 8px;
                border: none;
                padding: 0 24px;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #3b82f6, stop:1 #6366f1);
            }
            QPushButton:pressed {
                background: #1d4ed8;
            }
            QPushButton:disabled {
                background-color: #1e293b;
                color: #64748b;
            }
        """)
        self.btn_generate.clicked.connect(self.generate_script)
        btn_box.addWidget(self.btn_generate)
        btn_box.addStretch()

        card_layout.addLayout(btn_box)

        # Thanh tiến trình
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 0)
        self.progress_bar.setFixedHeight(6)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                background-color: #1e293b;
                border: none;
                border-radius: 3px;
            }
            QProgressBar::chunk {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #3b82f6, stop:1 #8b5cf6);
                border-radius: 3px;
            }
        """)
        self.progress_bar.setVisible(False)
        card_layout.addWidget(self.progress_bar)

        content_layout.addWidget(self.card_input)

        # ========================================================
        # 3. EMPTY STATE / JAPAN RULES GUIDE CARD
        # (Hiển thị khi chưa sinh kịch bản để giao diện không bị trống trải)
        # ========================================================
        self.card_guide = QFrame()
        self.card_guide.setStyleSheet("""
            QFrame {
                background-color: rgba(15, 23, 42, 0.4);
                border: 1px dashed #1e293b;
                border-radius: 12px;
                padding: 16px;
            }
        """)
        guide_layout = QVBoxLayout(self.card_guide)
        guide_layout.setSpacing(10)

        lbl_guide_title = QLabel("📌 Quy trình Kịch bản & Tối ưu SEO cho Video Nhật Bản (Japanese Faceless Pipeline):")
        lbl_guide_title.setStyleSheet("color: #94a3b8; font-weight: 700; font-size: 12px;")
        guide_layout.addWidget(lbl_guide_title)

        grid_rules = QGridLayout()
        grid_rules.setSpacing(10)

        rule1 = QLabel("⚡ <b>Hook 3 Giây Đầu:</b> Giật tít kích thích tò mò cực đại, ngăn chặn khán giả lướt qua.")
        rule2 = QLabel("📖 <b>Thân bài (Body):</b> Ngắt nhịp ngắn, ngữ pháp chuẩn người bản xứ (sẵn sàng cho giọng Zundamon).")
        rule3 = QLabel("🚀 <b>CTA Tự Nhiên:</b> Kêu gọi đăng ký kênh khéo léo ở phân đoạn cuối video.")
        rule4 = QLabel("🏷️ <b>Bộ Thẻ SEO Viral:</b> Tự động sinh 5 Tiêu đề đề xuất, Mô tả chuẩn SEO, Tags & Hashtags tiếng Nhật.")

        for idx, r in enumerate([rule1, rule2, rule3, rule4]):
            r.setStyleSheet("color: #64748b; font-size: 11px;")
            r.setWordWrap(True)
            grid_rules.addWidget(r, idx // 2, idx % 2)

        guide_layout.addLayout(grid_rules)
        content_layout.addWidget(self.card_guide)

        # ========================================================
        # 4. SCRIPT & SEO REVIEW SECTION (Hiển thị khi đã có kết quả)
        # ========================================================
        self.card_review = QWidget()
        review_layout = QVBoxLayout(self.card_review)
        review_layout.setContentsMargins(0, 0, 0, 0)
        review_layout.setSpacing(12)

        # Top Stats Bar
        stats_bar = QFrame()
        stats_bar.setStyleSheet("background-color: #0b1120; border: 1px solid #1e293b; border-radius: 8px; padding: 6px 12px;")
        stats_layout = QHBoxLayout(stats_bar)
        stats_layout.setContentsMargins(8, 4, 8, 4)

        self.lbl_status_badge = QLabel("✓ Đã tạo xong Kịch bản & Bộ thẻ SEO")
        self.lbl_status_badge.setStyleSheet("color: #10b981; font-weight: bold; font-size: 12px;")
        stats_layout.addWidget(self.lbl_status_badge)

        stats_layout.addStretch()

        self.lbl_stats = QLabel("Ký tự: 0 | Từ: 0")
        self.lbl_stats.setStyleSheet("color: #64748b; font-size: 11px; font-family: monospace;")
        stats_layout.addWidget(self.lbl_stats)

        review_layout.addWidget(stats_bar)

        # 2 Cột hiển thị: Lời thoại (Bên trái) + SEO Metadata (Bên phải)
        self.output_splitter = QSplitter(Qt.Horizontal)
        self.output_splitter.setStyleSheet("""
            QSplitter::handle {
                background-color: #1e293b;
                width: 2px;
            }
        """)

        # Cột Trái: Lời thoại
        box_script = QFrame()
        box_script.setStyleSheet("background-color: #0d1322; border: 1px solid #1e293b; border-radius: 10px;")
        layout_sc = QVBoxLayout(box_script)
        layout_sc.setContentsMargins(12, 12, 12, 12)
        layout_sc.setSpacing(8)

        sc_header = QHBoxLayout()
        lbl_sc_title = QLabel("📜 LỜI THOẠI KỊCH BẢN (VOICEOVER)")
        lbl_sc_title.setStyleSheet("color: #cbd5e1; font-weight: bold; font-size: 12px;")
        sc_header.addWidget(lbl_sc_title)
        sc_header.addStretch()

        btn_copy_script = QPushButton("📋 Sao chép")
        btn_copy_script.setStyleSheet("background-color: #1e293b; color: #94a3b8; font-size: 11px; padding: 4px 10px; border-radius: 4px;")
        btn_copy_script.clicked.connect(self._copy_script)
        sc_header.addWidget(btn_copy_script)
        layout_sc.addLayout(sc_header)

        self.txt_script = QTextEdit()
        self.txt_script.setPlaceholderText("Văn bản lời thoại sẽ hiển thị tại đây...")
        self.txt_script.setStyleSheet("""
            QTextEdit {
                background-color: #070b14;
                color: #e2e8f0;
                border: 1px solid #1e293b;
                border-radius: 6px;
                padding: 10px;
                font-size: 13px;
                line-height: 1.5;
            }
        """)
        self.txt_script.textChanged.connect(self._update_stats)
        layout_sc.addWidget(self.txt_script)

        self.output_splitter.addWidget(box_script)

        # Cột Phải: SEO Metadata
        box_seo = QFrame()
        box_seo.setStyleSheet("background-color: #0d1322; border: 1px solid #1e293b; border-radius: 10px;")
        layout_seo = QVBoxLayout(box_seo)
        layout_seo.setContentsMargins(12, 12, 12, 12)
        layout_seo.setSpacing(8)

        seo_header = QHBoxLayout()
        lbl_seo_title = QLabel("🎯 BỘ THẺ SEO (TITLES, DESCRIPTION, TAGS)")
        lbl_seo_title.setStyleSheet("color: #cbd5e1; font-weight: bold; font-size: 12px;")
        seo_header.addWidget(lbl_seo_title)
        seo_header.addStretch()

        btn_copy_seo = QPushButton("📋 Sao chép")
        btn_copy_seo.setStyleSheet("background-color: #1e293b; color: #94a3b8; font-size: 11px; padding: 4px 10px; border-radius: 4px;")
        btn_copy_seo.clicked.connect(self._copy_seo)
        seo_header.addWidget(btn_copy_seo)
        layout_seo.addLayout(seo_header)

        self.txt_seo = QTextEdit()
        self.txt_seo.setPlaceholderText("Thông tin SEO (Tiêu đề đề xuất, Mô tả, Tags) sẽ hiển thị ở đây...")
        self.txt_seo.setStyleSheet("""
            QTextEdit {
                background-color: #070b14;
                color: #cbd5e1;
                border: 1px solid #1e293b;
                border-radius: 6px;
                padding: 10px;
                font-size: 12px;
                line-height: 1.4;
            }
        """)
        layout_seo.addWidget(self.txt_seo)

        self.output_splitter.addWidget(box_seo)
        self.output_splitter.setSizes([600, 450])

        review_layout.addWidget(self.output_splitter)
        self.card_review.setVisible(False)
        content_layout.addWidget(self.card_review)

    def generate_script(self):
        topic = self.txt_topic.toPlainText().strip()
        if not topic:
            QMessageBox.warning(self, "Lỗi", "Vui lòng nhập chủ đề trước khi tạo kịch bản!")
            return
            
        audience = self.combo_audience.currentText()
        style = self.combo_style.currentText()
        language = self.combo_language.currentText()
        duration = self.combo_duration.currentText().strip()
        if not duration:
            duration = "3 - 5 phút"
            
        self.btn_generate.setEnabled(False)
        self.btn_generate.setText("⏳ Đang viết Kịch bản & Tối ưu SEO theo Rules...")
        self.progress_bar.setVisible(True)
        
        self.worker = ScriptGeneratorWorker(topic, audience, style, language, duration)
        self.worker.success_signal.connect(self.on_success)
        self.worker.error_signal.connect(self.on_error)
        self.worker.start()

    def on_success(self, data: dict):
        self.btn_generate.setEnabled(True)
        self.btn_generate.setText("✨ Tạo Kịch Bản 1-Click (Tuân thủ Rules Nhật)")
        self.progress_bar.setVisible(False)

        # Ẩn input card, ẩn guide card, mở review card
        self.card_input.setVisible(False)
        self.card_guide.setVisible(False)
        self.card_review.setVisible(True)
        self.btn_toggle_view.setVisible(True)
        self.btn_toggle_view.setText("🔄 Sửa cấu hình / Tạo lại")

        script_text = data.get("script", "")
        self.txt_script.setPlainText(script_text)

        seo_text = ""
        seo_text += "🔥 5 TIÊU ĐỀ ĐỀ XUẤT:\n"
        for i, title in enumerate(data.get("titles", [])):
            seo_text += f"{i+1}. {title}\n"
            
        seo_text += "\n📝 MÔ TẢ (DESCRIPTION):\n"
        seo_text += f"{data.get('description', '')}\n"
        
        seo_text += "\n🏷️ TAGS:\n"
        seo_text += ", ".join(data.get("tags", [])) + "\n"
        
        seo_text += "\n#️⃣ HASHTAGS:\n"
        seo_text += " ".join(data.get("hashtags", [])) + "\n"
        
        self.txt_seo.setPlainText(seo_text)
        self._update_stats()

    def on_error(self, error_msg):
        self.btn_generate.setEnabled(True)
        self.btn_generate.setText("✨ Tạo Kịch Bản 1-Click (Tuân thủ Rules Nhật)")
        self.progress_bar.setVisible(False)
        QMessageBox.critical(self, "Lỗi sinh kịch bản", f"Không thể tạo kịch bản:\n{error_msg}")

    def _toggle_input_view(self):
        """Bật/tắt giữa chế độ nhập cấu hình và xem kết quả."""
        is_input_visible = self.card_input.isVisible()
        if is_input_visible:
            # Chuyển sang xem kết quả nếu đã có kịch bản
            if self.txt_script.toPlainText().strip():
                self.card_input.setVisible(False)
                self.card_guide.setVisible(False)
                self.card_review.setVisible(True)
                self.btn_toggle_view.setText("✏️ Sửa cấu hình / Tạo lại")
        else:
            # Chuyển sang hiển thị form cấu hình
            self.card_input.setVisible(True)
            self.card_review.setVisible(True) # Để hiển thị song song nếu người dùng muốn đối chiếu
            self.btn_toggle_view.setText("👁️ Xem kết quả kịch bản")

    def _update_stats(self):
        text = self.txt_script.toPlainText()
        char_count = len(text)
        word_count = len(text.split())
        self.lbl_stats.setText(f"Ký tự: {char_count:,} | Từ: {word_count:,}")

    def _copy_script(self):
        text = self.txt_script.toPlainText()
        if text:
            QApplication.clipboard().setText(text)
            QMessageBox.information(self, "Đã sao chép", "Đã sao chép toàn bộ lời thoại vào Clipboard!")

    def _copy_seo(self):
        text = self.txt_seo.toPlainText()
        if text:
            QApplication.clipboard().setText(text)
            QMessageBox.information(self, "Đã sao chép", "Đã sao chép bộ thẻ SEO vào Clipboard!")

    def get_state(self):
        """Lấy trạng thái dữ liệu hiện tại để lưu Session."""
        return {
            "topic": self.txt_topic.toPlainText(),
            "language": self.combo_language.currentText(),
            "duration": self.combo_duration.currentText(),
            "audience": self.combo_audience.currentText(),
            "style": self.combo_style.currentText(),
            "script": self.txt_script.toPlainText(),
            "seo": self.txt_seo.toPlainText()
        }

    def set_state(self, state: dict):
        """Phục hồi trạng thái từ Session cũ."""
        if not state:
            return
            
        self.txt_topic.setPlainText(state.get("topic", ""))
        
        lang = state.get("language")
        if lang:
            idx = self.combo_language.findText(lang)
            if idx >= 0: self.combo_language.setCurrentIndex(idx)
            
        dur = state.get("duration")
        if dur:
            idx = self.combo_duration.findText(dur)
            if idx >= 0:
                self.combo_duration.setCurrentIndex(idx)
            else:
                self.combo_duration.setEditText(dur)
                
        aud = state.get("audience")
        if aud:
            idx = self.combo_audience.findText(aud)
            if idx >= 0: self.combo_audience.setCurrentIndex(idx)
            
        style = state.get("style")
        if style:
            idx = self.combo_style.findText(style)
            if idx >= 0: self.combo_style.setCurrentIndex(idx)
            
        script_text = state.get("script", "")
        seo_text = state.get("seo", "")
        
        if script_text.strip() or seo_text.strip():
            self.txt_script.setPlainText(script_text)
            self.txt_seo.setPlainText(seo_text)
            self.card_input.setVisible(False)
            self.card_guide.setVisible(False)
            self.card_review.setVisible(True)
            self.btn_toggle_view.setVisible(True)
            self.btn_toggle_view.setText("🔄 Sửa cấu hình / Tạo lại")
            self._update_stats()
        else:
            self.card_input.setVisible(True)
            self.card_guide.setVisible(True)
            self.card_review.setVisible(False)
            self.btn_toggle_view.setVisible(False)
