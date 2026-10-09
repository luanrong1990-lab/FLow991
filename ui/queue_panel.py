import os
import time
import random
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QProgressBar, 
    QFrame, QScrollArea, QPushButton, QMessageBox
)
from PySide6.QtCore import Qt, Signal, QThread, QTimer
from visual.flow_provider import FlowImageProvider
from config.config_manager import load_settings
from utils.logger import app_logger

class QueueWorkerThread(QThread):
    progress_signal = Signal(str, str) # worker_id, status_msg
    progress_val_signal = Signal(str, int, int) # worker_id, current, total
    finished_signal = Signal(str) # worker_id
    image_ready_signal = Signal(str, str, object) # seg_id, path, card_ref

    def __init__(self, worker_id, client_ws, jobs, flow_controller, project_dir, character_media_ids=None):
        super().__init__()
        self.worker_id = worker_id
        # client_ws và flow_controller giờ không cần dùng vì ta xài thẳng API của flowkit
        self.jobs = jobs  # list of (seg_id, prompt, card_obj)
        self.project_dir = project_dir
        self.character_media_ids = character_media_ids or []
        self.is_running = True

    def run(self):
        import requests
        import urllib.request
        
        total = len(self.jobs)
        self.progress_val_signal.emit(self.worker_id, 0, total)
        
        settings = load_settings()
        flow_project_id = settings.get("FLOW_PROJECT_ID", "85222c0e-de50-4e6f-85dd-0d33d1eb127d")
        
        # Đảm bảo thư mục lưu ảnh tồn tại
        dest_dir = os.path.join(self.project_dir, "images")
        os.makedirs(dest_dir, exist_ok=True)
        
        for i, (seg_id, prompt, card_obj) in enumerate(self.jobs):
            if not self.is_running:
                break
                
            self.progress_signal.emit(self.worker_id, f"Đang tạo: {seg_id}...")
            
            payload = {
                "prompt": prompt,
                "project_id": flow_project_id,
                "aspect_ratio": "IMAGE_ASPECT_RATIO_LANDSCAPE", # 16:9
                "count": 1
            }
            if self.character_media_ids:
                payload["character_media_ids"] = self.character_media_ids
            
            try:
                # Gửi request sang flowkit
                response = requests.post("http://127.0.0.1:8100/api/flow/generate-image", json=payload, timeout=300)
                if response.status_code == 200:
                    data = response.json()
                    # flowkit trả về fifeUrl của hình ảnh
                    media_list = data.get("media", [])
                    if media_list and "image" in media_list[0]:
                        url = media_list[0]["image"].get("generatedImage", {}).get("fifeUrl")
                        if url:
                            # Tải hình ảnh về
                            dest_path = os.path.join(dest_dir, f"{seg_id}.png")
                            urllib.request.urlretrieve(url, dest_path)
                            self.image_ready_signal.emit(seg_id, dest_path, card_obj)
                            self.progress_signal.emit(self.worker_id, f"Hoàn tất {seg_id}!")
                        else:
                            raise Exception("Không tìm thấy fifeUrl trong response")
                    else:
                        raise Exception("Dữ liệu media không hợp lệ")
                else:
                    raise Exception(f"HTTP {response.status_code}: {response.text}")
                    
            except Exception as e:
                self.progress_signal.emit(self.worker_id, f"Lỗi {seg_id}: {e}")
                app_logger.error(f"Worker {self.worker_id} lỗi tại {seg_id}: {e}")
                time.sleep(2)
                
            self.progress_val_signal.emit(self.worker_id, i + 1, total)
            
            # Chống ban: Delay random (Chỉ nghỉ nếu chưa phải job cuối)
            if i < total - 1 and self.is_running:
                delay = random.randint(5, 10) # BATCH RPC của flowkit xịn hơn nên delay ngắn lại
                for d in range(delay, 0, -1):
                    if not self.is_running: break
                    self.progress_signal.emit(self.worker_id, f"Nghỉ chống ban ({d}s)...")
                    time.sleep(1)
                    
        self.progress_signal.emit(self.worker_id, "Đã xong tất cả nhiệm vụ!")
        self.finished_signal.emit(self.worker_id)

    def stop(self):
        self.is_running = False


class WorkerUI(QFrame):
    def __init__(self, worker_id, num_jobs):
        super().__init__()
        self.setStyleSheet("QFrame { background-color: #1e293b; border-radius: 8px; padding: 10px; margin-bottom: 5px; }")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        
        # Header
        header_layout = QHBoxLayout()
        self.lbl_title = QLabel(f"🤖 Worker {worker_id}")
        self.lbl_title.setStyleSheet("font-weight: bold; color: #38bdf8;")
        
        self.lbl_status = QLabel("Đang chờ...")
        self.lbl_status.setStyleSheet("color: #94a3b8; font-style: italic;")
        self.lbl_status.setAlignment(Qt.AlignRight)
        
        header_layout.addWidget(self.lbl_title)
        header_layout.addWidget(self.lbl_status)
        layout.addLayout(header_layout)
        
        # Progress
        self.progress = QProgressBar()
        self.progress.setRange(0, num_jobs)
        self.progress.setValue(0)
        self.progress.setStyleSheet("""
            QProgressBar { border: 1px solid #334155; border-radius: 4px; text-align: center; color: white; background-color: #0f172a; }
            QProgressBar::chunk { background-color: #10b981; border-radius: 3px; }
        """)
        layout.addWidget(self.progress)
        
    def update_status(self, msg):
        self.lbl_status.setText(msg)
        
    def update_total(self, total):
        self.progress.setRange(0, total)
        self.progress.setFormat(f"0/{total} Jobs")
        
    def update_progress(self, current, total):
        self.progress.setValue(current)
        self.progress.setFormat(f"{current}/{total} Jobs")


