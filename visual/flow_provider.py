"""
visual/flow_provider.py - Tích hợp ImageProvider với FlowController.
"""
from visual.image_provider import ImageProvider
import os, time, glob, shutil
from PySide6.QtCore import QThread, Signal, QObject

class DownloadWatcher(QThread):
    finished_signal = Signal(str, str) # seg_id, image_path
    error_signal = Signal(str, str) # seg_id, error_message
    
    def __init__(self, seg_id, dest_path, job_start_time, source_filepath=None):
        super().__init__()
        self.seg_id = seg_id
        self.dest_path = dest_path
        self.job_start_time = job_start_time
        self.source_filepath = source_filepath  # Đường dẫn chính xác từ Extension
        self.timeout = 30 # Chờ tối đa 30s sau khi Chrome báo xong

    def run(self):
        start_time = time.time()
        
        # Phương án 1: Nếu Extension gửi filepath chính xác -> dùng luôn
        if self.source_filepath:
            # Chrome downloads API trả về relative path, cần tìm trong default downloads dir
            search_paths = [
                self.source_filepath,
                os.path.join(os.path.expanduser('~\\Downloads'), self.source_filepath),
                os.path.join(os.path.expanduser('~\\Downloads'), os.path.basename(self.source_filepath)),
            ]
            
            for attempt in range(15):  # Chờ tối đa 15 giây
                for path in search_paths:
                    if os.path.exists(path):
                        time.sleep(1)  # Chờ Chrome nhả khoá file
                        try:
                            shutil.move(path, self.dest_path)
                            self.finished_signal.emit(self.seg_id, self.dest_path)
                            return
                        except Exception:
                            pass
                time.sleep(1)
        
        # Phương án 2: Quét thư mục Downloads + Flow_Images (fallback)
        downloads_dir = os.path.expanduser('~\\Downloads')
        flow_images_dir = os.path.join(downloads_dir, 'Flow_Images')
        
        while time.time() - start_time < self.timeout:
            # Nếu source_filepath được cung cấp nhưng lần đầu chưa tồn tại, chờ nó xuất hiện
            if self.source_filepath:
                if os.path.exists(self.source_filepath):
                    time.sleep(1)
                    try:
                        shutil.move(self.source_filepath, self.dest_path)
                        self.finished_signal.emit(self.seg_id, self.dest_path)
                        return
                    except Exception:
                        pass
                time.sleep(1)
                continue
            
            # Quét thư mục nếu không có filepath
            # Ưu tiên 1: Tìm file đặt tên theo seg_id trong Flow_Images (direct download)
            if os.path.exists(flow_images_dir):
                for ext in ['.png', '.jpg', '.jpeg', '.webp']:
                    seg_file = os.path.join(flow_images_dir, f"{self.seg_id}{ext}")
                    if os.path.exists(seg_file):
                        time.sleep(1)
                        try:
                            shutil.move(seg_file, self.dest_path)
                            self.finished_signal.emit(self.seg_id, self.dest_path)
                            return
                        except Exception:
                            pass
            
            # Ưu tiên 2: Quét file mới nhất trong Downloads (click-based download)
            all_files = glob.glob(os.path.join(downloads_dir, '*.*'))
            if os.path.exists(flow_images_dir):
                all_files += glob.glob(os.path.join(flow_images_dir, '*.*'))
            valid_files = [f for f in all_files if f.lower().endswith(('.png', '.jpg', '.jpeg', '.webp'))]
            
            if valid_files:
                latest_file = max(valid_files, key=os.path.getctime)
                # Chỉ lấy file được tạo ra SAU KHI job bắt đầu (có trừ hao 5 giây)
                if os.path.getctime(latest_file) >= self.job_start_time - 5:
                    # Đảm bảo file không bị tải dở
                    if not any(f.startswith(latest_file) and f.endswith('.crdownload') for f in all_files):
                        time.sleep(1)
                        try:
                            shutil.move(latest_file, self.dest_path)
                            self.finished_signal.emit(self.seg_id, self.dest_path)
                            return
                        except Exception:
                            pass
            
            time.sleep(1)
            
        self.error_signal.emit(self.seg_id, "Lỗi: Không tìm thấy file ảnh mới tải về trong thư mục Downloads.")

class FlowImageProvider(QObject):
    # Signals for async result handling in PySide6
    finished_signal = Signal(str, str) # seg_id, image_path
    error_signal = Signal(str, str) # seg_id, error_message

    def __init__(self, flow_controller, project_dir=None):
        super().__init__()
        self.flow_controller = flow_controller
        self.project_dir = project_dir if project_dir else os.getcwd()
        self.job_start_times = {}
        
        # Connect signals
        self.flow_controller.job_completed_signal.connect(self._on_job_completed)
        self.flow_controller.job_failed_signal.connect(self._on_job_failed)
        self.watchers = [] # Giữ reference để thread không bị gom rác

    def generate_image(self, prompt: str, aspect_ratio: str, model: str, num_images: str, segment_id: str) -> str:
        self.job_start_times[segment_id] = time.time()
        self.flow_controller.request_generation(segment_id, prompt, aspect_ratio, model, num_images)
        return None 
        
    def _on_job_completed(self, seg_id, data):
        if seg_id not in self.job_start_times:
            return # Bỏ qua nếu không phải job do instance này khởi tạo
            
        # Tạo thư mục đích trong project_dir
        dest_dir = os.path.join(self.project_dir, "images")
        os.makedirs(dest_dir, exist_ok=True)
        dest_path = os.path.join(dest_dir, f"{seg_id}.png")
        
        job_start = self.job_start_times.get(seg_id, time.time() - 120)
        
        # Lấy filepath chính xác từ Extension (nếu có)
        source_filepath = None
        if isinstance(data, dict):
            source_filepath = data.get("filepath")
        
        # Chạy luồng quét thư mục Downloads (hoặc dùng filepath chính xác)
        watcher = DownloadWatcher(seg_id, dest_path, job_start, source_filepath)
        watcher.finished_signal.connect(self.finished_signal.emit)
        watcher.error_signal.connect(self.error_signal.emit)
        self.watchers.append(watcher)
        watcher.start()

    def _on_job_failed(self, seg_id, error_msg):
        if seg_id not in self.job_start_times:
            return
        self.error_signal.emit(seg_id, error_msg)
