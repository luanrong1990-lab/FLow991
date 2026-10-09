"""
ui/main_window.py - Giao diện Studio Stepper cho VQPVEO3PRO.

Chức năng:
1. Quy trình Stepper 5 bước trực quan (Dự án -> Kịch bản AI -> Âm thanh -> Hình ảnh -> Xuất Video).
2. Tích hợp Màn hình Live Preview 16:9 và Quick Status Summary bên phải.
3. Thanh điều hướng Tiếp tục / Quay lại dẫn dắt người dùng từ A-Z.
4. Tích hợp Flowkit, Voicevox, Channel Panel và Settings Panel.
"""

from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
    QStackedWidget, QPushButton, QLabel, QMessageBox, QApplication,
    QFrame, QSplitter
)
from PySide6.QtGui import QKeySequence, QShortcut, QPixmap, QFont
from PySide6.QtCore import Qt, Signal
import sys
import os
import subprocess
import threading

# Import các panel
from ui.project_panel import ProjectPanel
from ui.script_panel import ScriptPanel
from ui.voice_panel import VoicePanel
from ui.visual_grid import VisualGridPanel
from ui.timeline import TimelinePanel
from ui.settings_panel import SettingsPanel
from ui.channel_panel import ChannelPanel
from config.config_manager import load_settings


