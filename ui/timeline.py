import os
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
    QPushButton, QMessageBox, QProgressBar, QListWidget
)
from PySide6.QtCore import Qt, QThread, Signal

from utils.logger import app_logger
from video.render_engine import RenderEngine
from config.config_manager import load_settings

class RenderWorker(QThread):
    progress_signal = Signal(str)
    success_signal = Signal(str)
    error_signal = Signal(str)
    
    def __init__(self, segments, audio_path, subtitle_path, project_dir):
        super().__init__()
        self.segments = segments
        self.audio_path = audio_path
        self.subtitle_path = subtitle_path
        self.project_dir = project_dir
        
    def run(self):
        try:
            self.progress_signal.emit("Đang khởi tạo Render Engine...")
            engine = RenderEngine(self.project_dir)
            
            # TODO: Truyền callback vào render() nếu muốn update % tiến độ chi tiết
            self.progress_signal.emit("Đang render (FFmpeg đang chạy)... Vui lòng chờ vài phút.")
            
            output_path = engine.render(
                self.segments, 
                self.audio_path, 
                self.subtitle_path
            )
            
            if output_path:
                self.success_signal.emit(output_path)
            else:
                self.error_signal.emit("Render thất bại. Kiểm tra log để biết thêm chi tiết.")
        except Exception as e:
            self.error_signal.emit(str(e))

class TimelinePanel(QWidget):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        
        # Header
        lbl_title = QLabel("TIMELINE & RENDERING (PHASE 9 & 10)")
        lbl_title.setStyleSheet("font-size: 18px; font-weight: bold; color: #f59e0b; margin-bottom: 10px;")
        layout.addWidget(lbl_title)
        
        # Action Buttons
        btn_layout = QHBoxLayout()
        self.btn_sync = QPushButton("🔄 Đồng bộ Dữ liệu từ các Tab")
        self.btn_sync.setStyleSheet("background-color: #3b82f6; color: white; padding: 8px; border-radius: 4px;")
        self.btn_sync.clicked.connect(self.sync_data)
        
        self.btn_render = QPushButton("🎬 XUẤT VIDEO (RENDER MP4)")
        self.btn_render.setStyleSheet("background-color: #10b981; color: white; padding: 8px; border-radius: 4px; font-weight: bold;")
        self.btn_render.clicked.connect(self.start_render)
        self.btn_render.setEnabled(False)
        
        btn_layout.addWidget(self.btn_sync)
        btn_layout.addWidget(self.btn_render)
        layout.addLayout(btn_layout)
        
        # Summary
        self.list_summary = QListWidget()
        self.list_summary.setStyleSheet("background-color: #0d121f; border: 1px solid #1e293b; color: #e2e8f0; padding: 10px;")
        layout.addWidget(self.list_summary)
        
        # Status & Progress
        self.lbl_status = QLabel("Nhấn 'Đồng bộ Dữ liệu' để kiểm tra tài nguyên.")
        self.lbl_status.setStyleSheet("color: #9ca3af; font-style: italic;")
        
        self.progress = QProgressBar()
        self.progress.setRange(0, 0) # Indeterminate
        self.progress.setVisible(False)
        
        layout.addWidget(self.lbl_status)
        layout.addWidget(self.progress)
        
        self.timeline_data = None
        self.audio_path = None
        self.subtitle_path = None
        
    def sync_data(self):
        main_win = self.window()
        self.list_summary.clear()
        self.timeline_data = None
        self.audio_path = None
        self.subtitle_path = None
        self.btn_render.setEnabled(False)
        
        try:
            # 1. Lấy dữ liệu từ Visuals
            visual_state = main_win.tab_visuals.get_state() if hasattr(main_win, 'tab_visuals') else []
            if isinstance(visual_state, dict):
                segments = visual_state.get("cards", [])
            else:
                segments = visual_state # Format cũ
                
            if not segments:
                self.list_summary.addItem("❌ Lỗi: Chưa có dữ liệu Visual (Visual Grid trống).")
                self.btn_render.setEnabled(False)
                return
                
            # Kiểm tra ảnh
            missing_images = sum(1 for s in segments if not s.get("image_path") or not os.path.exists(s.get("image_path")))
            if missing_images > 0:
                self.list_summary.addItem(f"⚠️ Cảnh báo: Có {missing_images} đoạn chưa có ảnh!")
            else:
                self.list_summary.addItem(f"✅ Đã tải {len(segments)} đoạn có đầy đủ hình ảnh.")
                
            self.timeline_data = segments
            
            # 2. Lấy Audio file
            settings = load_settings()
            project_dir = settings.get("PROJECT_DIR", os.getcwd())
            merged_audio = os.path.join(project_dir, "audio", "merged.wav")
            if os.path.exists(merged_audio):
                self.audio_path = merged_audio
                self.list_summary.addItem(f"✅ Đã tìm thấy âm thanh gốc: {os.path.basename(merged_audio)}")
            else:
                self.list_summary.addItem("❌ Lỗi: Không tìm thấy âm thanh gốc (merged.wav). Hãy ghép âm thanh ở Tab Voice trước.")
                self.btn_render.setEnabled(False)
                return
                
            # 3. Lấy Subtitle file
            ass_path = os.path.join(project_dir, "subtitles", "subtitles.ass")
            if os.path.exists(ass_path):
                self.subtitle_path = ass_path
                self.list_summary.addItem("✅ Đã tìm thấy file Karaoke Subtitle (.ass).")
            else:
                self.list_summary.addItem("⚠️ Cảnh báo: Không tìm thấy phụ đề .ass. Chạy lại Phân tích ASR ở Tab Voice để sinh phụ đề.")
                
            # OK
            if missing_images == 0:
                self.lbl_status.setText("Sẵn sàng để Render Video.")
                self.btn_render.setEnabled(True)
            else:
                self.lbl_status.setText("Chưa hoàn thiện hình ảnh. Hãy tạo đủ ảnh trước khi Render.")
                self.btn_render.setEnabled(False)
                
        except Exception as e:
            QMessageBox.critical(self, "Lỗi Đồng bộ", f"Có lỗi xảy ra:\n{str(e)}")
            
    def start_render(self):
        if not self.timeline_data or not self.audio_path:
            return
            
        self.btn_render.setEnabled(False)
        self.btn_sync.setEnabled(False)
        self.progress.setVisible(True)
        
        settings = load_settings()
        project_dir = settings.get("PROJECT_DIR", os.getcwd())
        
        self.worker = RenderWorker(self.timeline_data, self.audio_path, self.subtitle_path, project_dir)
        self.worker.progress_signal.connect(self.update_status)
        self.worker.success_signal.connect(self.on_render_success)
        self.worker.error_signal.connect(self.on_render_error)
        self.worker.start()
        
    def update_status(self, msg):
        self.lbl_status.setText(msg)
        
    def on_render_success(self, output_path):
        self.progress.setVisible(False)
        self.btn_render.setEnabled(True)
        self.btn_sync.setEnabled(True)
        self.lbl_status.setText(f"Thành công! Video đã lưu tại:\n{output_path}")
        
        # Mở thư mục
        try:
            os.startfile(os.path.dirname(output_path))
        except:
            pass
            
    def on_render_error(self, err_msg):
        self.progress.setVisible(False)
        self.btn_render.setEnabled(True)
        self.btn_sync.setEnabled(True)
        self.lbl_status.setText("Lỗi khi render.")
        QMessageBox.critical(self, "Lỗi Render", err_msg)
