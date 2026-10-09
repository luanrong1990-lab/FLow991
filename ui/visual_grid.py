"""
ui/visual_grid.py - Giao diện quản lý lưới Visual Prompts và hình ảnh.
"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, 
    QScrollArea, QTextEdit, QFrame, QMessageBox, QComboBox,
    QGroupBox, QFormLayout, QLineEdit, QDialog, QDialogButtonBox,
    QListWidget, QListWidgetItem, QFileDialog
)
from PySide6.QtCore import Qt, Signal, QThread, QTimer
from PySide6.QtGui import QPixmap

from visual.prompt_engine import VisualPromptEngine
from visual.image_provider import MockImageProvider
from utils.logger import app_logger
import os

class AutoPromptWorker(QThread):
    progress_signal = Signal(str)
    success_signal = Signal(list)
    error_signal = Signal(str)

    def __init__(self, script_text, segments, character_descriptions=""):
        super().__init__()
        self.script_text = script_text
        self.segments = segments
        self.character_descriptions = character_descriptions

    def run(self):
        try:
            self.progress_signal.emit("Đang gọi AI sinh Visual Prompts...")
            engine = VisualPromptEngine()
            results = engine.generate_prompts(
                self.script_text, self.segments, 
                character_descriptions=self.character_descriptions
            )
            self.success_signal.emit(results)
        except Exception as e:
            self.error_signal.emit(str(e))


class SingleFlowkitImageWorker(QThread):
    finished_signal = Signal(str, str, bool) # id, image_path, success
    error_signal = Signal(str, str)
    
    def __init__(self, seg_id, prompt, project_dir, character_media_ids=None):
        super().__init__()
        self.seg_id = seg_id
        self.prompt = prompt
        self.project_dir = project_dir
        self.character_media_ids = character_media_ids or []

    def run(self):
        import requests
        import urllib.request
        from config.config_manager import load_settings
        
        settings = load_settings()
        flow_project_id = settings.get("FLOW_PROJECT_ID", "85222c0e-de50-4e6f-85dd-0d33d1eb127d")
        dest_dir = os.path.join(self.project_dir, "images")
        os.makedirs(dest_dir, exist_ok=True)
        dest_path = os.path.join(dest_dir, f"{self.seg_id}.png")
        
        payload = {
            "prompt": self.prompt,
            "project_id": flow_project_id,
            "aspect_ratio": "IMAGE_ASPECT_RATIO_LANDSCAPE",
            "count": 1
        }
        if self.character_media_ids:
            payload["character_media_ids"] = self.character_media_ids
            
        try:
            res = requests.post("http://127.0.0.1:8100/api/flow/generate-image", json=payload, timeout=300)
            if res.status_code == 200:
                data = res.json()
                media_list = data.get("media", [])
                if media_list and "image" in media_list[0]:
                    url = media_list[0]["image"].get("generatedImage", {}).get("fifeUrl")
                    if url:
                        urllib.request.urlretrieve(url, dest_path)
                        self.finished_signal.emit(self.seg_id, dest_path, True)
                        return
            err_msg = f"HTTP {res.status_code}: {res.text}"
            app_logger.error(f"Single image gen error: {err_msg}")
            self.error_signal.emit(self.seg_id, err_msg)
            self.finished_signal.emit(self.seg_id, "", False)
        except Exception as e:
            app_logger.error(f"Single image gen exception: {e}")
            self.error_signal.emit(self.seg_id, str(e))
            self.finished_signal.emit(self.seg_id, "", False)


class VisualCard(QFrame):
    def __init__(self, seg_id, text, prompt="", image_path="", start=0.0, end=0.0, duration=0.0):
        super().__init__()
        self.seg_id = seg_id
        self.text = text
        self.image_path = image_path
        self.start = start
        self.end = end
        self.duration = duration
        
        self.setStyleSheet("""
            QFrame { background-color: #0d121f; border: 1px solid #1e293b; border-radius: 8px; margin-bottom: 10px; }
            QLabel { border: none; }
            QTextEdit { background-color: #1a2234; border: 1px solid #334155; border-radius: 4px; color: #ffffff; }
        """)
        
        layout = QHBoxLayout(self)
        
        # Cột trái: Thông tin text
        left_layout = QVBoxLayout()
        timeline_str = f" [{start}s - {end}s] ({duration}s)" if duration > 0 else ""
        lbl_id = QLabel(f"<b>{seg_id}</b> <span style='color:#3b82f6; font-size:11px;'>{timeline_str}</span>")
        lbl_id.setStyleSheet("color: #f59e0b;")
        
        lbl_text = QLabel(f"<i>{text}</i>")
        lbl_text.setWordWrap(True)
        lbl_text.setStyleSheet("color: #9ca3af; margin-bottom: 10px;")
        
        self.txt_prompt = QTextEdit(prompt)
        self.txt_prompt.setPlaceholderText("Nhập Image Prompt tiếng Anh tại đây...")
        self.txt_prompt.setMaximumHeight(60)
        
        # Hàng nút công cụ bên trái (Play Audio, Effects)
        tools_layout = QHBoxLayout()
        self.btn_play_audio = QPushButton("▶ Phát thoại")
        self.btn_play_audio.setToolTip("Nghe lại đoạn thoại này")
        self.btn_play_audio.setStyleSheet("background-color: #4b5563; padding: 4px 8px; border-radius: 4px;")
        
        self.combo_effect = QComboBox()
        self.combo_effect.addItems(["Hiệu ứng: Tĩnh (None)", "Random", "Zoom In", "Zoom Out", "Pan Left", "Pan Right", "Pan Up", "Pan Down"])
        self.combo_effect.setToolTip("Chọn hiệu ứng chuyển động khi xuất Video")
        
        tools_layout.addWidget(self.btn_play_audio)
        tools_layout.addWidget(QLabel("Motion:"))
        tools_layout.addWidget(self.combo_effect)
        tools_layout.addStretch()
        
        left_layout.addWidget(lbl_id)
        left_layout.addWidget(lbl_text)
        left_layout.addWidget(self.txt_prompt)
        left_layout.addLayout(tools_layout)
        
        # Cột phải: Image và các nút liên quan ảnh
        right_layout = QVBoxLayout()
        
        self.lbl_image = QLabel("Chưa có ảnh")
        self.lbl_image.setFixedSize(240, 135) # 16:9 ratio
        self.lbl_image.setAlignment(Qt.AlignCenter)
        self.lbl_image.setStyleSheet("background-color: #070a12; border: 1px dashed #334155;")
        
        img_btns_layout = QHBoxLayout()
        self.btn_gen_img = QPushButton("Tạo Ảnh (AI)")
        self.btn_gen_img.setStyleSheet("background-color: #3b82f6; color: white; border-radius: 4px; padding: 5px;")
        
        self.btn_replace_img = QPushButton("Thay Ảnh")
        self.btn_replace_img.setToolTip("Tải ảnh từ máy tính")
        self.btn_replace_img.setStyleSheet("background-color: #10b981; color: white; border-radius: 4px; padding: 5px;")
        self.btn_replace_img.clicked.connect(self._replace_image)
        
        img_btns_layout.addWidget(self.btn_gen_img)
        img_btns_layout.addWidget(self.btn_replace_img)
        
        right_layout.addWidget(self.lbl_image)
        right_layout.addLayout(img_btns_layout)
        
        layout.addLayout(left_layout, stretch=3)
        layout.addLayout(right_layout, stretch=1)
        
        if image_path and os.path.exists(image_path):
            self.set_image(image_path)
            
    def _replace_image(self):
        from PySide6.QtWidgets import QFileDialog
        path, _ = QFileDialog.getOpenFileName(self, "Chọn ảnh thay thế", "", "Images (*.png *.jpg *.jpeg *.webp)")
        if path:
            self.set_image(path)
            
    def get_prompt(self):
        return self.txt_prompt.toPlainText().strip()
        
    def get_effect(self):
        return self.combo_effect.currentText().replace("Hiệu ứng: ", "")
        
    def set_effect(self, effect_name):
        if effect_name:
            idx = self.combo_effect.findText(effect_name, Qt.MatchContains)
            if idx >= 0:
                self.combo_effect.setCurrentIndex(idx)
        
    def mousePressEvent(self, event):
        super().mousePressEvent(event)
        main_win = self.window()
        if hasattr(main_win, 'update_live_preview'):
            main_win.update_live_preview(getattr(self, 'image_path', ''), self.text)
        
    def set_image(self, path):
        self.image_path = path
        pixmap = QPixmap(path)
        if not pixmap.isNull():
            self.lbl_image.setPixmap(pixmap.scaled(self.lbl_image.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation))
            self.lbl_image.setText("")
        main_win = self.window()
        if hasattr(main_win, 'update_live_preview'):
            main_win.update_live_preview(path, self.text)
            
    def get_state(self):
        return {
            "id": self.seg_id,
            "text": self.text,
            "prompt": self.get_prompt(),
            "image_path": self.image_path,
            "effect": self.get_effect(),
            "start": getattr(self, "start", 0.0),
            "end": getattr(self, "end", 0.0),
            "duration": getattr(self, "duration", 0.0)
        }


class VisualGridPanel(QWidget):
    def __init__(self):
        super().__init__()
        self.cards = []
        self.flow_controller = None
        
        # Khởi tạo thư viện persistent
        from visual.library_manager import StyleLibrary, CharacterLibrary
        self.style_library = StyleLibrary()
        self.character_library = CharacterLibrary()
        
        self._init_ui()
        
    def set_flow_controller(self, controller):
        self.flow_controller = controller

    def _init_ui(self):
        layout = QVBoxLayout(self)
        
        # Header
        header_layout = QHBoxLayout()
        lbl_title = QLabel("🎨 Lưới Phân Cảnh & Quản Lý Prompt (Storyboard)")
        lbl_title.setStyleSheet("font-size: 17px; font-weight: 800; color: #f8fafc;")
        
        self.btn_sync = QPushButton("🔄 Đồng bộ từ Voicevox")
        self.btn_sync.setStyleSheet("background-color: #1e293b; color: #cbd5e1; font-weight: 600; padding: 6px 12px; border-radius: 6px;")
        self.btn_sync.clicked.connect(self.sync_from_voice)
        
        self.btn_auto_prompt = QPushButton("⚡ Tự động sinh Prompts AI")
        self.btn_auto_prompt.setStyleSheet("background-color: #10b981; color: white; font-weight: bold; padding: 6px 14px; border-radius: 6px;")
        self.btn_auto_prompt.clicked.connect(self.run_auto_prompt)
        
        self.btn_generate_all = QPushButton("🚀 Tạo toàn bộ ảnh (Queue)")
        self.btn_generate_all.setStyleSheet("background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #2563eb, stop:1 #4f46e5); color: white; font-weight: bold; padding: 6px 16px; border-radius: 6px;")
        self.btn_generate_all.clicked.connect(self.generate_all_images)
        
        self.btn_export = QPushButton("📥 Xuất Prompts")
        self.btn_export.setStyleSheet("background-color: #1e293b; color: #cbd5e1; padding: 6px 10px; border-radius: 6px;")
        self.btn_export.clicked.connect(self.export_prompts)
        
        self.btn_import = QPushButton("📤 Nhập Ảnh")
        self.btn_import.setStyleSheet("background-color: #1e293b; color: #cbd5e1; padding: 6px 10px; border-radius: 6px;")
        self.btn_import.clicked.connect(self.import_images_batch)
        
        header_layout.addWidget(lbl_title)
        header_layout.addStretch()
        
        from PySide6.QtWidgets import QComboBox
        self.combo_global_effect = QComboBox()
        self.combo_global_effect.addItems(["Hiệu ứng: Tĩnh (None)", "Random", "Zoom In", "Zoom Out", "Pan Left", "Pan Right", "Pan Up", "Pan Down"])
        self.combo_global_effect.setStyleSheet("padding: 6px 10px; background-color: #1e293b; color: white; border-radius: 6px; font-weight: 600;")
        self.combo_global_effect.currentIndexChanged.connect(self.apply_global_effect)
        
        header_layout.addWidget(self.btn_sync)
        header_layout.addWidget(self.combo_global_effect)
        header_layout.addWidget(self.btn_export)
        header_layout.addWidget(self.btn_import)
        header_layout.addWidget(self.btn_auto_prompt)
        header_layout.addWidget(self.btn_generate_all)
        layout.addLayout(header_layout)
        
        # === CHỌN PHONG CÁCH HÌNH ẢNH (Visual Style) ===
        style_frame = QFrame()
        style_frame.setStyleSheet("QFrame { background-color: #111827; border: 1px solid #374151; border-radius: 6px; padding: 8px; }")
        style_layout = QHBoxLayout(style_frame)
        style_layout.setContentsMargins(10, 5, 10, 5)
        
        lbl_style = QLabel("🎨 Phong cách hình ảnh:")
        lbl_style.setStyleSheet("color: #f59e0b; font-weight: bold; border: none;")
        
        self.combo_visual_style = QComboBox()
        self.combo_visual_style.setMinimumWidth(250)
        self.combo_visual_style.setStyleSheet("padding: 5px; background-color: #1f2937; color: white; border: 1px solid #4b5563;")
        
        # Tải styles từ thư viện (saved + defaults)
        self._reload_style_combo()
        
        self.combo_visual_style.setEditable(True)  # Cho phép nhập style tùy chỉnh
        self.combo_visual_style.setCurrentIndex(0)
        
        # Nút phân tích ảnh mẫu
        self.btn_analyze_style = QPushButton("🖼️ Phân tích ảnh mẫu")
        self.btn_analyze_style.setStyleSheet("background-color: #8b5cf6; color: white; padding: 6px; border-radius: 4px;")
        self.btn_analyze_style.setToolTip("Tải ảnh mẫu lên → AI phân tích phong cách → Áp dụng cho dự án")
        self.btn_analyze_style.clicked.connect(self._analyze_reference_image)
        
        # Thumbnail ảnh mẫu (nhỏ)
        self.lbl_ref_thumb = QLabel()
        self.lbl_ref_thumb.setFixedSize(40, 40)
        self.lbl_ref_thumb.setStyleSheet("border: 1px solid #4b5563; border-radius: 4px; background-color: #1f2937;")
        self.lbl_ref_thumb.setAlignment(Qt.AlignCenter)
        self.lbl_ref_thumb.setToolTip("Ảnh mẫu tham khảo")
        self.lbl_ref_thumb.hide()  # Ẩn khi chưa có ảnh
        
        lbl_style_hint = QLabel("⬅ Style áp dụng cho TẤT CẢ ảnh")
        lbl_style_hint.setStyleSheet("color: #6b7280; font-size: 11px; font-style: italic; border: none;")
        
        style_layout.addWidget(lbl_style)
        style_layout.addWidget(self.combo_visual_style)
        style_layout.addWidget(self.btn_analyze_style)
        style_layout.addWidget(self.lbl_ref_thumb)
        style_layout.addWidget(lbl_style_hint)
        style_layout.addStretch()
        
        layout.addWidget(style_frame)
        
        # === QUẢN LÝ NHÂN VẬT (Character Consistency) ===
        self.char_group = QGroupBox("👤 Quản lý Nhân vật (Character Consistency)")
        self.char_group.setCheckable(True)
        self.char_group.setChecked(False)  # Mặc định thu gọn
        self.char_group.setStyleSheet("""
            QGroupBox { 
                font-weight: bold; color: #f59e0b; border: 1px solid #334155; 
                border-radius: 6px; margin-top: 10px; padding-top: 20px;
            }
            QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 5px; }
        """)
        
        char_layout = QVBoxLayout()
        
        # Nút điều khiển
        char_btn_layout = QHBoxLayout()
        self.btn_auto_detect_chars = QPushButton("🔍 Tự động phát hiện nhân vật (AI)")
        self.btn_auto_detect_chars.setStyleSheet("background-color: #8b5cf6; color: white; padding: 6px;")
        self.btn_auto_detect_chars.clicked.connect(self._auto_detect_characters)
        
        self.btn_add_char = QPushButton("➕ Thêm nhân vật")
        self.btn_add_char.clicked.connect(self._add_character_dialog)
        
        self.btn_remove_char = QPushButton("🗑️ Xóa")
        self.btn_remove_char.clicked.connect(self._remove_selected_character)
        
        char_btn_layout.addWidget(self.btn_auto_detect_chars)
        char_btn_layout.addWidget(self.btn_add_char)
        char_btn_layout.addWidget(self.btn_remove_char)
        char_btn_layout.addStretch()
        
        # Nút lưu/tải từ thư viện
        self.btn_save_chars_lib = QPushButton("💾 Lưu vào Thư viện")
        self.btn_save_chars_lib.setToolTip("Lưu nhân vật dự án hiện tại để tái sử dụng cho dự án khác")
        self.btn_save_chars_lib.clicked.connect(self._save_characters_to_library)
        
        self.btn_load_chars_lib = QPushButton("📂 Tải từ Thư viện")
        self.btn_load_chars_lib.setToolTip("Tải nhân vật đã lưu từ dự án trước")
        self.btn_load_chars_lib.clicked.connect(self._load_characters_from_library)
        
        char_btn_layout.addWidget(self.btn_save_chars_lib)
        char_btn_layout.addWidget(self.btn_load_chars_lib)
        
        char_layout.addLayout(char_btn_layout)
        
        # Danh sách nhân vật
        self.list_characters = QListWidget()
        self.list_characters.setMaximumHeight(120)
        self.list_characters.setStyleSheet("background-color: #1a2234; color: #e2e8f0; border: 1px solid #334155;")
        self.list_characters.itemDoubleClicked.connect(self._edit_character_dialog)
        char_layout.addWidget(self.list_characters)
        
        # Label mô tả ngắn
        self.lbl_char_info = QLabel("💡 Nhân vật sẽ được đưa vào prompt để đảm bảo nhất quán hình ảnh xuyên suốt video.")
        self.lbl_char_info.setStyleSheet("color: #6b7280; font-size: 11px; font-style: italic;")
        self.lbl_char_info.setWordWrap(True)
        char_layout.addWidget(self.lbl_char_info)
        
        self.char_group.setLayout(char_layout)
        layout.addWidget(self.char_group)
        
        # Khởi tạo CharacterManager
        self._init_character_manager()
        
        # Scroll Area cho các Cards
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setStyleSheet("QScrollArea { border: none; background-color: transparent; }")
        
        self.scroll_content = QWidget()
        self.scroll_layout = QVBoxLayout(self.scroll_content)
        self.scroll_layout.setAlignment(Qt.AlignTop)
        
        self.scroll_area.setWidget(self.scroll_content)
        layout.addWidget(self.scroll_area)
        
        from ui.queue_panel import QueueManagerPanel
        self.queue_panel = QueueManagerPanel(self)
        self.queue_panel.setVisible(False)
        layout.addWidget(self.queue_panel)
        
        self.lbl_status = QLabel("Sẵn sàng.")
        self.lbl_status.setStyleSheet("color: #9ca3af; font-style: italic;")
        layout.addWidget(self.lbl_status)
        
    def apply_global_effect(self, index):
        if index == 0:
            return
        
        effect_index = index - 1
        for card in self.cards:
            if hasattr(card, 'combo_effect'):
                card.combo_effect.setCurrentIndex(effect_index)
                
        self.combo_global_effect.setCurrentIndex(0) # Reset lại
        self.lbl_status.setText(f"Đã áp dụng hiệu ứng hàng loạt cho {len(self.cards)} ảnh.")
        
    def export_prompts(self):
        import csv
        from config.config_manager import load_settings
        settings = load_settings()
        proj_dir = settings.get("PROJECT_DIR", os.getcwd())
        
        path, filter_type = QFileDialog.getSaveFileName(
            self, "Xuất Prompts ra file", proj_dir, "Excel CSV (*.csv);;Text File (*.txt)"
        )
        
        if not path: return
            
        try:
            if path.endswith('.csv'):
                with open(path, 'w', newline='', encoding='utf-8') as f:
                    writer = csv.writer(f)
                    writer.writerow(["Index", "File Name", "Segment ID", "Duration", "Prompt"])
                    for i, card in enumerate(self.cards):
                        writer.writerow([
                            i+1, f"{i+1:03d}.png", card.seg_id, 
                            f"{card.duration:.2f}s", card.get_prompt()
                        ])
            else:
                with open(path, 'w', encoding='utf-8') as f:
                    for i, card in enumerate(self.cards):
                        f.write(f"--- File: {i+1:03d}.png | {card.seg_id} | {card.duration:.2f}s ---\n")
                        f.write(f"{card.get_prompt()}\n\n")
                        
            QMessageBox.information(self, "Thành công", f"Đã xuất toàn bộ prompts ra:\n{path}")
        except Exception as e:
            QMessageBox.critical(self, "Lỗi", f"Không thể xuất file:\n{e}")

    def import_images_batch(self):
        import shutil
        import re
        from config.config_manager import load_settings
        settings = load_settings()
        proj_dir = settings.get("PROJECT_DIR", os.getcwd())
        
        dir_path = QFileDialog.getExistingDirectory(self, "Chọn thư mục chứa ảnh đã tạo (VD: 001.png, 002.png...)")
        if not dir_path: return
            
        img_files = [f for f in os.listdir(dir_path) if f.lower().endswith(('.png', '.jpg', '.jpeg', '.webp'))]
        if not img_files:
            QMessageBox.warning(self, "Trống", "Không tìm thấy file ảnh nào trong thư mục này!")
            return
            
        dest_dir = os.path.join(proj_dir, "images")
        os.makedirs(dest_dir, exist_ok=True)
        
        matched_count = 0
        for img_file in img_files:
            # Tìm số trong tên file (VD: 001.png -> 1)
            match = re.search(r'\d+', img_file)
            if match:
                idx = int(match.group()) - 1
                if 0 <= idx < len(self.cards):
                    card = self.cards[idx]
                    src = os.path.join(dir_path, img_file)
                    dest = os.path.join(dest_dir, f"{card.seg_id}.png")
                    shutil.copy2(src, dest)
                    card.set_image(dest)
                    matched_count += 1
                    
        QMessageBox.information(self, "Thành công", f"Đã nhập và khớp thành công {matched_count}/{len(self.cards)} ảnh!")
        self.lbl_status.setText(f"Vừa nhập thủ công {matched_count} ảnh.")
        
    def sync_from_voice(self):
        """Lấy danh sách segment từ Voice Panel"""
        # Hack để truy cập MainWindow
        main_win = self.window()
        if hasattr(main_win, 'tab_voice'):
            voice_state = main_win.tab_voice.get_state()
            segments = voice_state.get("segments", [])
            if not segments:
                QMessageBox.warning(self, "Trống", "Không tìm thấy đoạn hội thoại nào. Hãy chạy Phase 3 trước.")
                return
                
            self._build_cards(segments)
            self.lbl_status.setText(f"Đã đồng bộ {len(segments)} đoạn hội thoại.")

    def _build_cards(self, segments):
        # Xóa cũ
        for card in self.cards:
            self.scroll_layout.removeWidget(card)
            card.deleteLater()
        self.cards.clear()
        
        # Tạo mới
        for seg in segments:
            card = VisualCard(
                seg["id"], 
                seg.get("text", ""),
                start=seg.get("start", 0.0),
                end=seg.get("end", 0.0),
                duration=seg.get("duration", 0.0)
            )
            card.btn_gen_img.clicked.connect(lambda checked=False, c=card: self.generate_image_for_card(c))
            self.scroll_layout.addWidget(card)
            self.cards.append(card)

    def run_auto_prompt(self):
        if not self.cards:
            QMessageBox.warning(self, "Lỗi", "Chưa có Segments nào. Vui lòng đồng bộ trước.")
            return
            
        main_win = self.window()
        script_text = ""
        # Ưu tiên 1: Kịch bản gốc
        if hasattr(main_win, 'tab_script'):
            script_text = main_win.tab_script.get_state().get("script", "").strip()
            
        # Ưu tiên 2: ASR Text từ Voice
        if not script_text and hasattr(main_win, 'tab_voice'):
            voice_segments = main_win.tab_voice.get_state().get("segments", [])
            if voice_segments:
                script_text = "\n\n".join([seg.get("text", "") for seg in voice_segments])
                
        # Ưu tiên 3: Từ Card
        if not script_text and self.cards:
            script_text = "\n\n".join([c.text for c in self.cards])
            
        # Thu thập các đoạn kèm theo timeline
        segments = [
            {
                "id": c.seg_id, 
                "text": c.text,
                "start": getattr(c, "start", 0.0),
                "end": getattr(c, "end", 0.0),
                "duration": getattr(c, "duration", 0.0)
            } for c in self.cards
        ]
        
        # Lấy phong cách hình ảnh đã chọn (bỏ icon prefix)
        global_style = self._get_clean_style_text()
        
        # Lưu style đã sử dụng vào thư viện
        self.style_library.mark_used(global_style)
        
        # Lấy mô tả nhân vật để đảm bảo tính nhất quán
        char_desc = ""
        if self.character_manager and self.character_manager.get_all_characters():
            # Đồng bộ visual_style của tất cả nhân vật theo global style
            for char in self.character_manager.get_all_characters():
                char.visual_style = global_style
            char_desc = self.character_manager.build_all_descriptions()
            self.lbl_status.setText(f"Đang sinh prompts ({len(self.character_manager.get_all_characters())} nhân vật, style: {global_style})...")
        else:
            self.lbl_status.setText(f"Đang sinh prompts (style: {global_style})...")
        
        # Thêm global style vào đầu character descriptions
        style_instruction = f"GLOBAL VISUAL STYLE: All images MUST be rendered in this style: \"{global_style}\". Apply this style consistently to EVERY prompt."
        if char_desc:
            char_desc = f"{style_instruction}\n\n{char_desc}"
        else:
            char_desc = style_instruction
        
        self.btn_auto_prompt.setEnabled(False)
        
        self.worker = AutoPromptWorker(script_text, segments, char_desc)
        self.worker.success_signal.connect(self.on_prompt_success)
        self.worker.error_signal.connect(self.on_prompt_error)
        self.worker.start()

    def on_prompt_success(self, results):
        self.btn_auto_prompt.setEnabled(True)
        self.lbl_status.setText("Sinh Prompts hoàn tất!")
        
        # Map kết quả vào các Card
        res_dict = {item["id"]: item.get("prompt", "") for item in results}
        for card in self.cards:
            if card.seg_id in res_dict:
                card.txt_prompt.setPlainText(res_dict[card.seg_id])
                
    def on_prompt_error(self, error):
        self.btn_auto_prompt.setEnabled(True)
        self.lbl_status.setText("Lỗi sinh Prompts.")
        QMessageBox.critical(self, "Lỗi", error)


    def get_active_character_media_ids(self):
        """Lấy danh sách media_id của các nhân vật đã được upload lên Google Flow để làm ảnh tham chiếu."""
        media_ids = []
        if not self.character_manager:
            return media_ids
            
        import requests
        from config.config_manager import load_settings
        settings = load_settings()
        flow_project_id = settings.get("FLOW_PROJECT_ID", "85222c0e-de50-4e6f-85dd-0d33d1eb127d")
        
        for char in self.character_manager.get_all_characters():
            mid = getattr(char, 'media_id', '').strip()
            ref_path = getattr(char, 'reference_image_path', '').strip()
            
            if mid:
                if mid not in media_ids:
                    media_ids.append(mid)
            elif ref_path and os.path.exists(ref_path):
                try:
                    self.lbl_status.setText(f"Đang tự động upload ảnh mẫu của {char.name} lên Google Flow...")
                    res = requests.post("http://127.0.0.1:8100/api/flow/upload-image", json={
                        "file_path": ref_path,
                        "project_id": flow_project_id
                    }, timeout=30)
                    if res.status_code == 200:
                        uploaded_mid = res.json().get("media_id")
                        if uploaded_mid:
                            char.media_id = uploaded_mid
                            if uploaded_mid not in media_ids:
                                media_ids.append(uploaded_mid)
                            self._refresh_character_list()
                except Exception as ex:
                    app_logger.error(f"Lỗi tự upload ảnh nhân vật {char.name}: {ex}")
                    
        return media_ids

    def generate_all_images(self):
        """Tạo toàn bộ ảnh thông qua Flowkit API Queue."""
        # 1. Kiểm tra kịch bản và cards
        if not self.cards:
            QMessageBox.warning(self, "Lỗi", "Chưa có danh sách phân cảnh nào để tạo ảnh.")
            return

        from config.config_manager import load_settings
        settings = load_settings()
        project_dir = settings.get("PROJECT_DIR", os.getcwd())

        # Thu thập các jobs cần làm (những card chưa có ảnh)
        jobs = []
        for card in self.cards:
            if not card.get_prompt():
                continue
            if hasattr(card, 'image_path') and card.image_path and os.path.exists(card.image_path):
                continue
            jobs.append((card.seg_id, card.get_prompt(), card))
            
        if not jobs:
            QMessageBox.information(self, "Thông báo", "Tất cả các phân cảnh đã có ảnh!")
            return
            
        # Khóa nút
        self.btn_generate_all.setEnabled(False)
        self.btn_generate_all.setText("Đang chạy Queue...")
        
        # Mở panel
        self.queue_panel.setVisible(True)
        
        # Sử dụng flowkit API, có thể chạy đa luồng đồng thời
        NUM_WORKERS = int(settings.get("MAX_WORKERS", 5))
        if NUM_WORKERS > 10: NUM_WORKERS = 10
        
        char_media_ids = self.get_active_character_media_ids()
        ref_info = f" (Đã khoá {len(char_media_ids)} ảnh mẫu)" if char_media_ids else ""
        self.lbl_status.setText(f"Đã đưa {len(jobs)} jobs vào Queue Manager ({NUM_WORKERS} workers){ref_info}")
        
        self._gen_total = len(jobs)
        self._gen_completed = 0
        self._gen_failed = 0
        self._gen_failed_cards = set()
        
        # Bắt đầu Queue kèm ảnh tham chiếu nhân vật
        self.queue_panel.start_batch(NUM_WORKERS, jobs, getattr(self, 'flow_controller', None), project_dir, character_media_ids=char_media_ids)

    def generate_image_for_card(self, card):
        prompt = card.get_prompt()
        if not prompt:
            QMessageBox.warning(self, "Lỗi", "Vui lòng sinh Prompt trước khi tạo ảnh.")
            return
            
        card.btn_gen_img.setEnabled(False)
        card.btn_gen_img.setText("Đang vẽ...")
        
        from config.config_manager import load_settings
        settings = load_settings()
        project_dir = settings.get("PROJECT_DIR", os.getcwd())
        
        char_media_ids = self.get_active_character_media_ids()
        worker = SingleFlowkitImageWorker(card.seg_id, prompt, project_dir, char_media_ids)
        setattr(self, f"worker_{card.seg_id}", worker)
        worker.finished_signal.connect(lambda sid, path, suc: self.on_image_finished(sid, path, suc, card))
        worker.error_signal.connect(lambda sid, err: self.on_image_error(sid, err, card))
        worker.start()
        
    def on_image_finished(self, seg_id, path, success, card):
        card.btn_gen_img.setEnabled(True)
        card.btn_gen_img.setText("Tạo ảnh")
        if success:
            card.set_image(path)
            card.btn_gen_img.setStyleSheet("background-color: #22c55e; color: white;")
        else:
            card.btn_gen_img.setStyleSheet("background-color: #ef4444; color: white;")
        
        # Cập nhật tiến trình tổng thể
        self._update_generation_progress(seg_id, success, card)
            
    def on_image_error(self, seg_id, error_msg, card):
        card.btn_gen_img.setEnabled(True)
        card.btn_gen_img.setText("❌ Lỗi - Bấm để thử lại")
        card.btn_gen_img.setStyleSheet("background-color: #ef4444; color: white;")
        
        # Cập nhật tiến trình (đánh dấu lỗi)
        self._update_generation_progress(seg_id, False, card, error_msg)
    
    def _update_generation_progress(self, seg_id, success, card, error_msg=None):
        """Cập nhật tiến trình và xử lý khi hoàn thành tất cả"""
        if not hasattr(self, '_gen_total') or self._gen_total == 0:
            return
        
        MAX_RETRY = 3
        
        if success:
            self._gen_completed += 1
        else:
            # Kiểm tra xem có nên auto-retry không
            retry_count = self._gen_retry_counts.get(seg_id, 0)
            if retry_count < MAX_RETRY:
                self._gen_retry_counts[seg_id] = retry_count + 1
                self._gen_failed_cards.append(card)
                self.lbl_status.setText(
                    f"⚠️ Phân cảnh {seg_id} lỗi (lần {retry_count + 1}/{MAX_RETRY}), sẽ tự động thử lại..."
                )
            else:
                self._gen_failed += 1
                self.lbl_status.setText(
                    f"❌ Phân cảnh {seg_id} lỗi sau {MAX_RETRY} lần thử. Bỏ qua."
                )
        
        done_count = self._gen_completed + self._gen_failed
        self.btn_generate_all.setText(f"⏳ Đang tạo... {done_count}/{self._gen_total}")
        
        # Kiểm tra xem đã xong tất cả chưa
        pending = self._gen_total - done_count
        retry_cards = list(self._gen_failed_cards)
        self._gen_failed_cards.clear()
        
        if pending <= 0 and not retry_cards:
            # === HOÀN THÀNH TẤT CẢ ===
            self.btn_generate_all.setEnabled(True)
            
            if self._gen_failed == 0:
                self.btn_generate_all.setText("✅ Hoàn thành! Bấm để tạo lại")
                self.btn_generate_all.setStyleSheet("background-color: #22c55e; color: white; font-weight: bold; padding: 8px;")
                self.lbl_status.setText(
                    f"🎉 Đã tạo thành công tất cả {self._gen_completed}/{self._gen_total} phân cảnh!"
                )
                QMessageBox.information(
                    self, "Hoàn thành!", 
                    f"🎉 Đã tạo xong tất cả {self._gen_completed} phân cảnh!\n\n"
                    f"Bạn có thể chuyển sang bước tiếp theo."
                )
            else:
                self.btn_generate_all.setText(f"⚠️ {self._gen_failed} lỗi - Bấm để thử lại")
                self.btn_generate_all.setStyleSheet("background-color: #f59e0b; color: white; font-weight: bold; padding: 8px;")
                self.lbl_status.setText(
                    f"✅ {self._gen_completed} thành công, ❌ {self._gen_failed} thất bại"
                )
                QMessageBox.warning(
                    self, "Hoàn thành (có lỗi)", 
                    f"✅ Thành công: {self._gen_completed}/{self._gen_total} phân cảnh\n"
                    f"❌ Thất bại: {self._gen_failed} phân cảnh (sau {MAX_RETRY} lần thử)\n\n"
                    f"Bạn có thể bấm nút 'Tạo toàn bộ ảnh' để thử lại các phân cảnh bị lỗi,\n"
                    f"hoặc vào từng phân cảnh bấm 'Tạo ảnh' để thử thủ công."
                )
        elif retry_cards:
            # === TỰ ĐỘNG THỬ LẠI CÁC CARD BỊ LỖI ===
            from PySide6.QtCore import QTimer
            def do_retry():
                for retry_card in retry_cards:
                    self.generate_image_for_card(retry_card)
            QTimer.singleShot(3000, do_retry)  # Chờ 3 giây rồi retry

    # ============================================================
    # === PHÂN TÍCH ẢNH MẪU (Reference Image Style Analysis) ===
    # ============================================================
    
    def _reload_style_combo(self):
        """Tải lại danh sách styles từ thư viện vào dropdown."""
        current_text = self.combo_visual_style.currentText() if self.combo_visual_style.count() > 0 else ""
        self.combo_visual_style.clear()
        
        # Lấy styles đã lưu
        saved = self.style_library.get_saved_styles()
        if saved:
            for s in saved:
                source_icon = "🖼️" if s.get("source") == "analyzed" else "⭐"
                self.combo_visual_style.addItem(f"{source_icon} {s['text']}")
            self.combo_visual_style.insertSeparator(len(saved))
        
        # Thêm defaults
        from visual.library_manager import StyleLibrary
        for d in StyleLibrary.DEFAULT_STYLES:
            self.combo_visual_style.addItem(d)
        
        # Khôi phục selection
        if current_text:
            # Tìm text thuần (bỏ icon prefix)
            for i in range(self.combo_visual_style.count()):
                item_text = self.combo_visual_style.itemText(i)
                clean = item_text.lstrip("🖼️⭐ ").strip()
                if clean == current_text or item_text == current_text:
                    self.combo_visual_style.setCurrentIndex(i)
                    return
            self.combo_visual_style.setCurrentText(current_text)
    
    def _get_clean_style_text(self) -> str:
        """Lấy style text thuần (bỏ icon prefix)."""
        text = self.combo_visual_style.currentText().strip()
        # Bỏ các icon prefix nếu có
        for prefix in ["🖼️ ", "⭐ "]:
            if text.startswith(prefix):
                text = text[len(prefix):]
        return text.strip()
    
    def _analyze_reference_image(self):
        """Cho user chọn ảnh mẫu → AI phân tích style → áp dụng cho dự án."""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Chọn ảnh mẫu tham khảo", "",
            "Images (*.png *.jpg *.jpeg *.webp *.bmp);;All Files (*)"
        )
        if not file_path:
            return
        
        # Hiển thị thumbnail ảnh mẫu
        pixmap = QPixmap(file_path)
        if not pixmap.isNull():
            self.lbl_ref_thumb.setPixmap(pixmap.scaled(40, 40, Qt.KeepAspectRatio, Qt.SmoothTransformation))
            self.lbl_ref_thumb.show()
            self.lbl_ref_thumb.setToolTip(f"Ảnh mẫu: {os.path.basename(file_path)}")
        
        # Phân tích trong thread riêng
        self.btn_analyze_style.setEnabled(False)
        self.btn_analyze_style.setText("⏳ Đang phân tích...")
        self.lbl_status.setText(f"AI đang phân tích style ảnh: {os.path.basename(file_path)}...")
        
        class AnalyzeWorker(QThread):
            success = Signal(str)
            error = Signal(str)
            def __init__(self, path):
                super().__init__()
                self.path = path
            def run(self):
                try:
                    from ai.gemini_provider import GeminiProvider
                    ai = GeminiProvider()
                    style = ai.analyze_image_style(self.path)
                    self.success.emit(style)
                except Exception as e:
                    self.error.emit(str(e))
        
        self._analyze_worker = AnalyzeWorker(file_path)
        self._analyze_worker.success.connect(self._on_analyze_success)
        self._analyze_worker.error.connect(self._on_analyze_error)
        self._analyze_worker.start()
    
    def _on_analyze_success(self, style_text):
        self.btn_analyze_style.setEnabled(True)
        self.btn_analyze_style.setText("🖼️ Phân tích ảnh mẫu")
        
        # Lưu style vào thư viện
        self.style_library.add_style(style_text, source="analyzed")
        
        # Refresh dropdown và chọn style mới
        self._reload_style_combo()
        # Tìm và chọn style vừa phân tích
        for i in range(self.combo_visual_style.count()):
            if style_text in self.combo_visual_style.itemText(i):
                self.combo_visual_style.setCurrentIndex(i)
                break
        
        self.lbl_status.setText(f"✅ Đã phân tích và lưu style: \"{style_text}\"")
        QMessageBox.information(
            self, "Phân tích thành công",
            f"🎨 Phong cách ảnh mẫu:\n\n\"{style_text}\"\n\n"
            f"Style đã được lưu vào thư viện và áp dụng cho dự án.\n"
            f"Bạn có thể tái sử dụng style này cho các dự án khác."
        )
    
    def _on_analyze_error(self, error):
        self.btn_analyze_style.setEnabled(True)
        self.btn_analyze_style.setText("🖼️ Phân tích ảnh mẫu")
        self.lbl_status.setText("❌ Lỗi phân tích ảnh.")
        QMessageBox.critical(self, "Lỗi", f"Không thể phân tích style ảnh:\n{error}")
    
    # ============================================================
    # === QUẢN LÝ NHÂN VẬT (Character Manager) ===
    # ============================================================
    
    def _init_character_manager(self):
        """Khởi tạo CharacterManager cho dự án hiện tại."""
        try:
            from visual.character_manager import CharacterManager
            self.character_manager = CharacterManager()
        except ImportError:
            self.character_manager = None
            app_logger.warning("Chưa có character_manager module.")
    
    def _refresh_character_list(self):
        """Cập nhật danh sách nhân vật lên UI."""
        self.list_characters.clear()
        if not self.character_manager:
            return
        for char in self.character_manager.get_all_characters():
            desc = self.character_manager.build_character_description(char.id)
            status_badge = ""
            if getattr(char, 'media_id', ''):
                status_badge = f" [🔒 Ref ID: {char.media_id[:8]}...]"
            elif getattr(char, 'reference_image_path', ''):
                status_badge = " [🖼️ Ảnh mẫu sẵn sàng]"
                
            item = QListWidgetItem(f"[{char.id}] {char.name}{status_badge} — {desc[:60]}...")
            item.setData(Qt.UserRole, char.id)
            self.list_characters.addItem(item)
        
        count = len(self.character_manager.get_all_characters())
        self.lbl_char_info.setText(
            f"✅ Đang có {count} nhân vật (Nhân vật có ảnh mẫu & Ref ID sẽ được khoá mặt xuyên suốt video). Double-click để chỉnh sửa."
            if count > 0 else
            "💡 Nhân vật sẽ được đưa vào prompt và ảnh mẫu tham chiếu để đảm bảo nhất quán hình ảnh xuyên suốt video."
        )
    
    def _auto_detect_characters(self):
        """Dùng AI phân tích kịch bản và tự động tạo nhân vật."""
        if not self.character_manager:
            QMessageBox.warning(self, "Lỗi", "CharacterManager chưa được khởi tạo.")
            return
        
        main_win = self.window()
        script_text = ""
        # Ưu tiên 1: Lấy kịch bản gốc từ Tab Script
        if hasattr(main_win, 'tab_script'):
            script_text = main_win.tab_script.get_state().get("script", "").strip()
        
        # Ưu tiên 2: Lấy từ kết quả ASR của Tab Voice (đúng ý người dùng)
        if not script_text and hasattr(main_win, 'tab_voice'):
            voice_segments = main_win.tab_voice.get_state().get("segments", [])
            if voice_segments:
                script_text = "\n\n".join([seg.get("text", "") for seg in voice_segments])
                
        # Ưu tiên 3: Lấy từ các Card đang hiển thị trên UI
        if not script_text and self.cards:
            script_text = "\n\n".join([c.text for c in self.cards])
            
        if not script_text:
            QMessageBox.warning(self, "Lỗi", "Chưa có kịch bản và phân đoạn nào. Vui lòng tạo kịch bản trước.")
            return
        
        self.btn_auto_detect_chars.setEnabled(False)
        self.btn_auto_detect_chars.setText("⏳ Đang phân tích...")
        self.lbl_status.setText("AI đang phân tích kịch bản để phát hiện nhân vật...")
        
        # Chạy trong thread riêng để không block UI
        class DetectWorker(QThread):
            success = Signal(list)
            error = Signal(str)
            def __init__(self, cm, text):
                super().__init__()
                self.cm = cm
                self.text = text
            def run(self):
                try:
                    chars = self.cm.auto_detect_characters(self.text)
                    self.success.emit(chars)
                except Exception as e:
                    self.error.emit(str(e))
        
        self._detect_worker = DetectWorker(self.character_manager, script_text)
        self._detect_worker.success.connect(self._on_detect_success)
        self._detect_worker.error.connect(self._on_detect_error)
        self._detect_worker.start()
    
    def _on_detect_success(self, chars):
        self.btn_auto_detect_chars.setEnabled(True)
        self.btn_auto_detect_chars.setText("🔍 Tự động phát hiện nhân vật (AI)")
        self._refresh_character_list()
        self.lbl_status.setText(f"✅ Phát hiện {len(chars)} nhân vật từ kịch bản!")
        QMessageBox.information(self, "Thành công", f"Đã phát hiện {len(chars)} nhân vật.\nDouble-click vào nhân vật để chỉnh sửa chi tiết.")
    
    def _on_detect_error(self, error):
        self.btn_auto_detect_chars.setEnabled(True)
        self.btn_auto_detect_chars.setText("🔍 Tự động phát hiện nhân vật (AI)")
        self.lbl_status.setText("❌ Lỗi phát hiện nhân vật.")
        QMessageBox.critical(self, "Lỗi", f"Không thể phát hiện nhân vật:\n{error}")
    
    def _add_character_dialog(self):
        """Mở dialog thêm nhân vật mới."""
        if not self.character_manager:
            return
        dialog = self._create_character_dialog("Thêm nhân vật mới")
        if dialog.exec() == QDialog.Accepted:
            from visual.character_manager import Character
            data = dialog.get_data()
            # Tạo ID tự động
            count = len(self.character_manager.get_all_characters()) + 1
            char_id = f"CHAR_{count:03d}"
            char = Character(
                id=char_id, name=data.get("name", ""), age=data.get("age", ""),
                gender=data.get("gender", ""), face=data.get("face", ""),
                hair=data.get("hair", ""), clothing=data.get("clothing", ""),
                body_type=data.get("body_type", ""), personality=data.get("personality", ""),
                visual_style=data.get("visual_style", ""), custom_tags=[],
                reference_image_path=data.get("reference_image_path", ""),
                media_id=data.get("media_id", "")
            )
            self.character_manager.add_character(char)
            self._refresh_character_list()
    
    def _edit_character_dialog(self, item):
        """Mở dialog chỉnh sửa nhân vật đã chọn."""
        if not self.character_manager:
            return
        char_id = item.data(Qt.UserRole)
        char = self.character_manager.get_character(char_id)
        if not char:
            return
        
        dialog = self._create_character_dialog("Chỉnh sửa nhân vật", char)
        if dialog.exec() == QDialog.Accepted:
            data = dialog.get_data()
            self.character_manager.update_character(char_id, **data)
            self._refresh_character_list()
    
    def _remove_selected_character(self):
        """Xóa nhân vật đang được chọn."""
        if not self.character_manager:
            return
        current = self.list_characters.currentItem()
        if not current:
            QMessageBox.warning(self, "Chưa chọn", "Vui lòng chọn nhân vật cần xóa.")
            return
        char_id = current.data(Qt.UserRole)
        reply = QMessageBox.question(self, "Xác nhận", f"Xóa nhân vật {char_id}?")
        if reply == QMessageBox.Yes:
            self.character_manager.remove_character(char_id)
            self._refresh_character_list()
    
    def _save_characters_to_library(self):
        """Lưu tất cả nhân vật dự án hiện tại vào thư viện để tái sử dụng."""
        if not self.character_manager:
            return
        chars = self.character_manager.get_all_characters()
        if not chars:
            QMessageBox.warning(self, "Trống", "Chưa có nhân vật nào để lưu.")
            return
        
        from dataclasses import asdict
        for c in chars:
            self.character_library.save_character(asdict(c))
        
        self._refresh_character_list()
        QMessageBox.information(
            self, "Đã lưu",
            f"💾 Đã lưu {len(chars)} nhân vật vào thư viện.\n"
            f"Bạn có thể tải lại trong bất kỳ dự án nào."
        )
    
    def _load_characters_from_library(self):
        """Mở dialog chọn nhân vật từ thư viện để thêm vào dự án."""
        presets = self.character_library.get_all_presets()
        if not presets:
            QMessageBox.information(self, "Thư viện trống", "Chưa có nhân vật nào trong thư viện.\nHãy tạo nhân vật rồi bấm '💾 Lưu vào Thư viện'.")
            return
        
        # Tạo dialog chọn nhân vật
        dialog = QDialog(self)
        dialog.setWindowTitle("📂 Tải nhân vật từ Thư viện")
        dialog.setMinimumWidth(500)
        dialog.setMinimumHeight(350)
        
        layout = QVBoxLayout(dialog)
        
        lbl_hint = QLabel(f"Chọn nhân vật để thêm vào dự án ({len(presets)} nhân vật trong thư viện):")
        lbl_hint.setStyleSheet("font-weight: bold; margin-bottom: 5px;")
        layout.addWidget(lbl_hint)
        
        # Danh sách nhân vật dạng checkbox
        list_widget = QListWidget()
        list_widget.setSelectionMode(QListWidget.MultiSelection)
        for p in presets:
            name = p.get("name", "?")
            age = p.get("age", "")
            gender = p.get("gender", "")
            face = p.get("face", "")[:40]
            saved_at = p.get("saved_at", "")[:10]
            
            item_text = f"{name} — {age} {gender}, {face}..."
            if saved_at:
                item_text += f"  [Lưu: {saved_at}]"
            
            item = QListWidgetItem(item_text)
            item.setData(Qt.UserRole, p)
            list_widget.addItem(item)
        
        layout.addWidget(list_widget)
        
        # Nút chọn tất cả
        btn_select_all = QPushButton("Chọn tất cả")
        btn_select_all.clicked.connect(list_widget.selectAll)
        layout.addWidget(btn_select_all)
        
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)
        
        if dialog.exec() != QDialog.Accepted:
            return
        
        # Thêm các nhân vật đã chọn vào dự án
        selected = list_widget.selectedItems()
        if not selected:
            return
        
        from visual.character_manager import Character
        added = 0
        for item in selected:
            char_data = item.data(Qt.UserRole)
            try:
                char = Character.from_dict(char_data)
                # Cập nhật ID để tránh trùng
                existing_ids = [c.id for c in self.character_manager.get_all_characters()]
                if char.id in existing_ids:
                    count = len(existing_ids) + 1
                    char.id = f"CHAR_{count:03d}"
                self.character_manager.add_character(char)
                added += 1
            except Exception:
                pass
        
        self._refresh_character_list()
        self.lbl_status.setText(f"✅ Đã tải {added} nhân vật từ thư viện.")
    
    def _create_character_dialog(self, title, char=None):
        """Tạo dialog nhập/chỉnh sửa thông tin nhân vật."""
        dialog = QDialog(self)
        dialog.setWindowTitle(title)
        dialog.setMinimumWidth(500)
        
        form = QFormLayout(dialog)
        
        fields = {}
        field_defs = [
            ("name", "Tên nhân vật", "Ông Minh"),
            ("age", "Tuổi / Mô tả tuổi", "65-year-old"),
            ("gender", "Giới tính", "male"),
            ("face", "Khuôn mặt", "warm brown eyes, weathered face, gentle smile"),
            ("hair", "Tóc", "short silver hair, neatly combed"),
            ("clothing", "Trang phục", "navy blue cardigan over white shirt"),
            ("body_type", "Dáng người", "medium build, slightly hunched"),
            ("personality", "Tính cách / Biểu cảm", "kind, gentle, wise"),
            ("visual_style", "Phong cách hình ảnh", "photorealistic, cinematic lighting"),
        ]
        
        for key, label, placeholder in field_defs:
            edit = QLineEdit()
            edit.setPlaceholderText(placeholder)
            if char and hasattr(char, key):
                edit.setText(getattr(char, key, ""))
            fields[key] = edit
            form.addRow(label + ":", edit)
        
        # Thêm mục Ảnh mẫu tham chiếu (Reference Image)
        img_row = QHBoxLayout()
        edit_img = QLineEdit()
        edit_img.setPlaceholderText("Đường dẫn ảnh nhân vật mẫu (PNG/JPG)...")
        if char and hasattr(char, "reference_image_path"):
            edit_img.setText(char.reference_image_path)
        fields["reference_image_path"] = edit_img
        
        btn_browse_img = QPushButton("📁 Chọn ảnh mẫu...")
        def _browse_ref():
            f_path, _ = QFileDialog.getOpenFileName(dialog, "Chọn ảnh nhân vật mẫu", "", "Images (*.png *.jpg *.jpeg *.webp)")
            if f_path:
                edit_img.setText(f_path)
        btn_browse_img.clicked.connect(_browse_ref)
        
        img_row.addWidget(edit_img)
        img_row.addWidget(btn_browse_img)
        form.addRow("Ảnh mẫu (Ref Image):", img_row)
        
        # Thêm mục Media ID (Google Flow)
        flow_row = QHBoxLayout()
        edit_mid = QLineEdit()
        edit_mid.setPlaceholderText("Media ID trên Google Flow (tự sinh khi upload)")
        if char and hasattr(char, "media_id"):
            edit_mid.setText(char.media_id)
        fields["media_id"] = edit_mid
        
        btn_upload_mid = QPushButton("☁️ Upload lên Flow")
        btn_upload_mid.setToolTip("Upload ảnh mẫu lên Google Flow để lấy Media ID phục vụ khoá nhân vật")
        def _upload_to_flow():
            f_path = edit_img.text().strip()
            if not f_path or not os.path.exists(f_path):
                QMessageBox.warning(dialog, "Lỗi", "Vui lòng chọn file ảnh mẫu trước.")
                return
            try:
                import requests
                btn_upload_mid.setEnabled(False)
                btn_upload_mid.setText("Đang upload...")
                res = requests.post("http://127.0.0.1:8100/api/flow/upload-image", json={
                    "file_path": f_path,
                    "project_id": "85222c0e-de50-4e6f-85dd-0d33d1eb127d"
                }, timeout=30)
                if res.status_code == 200:
                    mid = res.json().get("media_id")
                    if mid:
                        edit_mid.setText(mid)
                        QMessageBox.information(dialog, "Thành công", f"Đã upload lên Google Flow!\nMedia ID: {mid}")
                    else:
                        QMessageBox.warning(dialog, "Lỗi", "Không nhận được media_id từ server.")
                else:
                    QMessageBox.critical(dialog, "Lỗi", f"HTTP {res.status_code}: {res.text}")
            except Exception as ex:
                QMessageBox.critical(dialog, "Lỗi kết nối", f"Không thể kết nối Flowkit (port 8100):\n{ex}")
            finally:
                btn_upload_mid.setEnabled(True)
                btn_upload_mid.setText("☁️ Upload lên Flow")
                
        btn_upload_mid.clicked.connect(_upload_to_flow)
        flow_row.addWidget(edit_mid)
        flow_row.addWidget(btn_upload_mid)
        form.addRow("Flow Media ID:", flow_row)
        
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        form.addRow(buttons)
        
        def get_data():
            return {k: v.text().strip() for k, v in fields.items()}
        dialog.get_data = get_data
        
        return dialog
    
    # ============================================================
    # === STATE MANAGEMENT (Lưu/Phục hồi trạng thái dự án) ===
    # ============================================================
    
    def get_state(self):
        state = {
            "cards": [card.get_state() for card in self.cards],
            "characters": [],
            "visual_style": self.combo_visual_style.currentText()
        }
        # Lưu nhân vật vào state
        if self.character_manager:
            state["characters"] = [
                {
                    "id": c.id, "name": c.name, "age": c.age, "gender": c.gender,
                    "face": c.face, "hair": c.hair, "clothing": c.clothing,
                    "body_type": c.body_type, "personality": c.personality,
                    "visual_style": c.visual_style, "custom_tags": c.custom_tags,
                    "reference_image_path": getattr(c, "reference_image_path", ""),
                    "media_id": getattr(c, "media_id", "")
                }
                for c in self.character_manager.get_all_characters()
            ]
        return state

    def set_state(self, state_data):
        # Hỗ trợ cả format cũ (list) và format mới (dict)
        if isinstance(state_data, list):
            state_list = state_data
            characters = []
            visual_style = ""
        elif isinstance(state_data, dict):
            state_list = state_data.get("cards", [])
            characters = state_data.get("characters", [])
            visual_style = state_data.get("visual_style", "")
        else:
            return
        
        # Phục hồi phong cách hình ảnh
        if visual_style:
            idx = self.combo_visual_style.findText(visual_style)
            if idx >= 0:
                self.combo_visual_style.setCurrentIndex(idx)
            else:
                self.combo_visual_style.setCurrentText(visual_style)
            
        if not state_list:
            return
            
        # Xóa cũ
        for card in self.cards:
            self.scroll_layout.removeWidget(card)
            card.deleteLater()
        self.cards.clear()
        
        # Dựng lại từ state
        for item in state_list:
            card = VisualCard(
                item.get("id", ""), 
                item.get("text", ""), 
                item.get("prompt", ""), 
                item.get("image_path", ""),
                start=item.get("start", 0.0),
                end=item.get("end", 0.0),
                duration=item.get("duration", 0.0)
            )
            card.set_effect(item.get("effect", ""))
            card.btn_gen_img.clicked.connect(lambda checked=False, c=card: self.generate_image_for_card(c))
            self.scroll_layout.addWidget(card)
            self.cards.append(card)
        
        # Phục hồi nhân vật
        if characters and self.character_manager:
            from visual.character_manager import Character
            for ch_data in characters:
                try:
                    char = Character.from_dict(ch_data)
                    self.character_manager.add_character(char)
                except Exception:
                    pass
            self._refresh_character_list()
            
        self.lbl_status.setText("Đã khôi phục dữ liệu Visual.")

