"""
ui/settings_panel.py - Giao diện Cài đặt (Settings) cho VQPVEO3PRO.

Nơi cấu hình các thông số toàn cục, quản lý API Keys.
Bổ sung tính năng chọn thiết bị (CPU/GPU) cho ASR Whisper.
"""

import requests
import os
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QComboBox,
    QGroupBox, QFormLayout, QLineEdit, QMessageBox, QTextEdit, QRadioButton, QButtonGroup,
    QListWidget, QListWidgetItem
)
from PySide6.QtCore import Qt, QThread, Signal

from config.config_manager import load_settings, save_settings

class ApiCheckWorker(QThread):
    """
    Background Thread (Luồng nền) để kiểm tra API Key
    Đảm bảo giao diện PySide6 không bị đơ (freeze) khi request mạng.
    """
    log_signal = Signal(str)
    models_found_signal = Signal(list)
    valid_keys_signal = Signal(list)
    finished_signal = Signal()

    def __init__(self, provider, keys_str):
        super().__init__()
        self.provider = provider
        self.keys_str = keys_str

    def run(self):
        keys = [k.strip() for k in self.keys_str.split(",") if k.strip()]
        if not keys:
            self.log_signal.emit("⚠️ Không có key nào để kiểm tra trong hệ thống hoặc vừa nhập.")
            self.finished_signal.emit()
            return
            
        self.log_signal.emit(f"🔄 Đang kiểm tra {len(keys)} key(s) của {self.provider}...\n")
        
        all_models = set()
        valid_keys = []
        
        for idx, key in enumerate(keys):
            masked_key = key[:5] + "..." + key[-4:] if len(key) > 10 else "***"
            
            if "Gemini" in self.provider:
                try:
                    url = f"https://generativelanguage.googleapis.com/v1beta/models?key={key}"
                    resp = requests.get(url, timeout=10)
                    if resp.status_code == 200:
                        data = resp.json()
                        api_models = [m['name'] for m in data.get('models', [])]
                        RECOMMENDED_MODELS = [
                            "models/gemini-2.5-flash",
                            "models/gemini-3.8-flash",
                            "models/gemini-3.6-flash",
                            "models/gemini-3.5-flash",
                            "models/gemini-3.1-flash-lite",
                            "models/gemini-flash-lite-latest",
                            "models/gemini-3-flash-preview",
                            "models/gemma-4-26b-a4b-it"
                        ]
                        for m in RECOMMENDED_MODELS:
                            if m in api_models:
                                all_models.add(m)
                            
                        valid_keys.append(key)
                        self.log_signal.emit(f"✅ Key {idx+1} ({masked_key}): HỢP LỆ (HTTP 200).")
                    else:
                        self.log_signal.emit(f"❌ Key {idx+1} ({masked_key}): KHÔNG HỢP LỆ (Lỗi {resp.status_code}) -> Sẽ bị xóa.")
                except Exception as e:
                    self.log_signal.emit(f"❌ Key {idx+1} ({masked_key}): LỖI MẠNG ({str(e)}) -> Không được thêm vào.")
            else:
                self.log_signal.emit(f"⚠️ Chưa hỗ trợ kiểm tra tự động cho provider: {self.provider}")
                valid_keys.append(key)
        
        self.log_signal.emit("\nHoàn tất kiểm tra!")
        self.models_found_signal.emit(list(all_models))
        self.valid_keys_signal.emit(valid_keys)
        self.finished_signal.emit()

class GpuCheckWorker(QThread):
    """
    Luồng kiểm tra thư viện GPU và CTranslate2 / faster-whisper.
    """
    result_signal = Signal(bool, str)
    
    def run(self):
        try:
            import ctranslate2
            types = ctranslate2.get_supported_compute_types("cuda")
            if types:
                self.result_signal.emit(True, f"Kiểm tra thành công! GPU hợp lệ. Compute_types hỗ trợ: {', '.join(types)}")
            else:
                self.result_signal.emit(False, "Cài đặt faster-whisper (ctranslate2) thành công, nhưng không tìm thấy CUDA tương thích (Có thể thiếu cuDNN).")
        except ImportError:
            self.result_signal.emit(False, "Chưa cài đặt faster-whisper hoặc ctranslate2. Vui lòng cài đặt trước.")
        except Exception as e:
            self.result_signal.emit(False, f"Lỗi không xác định khi kiểm tra GPU: {str(e)}")

