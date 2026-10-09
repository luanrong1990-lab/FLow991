"""
ui/voice_panel.py - Giao diện quản lý Âm thanh và Nhận diện giọng nói (Phase 3).

Cho phép:
1. Import nhiều file âm thanh.
2. Sắp xếp thứ tự file.
3. Ghép nối và chạy nhận diện giọng nói (ASR).
4. Hiển thị kết quả Timeline (Segments).
"""

import os
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, 
    QListWidget, QAbstractItemView, QFileDialog, QMessageBox,
    QProgressBar, QTableWidget, QTableWidgetItem, QHeaderView, QSplitter
)
from PySide6.QtCore import Qt, QThread, Signal

from audio.audio_manager import AudioManager
from audio.asr_engine import ASREngine
from utils.logger import app_logger

class ASRWorker(QThread):
    """Luồng nền xử lý việc ghép file và chạy Whisper."""
    progress_signal = Signal(str)
    success_signal = Signal(list)
    error_signal = Signal(str)
    
    def __init__(self, file_paths, output_merged_path):
        super().__init__()
        self.file_paths = file_paths
        self.output_merged_path = output_merged_path
        
    def run(self):
        try:
            if len(self.file_paths) == 1:
                self.progress_signal.emit("Đang chuẩn hóa định dạng âm thanh bằng FFmpeg...")
            else:
                self.progress_signal.emit("Đang ghép nối âm thanh bằng FFmpeg...")
                
            success = AudioManager.concatenate_audio_files(self.file_paths, self.output_merged_path)
            if not success:
                self.error_signal.emit("Lỗi trong quá trình ghép nối âm thanh. Vui lòng kiểm tra file đầu vào.")
                return
                
            self.progress_signal.emit("Đang tải mô hình AI Nhận diện giọng nói (Whisper)...")
            # Dùng model base cho tốc độ nhanh, chất lượng ổn định
            engine = ASREngine(model_size="base")
            
            self.progress_signal.emit("Đang phân tích âm thanh và chia đoạn (Có thể mất vài phút)...")
            segments = engine.analyze_audio(self.output_merged_path)
            
            self.success_signal.emit(segments)
            
        except Exception as e:
            import traceback
            err_trace = traceback.format_exc()
            app_logger.error(f"Worker Error Traceback: {err_trace}")
            self.error_signal.emit(f"Lỗi: {str(e)}\n\nChi tiết:\n{err_trace}")

class VoicevoxWorker(QThread):
    progress_signal = Signal(str)
    success_signal = Signal(str)
    error_signal = Signal(str)

    def __init__(self, script_text, output_path):
        super().__init__()
        self.script_text = script_text
        self.output_path = output_path

    def run(self):
        try:
            self.progress_signal.emit("Đang kết nối Voicevox Engine...")
            import asyncio
            from ai.voicevox_engine import VoicevoxTTS
            
            tts = VoicevoxTTS()
            if not tts.check_health():
                self.error_signal.emit("Không thể kết nối Voicevox (127.0.0.1:50021). Đảm bảo Docker Voicevox đang chạy!")
                return
                
            self.progress_signal.emit("Đang tạo giọng đọc (TTS) từ Kịch bản...")
            # Chạy async trong thread đồng bộ
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            success = loop.run_until_complete(tts.generate_audio(self.script_text, self.output_path))
            loop.close()
            
            if success:
                self.success_signal.emit(self.output_path)
            else:
                self.error_signal.emit("Lỗi trong quá trình tạo TTS từ Voicevox.")
                
        except Exception as e:
            self.error_signal.emit(f"Lỗi: {str(e)}")

