from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel
from PySide6.QtCore import Qt

def create_placeholder_panel(title, subtitle):
    class Panel(QWidget):
        def __init__(self, parent=None):
            super().__init__(parent)
            layout = QVBoxLayout(self)
            layout.setAlignment(Qt.AlignCenter)
            
            lbl_title = QLabel(title)
            lbl_title.setStyleSheet("font-size: 24px; font-weight: bold; color: #f59e0b;")
            lbl_title.setAlignment(Qt.AlignCenter)
            
            lbl_sub = QLabel(subtitle)
            lbl_sub.setStyleSheet("font-size: 14px; color: #9ca3af; margin-top: 10px;")
            lbl_sub.setAlignment(Qt.AlignCenter)
            
            layout.addWidget(lbl_title)
            layout.addWidget(lbl_sub)
    return Panel

ProjectPanel = create_placeholder_panel("PROJECT NAVIGATION", "Sẽ triển khai trong Phase 13 (Project Recovery & Management)")
ScriptPanel = create_placeholder_panel("AI SCRIPT GENERATION", "Sẽ triển khai trong Phase 2 (Topic to Script)")
VoicePanel = create_placeholder_panel("VOICE & SEGMENTATION", "Sẽ triển khai trong Phase 4 (ASR & Semantic Segmentation)")
VisualGridPanel = create_placeholder_panel("VISUAL GRID EDITOR", "Sẽ triển khai trong Phase 8 (Grid Card Editor)")
TimelinePanel = create_placeholder_panel("TIMELINE SYNCHRONIZATION", "Sẽ triển khai trong Phase 11 (Timeline & FFmpeg)")