class SettingsPanel(QWidget):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        title_label = QLabel("SYSTEM SETTINGS")
        title_label.setStyleSheet("font-size: 20px; font-weight: bold; color: #f59e0b;")
        layout.addWidget(title_label)

        # ------------------------------------------------
        # 1. AI Configuration Group
        # ------------------------------------------------
        ai_group = QGroupBox("AI Providers (API Keys)")
        ai_group.setStyleSheet("QGroupBox { font-weight: bold; padding-top: 15px; margin-top: 10px; border: 1px solid #1e293b; border-radius: 6px; }")
        ai_layout = QFormLayout(ai_group)
        ai_layout.setSpacing(12)
        
        self.combo_ai_provider = QComboBox()
        self.combo_ai_provider.addItems(["Gemini (Google)", "OpenAI (ChatGPT)", "OpenRouter"])
        self.combo_ai_provider.setFixedHeight(30)
        self.combo_ai_provider.currentTextChanged.connect(self.load_current_provider_keys)
        ai_layout.addRow("AI Provider:", self.combo_ai_provider)
        
        self.api_key_input = QLineEdit()
        self.api_key_input.setPlaceholderText("Nhập API Key MỚI vào đây (cách nhau bởi dấu phẩy ',') để thêm...")
        self.api_key_input.setEchoMode(QLineEdit.Password)
        self.api_key_input.setFixedHeight(30)
        ai_layout.addRow("Thêm API Keys:", self.api_key_input)
        
        self.combo_ai_model = QComboBox()
        self.combo_ai_model.setFixedHeight(30)
        ai_layout.addRow("AI Model:", self.combo_ai_model)
        
        check_layout = QVBoxLayout()
        self.btn_check_api = QPushButton("Kiểm tra API Keys hệ thống & Lấy danh sách Models")
        self.btn_check_api.setFixedSize(320, 35)
        self.btn_check_api.setStyleSheet("background-color: #3b82f6; color: white; font-weight: bold; border-radius: 6px;")
        self.btn_check_api.clicked.connect(self.check_api_keys)
        
        self.txt_log = QTextEdit()
        self.txt_log.setReadOnly(True)
        self.txt_log.setFixedHeight(120)
        self.txt_log.setStyleSheet("background-color: #070a12; color: #9ca3af; font-family: monospace; border: 1px solid #1e293b;")
        
        check_layout.addWidget(self.btn_check_api)
        check_layout.addWidget(self.txt_log)
        ai_layout.addRow("Trạng thái:", check_layout)
        
        layout.addWidget(ai_group)
        
        # ------------------------------------------------
        # 2. ASR (Whisper) Hardware Configuration Group
        # ------------------------------------------------
        asr_group = QGroupBox("Cấu hình Nhận diện giọng nói (ASR / Whisper)")
        asr_group.setStyleSheet("QGroupBox { font-weight: bold; padding-top: 15px; margin-top: 10px; border: 1px solid #1e293b; border-radius: 6px; }")
        asr_layout = QVBoxLayout(asr_group)
        asr_layout.setSpacing(12)
        
        lbl_asr_desc = QLabel("Thiết bị xử lý mô hình AI nhận diện giọng nói:")
        asr_layout.addWidget(lbl_asr_desc)
        
        radio_layout = QVBoxLayout()
        self.radio_cpu = QRadioButton("CPU (Chạy nội bộ, chậm hơn, an toàn trên mọi máy)")
        self.radio_gpu = QRadioButton("GPU - NVIDIA CUDA (Chạy nội bộ, cực nhanh, yêu cầu Card NVIDIA)")
        self.radio_groq = QRadioButton("API - Groq Cloud (Tốc độ siêu nhanh, không tốn tài nguyên máy tính)")
        
        # Mặc định là CPU
        self.radio_cpu.setChecked(True)
        
        self.btn_group_asr = QButtonGroup(self)
        self.btn_group_asr.addButton(self.radio_cpu)
        self.btn_group_asr.addButton(self.radio_gpu)
        self.btn_group_asr.addButton(self.radio_groq)
        
        radio_layout.addWidget(self.radio_cpu)
        radio_layout.addWidget(self.radio_gpu)
        radio_layout.addWidget(self.radio_groq)
        asr_layout.addLayout(radio_layout)
        
        # Ô nhập API Key cho Groq
        self.groq_key_layout = QHBoxLayout()
        self.lbl_groq_key = QLabel("Groq API Key:")
        self.txt_groq_key = QLineEdit()
        self.txt_groq_key.setEchoMode(QLineEdit.Password)
        self.txt_groq_key.setPlaceholderText("Nhập Groq API Key (bắt buộc nếu chọn Groq Cloud)...")
        self.txt_groq_key.setEnabled(False) # Chỉ bật khi chọn Groq
        self.groq_key_layout.addWidget(self.lbl_groq_key)
        self.groq_key_layout.addWidget(self.txt_groq_key)
        asr_layout.addLayout(self.groq_key_layout)
        
        self.lbl_gpu_status = QLabel("")
        self.lbl_gpu_status.setStyleSheet("color: #f59e0b; font-style: italic;")
        asr_layout.addWidget(self.lbl_gpu_status)
        
        # Xử lý Event thay đổi
        self.radio_gpu.toggled.connect(self.on_gpu_toggled)
        self.radio_groq.toggled.connect(self.on_groq_toggled)
        
        layout.addWidget(asr_group)

        # ------------------------------------------------
        # 3. CHROME & GOOGLE FLOW INTEGRATION
        # ------------------------------------------------
        chrome_group = QGroupBox("Cấu hình Trình duyệt Chrome & Google Flow")
        chrome_group.setStyleSheet("QGroupBox { font-weight: bold; padding-top: 15px; margin-top: 10px; border: 1px solid #1e293b; border-radius: 6px; }")
        chrome_layout = QVBoxLayout(chrome_group)
        chrome_layout.setSpacing(12)
        
        lbl_chrome_desc = QLabel("Chọn các tài khoản (Profiles) Chrome đã đăng nhập sẵn Google để dùng Flow (Tích chọn để sử dụng):")
        chrome_layout.addWidget(lbl_chrome_desc)
        
        chrome_row = QHBoxLayout()
        self.list_chrome_profiles = QListWidget()
        self.list_chrome_profiles.setFixedHeight(100)
        
        self.btn_test_chrome = QPushButton("Mở thủ công (Test)")
        self.btn_test_chrome.setFixedSize(150, 32)
        self.btn_test_chrome.setStyleSheet("background-color: #3b82f6; color: white; font-weight: bold; border-radius: 4px;")
        self.btn_test_chrome.clicked.connect(self.test_launch_chrome)
        
        chrome_row.addWidget(self.list_chrome_profiles, stretch=1)
        chrome_row.addWidget(self.btn_test_chrome)
        chrome_layout.addLayout(chrome_row)
        
        # Thêm cấu hình tạo ảnh mặc định
        flow_settings_layout = QHBoxLayout()
        flow_settings_layout.addWidget(QLabel("Tỷ lệ Flow:"))
        self.cmb_flow_ratio = QComboBox()
        self.cmb_flow_ratio.addItems(["Mặc định", "16:9", "9:16", "1:1", "4:3", "3:4"])
        flow_settings_layout.addWidget(self.cmb_flow_ratio)
        
        flow_settings_layout.addWidget(QLabel("Model Flow:"))
        self.cmb_flow_model = QComboBox()
        self.cmb_flow_model.addItems(["Mặc định", "Nano Banana pro", "Nano Banana 2", "Nano Banana 2 Lite"])
        flow_settings_layout.addWidget(self.cmb_flow_model)
        
        flow_settings_layout.addWidget(QLabel("Số lượng Flow:"))
        self.cmb_flow_num = QComboBox()
        self.cmb_flow_num.addItems(["Mặc định", "1", "2", "3", "4"])
        flow_settings_layout.addWidget(self.cmb_flow_num)
        
        flow_settings_layout.addStretch()
        chrome_layout.addLayout(flow_settings_layout)
        
        layout.addWidget(chrome_group)

        # Nút Lưu cấu hình tổng
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        self.btn_save = QPushButton("Save Configuration")
        self.btn_save.setFixedSize(160, 40)
        self.btn_save.setStyleSheet("""
            QPushButton { background-color: #10b981; color: white; font-weight: bold; border-radius: 6px; }
            QPushButton:hover { background-color: #059669; }
        """)
        self.btn_save.clicked.connect(self.save_settings)
        btn_layout.addWidget(self.btn_save)
        layout.addLayout(btn_layout)
        
        layout.addStretch()
        
        # Khởi tạo load dữ liệu đã lưu
        self.load_current_provider_keys()
        self.load_asr_settings()

    def load_asr_settings(self):
        self.load_chrome_profiles()
        settings = load_settings()
        asr_device = settings.get("ASR_DEVICE", "cpu")
        groq_key = settings.get("GROQ_API_KEY", "")
        
        self.txt_groq_key.setText(groq_key)
        
        flow_ratio = settings.get("FLOW_RATIO", "Mặc định")
        flow_model = settings.get("FLOW_MODEL", "Mặc định")
        flow_num = settings.get("FLOW_NUM", "Mặc định")
        
        self.cmb_flow_ratio.setCurrentText(flow_ratio)
        self.cmb_flow_model.setCurrentText(flow_model)
        self.cmb_flow_num.setCurrentText(flow_num)
        
        if asr_device == "gpu":
            self.radio_gpu.blockSignals(True)
            self.radio_gpu.setChecked(True)
            self.radio_gpu.blockSignals(False)
            self.lbl_gpu_status.setText("Đang sử dụng cấu hình GPU.")
        elif asr_device == "groq":
            self.radio_groq.blockSignals(True)
            self.radio_groq.setChecked(True)
            self.radio_groq.blockSignals(False)
            self.txt_groq_key.setEnabled(True)
            self.lbl_gpu_status.setText("Đang sử dụng dịch vụ nhận diện API Groq Cloud.")

    def on_groq_toggled(self, checked):
        self.txt_groq_key.setEnabled(checked)
        if checked:
            self.lbl_gpu_status.setText("Đang sử dụng dịch vụ nhận diện API Groq Cloud.")

    def on_gpu_toggled(self, checked):
        if checked:
            self.lbl_gpu_status.setText("Đang kiểm tra thư viện GPU...")
            self.gpu_worker = GpuCheckWorker()
            self.gpu_worker.result_signal.connect(self.on_gpu_check_result)
            self.gpu_worker.start()
        else:
            if not self.radio_groq.isChecked():
                self.lbl_gpu_status.setText("Đang sử dụng CPU.")

    def on_gpu_check_result(self, is_valid, message):
        if is_valid:
            self.lbl_gpu_status.setText(f"✅ {message}")
            self.lbl_gpu_status.setStyleSheet("color: #10b981; font-style: italic;")
        else:
            self.lbl_gpu_status.setText(f"❌ {message}")
            self.lbl_gpu_status.setStyleSheet("color: #ef4444; font-style: italic;")
            QMessageBox.warning(
                self, "Lỗi GPU",
                f"Không thể sử dụng GPU vì:\n{message}\n\nHệ thống sẽ tự động chuyển về CPU để đảm bảo an toàn."
            )
            # Tự động trả về CPU
            self.radio_gpu.blockSignals(True)
            self.radio_cpu.setChecked(True)
            self.radio_gpu.blockSignals(False)

    def load_current_provider_keys(self):
        provider = self.combo_ai_provider.currentText()
        settings = load_settings()
        saved_model = settings.get(f"{provider}_MODEL", "")
        self.api_key_input.clear()
        self.combo_ai_model.clear()
        
        if "Gemini" in provider:
            available_models = [
                "models/gemini-2.5-flash",
                "models/gemini-3.8-flash",
                "models/gemini-3.6-flash",
                "models/gemini-3.5-flash",
                "models/gemini-3.1-flash-lite",
                "models/gemini-flash-lite-latest",
                "models/gemini-3-flash-preview",
                "models/gemma-4-26b-a4b-it"
            ]
            self.combo_ai_model.addItems(available_models)
            if saved_model and saved_model in available_models:
                self.combo_ai_model.setCurrentText(saved_model)
            elif saved_model:
                self.combo_ai_model.addItem(saved_model)
                self.combo_ai_model.setCurrentText(saved_model)
            else:
                self.combo_ai_model.setCurrentText("models/gemini-2.5-flash")
        elif saved_model:
            self.combo_ai_model.addItem(saved_model)

    def check_api_keys(self):
        provider = self.combo_ai_provider.currentText()
        new_keys_str = self.api_key_input.text()
        settings = load_settings()
        existing_keys_str = settings.get(f"{provider}_API_KEYS", "")
        all_keys = []
        if existing_keys_str:
            all_keys.extend([k.strip() for k in existing_keys_str.split(",") if k.strip()])
        if new_keys_str:
            all_keys.extend([k.strip() for k in new_keys_str.split(",") if k.strip()])
        all_keys = list(dict.fromkeys(all_keys))
        combined_keys_str = ",".join(all_keys)
        
        self.txt_log.clear()
        self.btn_check_api.setEnabled(False)
        self.btn_save.setEnabled(False)
        
        self.worker = ApiCheckWorker(provider, combined_keys_str)
        self.worker.log_signal.connect(self.append_log)
        self.worker.models_found_signal.connect(self.populate_models)
        self.worker.valid_keys_signal.connect(self.save_valid_keys)
        self.worker.finished_signal.connect(self.on_check_finished)
        self.worker.start()
        
    def append_log(self, text):
        self.txt_log.append(text)
        
    def save_valid_keys(self, valid_keys):
        provider = self.combo_ai_provider.currentText()
        save_settings({
            f"{provider}_API_KEYS": ",".join(valid_keys)
        })
        self.api_key_input.clear()
        self.txt_log.append(f"\n[HỆ THỐNG] Đã lưu {len(valid_keys)} key hợp lệ vào config.")
        
    def populate_models(self, models):
        if models:
            current_model = self.combo_ai_model.currentText()
            self.combo_ai_model.clear()
            sorted_models = sorted(models)
            self.combo_ai_model.addItems(sorted_models)
            if current_model in sorted_models:
                self.combo_ai_model.setCurrentText(current_model)
            else:
                # Ưu tiên gemini-2.5-flash vì tính ổn định cao nhất
                default_target = "models/gemini-2.5-flash"
                if default_target in sorted_models:
                    self.combo_ai_model.setCurrentText(default_target)
                elif sorted_models:
                    self.combo_ai_model.setCurrentIndex(0)

    def save_settings(self):
        provider = self.combo_ai_provider.currentText()
        selected_model = self.combo_ai_model.currentText()
        
        if self.radio_gpu.isChecked():
            asr_device = "gpu"
        elif self.radio_groq.isChecked():
            asr_device = "groq"
        else:
            asr_device = "cpu"
            
        groq_key = self.txt_groq_key.text().strip()
        
        flow_ratio = self.cmb_flow_ratio.currentText()
        flow_model = self.cmb_flow_model.currentText()
        flow_num = self.cmb_flow_num.currentText()
        
        # Lấy danh sách profile được check
        selected_profiles = []
        for i in range(self.list_chrome_profiles.count()):
            item = self.list_chrome_profiles.item(i)
            if item.checkState() == Qt.Checked:
                selected_profiles.append(item.data(Qt.UserRole))
        
        save_settings({
            "DEFAULT_AI_PROVIDER": provider,
            f"{provider}_MODEL": selected_model,
            "ASR_DEVICE": asr_device,
            "GROQ_API_KEY": groq_key,
            "FLOW_RATIO": flow_ratio,
            "FLOW_MODEL": flow_model,
            "FLOW_NUM": flow_num,
            "SELECTED_CHROME_PROFILES": selected_profiles
        })
        
        QMessageBox.information(
            self, "Settings Saved",
            f"Đã lưu các thiết lập thành công!\n- API Model: {selected_model}\n- ASR Device: {asr_device.upper()}\n- Flow Tỉ lệ: {flow_ratio}\n- Flow Model: {flow_model}\n- Số Profiles Flow: {len(selected_profiles)}"
        )

    def on_check_finished(self):
        self.btn_check_api.setEnabled(True)
        self.btn_save.setEnabled(True)

    def load_chrome_profiles(self):
        from chrome.profile_manager import ChromeProfileManager
        from config.config_manager import load_settings
        self.list_chrome_profiles.clear()
        
        settings = load_settings()
        selected_profiles = settings.get("SELECTED_CHROME_PROFILES", [])
        
        profiles = ChromeProfileManager.get_available_profiles()
        for p_dir, p_name in profiles.items():
            item = QListWidgetItem(f"{p_name} ({p_dir})")
            item.setData(Qt.UserRole, p_dir)
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
            
            # Khôi phục trạng thái đã check
            if p_dir in selected_profiles:
                item.setCheckState(Qt.Checked)
            else:
                item.setCheckState(Qt.Unchecked)
                
            self.list_chrome_profiles.addItem(item)
            
    def test_launch_chrome(self):
        from chrome.chrome_manager import ChromeManager
        # Chỉ launch các profile được chọn
        selected_dirs = []
        for i in range(self.list_chrome_profiles.count()):
            item = self.list_chrome_profiles.item(i)
            if item.checkState() == Qt.Checked:
                selected_dirs.append(item.data(Qt.UserRole))
                
        if not selected_dirs:
            QMessageBox.warning(self, "Lỗi", "Vui lòng tích chọn ít nhất 1 Profile.")
            return
            
        try:
            self.btn_test_chrome.setText("Đang mở...")
            self.btn_test_chrome.setEnabled(False)
            for p_dir in selected_dirs:
                ChromeManager.launch_chrome(p_dir)
            QMessageBox.information(self, "Thành công", f"Đã khởi chạy {len(selected_dirs)} Chrome! Hãy kiểm tra đèn báo kết nối ở MainWindow.")
        except Exception as e:
            QMessageBox.critical(self, "Lỗi", f"Không thể khởi chạy Chrome: {e}")
        finally:
            self.btn_test_chrome.setText("Mở thủ công (Test)")
            self.btn_test_chrome.setEnabled(True)