class VoicePanel(QWidget):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        # Header
        header_row = QHBoxLayout()
        title_box = QVBoxLayout()
        title_box.setSpacing(2)
        lbl_title = QLabel("🎙 Lồng tiếng Voicevox & Phụ đề Karaoke")
        lbl_title.setStyleSheet("font-size: 17px; font-weight: 800; color: #f8fafc;")
        lbl_desc = QLabel("Tự động tạo giọng đọc từ kịch bản hoặc import audio có sẵn, đồng thời tự bóc tách phụ đề Karaoke.")
        lbl_desc.setStyleSheet("color: #64748b; font-size: 12px;")
        title_box.addWidget(lbl_title)
        title_box.addWidget(lbl_desc)
        header_row.addLayout(title_box)
        header_row.addStretch()
        
        lbl_badge = QLabel("Auto Whisper ASR")
        lbl_badge.setStyleSheet("""
            background-color: rgba(16, 185, 129, 0.15);
            color: #34d399;
            border: 1px solid rgba(16, 185, 129, 0.4);
            border-radius: 12px;
            padding: 4px 14px;
            font-size: 11px;
            font-weight: 700;
        """)
        header_row.addWidget(lbl_badge)
        layout.addLayout(header_row)

        # Main Splitter
        splitter = QSplitter(Qt.Horizontal)
        layout.addWidget(splitter)
        
        # --- LEFT PANEL: Quản lý File (Multi-file Import) ---
        file_widget = QWidget()
        file_layout = QVBoxLayout(file_widget)
        file_layout.setContentsMargins(0, 0, 10, 0)
        
        lbl_files = QLabel("Danh sách File Âm Thanh (Kéo thả để sắp xếp lại):")
        lbl_files
        file_layout.addWidget(lbl_files)
        
        self.list_files = QListWidget()
        # Cho phép kéo thả để sắp xếp trong nội bộ
        self.list_files.setDragDropMode(QAbstractItemView.InternalMove)
        self.list_files.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.list_files.setStyleSheet("""
            QListWidget { background-color: #0f172a; border: 1px solid #334155; border-radius: 4px; padding: 5px; }
            QListWidget::item { padding: 8px; border-bottom: 1px solid #1e293b; }
            QListWidget::item:selected { background-color: #3b82f6; }
        """)
        file_layout.addWidget(self.list_files)
        
        # Nút điều khiển File
        file_controls = QHBoxLayout()
        self.btn_tts = QPushButton("🎙 Tạo từ Kịch bản (Voicevox)")
        self.btn_tts.clicked.connect(self.run_voicevox_tts)
        btn_add = QPushButton("Thêm File")
        btn_add.clicked.connect(self.add_files)
        btn_remove = QPushButton("Xóa File")
        btn_remove.clicked.connect(self.remove_files)
        
        file_controls.addWidget(self.btn_tts)
        file_controls.addWidget(btn_add)
        file_controls.addWidget(btn_remove)
        file_layout.addLayout(file_controls)
        
        # Nút chạy ASR
        self.btn_process = QPushButton("Ghép nối & Phân tích ASR")
        self.btn_process.setFixedHeight(45)
        self.btn_process.setStyleSheet("""
            QPushButton { background-color: #10b981; color: white; font-weight: bold; font-size: 14px; border-radius: 6px; margin-top: 10px; }
            QPushButton:hover { background-color: #059669; }
            QPushButton:disabled { background-color: #1e293b; color: #64748b; }
        """)
        self.btn_process.clicked.connect(self.run_asr)
        file_layout.addWidget(self.btn_process)
        
        self.lbl_status = QLabel("")
        self.lbl_status
        file_layout.addWidget(self.lbl_status)
        
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 0)
        self.progress_bar.setFixedHeight(8)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setVisible(False)
        file_layout.addWidget(self.progress_bar)
        
        splitter.addWidget(file_widget)
        
        # --- RIGHT PANEL: Kết quả Timeline (Segments) ---
        result_widget = QWidget()
        result_layout = QVBoxLayout(result_widget)
        result_layout.setContentsMargins(10, 0, 0, 0)
        
        lbl_result = QLabel("Kết quả Phân đoạn (Segments):")
        lbl_result
        result_layout.addWidget(lbl_result)
        
        self.table_segments = QTableWidget()
        self.table_segments.setColumnCount(4)
        self.table_segments.setHorizontalHeaderLabels(["Mã", "Bắt đầu", "Thời lượng", "Nội dung thoại"])
        self.table_segments.horizontalHeader().setSectionResizeMode(3, QHeaderView.Stretch)
        self.table_segments.setStyleSheet("""
            QTableWidget { background-color: #0f172a; border: 1px solid #334155; }
            QHeaderView::section { background-color: #1e293b; padding: 4px; font-weight: bold; border: none; border-right: 1px solid #334155; }
        """)
        result_layout.addWidget(self.table_segments)
        
        splitter.addWidget(result_widget)
        splitter.setSizes([350, 650]) # Tỷ lệ chia màn hình

    def add_files(self):
        files, _ = QFileDialog.getOpenFileNames(
            self, "Chọn file âm thanh", "", "Audio Files (*.mp3 *.wav *.m4a *.flac)"
        )
        if files:
            for f in files:
                # Tránh thêm trùng
                items = [self.list_files.item(i).text() for i in range(self.list_files.count())]
                if f not in items:
                    self.list_files.addItem(f)

    def run_voicevox_tts(self):
        from config.config_manager import load_settings
        settings = load_settings()
        project_dir = settings.get("PROJECT_DIR", os.getcwd())
        script_path = os.path.join(project_dir, "script", "script.txt")
        
        if not os.path.exists(script_path):
            QMessageBox.warning(self, "Lỗi", "Không tìm thấy kịch bản (script.txt) trong thư mục Dự án. Hãy sang Tab Script để tạo trước!")
            return
            
        with open(script_path, "r", encoding="utf-8") as f:
            script_text = f.read().strip()
            
        if not script_text:
            QMessageBox.warning(self, "Lỗi", "Kịch bản trống!")
            return

        # Nơi lưu file Voicevox sẽ dùng làm gốc
        output_dir = os.path.join(project_dir, "audio")
        os.makedirs(output_dir, exist_ok=True)
        self.tts_output_path = os.path.join(output_dir, "voicevox_raw.wav")
        self.final_merged_path = os.path.join(output_dir, "merged.wav")
        
        self.btn_tts.setEnabled(False)
        self.btn_process.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.table_segments.setRowCount(0)
        
        self.tts_worker = VoicevoxWorker(script_text, self.tts_output_path)
        self.tts_worker.progress_signal.connect(self.update_status)
        self.tts_worker.success_signal.connect(self.on_tts_success)
        self.tts_worker.error_signal.connect(self.on_error)
        self.tts_worker.start()

    def on_tts_success(self, raw_audio_path):
        self.update_status("TTS hoàn tất! Đang chuyển qua Whisper ASR...")
        # Add to list automatically
        self.list_files.clear()
        self.list_files.addItem(raw_audio_path)
        
        # Now run ASR automatically on it
        self.worker = ASRWorker([raw_audio_path], self.final_merged_path)
        self.worker.progress_signal.connect(self.update_status)
        self.worker.success_signal.connect(self.on_success)
        self.worker.error_signal.connect(self.on_error)
        self.worker.start()

    def remove_files(self):
        for item in self.list_files.selectedItems():
            self.list_files.takeItem(self.list_files.row(item))

    def run_asr(self):
        file_count = self.list_files.count()
        if file_count == 0:
            QMessageBox.warning(self, "Lỗi", "Vui lòng thêm ít nhất 1 file âm thanh!")
            return
            
        file_paths = [self.list_files.item(i).text() for i in range(file_count)]
        
        # Nơi lưu file. Sử dụng thư mục dự án hiện tại (PROJECT_DIR)
        from config.config_manager import load_settings
        settings = load_settings()
        project_dir = settings.get("PROJECT_DIR", os.getcwd())
        output_dir = os.path.join(project_dir, "audio")
        os.makedirs(output_dir, exist_ok=True)
        merged_path = os.path.join(output_dir, "merged.wav")
        
        self.btn_process.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.table_segments.setRowCount(0) # Xóa kết quả cũ
        
        self.worker = ASRWorker(file_paths, merged_path)
        self.worker.progress_signal.connect(self.update_status)
        self.worker.success_signal.connect(self.on_success)
        self.worker.error_signal.connect(self.on_error)
        self.worker.start()

    def update_status(self, msg):
        self.lbl_status.setText(msg)

    def on_success(self, segments):
        self.current_segments = segments
        self.lbl_status.setText(f"Hoàn tất! Đã phân tích thành {len(segments)} segments.")
        self.progress_bar.setVisible(False)
        self.btn_process.setEnabled(True)
        self.btn_tts.setEnabled(True)
        
        self.table_segments.setRowCount(len(segments))
        for row, seg in enumerate(segments):
            self.table_segments.setItem(row, 0, QTableWidgetItem(seg["id"]))
            self.table_segments.setItem(row, 1, QTableWidgetItem(f"{seg['start']}s"))
            self.table_segments.setItem(row, 2, QTableWidgetItem(f"{seg['duration']}s"))
            
            # Hiển thị text trọn vẹn
            txt_item = QTableWidgetItem(seg["text"])
            txt_item.setToolTip(seg["text"]) 
            self.table_segments.setItem(row, 3, txt_item)
            
        self.table_segments.resizeRowsToContents()
        
        # Tự động sinh file Karaoke Subtitles (.ass) (Phase 8)
        try:
            from video.subtitle_engine import SubtitleEngine
            import os
            from config.config_manager import load_settings
            
            settings = load_settings()
            project_dir = settings.get("PROJECT_DIR", os.getcwd())
            sub_engine = SubtitleEngine(project_dir)
            ass_path = sub_engine.generate_ass(segments)
            if ass_path:
                self.lbl_status.setText(f"Đã phân tích ASR & Sinh file Karaoke Subtitle: {os.path.basename(ass_path)}")
        except Exception as e:
            app_logger.error(f"Lỗi khi sinh Karaoke Subtitles: {e}")

    def on_error(self, error_msg):
        self.lbl_status.setText("Đã xảy ra lỗi!")
        self.progress_bar.setVisible(False)
        self.btn_process.setEnabled(True)
        if hasattr(self, 'btn_tts'):
            self.btn_tts.setEnabled(True)
        QMessageBox.critical(self, "Lỗi", error_msg)

    def get_state(self):
        """Lấy trạng thái dữ liệu hiện tại để lưu Session."""
        files = [self.list_files.item(i).text() for i in range(self.list_files.count())]
        segments = getattr(self, "current_segments", [])
        
        # Cập nhật text từ table phòng trường hợp user có sửa text (tuỳ chọn)
        for row, seg in enumerate(segments):
            if row < self.table_segments.rowCount():
                seg["text"] = self.table_segments.item(row, 3).text()
                
        return {"files": files, "segments": segments}
        
    def set_state(self, state: dict):
        """Phục hồi trạng thái từ Session cũ."""
        if not state:
            return
            
        for f in state.get("files", []):
            self.list_files.addItem(f)
            
        segments = state.get("segments", [])
        self.table_segments.setRowCount(len(segments))
        for row, seg in enumerate(segments):
            self.table_segments.setItem(row, 0, QTableWidgetItem(seg["id"]))
            self.table_segments.setItem(row, 1, QTableWidgetItem(seg["start"]))
            self.table_segments.setItem(row, 2, QTableWidgetItem(seg["duration"]))
            txt_item = QTableWidgetItem(seg["text"])
            txt_item.setToolTip(seg["text"])
            self.table_segments.setItem(row, 3, txt_item)
            
        if segments:
            self.table_segments.resizeRowsToContents()
            self.lbl_status.setText("Đã khôi phục dữ liệu phiên trước.")
