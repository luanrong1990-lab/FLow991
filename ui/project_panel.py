"""
ui/project_panel.py - Quản lý Dự án & Cấu hình Workspace (Bước 1) chuẩn Studio Stepper.

Thiết kế hiện đại:
- Responsive container (giới hạn max-width 1100px, căn giữa, không bị kéo dãn vô tận).
- 2 Action Cards trực quan: Tạo Dự Án Mới & Mở Dự Án Cũ.
- Card hiển thị thông tin dự án đang mở và danh sách các dự án trong Workspace.
"""

import os
import json
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
    QPushButton, QFileDialog, QListWidget, QMessageBox, QInputDialog,
    QFrame, QScrollArea, QListWidgetItem
)
from PySide6.QtCore import Qt
from config.config_manager import load_settings, save_settings
from config.session_manager import clear_session
from utils.logger import app_logger


class ProjectPanel(QWidget):
    def __init__(self):
        super().__init__()
        self.workspace_dir = os.path.abspath(os.path.join(os.getcwd(), "Projects"))
        os.makedirs(self.workspace_dir, exist_ok=True)
        self._init_ui()

    def _init_ui(self):
        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(0, 0, 0, 0)
        outer_layout.setSpacing(0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setStyleSheet("QScrollArea { background-color: transparent; border: none; }")

        container = QWidget()
        container.setStyleSheet("background-color: transparent;")
        
        center_h_layout = QHBoxLayout(container)
        center_h_layout.setContentsMargins(16, 16, 16, 16)
        
        content_box = QWidget()
        content_box.setMaximumWidth(1100) # Khắc phục giãn bè ngang
        content_layout = QVBoxLayout(content_box)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(16)

        center_h_layout.addWidget(content_box)
        scroll.setWidget(container)
        outer_layout.addWidget(scroll)

        # ========================================================
        # 1. HEADER
        # ========================================================
        header_widget = QWidget()
        header_layout = QHBoxLayout(header_widget)
        header_layout.setContentsMargins(0, 0, 0, 0)
        
        title_box = QVBoxLayout()
        title_box.setSpacing(2)
        
        lbl_title = QLabel("📁 Quản lý Dự án & Cấu hình Workspace")
        lbl_title.setStyleSheet("font-size: 17px; font-weight: 800; color: #f8fafc;")
        lbl_subtitle = QLabel("Khởi tạo workspace riêng biệt và thiết lập thông số xuất video cho từng nội dung.")
        lbl_subtitle.setStyleSheet("color: #64748b; font-size: 12px;")
        
        title_box.addWidget(lbl_title)
        title_box.addWidget(lbl_subtitle)
        header_layout.addLayout(title_box)
        header_layout.addStretch()
        
        self.lbl_current_badge = QLabel("Dự án hiện tại: Chưa mở")
        self.lbl_current_badge.setStyleSheet("""
            background-color: rgba(59, 130, 246, 0.15);
            color: #60a5fa;
            border: 1px solid rgba(59, 130, 246, 0.4);
            border-radius: 12px;
            padding: 4px 14px;
            font-size: 11px;
            font-weight: 700;
        """)
        header_layout.addWidget(self.lbl_current_badge)
        
        content_layout.addWidget(header_widget)

        # ========================================================
        # 2. TWO ACTION CARDS (Tạo mới & Mở dự án)
        # ========================================================
        cards_layout = QHBoxLayout()
        cards_layout.setSpacing(14)

        # Card 1: Tạo dự án mới
        self.card_new = QFrame()
        self.card_new.setCursor(Qt.PointingHandCursor)
        self.card_new.setStyleSheet("""
            QFrame {
                background-color: #0d1322;
                border: 1px solid #1e293b;
                border-radius: 12px;
                padding: 16px;
            }
            QFrame:hover {
                border: 1px solid #10b981;
                background-color: rgba(16, 185, 129, 0.05);
            }
        """)
        card_new_layout = QVBoxLayout(self.card_new)
        card_new_layout.setSpacing(6)
        
        lbl_new_title = QLabel("➕ Tạo Dự Án Mới")
        lbl_new_title.setStyleSheet("color: #10b981; font-weight: bold; font-size: 14px;")
        lbl_new_desc = QLabel("Khởi tạo thư mục dự án mới riêng biệt với đầy đủ cấu trúc: kịch bản, âm thanh, ảnh AI.")
        lbl_new_desc.setStyleSheet("color: #94a3b8; font-size: 11px;")
        lbl_new_desc.setWordWrap(True)
        
        btn_new_act = QPushButton("Bắt đầu tạo dự án")
        btn_new_act.setStyleSheet("""
            QPushButton {
                background-color: #10b981; color: white; font-weight: bold;
                border-radius: 6px; padding: 8px 16px; font-size: 12px; margin-top: 6px;
            }
            QPushButton:hover { background-color: #059669; }
        """)
        btn_new_act.clicked.connect(self.create_new_project)
        
        card_new_layout.addWidget(lbl_new_title)
        card_new_layout.addWidget(lbl_new_desc)
        card_new_layout.addWidget(btn_new_act)
        cards_layout.addWidget(self.card_new)

        # Card 2: Mở dự án cũ
        self.card_open = QFrame()
        self.card_open.setCursor(Qt.PointingHandCursor)
        self.card_open.setStyleSheet("""
            QFrame {
                background-color: #0d1322;
                border: 1px solid #1e293b;
                border-radius: 12px;
                padding: 16px;
            }
            QFrame:hover {
                border: 1px solid #3b82f6;
                background-color: rgba(59, 130, 246, 0.05);
            }
        """)
        card_open_layout = QVBoxLayout(self.card_open)
        card_open_layout.setSpacing(6)
        
        lbl_open_title = QLabel("📂 Mở Dự Án Khác")
        lbl_open_title.setStyleSheet("color: #3b82f6; font-weight: bold; font-size: 14px;")
        lbl_open_desc = QLabel("Chọn một thư mục dự án có sẵn để phục hồi toàn bộ tiến độ kịch bản và phân cảnh.")
        lbl_open_desc.setStyleSheet("color: #94a3b8; font-size: 11px;")
        lbl_open_desc.setWordWrap(True)
        
        btn_open_act = QPushButton("Duyệt thư mục...")
        btn_open_act.setStyleSheet("""
            QPushButton {
                background-color: #3b82f6; color: white; font-weight: bold;
                border-radius: 6px; padding: 8px 16px; font-size: 12px; margin-top: 6px;
            }
            QPushButton:hover { background-color: #2563eb; }
        """)
        btn_open_act.clicked.connect(self.open_existing_project)
        
        card_open_layout.addWidget(lbl_open_title)
        card_open_layout.addWidget(lbl_open_desc)
        card_open_layout.addWidget(btn_open_act)
        cards_layout.addWidget(self.card_open)

        content_layout.addLayout(cards_layout)

        # ========================================================
        # 3. CURRENT PROJECT INFO CARD
        # ========================================================
        self.card_info = QFrame()
        self.card_info.setStyleSheet("""
            QFrame {
                background-color: #070b14;
                border: 1px solid #1e293b;
                border-radius: 10px;
                padding: 14px;
            }
        """)
        info_layout = QVBoxLayout(self.card_info)
        info_layout.setSpacing(8)
        
        row1 = QHBoxLayout()
        lbl_p_title = QLabel("Đường dẫn lưu trữ dự án:")
        lbl_p_title.setStyleSheet("color: #94a3b8; font-size: 12px; font-weight: 600;")
        self.lbl_proj_path = QLabel("Chưa mở dự án nào")
        self.lbl_proj_path.setStyleSheet("color: #f8fafc; font-size: 12px; font-family: monospace; font-weight: bold;")
        row1.addWidget(lbl_p_title)
        row1.addWidget(self.lbl_proj_path)
        row1.addStretch()
        info_layout.addLayout(row1)

        row2 = QHBoxLayout()
        lbl_mode_title = QLabel("Chế độ xuất video:")
        lbl_mode_title.setStyleSheet("color: #94a3b8; font-size: 12px; font-weight: 600;")
        lbl_mode_val = QLabel("16:9 Landscape (YouTube) - 1080p Full HD")
        lbl_mode_val.setStyleSheet("color: #10b981; font-size: 12px; font-weight: bold;")
        row2.addWidget(lbl_mode_title)
        row2.addWidget(lbl_mode_val)
        row2.addStretch()
        info_layout.addLayout(row2)

        content_layout.addWidget(self.card_info)

        # ========================================================
        # 4. WORKSPACE PROJECTS LIST
        # ========================================================
        list_container = QFrame()
        list_container.setStyleSheet("""
            QFrame {
                background-color: #0d1322;
                border: 1px solid #1e293b;
                border-radius: 12px;
                padding: 16px;
            }
        """)
        list_v_layout = QVBoxLayout(list_container)
        list_v_layout.setSpacing(10)

        list_header = QHBoxLayout()
        lbl_list_title = QLabel("Danh sách dự án trong Workspace (Nhấn đúp chuột để mở):")
        lbl_list_title.setStyleSheet("color: #cbd5e1; font-weight: bold; font-size: 12px;")
        list_header.addWidget(lbl_list_title)
        list_header.addStretch()

        btn_refresh = QPushButton("🔄 Làm mới")
        btn_refresh.setStyleSheet("background-color: #1e293b; color: #94a3b8; font-size: 11px; padding: 4px 10px; border-radius: 4px;")
        btn_refresh.clicked.connect(self.refresh_project_list)
        list_header.addWidget(btn_refresh)
        list_v_layout.addLayout(list_header)

        self.list_projects = QListWidget()
        self.list_projects.setStyleSheet("""
            QListWidget {
                background-color: #070b14;
                border: 1px solid #1e293b;
                border-radius: 8px;
                color: #e2e8f0;
                padding: 6px;
                font-size: 13px;
            }
            QListWidget::item {
                padding: 8px 12px;
                border-radius: 6px;
                margin-bottom: 2px;
            }
            QListWidget::item:hover {
                background-color: #1e293b;
            }
            QListWidget::item:selected {
                background-color: rgba(59, 130, 246, 0.2);
                border: 1px solid #3b82f6;
                color: #ffffff;
            }
        """)
        self.list_projects.itemDoubleClicked.connect(self._on_item_double_clicked)
        list_v_layout.addWidget(self.list_projects)

        content_layout.addWidget(list_container)

        self.refresh_project_list()
        self._load_current_project()

    def _load_current_project(self):
        settings = load_settings()
        proj_dir = settings.get("PROJECT_DIR")
        if proj_dir and os.path.exists(proj_dir):
            proj_name = os.path.basename(proj_dir)
            self.lbl_proj_path.setText(proj_dir)
            self.lbl_proj_path.setStyleSheet("color: #10b981; font-size: 12px; font-family: monospace; font-weight: bold;")
            self.lbl_current_badge.setText(f"Dự án: {proj_name}")
            self.lbl_current_badge.setStyleSheet("""
                background-color: rgba(16, 185, 129, 0.15);
                color: #34d399;
                border: 1px solid rgba(16, 185, 129, 0.4);
                border-radius: 12px;
                padding: 4px 14px;
                font-size: 11px;
                font-weight: 700;
            """)
        else:
            self.lbl_proj_path.setText("Thư mục dùng chung (Chưa tạo dự án riêng)")
            self.lbl_proj_path.setStyleSheet("color: #ef4444; font-size: 12px;")
            self.lbl_current_badge.setText("Chưa mở dự án")

    def refresh_project_list(self):
        self.list_projects.clear()
        if os.path.exists(self.workspace_dir):
            for item in os.listdir(self.workspace_dir):
                full_path = os.path.join(self.workspace_dir, item)
                if os.path.isdir(full_path):
                    list_item = QListWidgetItem(f"📁 {item}")
                    list_item.setData(Qt.UserRole, full_path)
                    self.list_projects.addItem(list_item)
                    
    def _on_item_double_clicked(self, item):
        proj_dir = item.data(Qt.UserRole)
        if proj_dir:
            self.load_project(proj_dir)

    def create_new_project(self):
        name, ok = QInputDialog.getText(self, "Tạo Dự Án Mới", "Nhập tên dự án (ví dụ: Japan_Mysteries_01):")
        if ok and name.strip():
            proj_name = name.strip()
            proj_dir = os.path.join(self.workspace_dir, proj_name)
            
            if os.path.exists(proj_dir):
                QMessageBox.warning(self, "Lỗi", f"Dự án '{proj_name}' đã tồn tại!")
                return
                
            os.makedirs(proj_dir, exist_ok=True)
            os.makedirs(os.path.join(proj_dir, "images"), exist_ok=True)
            os.makedirs(os.path.join(proj_dir, "audio"), exist_ok=True)
            os.makedirs(os.path.join(proj_dir, "subtitles"), exist_ok=True)
            os.makedirs(os.path.join(proj_dir, "exports"), exist_ok=True)
            
            self.load_project(proj_dir, is_new=True)
            self.refresh_project_list()
            
    def open_existing_project(self):
        dir_path = QFileDialog.getExistingDirectory(self, "Chọn thư mục Dự Án", self.workspace_dir)
        if dir_path:
            self.load_project(dir_path)

    def load_project(self, proj_dir, is_new=False):
        save_settings({"PROJECT_DIR": proj_dir})
        self._load_current_project()
        
        main_win = self.window()
        if hasattr(main_win, 'clear_all_panels'):
            main_win.clear_all_panels()
            
        if not is_new:
            state_file = os.path.join(proj_dir, "project_state.json")
            if os.path.exists(state_file):
                try:
                    with open(state_file, 'r', encoding='utf-8') as f:
                        state_data = json.load(f)
                    if hasattr(main_win, 'load_project_state'):
                        main_win.load_project_state(state_data)
                except Exception as e:
                    app_logger.error(f"Lỗi đọc project state: {e}")
            
        QMessageBox.information(self, "Thành công", f"Đã chuyển sang dự án:\n{proj_dir}")