class LivePreviewPanel(QFrame):
    """Màn hình Live Preview 16:9 và hộp thông tin tóm tắt dự án bên phải."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumWidth(380)
        self.setMaximumWidth(450)
        self.setStyleSheet("""
            QFrame#previewPanel {
                background-color: #0b0f19;
                border-left: 1px solid #1a2234;
            }
        """)
        self.setObjectName("previewPanel")
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(14)
        
        # Header
        header = QHBoxLayout()
        header.setSpacing(8)
        
        lbl_dot = QLabel("●")
        lbl_dot.setStyleSheet("color: #38bdf8; font-size: 14px;")
        header.addWidget(lbl_dot)
        
        lbl_title = QLabel("MÀN HÌNH LIVE PREVIEW")
        lbl_title.setStyleSheet("font-weight: 800; font-size: 13px; color: #f8fafc; letter-spacing: 0.5px;")
        header.addWidget(lbl_title)
        
        header.addStretch()
        
        lbl_res = QLabel("1920x1080 (16:9)")
        lbl_res.setStyleSheet("font-size: 11px; color: #64748b; font-family: monospace; font-weight: 600;")
        header.addWidget(lbl_res)
        layout.addLayout(header)
        
        # 16:9 Aspect Ratio Container
        self.video_box = QWidget()
        self.video_box.setFixedHeight(215)
        self.video_box.setStyleSheet("background-color: #020617; border: 1px solid #1e293b; border-radius: 10px;")
        
        v_layout = QVBoxLayout(self.video_box)
        v_layout.setContentsMargins(0, 0, 0, 0)
        v_layout.setSpacing(0)
        
        # Container ảnh và mascot
        img_container = QWidget()
        img_container_layout = QVBoxLayout(img_container)
        img_container_layout.setContentsMargins(0, 0, 0, 0)
        
        self.lbl_img = QLabel()
        self.lbl_img.setAlignment(Qt.AlignCenter)
        self.lbl_img.setText("🎬 Chưa chọn phân cảnh")
        self.lbl_img.setStyleSheet("color: #475569; font-size: 12px; font-weight: 500;")
        img_container_layout.addWidget(self.lbl_img, stretch=1)
        
        mascot_row = QHBoxLayout()
        mascot_row.setContentsMargins(8, 0, 8, 6)
        mascot_row.addStretch()
        self.lbl_mascot_watermark = QLabel("👤 Zunda Mascot")
        self.lbl_mascot_watermark.setStyleSheet("""
            background-color: rgba(245, 158, 11, 0.18);
            color: #fbbf24;
            border: 1px solid rgba(245, 158, 11, 0.4);
            border-radius: 6px;
            padding: 2px 8px;
            font-size: 10px;
            font-weight: 700;
        """)
        mascot_row.addWidget(self.lbl_mascot_watermark)
        img_container_layout.addLayout(mascot_row)
        
        v_layout.addWidget(img_container, stretch=1)
        
        # Subtitle Overlay
        self.lbl_sub = QLabel("Phụ đề Karaoke sẽ hiển thị ở đây...")
        self.lbl_sub.setAlignment(Qt.AlignCenter)
        self.lbl_sub.setWordWrap(True)
        self.lbl_sub.setStyleSheet("""
            QLabel {
                background-color: rgba(0, 0, 0, 0.85);
                color: #fde047;
                font-weight: bold;
                font-size: 11px;
                padding: 6px 12px;
                border-bottom-left-radius: 10px;
                border-bottom-right-radius: 10px;
            }
        """)
        v_layout.addWidget(self.lbl_sub)
        layout.addWidget(self.video_box)
        
        # Quick Summary Box
        lbl_sum_title = QLabel("TIẾN ĐỘ DỰ ÁN HIỆN TẠI")
        lbl_sum_title.setStyleSheet("font-size: 11px; font-weight: 800; color: #94a3b8; letter-spacing: 0.5px; margin-top: 4px;")
        layout.addWidget(lbl_sum_title)
        
        self.info_box = QFrame()
        self.info_box.setStyleSheet("background-color: #070b14; border: 1px solid #1e293b; border-radius: 10px;")
        info_layout = QVBoxLayout(self.info_box)
        info_layout.setContentsMargins(14, 12, 14, 12)
        info_layout.setSpacing(8)
        
        self.lbl_proj = QLabel("📁 Dự án: <b style='color: #e2e8f0;'>Chưa chọn</b>")
        self.lbl_script = QLabel("Tiến độ kịch bản: <b style='color: #94a3b8;'>Chưa tạo</b>")
        self.lbl_audio = QLabel("Trạng thái âm thanh: <b style='color: #94a3b8;'>Chưa phân tích</b>")
        self.lbl_visual = QLabel("Tiến độ ảnh AI: <b style='color: #94a3b8;'>0 phân cảnh</b>")
        self.lbl_char = QLabel("Đồng nhất nhân vật: <b style='color: #f59e0b;'>🔒 Bật (Zunda Mascot)</b>")
        
        for l in [self.lbl_proj, self.lbl_script, self.lbl_audio, self.lbl_visual, self.lbl_char]:
            l.setStyleSheet("color: #94a3b8; font-size: 12px; border: none;")
            info_layout.addWidget(l)
            
        layout.addWidget(self.info_box)
        layout.addStretch()
        
        lbl_hint = QLabel("Giao diện mới theo chuẩn Studio Pipeline: Rõ ràng, dễ hiểu từng bước!")
        lbl_hint.setWordWrap(True)
        lbl_hint.setAlignment(Qt.AlignCenter)
        lbl_hint.setStyleSheet("color: #475569; font-size: 11px; font-style: italic; margin-bottom: 4px;")
        layout.addWidget(lbl_hint)

    def set_preview(self, image_path=None, subtitle_text=None):
        if image_path and os.path.exists(image_path):
            pix = QPixmap(image_path)
            if not pix.isNull():
                self.lbl_img.setPixmap(pix.scaled(380, 160, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        else:
            self.lbl_img.setText("🎬 Chưa có ảnh phân cảnh")
            
        if subtitle_text:
            self.lbl_sub.setText(subtitle_text)
            self.lbl_sub.setVisible(True)
        else:
            self.lbl_sub.setVisible(False)
            
    def update_summary(self, proj_name=None, script_info=None, audio_info=None, visual_info=None, char_info=None):
        if proj_name is not None: 
            self.lbl_proj.setText(f"📁 Dự án: <b style='color: #e2e8f0;'>{proj_name}</b>")
        if script_info is not None: 
            color = "#10b981" if ("ký tự" in script_info or "Hoàn tất" in script_info or "100%" in script_info) else "#94a3b8"
            self.lbl_script.setText(f"Tiến độ kịch bản: <b style='color: {color};'>{script_info}</b>")
        if audio_info is not None: 
            color = "#c084fc" if "câu thoại" in audio_info else "#94a3b8"
            self.lbl_audio.setText(f"Trạng thái âm thanh: <b style='color: {color};'>{audio_info}</b>")
        if visual_info is not None: 
            color = "#10b981" if (visual_info != "0 phân cảnh" and visual_info != "0 ảnh") else "#94a3b8"
            self.lbl_visual.setText(f"Tiến độ ảnh AI: <b style='color: {color};'>{visual_info}</b>")
        if char_info is not None: 
            self.lbl_char.setText(f"Đồng nhất nhân vật: <b style='color: #f59e0b;'>🔒 {char_info}</b>")
            if hasattr(self, 'lbl_mascot_watermark'):
                self.lbl_mascot_watermark.setText(f"👤 {char_info}")


class MainWindow(QMainWindow):
    voicevox_status_changed = Signal(str)

    STEPS_CONFIG = [
        ("1", "Dự án", "KHỞI TẠO"),
        ("2", "Kịch bản AI", "NỘI DUNG"),
        ("3", "Voicevox & Sub", "ÂM THANH"),
        ("4", "Nhân vật & Flow", "HÌNH ẢNH"),
        ("5", "Render Video", "HOÀN TẤT")
    ]

    def __init__(self):
        super().__init__()
        self.voicevox_status_changed.connect(self._show_voicevox_status)
        self.setWindowTitle("VQPVEO3PRO - AI Video Studio (Japan Market Edition)")
        self.resize(1366, 860)
        self.setMinimumSize(1150, 720)
        
        self.current_step = 0
        self.step_buttons = []
        
        # Thiết lập style tổng thể chuyên nghiệp (Modern Dark Theme)
        self.setStyleSheet("""
            QMainWindow { background-color: #070b14; }
            QWidget { color: #e2e8f0; font-family: 'Segoe UI', system-ui, sans-serif; font-size: 13px; }
            
            /* Inputs */
            QLineEdit, QComboBox, QTextEdit, QSpinBox, QDoubleSpinBox {
                background-color: #1e293b;
                color: #f8fafc;
                border: 1px solid #334155;
                border-radius: 6px;
                padding: 8px 12px;
                selection-background-color: #3b82f6;
            }
            QLineEdit:focus, QComboBox:focus, QTextEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus {
                border: 1px solid #3b82f6;
                background-color: #0f172a;
            }
            QComboBox::drop-down {
                subcontrol-origin: padding;
                subcontrol-position: top right;
                width: 20px;
                border-left-width: 1px;
                border-left-color: #334155;
                border-left-style: solid;
            }
            QComboBox QAbstractItemView {
                background-color: #1e293b;
                color: #f8fafc;
                border: 1px solid #334155;
                selection-background-color: #3b82f6;
                selection-color: white;
            }
            
            /* Buttons */
            QPushButton {
                background-color: #3b82f6;
                color: white;
                border: none;
                border-radius: 6px;
                padding: 8px 16px;
                font-weight: 600;
            }
            QPushButton:hover {
                background-color: #2563eb;
            }
            QPushButton:pressed {
                background-color: #1d4ed8;
            }
            QPushButton:disabled {
                background-color: #334155;
                color: #94a3b8;
            }
            
            /* Tables */
            QTableWidget, QTableView {
                background-color: #0f172a;
                alternate-background-color: #1e293b;
                color: #e2e8f0;
                border: 1px solid #334155;
                border-radius: 6px;
                gridline-color: #334155;
                selection-background-color: rgba(59, 130, 246, 0.3);
                selection-color: #ffffff;
            }
            QHeaderView::section {
                background-color: #1e293b;
                color: #94a3b8;
                padding: 6px;
                border: 1px solid #334155;
                font-weight: bold;
            }
            QTableWidget::item {
                padding: 4px;
            }
            
            /* Scrollbars */
            QScrollBar:vertical {
                border: none;
                background-color: #0f172a;
                width: 10px;
                margin: 0px;
            }
            QScrollBar::handle:vertical {
                background-color: #475569;
                min-height: 20px;
                border-radius: 5px;
                margin: 2px;
            }
            QScrollBar::handle:vertical:hover {
                background-color: #64748b;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0px;
            }
            
            /* GroupBox */
            QGroupBox {
                border: 1px solid #334155;
                border-radius: 6px;
                margin-top: 1.5ex;
                padding-top: 15px;
                background-color: transparent;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                subcontrol-position: top left;
                padding: 0 5px;
                color: #94a3b8;
                font-weight: bold;
                left: 10px;
            }
        """)
        
        self._init_ui()

    def _init_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        # ========================================================
        # 1. TOP HEADER (Logo + Title + Status Badges + Settings)
        # ========================================================
        topbar = QWidget()
        topbar.setFixedHeight(58)
        topbar.setStyleSheet("background-color: #0b0f19; border-bottom: 1px solid #1a2234;")
        top_layout = QHBoxLayout(topbar)
        top_layout.setContentsMargins(18, 0, 18, 0)
        top_layout.setSpacing(14)
        
        # Logo Icon
        logo_lbl = QLabel("V")
        logo_lbl.setFixedSize(36, 36)
        logo_lbl.setAlignment(Qt.AlignCenter)
        logo_lbl.setStyleSheet("""
            background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #2563eb, stop:1 #4f46e5);
            color: white; font-weight: 900; font-size: 18px; border-radius: 10px;
        """)
        top_layout.addWidget(logo_lbl)
        
        title_box = QVBoxLayout()
        title_box.setSpacing(1)
        title_lbl = QLabel("VQPVEO3PRO STUDIO")
        title_lbl.setStyleSheet("font-weight: 900; color: #f8fafc; font-size: 15px; letter-spacing: 0.5px;")
        subtitle_lbl = QLabel("AI Video Automation Pipeline (Japan Market Edition)")
        subtitle_lbl.setStyleSheet("color: #64748b; font-size: 11px;")
        title_box.addWidget(title_lbl)
        title_box.addWidget(subtitle_lbl)
        top_layout.addLayout(title_box)
        
        top_layout.addStretch()
        
        # Status Badges
        self.lbl_chrome_status = QLabel("● Flowkit Connected (Port 8100)")
        self.lbl_chrome_status.setStyleSheet("""
            background-color: rgba(16, 185, 129, 0.12); color: #34d399; border: 1px solid rgba(16, 185, 129, 0.35);
            border-radius: 14px; padding: 5px 14px; font-weight: 700; font-size: 11px;
        """)
        top_layout.addWidget(self.lbl_chrome_status)
        
        self.lbl_voicevox_status = QLabel("● Voicevox 50021 Online")
        self.lbl_voicevox_status.setStyleSheet("""
            background-color: rgba(168, 85, 247, 0.12); color: #c084fc; border: 1px solid rgba(168, 85, 247, 0.35);
            border-radius: 14px; padding: 5px 14px; font-weight: 700; font-size: 11px;
        """)
        top_layout.addWidget(self.lbl_voicevox_status)
        
        # Secondary Navigation Buttons (Kênh Nhật & Cài đặt)
        self.btn_nav_channel = QPushButton("🇯🇵 Kênh Nhật")
        self.btn_nav_channel.setStyleSheet("""
            QPushButton {
                background-color: #131b2e; color: #cbd5e1; border: 1px solid #1e293b;
                border-radius: 8px; font-size: 12px; font-weight: 600; padding: 6px 14px;
            }
            QPushButton:hover {
                background-color: #1e293b; color: #ffffff;
            }
        """)
        self.btn_nav_channel.clicked.connect(lambda: self._switch_step(6, is_extra=True))
        top_layout.addWidget(self.btn_nav_channel)
        
        self.btn_nav_settings = QPushButton("⚙️ Cài đặt")
        self.btn_nav_settings.setStyleSheet("""
            QPushButton {
                background-color: #131b2e; color: #cbd5e1; border: 1px solid #1e293b;
                border-radius: 8px; font-size: 12px; font-weight: 600; padding: 6px 14px;
            }
            QPushButton:hover {
                background-color: #1e293b; color: #ffffff;
            }
        """)
        self.btn_nav_settings.clicked.connect(lambda: self._switch_step(5, is_extra=True))
        top_layout.addWidget(self.btn_nav_settings)
        
        main_layout.addWidget(topbar)
        
        # ========================================================
        # 2. HORIZONTAL STEPPER BAR (5 BƯỚC QUY TRÌNH CHUẨN)
        # ========================================================
        stepper_bar = QWidget()
        stepper_bar.setFixedHeight(68)
        stepper_bar.setStyleSheet("background-color: #080d1a; border-bottom: 1px solid #1a2234;")
        stepper_layout = QHBoxLayout(stepper_bar)
        stepper_layout.setContentsMargins(18, 8, 18, 8)
        stepper_layout.setSpacing(12)
        
        self.step_buttons = []
        for idx, (num, title, desc) in enumerate(self.STEPS_CONFIG):
            btn = QPushButton()
            btn.setFixedHeight(50)
            btn.setCheckable(True)
            btn.setCursor(Qt.PointingHandCursor)
            
            btn_inner = QHBoxLayout(btn)
            btn_inner.setContentsMargins(12, 6, 12, 6)
            btn_inner.setSpacing(10)
            
            lbl_num = QLabel(num)
            lbl_num.setFixedSize(28, 28)
            lbl_num.setAlignment(Qt.AlignCenter)
            lbl_num.setStyleSheet("background-color: #1e293b; color: #94a3b8; font-weight: bold; border-radius: 8px; font-size: 12px;")
            btn_inner.addWidget(lbl_num)
            
            lbl_box = QVBoxLayout()
            lbl_box.setSpacing(1)
            lbl_d = QLabel(desc.upper())
            lbl_d.setStyleSheet("color: #64748b; font-size: 10px; font-weight: 700; letter-spacing: 0.5px;")
            lbl_t = QLabel(title)
            lbl_t.setStyleSheet("color: #cbd5e1; font-size: 12px; font-weight: 700;")
            lbl_box.addWidget(lbl_d)
            lbl_box.addWidget(lbl_t)
            btn_inner.addLayout(lbl_box)
            btn_inner.addStretch()
            
            btn.clicked.connect(lambda checked, i=idx: self._switch_step(i))
            stepper_layout.addWidget(btn)
            self.step_buttons.append((btn, lbl_num, lbl_t, lbl_d))
            
        main_layout.addWidget(stepper_bar)
        
        # ========================================================
        # 3. WORKSPACE (Stage bên trái + Live Preview bên phải)
        # ========================================================
        workspace_widget = QWidget()
        workspace_layout = QHBoxLayout(workspace_widget)
        workspace_layout.setContentsMargins(0, 0, 0, 0)
        workspace_layout.setSpacing(0)
        
        # Stage Left (Stacked Panels + Footer Navigation)
        stage_widget = QWidget()
        stage_layout = QVBoxLayout(stage_widget)
        stage_layout.setContentsMargins(16, 16, 16, 12)
        stage_layout.setSpacing(12)
        
        self.stacked_widget = QStackedWidget()
        
        # Khởi tạo các panels
        self.tab_project = ProjectPanel()
        self.tab_script = ScriptPanel()
        self.tab_voice = VoicePanel()
        self.tab_visuals = VisualGridPanel()
        self.tab_timeline = TimelinePanel()
        self.tab_settings = SettingsPanel()
        self.tab_channel = ChannelPanel()
        
        # Thêm vào stacked widget
        self.stacked_widget.addWidget(self.tab_project)   # 0
        self.stacked_widget.addWidget(self.tab_script)    # 1
        self.stacked_widget.addWidget(self.tab_voice)     # 2
        self.stacked_widget.addWidget(self.tab_visuals)   # 3
        self.stacked_widget.addWidget(self.tab_timeline)  # 4
        self.stacked_widget.addWidget(self.tab_settings)  # 5
        self.stacked_widget.addWidget(self.tab_channel)   # 6
        
        stage_layout.addWidget(self.stacked_widget, stretch=1)
        
        # Footer Navigation Bar
        footer_bar = QWidget()
        footer_bar.setFixedHeight(50)
        footer_bar.setStyleSheet("background-color: #0b0f19; border: 1px solid #1e293b; border-radius: 12px;")
        footer_layout = QHBoxLayout(footer_bar)
        footer_layout.setContentsMargins(16, 6, 16, 6)
        
        self.btn_prev_step = QPushButton("← Quay lại")
        self.btn_prev_step.setFixedHeight(36)
        self.btn_prev_step.setStyleSheet("""
            QPushButton {
                background-color: #1e293b; color: #cbd5e1; font-weight: bold;
                border: 1px solid #334155; border-radius: 8px; padding: 0 20px; font-size: 12px;
            }
            QPushButton:hover {
                background-color: #334155; color: #ffffff;
            }
            QPushButton:disabled {
                background-color: #0f172a; color: #475569; border-color: #1e293b;
            }
        """)
        self.btn_prev_step.clicked.connect(self._prev_step)
        
        self.lbl_step_indicator = QLabel("Bước 1 / 5: Khởi tạo - Dự án")
        self.lbl_step_indicator.setStyleSheet("""
            background-color: #131b2e; color: #94a3b8; font-weight: bold;
            font-size: 12px; padding: 6px 18px; border-radius: 14px; border: 1px solid #1e293b;
        """)
        
        self.btn_next_step = QPushButton("Tiếp tục sang Kịch bản AI →")
        self.btn_next_step.setFixedHeight(36)
        self.btn_next_step.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #2563eb, stop:1 #3b82f6);
                color: white; font-weight: bold; border-radius: 8px; padding: 0 24px; font-size: 12px; border: none;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #3b82f6, stop:1 #60a5fa);
            }
        """)
        self.btn_next_step.clicked.connect(self._next_step)
        
        footer_layout.addWidget(self.btn_prev_step)
        footer_layout.addStretch()
        footer_layout.addWidget(self.lbl_step_indicator)
        footer_layout.addStretch()
        footer_layout.addWidget(self.btn_next_step)
        
        stage_layout.addWidget(footer_bar)
        workspace_layout.addWidget(stage_widget, stretch=1)
        
        # Stage Right (Live Preview)
        self.preview_panel = LivePreviewPanel(self)
        workspace_layout.addWidget(self.preview_panel)
        
        main_layout.addWidget(workspace_widget, stretch=1)
        
        # Kích hoạt bước 1 mặc định
        self._switch_step(0)

        # Đề xuất phục hồi session
        self._check_and_load_session()

        # Khởi động Local Bridge cho Flowkit
        self._start_bridge_server()

        # Khởi động VOICEVOX Engine cài kèm
        self._start_voicevox_engine()

        # Thiết lập phím tắt F5 để làm mới ứng dụng
        self.shortcut_f5 = QShortcut(QKeySequence("F5"), self)
        self.shortcut_f5.activated.connect(self.restart_app)

    def _switch_step(self, step_idx, is_extra=False):
        """Chuyển đổi bước trong quy trình Stepper."""
        self.current_step = step_idx
        self.stacked_widget.setCurrentIndex(step_idx)
        
        # Cập nhật style của các nút Stepper
        for i, (btn, lbl_num, lbl_t, lbl_d) in enumerate(self.step_buttons):
            if not is_extra and i == step_idx:
                btn.setStyleSheet("""
                    QPushButton {
                        background-color: rgba(37, 99, 235, 0.15);
                        border: 2px solid #3b82f6;
                        border-radius: 12px;
                    }
                """)
                lbl_num.setStyleSheet("""
                    background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #2563eb, stop:1 #3b82f6);
                    color: white; font-weight: bold; border-radius: 8px; font-size: 12px;
                """)
                lbl_t.setStyleSheet("color: #ffffff; font-size: 12px; font-weight: 800;")
                lbl_d.setStyleSheet("color: #93c5fd; font-size: 10px; font-weight: 700; letter-spacing: 0.5px;")
            else:
                btn.setStyleSheet("""
                    QPushButton {
                        background-color: rgba(15, 23, 42, 0.65);
                        border: 1px solid #1e293b;
                        border-radius: 12px;
                    }
                    QPushButton:hover {
                        border: 1px solid #334155;
                        background-color: rgba(30, 41, 59, 0.7);
                    }
                """)
                lbl_num.setStyleSheet("background-color: #1e293b; color: #94a3b8; font-weight: bold; border-radius: 8px; font-size: 12px;")
                lbl_t.setStyleSheet("color: #94a3b8; font-size: 12px; font-weight: 700;")
                lbl_d.setStyleSheet("color: #64748b; font-size: 10px; font-weight: 700; letter-spacing: 0.5px;")

        # Cập nhật nút Previous / Next
        if is_extra:
            self.btn_prev_step.setEnabled(True)
            self.btn_prev_step.setText("← Quay lại Quy trình")
            self.btn_next_step.setText("Về Bước 1 (Dự án)")
            self.lbl_step_indicator.setText("Cấu hình & Quản lý nâng cao")
            return
            
        self.btn_prev_step.setEnabled(step_idx > 0)
        self.btn_prev_step.setText("← Quay lại")
        
        next_titles = [
            "Tiếp tục sang Kịch bản AI →",
            "Tiếp tục sang Voicevox & Sub →",
            "Tiếp tục sang Nhân vật & Flow →",
            "Tiếp tục sang Render Video →",
            "🎬 BẮT ĐẦU XUẤT VIDEO (MP4)"
        ]
        
        if step_idx == 4:
            self.btn_next_step.setText(next_titles[step_idx])
            self.btn_next_step.setStyleSheet("""
                QPushButton {
                    background-color: #10b981; color: white; font-weight: bold;
                    border-radius: 8px; padding: 0 24px; font-size: 12px; border: none;
                }
                QPushButton:hover { background-color: #059669; }
            """)
        else:
            self.btn_next_step.setText(next_titles[step_idx])
            self.btn_next_step.setStyleSheet("""
                QPushButton {
                    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #2563eb, stop:1 #3b82f6);
                    color: white; font-weight: bold; border-radius: 8px; padding: 0 24px; font-size: 12px; border: none;
                }
                QPushButton:hover {
                    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #3b82f6, stop:1 #60a5fa);
                }
            """)
            
        step_name = self.STEPS_CONFIG[step_idx][1]
        step_cat = self.STEPS_CONFIG[step_idx][2]
        self.lbl_step_indicator.setText(f"Bước {step_idx + 1} / 5: {step_cat} - {step_name}")
        
        # Tự động đồng bộ dữ liệu giữa các bước nếu cần
        self._auto_sync_step_data(step_idx)

    def _next_step(self):
        """Bấm nút Tiếp tục."""
        if self.current_step >= 5: # Đang ở Settings/Channel
            self._switch_step(0)
            return
            
        if self.current_step < 4:
            self._switch_step(self.current_step + 1)
        elif self.current_step == 4:
            # Ở bước cuối cùng, kích hoạt Render
            if hasattr(self.tab_timeline, 'btn_render') and self.tab_timeline.btn_render.isEnabled():
                self.tab_timeline.btn_render.click()
            else:
                self.tab_timeline.sync_data()

    def _prev_step(self):
        """Bấm nút Quay lại."""
        if self.current_step >= 5: # Đang ở Settings/Channel
            self._switch_step(0)
            return
            
        if self.current_step > 0:
            self._switch_step(self.current_step - 1)

    def _auto_sync_step_data(self, step_idx):
        """Tự động đồng bộ dữ liệu vào Live Preview và giữa các panel khi chuyển bước."""
        settings = load_settings()
        proj_dir = settings.get("PROJECT_DIR", "")
        proj_name = os.path.basename(proj_dir) if proj_dir else "Chưa mở"
        
        # Cập nhật thông tin tóm tắt trên Preview
        script_text = self.tab_script.get_state().get("script", "")
        script_info = f"{len(script_text)} ký tự" if script_text else "Chưa có"
        
        voice_segs = self.tab_voice.get_state().get("segments", [])
        audio_info = f"{len(voice_segs)} câu thoại" if voice_segs else "Chưa phân tích"
        
        cards = getattr(self.tab_visuals, 'cards', [])
        visual_info = f"{len(cards)} phân cảnh" if cards else "0 phân cảnh"
        
        char_name = "Mặc định"
        if hasattr(self.tab_visuals, 'character_manager') and self.tab_visuals.character_manager:
            chars = self.tab_visuals.character_manager.get_all_characters()
            if chars: char_name = chars[0].name
            
        self.preview_panel.update_summary(
            proj_name=proj_name, script_info=script_info, audio_info=audio_info,
            visual_info=visual_info, char_info=char_name
        )
        
        # Khi chuyển sang Bước 4 (Visuals), tự động nạp phân cảnh từ Voice nếu chưa có
        if step_idx == 3 and not cards and voice_segs:
            self.tab_visuals.sync_from_voice()
            
        # Khi chuyển sang Bước 5 (Timeline), tự động nạp đồng bộ
        if step_idx == 4:
            self.tab_timeline.sync_data()

    def update_live_preview(self, image_path=None, subtitle_text=None):
        """Hàm công khai cho phép các card ở Tab Visuals gọi để cập nhật Live Preview."""
        if hasattr(self, 'preview_panel'):
            self.preview_panel.set_preview(image_path, subtitle_text)

    def _start_bridge_server(self):
        import subprocess
        import os
        from utils.logger import app_logger
        
        agent_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "agent", "main.py")
        
        try:
            python_exe = sys.executable.replace("pythonw.exe", "python.exe")
            log_out = open(os.path.join(os.path.dirname(os.path.dirname(agent_path)), "flowkit_out.log"), "w")
            self.flowkit_process = subprocess.Popen(
                [python_exe, "-m", "agent.main"],
                cwd=os.path.dirname(os.path.dirname(agent_path)),
                creationflags=subprocess.CREATE_NO_WINDOW,
                stdout=log_out,
                stderr=log_out
            )
            app_logger.info(f"Đã khởi chạy Flowkit API (PID: {self.flowkit_process.pid})")
            
            class MockFlowController:
                pass
            self.flow_controller = MockFlowController()
            if hasattr(self, 'tab_visuals'):
                self.tab_visuals.set_flow_controller(self.flow_controller)
                
            self.lbl_chrome_status.setText("Flowkit: Online (Port 8100)")
            self.lbl_chrome_status.setStyleSheet("""
                background-color: rgba(16, 185, 129, 0.1); color: #10b981; border: 1px solid rgba(16, 185, 129, 0.3);
                border-radius: 12px; padding: 4px 10px; font-weight: bold; font-size: 11px;
            """)
            
        except Exception as e:
            app_logger.error(f"Không thể khởi chạy Flowkit API: {e}")
            self.lbl_chrome_status.setText("Flowkit: Lỗi khởi động")
            self.lbl_chrome_status.setStyleSheet("""
                background-color: rgba(239, 68, 68, 0.1); color: #ef4444; border: 1px solid rgba(239, 68, 68, 0.3);
                border-radius: 12px; padding: 4px 10px; font-weight: bold; font-size: 11px;
            """)

    def _start_voicevox_engine(self):
        from channel.voicevox_runtime import start_voicevox_engine
        from utils.logger import app_logger

        def launch():
            try:
                status = start_voicevox_engine()
                self.voicevox_status_changed.emit("Voicevox: Online (Port 50021)")
            except Exception as exc:
                app_logger.warning(f"Không thể tự khởi động VOICEVOX: {exc}")
                self.voicevox_status_changed.emit("Voicevox: Offline")

        threading.Thread(target=launch, daemon=True, name="voicevox-engine-start").start()

    def _show_voicevox_status(self, message):
        if "Online" in message:
            self.lbl_voicevox_status.setText(message)
            self.lbl_voicevox_status.setStyleSheet("""
                background-color: rgba(168, 85, 247, 0.15); color: #c084fc; border: 1px solid rgba(168, 85, 247, 0.3);
                border-radius: 12px; padding: 4px 10px; font-weight: bold; font-size: 11px;
            """)
        else:
            self.lbl_voicevox_status.setText(message)
            self.lbl_voicevox_status.setStyleSheet("""
                background-color: rgba(100, 116, 139, 0.1); color: #94a3b8; border: 1px solid rgba(100, 116, 139, 0.3);
                border-radius: 12px; padding: 4px 10px; font-weight: bold; font-size: 11px;
            """)

    def _check_and_load_session(self):
        from config.session_manager import load_session, clear_session
        session_data = load_session()
        if session_data:
            reply = QMessageBox.question(
                self, "Phục hồi phiên làm việc", 
                "Hệ thống phát hiện phiên làm việc cũ. Bạn có muốn tiếp tục công việc đang dang dở không?",
                QMessageBox.Yes | QMessageBox.No, QMessageBox.Yes
            )
            if reply == QMessageBox.Yes:
                self.tab_script.set_state(session_data.get("script_panel", {}))
                self.tab_voice.set_state(session_data.get("voice_panel", {}))
                self.tab_visuals.set_state(session_data.get("visual_panel", []))
                saved_idx = session_data.get("current_tab", 0)
                if 0 <= saved_idx < 5:
                    self._switch_step(saved_idx)
            else:
                clear_session()

    def clear_all_panels(self):
        """Xóa trắng dữ liệu hiện tại khi mở dự án mới."""
        self.tab_script.set_state({})
        self.tab_voice.set_state({})
        self.tab_visuals.set_state([])
        self._switch_step(0)
        
    def load_project_state(self, state_data):
        """Tải dữ liệu từ một dự án được chọn."""
        if state_data:
            self.tab_script.set_state(state_data.get("script_panel", {}))
            self.tab_voice.set_state(state_data.get("voice_panel", {}))
            self.tab_visuals.set_state(state_data.get("visual_panel", []))
            self._switch_step(0)

    def _save_session_data(self):
        try:
            from config.session_manager import save_session
            from utils.json_store import write_json_atomic
            
            session_data = {
                "script_panel": self.tab_script.get_state(),
                "voice_panel": self.tab_voice.get_state(),
                "visual_panel": self.tab_visuals.get_state(),
                "current_tab": self.current_step
            }
            save_session(session_data)
            
            settings = load_settings()
            proj_dir = settings.get("PROJECT_DIR")
            if proj_dir and os.path.exists(proj_dir):
                state_file = os.path.join(proj_dir, "project_state.json")
                write_json_atomic(state_file, session_data)
        except Exception as e:
            print(f"Lỗi khi lưu session: {e}")

    def restart_app(self):
        if self.tab_channel.is_busy():
            QMessageBox.information(self, "Đang sản xuất", "Dừng bước đang chạy ở KÊNH NHẬT trước khi khởi động lại.")
            return
        reply = QMessageBox.question(
            self, 'Làm mới ứng dụng',
            'Bạn có chắc chắn muốn làm mới (F5) ứng dụng không?\nDữ liệu hiện tại sẽ được lưu tạm thời.',
            QMessageBox.Yes | QMessageBox.No, QMessageBox.Yes
        )
        if reply == QMessageBox.Yes:
            self._save_session_data()
            if hasattr(self, 'flowkit_process') and self.flowkit_process:
                try: self.flowkit_process.terminate()
                except: pass
            from channel.voicevox_runtime import voicevox_runtime
            voicevox_runtime.stop()
                
            script_path = os.path.abspath(sys.argv[0])
            subprocess.Popen([sys.executable, script_path], cwd=os.path.dirname(os.path.dirname(script_path)))
            QApplication.quit()

    def closeEvent(self, event):
        if self.tab_channel.is_busy():
            QMessageBox.information(self, "Đang sản xuất", "Dừng bước đang chạy ở KÊNH NHẬT trước khi đóng ứng dụng.")
            event.ignore()
            return
        reply = QMessageBox.question(
            self, 'Xác nhận thoát',
            'Bạn có chắc chắn muốn thoát ứng dụng không?',
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            self._save_session_data()
            if hasattr(self, 'flowkit_process') and self.flowkit_process:
                try: self.flowkit_process.terminate()
                except: pass
            from channel.voicevox_runtime import voicevox_runtime
            voicevox_runtime.stop()
            event.accept()
            QApplication.quit()
        else:
            event.ignore()