class QueueManagerPanel(QWidget):
    def __init__(self, visual_grid_panel):
        super().__init__()
        self.visual_grid = visual_grid_panel
        self.threads = []
        
        self.setStyleSheet("background-color: #0f172a; color: white; border-top: 2px solid #1e293b;")
        layout = QVBoxLayout(self)
        
        # Tiêu đề & Nút Stop
        header_layout = QHBoxLayout()
        lbl_title = QLabel("🚀 TIẾN ĐỘ ĐA LUỒNG (QUEUE MANAGER)")
        lbl_title.setStyleSheet("font-size: 14px; font-weight: bold; color: #f59e0b;")
        
        self.btn_stop = QPushButton("Dừng toàn bộ")
        self.btn_stop.setStyleSheet("background-color: #ef4444; color: white; border-radius: 4px; padding: 4px 10px;")
        self.btn_stop.clicked.connect(self.stop_all)
        self.btn_stop.setVisible(False)
        
        header_layout.addWidget(lbl_title)
        header_layout.addStretch()
        header_layout.addWidget(self.btn_stop)
        layout.addLayout(header_layout)
        
        # Khu vực Scroll chứa các Worker
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setStyleSheet("border: none; background-color: transparent;")
        
        self.scroll_widget = QWidget()
        self.scroll_layout = QVBoxLayout(self.scroll_widget)
        self.scroll_layout.setAlignment(Qt.AlignTop)
        
        self.scroll_area.setWidget(self.scroll_widget)
        layout.addWidget(self.scroll_area)
        
        self.worker_uis = {}
        
    def start_batch(self, num_workers, jobs, flow_controller, project_dir, character_media_ids=None):
        """Khởi chạy đa luồng chia việc cho các worker ảo."""
        self.stop_all()
        self.worker_uis.clear()
        
        # Xóa các UI cũ
        for i in reversed(range(self.scroll_layout.count())): 
            widget = self.scroll_layout.itemAt(i).widget()
            if widget is not None:
                widget.setParent(None)
                
        # Khởi tạo UI cho từng worker ảo
        for i in range(num_workers):
            worker_id = f"Worker {i+1}"
            ui = WorkerUI(worker_id, 0)
            self.scroll_layout.addWidget(ui)
            self.worker_uis[worker_id] = ui
            
        # Chia đều jobs cho các worker
        import math
        chunk_size = math.ceil(len(jobs) / num_workers)
        chunks = [jobs[i:i + chunk_size] for i in range(0, len(jobs), chunk_size)]
        
        for i, chunk in enumerate(chunks):
            worker_id = f"Worker {i+1}"
            if worker_id in self.worker_uis:
                self.worker_uis[worker_id].update_total(len(chunk))
                
            t = QueueWorkerThread(worker_id, None, chunk, flow_controller, project_dir, character_media_ids=character_media_ids)
            t.progress_signal.connect(self._on_worker_progress)
            t.progress_val_signal.connect(self._on_worker_progress_val)
            t.finished_signal.connect(self._on_worker_finished)
            t.image_ready_signal.connect(self._on_image_ready)
            
            self.threads.append(t)
            t.start()
            
    def _on_worker_progress(self, worker_id, msg):
        if worker_id in self.worker_uis:
            self.worker_uis[worker_id].update_status(msg)
            
    def _on_worker_progress_val(self, worker_id, current, total):
        if worker_id in self.worker_uis:
            self.worker_uis[worker_id].update_progress(current, total)
            
    def _on_image_ready(self, seg_id, path, card_ref):
        # Callback lên VisualGrid
        self.visual_grid.on_image_finished(seg_id, path, True, card_ref)
        
    def _on_worker_finished(self, worker_id):
        # Kiểm tra xem tất cả xong chưa
        all_done = all(not t.isRunning() for t in self.threads)
        if all_done:
            self.btn_stop.setVisible(False)
            self.visual_grid.btn_generate_all.setEnabled(True)
            self.visual_grid.btn_generate_all.setText("Tạo Toàn bộ Ảnh")
            QMessageBox.information(self, "Hoàn tất", "Tất cả hàng đợi đã chạy xong!")

    def stop_all(self):
        for t in self.threads:
            t.stop()
            t.wait(2000)
        self.threads.clear()
        self.btn_stop.setVisible(False)
        self.visual_grid.btn_generate_all.setEnabled(True)
        self.visual_grid.btn_generate_all.setText("Tạo Toàn bộ Ảnh")
