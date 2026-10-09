"""Native channel control center; isolated episodes preserve existing projects."""
import json
from pathlib import Path
import threading

from PySide6.QtCore import QThread, Signal, Qt, QUrl, QTimer
from PySide6.QtGui import QDesktopServices, QPixmap, QFontDatabase
from PySide6.QtMultimedia import QMediaPlayer, QAudioOutput
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QFormLayout, QLabel, QPushButton,
                               QComboBox, QLineEdit, QTextEdit, QPlainTextEdit, QTabWidget,
                               QFileDialog, QMessageBox, QCheckBox, QGridLayout)
from channel.pipeline import Episode, ChannelPipeline, STAGES
from channel.rules import PROFILE, scene_issues
from config.config_manager import load_settings, save_settings

LABELS = {"topics": "1 · Gợi ý chủ đề", "script": "2 · Viết kịch bản", "voice": "3 · Tạo giọng đọc",
          "images": "4 · Tạo ảnh Flow", "thumbnails": "5 · Thumbnail A/B", "seo": "6 · SEO Nhật", "render": "7 · Xuất video"}


class ChannelWorker(QThread):
    progress = Signal(str)
    result = Signal(str)

    def __init__(self, folder, stage):
        super().__init__()
        self.folder, self.stage = folder, stage
        self.stop_event = threading.Event()

    def run(self):
        try:
            ChannelPipeline(Episode(self.folder), progress=self.progress.emit, stop=self.stop_event).run(self.stage)
            self.result.emit("")
        except Exception as exc:
            self.result.emit(str(exc))


class IntegrationWorker(QThread):
    success = Signal(object)
    error = Signal(str)

    def __init__(self, operation, *args):
        super().__init__()
        self.operation, self.args = operation, args

    def run(self):
        try:
            self.success.emit(self.operation(*self.args))
        except Exception as exc:
            self.error.emit(str(exc))


class ChannelPanel(QWidget):
    def __init__(self):
        super().__init__()
        self.episode = None
        self.worker = None
        self.integration_worker = None
        self.preview_player = QMediaPlayer(self)
        self.preview_audio = QAudioOutput(self)
        self.preview_player.setAudioOutput(self.preview_audio)
        self.preview_audio.setVolume(0.8)
        font_path = Path(__file__).resolve().parent.parent / "channel/assets/fonts/NotoSansJP[wght].ttf"
        if font_path.exists(): QFontDatabase.addApplicationFont(str(font_path))
        self.setObjectName("channelPanel")
        self.setStyleSheet("""
            QWidget { color: #e2e8f0; font-family: 'Noto Sans JP'; font-size: 12px; }
            QWidget#channelPanel { background: #101b30; }
            QLabel#channelTitle { color: #FFD400; font-size: 24px; font-weight: 800; }
            QTabWidget::pane { border: 1px solid #334b70; border-radius: 8px; }
            QTabBar::tab { background: #1F3864; color: white; padding: 10px 14px; }
            QTabBar::tab:selected { color: #FFD400; border-bottom: 3px solid #FFD400; }
            QPushButton { background: #1F3864; padding: 9px; }
            QPushButton:hover { background: #2b4c85; }
            QPushButton:disabled { background: #1c2940; color: #73829a; }
            QLineEdit, QTextEdit, QPlainTextEdit, QComboBox { background: #0b1425; color: #e2e8f0; border: 1px solid #334b70; border-radius: 5px; padding: 6px; }
            QComboBox QAbstractItemView { background: #101b30; color: #e2e8f0; }
        """)
        layout = QVBoxLayout(self); layout.setContentsMargins(20, 18, 20, 18); layout.setSpacing(12)
        title = QLabel("静かに稼ぐ研究室"); title.setObjectName("channelTitle")
        layout.addWidget(title)
        layout.addWidget(QLabel("KÊNH NHẬT  /  Series Bible 1.0  /  Kịch bản → Giọng đọc → Hình ảnh → Video"))
        controls = QHBoxLayout()
        self.new_button = QPushButton("Tạo tập mới"); self.new_button.clicked.connect(self.create_episode)
        self.open_button = QPushButton("Mở tập đã lưu"); self.open_button.clicked.connect(self.open_episode)
        self.folder_button = QPushButton("Mở thư mục đầu ra"); self.folder_button.clicked.connect(self.open_output)
        for button in (self.new_button, self.open_button, self.folder_button): controls.addWidget(button)
        layout.addLayout(controls)
        self.summary = QLabel("Chưa chọn tập · Nhập brief và nguồn trước khi tạo tập mới.")
        self.summary.setWordWrap(True); layout.addWidget(self.summary)
        self.tabs = QTabWidget(); layout.addWidget(self.tabs, 1)

        setup = QWidget(); setup_layout = QFormLayout(setup)
        setup_layout.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)
        self.episode_id = QLineEdit("ep001")
        self.pillar = QComboBox()
        for key, name in PROFILE["pillars"].items(): self.pillar.addItem(f"{key} · {name}", key)
        self.brief = QTextEdit(); self.brief.setPlaceholderText("Mục tiêu tập, vấn đề của người xem, điều muốn phân tích…")
        self.sources = QTextEdit(); self.sources.setPlaceholderText("URL chính thức + ngày kiểm tra + trích đoạn/số liệu đã xác minh. AI không tự truy cập các URL này.")
        self.topic = QComboBox(); self.topic.currentIndexChanged.connect(self.select_topic)
        self.topic_details = QPlainTextEdit(); self.topic_details.setReadOnly(True)
        for label, widget in [("Mã tập", self.episode_id), ("Trụ cột", self.pillar), ("Brief", self.brief),
                              ("Tài liệu nguồn", self.sources), ("Chủ đề được chọn", self.topic), ("Góc tiếp cận & dữ kiện cần tìm", self.topic_details)]:
            setup_layout.addRow(label, widget)
        self.save_brief_button = QPushButton("Lưu brief / nguồn (tạo lại các bước sau)")
        self.save_brief_button.clicked.connect(self.save_brief); setup_layout.addRow(self.save_brief_button)
        self.tabs.addTab(setup, "Chủ đề")

        script = QWidget(); script_layout = QVBoxLayout(script)
        script_layout.addWidget(QLabel("Chỉnh lời đọc, telop, biểu cảm và mô tả ảnh theo từng cảnh. Lưu sẽ kiểm tra rules."))
        self.script_editor = QPlainTextEdit(); script_layout.addWidget(self.script_editor)
        self.save_script_button = QPushButton("Kiểm tra và lưu kịch bản")
        self.save_script_button.clicked.connect(self.save_script); script_layout.addWidget(self.save_script_button)
        self.tabs.addTab(script, "Kịch bản")

        assets_page = QWidget(); assets_layout = QFormLayout(assets_page)
        self.asset_fields = {}
        defaults = load_settings()
        values = {"voicevox_url": defaults.get("VOICEVOX_URL", "http://127.0.0.1:50021"),
                  "speaker": str(defaults.get("VOICEVOX_SPEAKER", 3)), "flow_url": "http://127.0.0.1:8100",
                  "flow_project_id": "", "font": str(Path(__file__).resolve().parent.parent / "channel/assets/fonts/NotoSansJP[wght].ttf"),
                  "mascot_dir": str(Path(__file__).resolve().parent.parent / "channel/assets/mascot"),
                  "bgm": str(Path(__file__).resolve().parent.parent / "channel/assets/audio/channel_bed.wav")}
        values.update(defaults.get("JAPAN_CHANNEL_ASSETS", {}))
        descriptions = {"voicevox_url": "Địa chỉ VOICEVOX", "speaker": "Giọng VOICEVOX", "flow_url": "Địa chỉ FlowKit API",
                        "flow_project_id": "Project Google Flow", "font": "Noto Sans JP Bold/Heavy", "mascot_dir": "Thư mục 5 mascot PNG", "bgm": "Nhạc nền (tùy chọn)"}
        for key, value in values.items():
            if key not in descriptions: continue
            field = QLineEdit(str(value)); self.asset_fields[key] = field
            if key == "voicevox_url":
                row = QHBoxLayout(); row.addWidget(field)
                button = QPushButton("Kiểm tra & tải giọng"); button.clicked.connect(self.check_voicevox)
                row.addWidget(button); assets_layout.addRow(descriptions[key], row)
            elif key == "speaker":
                row = QHBoxLayout()
                self.voice_combo = QComboBox(); self.voice_combo.setMinimumWidth(330)
                self.voice_combo.addItem(f"Speaker ID đang lưu: {value}", int(value))
                self.voice_combo.currentIndexChanged.connect(self.voice_selected)
                field.setVisible(False)
                row.addWidget(self.voice_combo)
                button = QPushButton("Nghe thử"); button.clicked.connect(self.preview_voicevox)
                row.addWidget(button); assets_layout.addRow(descriptions[key], row)
            elif key == "flow_project_id":
                field.setPlaceholderText("Để trống = tự dùng project đang hoạt động trong FlowKit")
                row = QHBoxLayout(); row.addWidget(field)
                button = QPushButton("Tự lấy từ FlowKit"); button.clicked.connect(self.detect_flow_project)
                row.addWidget(button); assets_layout.addRow(descriptions[key], row)
            elif key in ("font", "mascot_dir", "bgm"):
                row = QHBoxLayout(); row.addWidget(field)
                button = QPushButton("Chọn…"); button.clicked.connect(lambda checked=False, k=key: self.choose_asset(k)); row.addWidget(button)
                assets_layout.addRow(descriptions[key], row)
            else:
                assets_layout.addRow(descriptions[key], field)
        engine_row = QHBoxLayout()
        self.engine_start_button = QPushButton("Khởi động VOICEVOX Engine")
        self.engine_start_button.clicked.connect(self.start_voicevox_engine)
        self.engine_stop_button = QPushButton("Dừng engine do app mở")
        self.engine_stop_button.clicked.connect(self.stop_voicevox_engine)
        engine_row.addWidget(self.engine_start_button); engine_row.addWidget(self.engine_stop_button)
        assets_layout.addRow("Engine tích hợp", engine_row)
        self.voice_status = QLabel("VOICEVOX: app sẽ tự khởi động engine đã cài. Bạn cũng có thể dùng các nút bên trên.")
        self.voice_status.setWordWrap(True); assets_layout.addRow("Trạng thái giọng", self.voice_status)
        self.flow_status = QLabel("FlowKit: chưa kiểm tra. UUID có thể để trống để pipeline tự lấy project đang hoạt động.")
        self.flow_status.setWordWrap(True); assets_layout.addRow("Trạng thái Flow", self.flow_status)
        info = QLabel("Mascot cố định: mascot_surprised.png, mascot_point.png, mascot_smile.png, mascot_think.png, mascot_sleep.png.\nPNG nền trong; nhân vật dùng lại ở mọi tập. Nhạc nền dùng file bạn có quyền sử dụng.")
        info.setWordWrap(True); assets_layout.addRow(info)
        guide_button = QPushButton("Mở hướng dẫn cài và dùng VOICEVOX")
        guide_button.clicked.connect(self.open_voicevox_guide); assets_layout.addRow(guide_button)
        self.save_assets_button = QPushButton("Lưu tài sản kênh")
        self.save_assets_button.clicked.connect(self.save_assets); assets_layout.addRow(self.save_assets_button)
        self.tabs.addTab(assets_page, "Tài sản kênh")

        outputs = QWidget(); outputs_layout = QVBoxLayout(outputs)
        thumb_row = QHBoxLayout()
        self.thumb_fields = [QLineEdit(), QLineEdit()]
        for index, field in enumerate(self.thumb_fields, 1):
            field.setPlaceholderText(f"Chữ thumbnail dòng {index} · tối đa 14 ký tự")
            thumb_row.addWidget(field)
        thumb_save = QPushButton("Lưu chữ thumbnail"); thumb_save.clicked.connect(self.save_thumb)
        thumb_row.addWidget(thumb_save); outputs_layout.addLayout(thumb_row)
        previews = QHBoxLayout(); self.preview_labels = []
        for name in ("Thumbnail A · Navy / Vàng", "Thumbnail B · Cream / Đen"):
            label = QLabel(name); label.setAlignment(Qt.AlignCenter); label.setMinimumHeight(150)
            previews.addWidget(label); self.preview_labels.append(label)
        outputs_layout.addLayout(previews)
        self.seo_output = QPlainTextEdit(); self.seo_output.setReadOnly(True); outputs_layout.addWidget(self.seo_output)
        self.tabs.addTab(outputs, "Thumbnail & SEO")

        review = QWidget(); review_layout = QVBoxLayout(review)
        self.reviewed = QCheckBox("Tôi đã kiểm tra nguồn, số liệu và nội dung kịch bản của tập này")
        self.reviewed.toggled.connect(self.set_reviewed); review_layout.addWidget(self.reviewed)
        self.qc = QPlainTextEdit(); self.qc.setReadOnly(True); review_layout.addWidget(self.qc)
        self.tabs.addTab(review, "Kiểm tra")
        bible = QPlainTextEdit(); bible.setReadOnly(True)
        from channel.rules import profile_snapshot
        bible.setPlainText(profile_snapshot()["bible"]); self.bible = bible
        self.tabs.addTab(bible, "Series Bible")

        stage_row = QGridLayout(); self.stage_buttons = {}
        for index, stage in enumerate(STAGES):
            button = QPushButton(LABELS[stage]); button.clicked.connect(lambda checked=False, s=stage: self.run_stage(s))
            stage_row.addWidget(button, index//4, index%4); self.stage_buttons[stage] = button
        layout.addLayout(stage_row)
        self.stop_button = QPushButton("Dừng sau thao tác đang chạy")
        self.stop_button.setEnabled(False); self.stop_button.clicked.connect(self.stop_worker); layout.addWidget(self.stop_button)
        self.log = QPlainTextEdit(); self.log.setReadOnly(True); self.log.setMaximumHeight(90)
        self.log.setMaximumBlockCount(100); layout.addWidget(self.log)
        self.refresh()

    def is_busy(self):
        return self.worker is not None and self.worker.isRunning()

    def assets(self):
        return {key: field.text().strip() for key, field in self.asset_fields.items()}

    def choose_asset(self, key):
        if key == "mascot_dir":
            path = QFileDialog.getExistingDirectory(self, "Chọn thư mục mascot")
        else:
            path, _ = QFileDialog.getOpenFileName(self, "Chọn tài sản", "", "Font (*.ttf *.otf)" if key == "font" else "Audio (*.wav *.mp3 *.flac *.m4a)")
        if path: self.asset_fields[key].setText(path)

    def start_integration(self, operation, args, success, status_label):
        if self.integration_worker and self.integration_worker.isRunning():
            return
        status_label.setText("Đang kiểm tra…")
        self.integration_worker = IntegrationWorker(operation, *args)
        self.integration_worker.success.connect(success)
        self.integration_worker.error.connect(lambda message: status_label.setText("Lỗi: " + message))
        self.integration_worker.error.connect(lambda message: self.log.appendPlainText("Lỗi kết nối: " + message))
        self.integration_worker.start()

    def check_voicevox(self):
        from channel.integrations import voicevox_info
        self.start_integration(voicevox_info, (self.asset_fields["voicevox_url"].text(),),
                               self.voicevox_ready, self.voice_status)

    def start_voicevox_engine(self):
        from channel.voicevox_runtime import start_voicevox_engine
        self.start_integration(start_voicevox_engine, (self.asset_fields["voicevox_url"].text(),),
                               self.voicevox_engine_ready, self.voice_status)

    def voicevox_engine_ready(self, status):
        ownership = "do ứng dụng quản lý" if status.get("owned_by_app") else "đã chạy từ bên ngoài"
        self.voice_status.setText(
            f"VOICEVOX Engine {status.get('version', '')} đang chạy · {ownership}. Đang tải danh sách giọng…"
        )
        QTimer.singleShot(150, self.check_voicevox)

    def stop_voicevox_engine(self):
        from channel.voicevox_runtime import stop_voicevox_engine
        status = stop_voicevox_engine()
        if status["running"]:
            self.voice_status.setText("Engine vẫn đang chạy vì tiến trình này không do ứng dụng mở.")
        else:
            self.voice_status.setText("Đã dừng VOICEVOX Engine do ứng dụng mở.")

    def voicevox_ready(self, info):
        current = int(self.asset_fields["speaker"].text() or 0)
        self.voice_combo.blockSignals(True); self.voice_combo.clear()
        selected = -1
        for index, voice in enumerate(info["speakers"]):
            self.voice_combo.addItem(voice["label"], voice["id"])
            if voice["id"] == current: selected = index
        if self.voice_combo.count(): self.voice_combo.setCurrentIndex(selected if selected >= 0 else 0)
        self.voice_combo.blockSignals(False)
        self.voice_selected(self.voice_combo.currentIndex())
        self.voice_status.setText(f"Đã kết nối VOICEVOX {info['version']} · tìm thấy {len(info['speakers'])} kiểu giọng.")

    def voice_selected(self, index):
        if index >= 0 and self.voice_combo.itemData(index) is not None:
            self.asset_fields["speaker"].setText(str(self.voice_combo.itemData(index)))

    def preview_voicevox(self):
        from channel.integrations import synthesize_voicevox_preview
        self.start_integration(synthesize_voicevox_preview,
                               (self.asset_fields["voicevox_url"].text(), self.asset_fields["speaker"].text()),
                               self.play_voice_preview, self.voice_status)

    def play_voice_preview(self, path):
        self.preview_player.setSource(QUrl.fromLocalFile(path))
        self.preview_player.play()
        label = self.voice_combo.currentText() or self.asset_fields["speaker"].text()
        self.voice_status.setText("Đang phát giọng thử: " + label)

    def detect_flow_project(self):
        from channel.integrations import discover_flowkit
        self.start_integration(discover_flowkit, (self.asset_fields["flow_url"].text(),),
                               self.flow_project_ready, self.flow_status)

    def flow_project_ready(self, info):
        if info["project_id"]:
            self.asset_fields["flow_project_id"].setText(info["project_id"])
        connection = "đã kết nối Extension" if info["extension_connected"] else "Extension chưa kết nối"
        project = info.get("project_name") or info.get("project_id") or "chưa có project"
        self.flow_status.setText(f"FlowKit {connection} · Project: {project} · nguồn: {info['source']}")

    def error(self, exc):
        self.log.appendPlainText(str(exc))
        QMessageBox.warning(self, "Kênh Nhật", str(exc))

    def create_episode(self):
        try:
            root = Path(__file__).resolve().parent.parent / "projects" / "japan_channel"
            self.episode = Episode.create(root, self.episode_id.text().strip(), self.pillar.currentData(),
                                          self.brief.toPlainText(), self.sources.toPlainText(), self.assets())
            self.refresh()
        except Exception as exc: self.error(exc)

    def open_episode(self):
        path, _ = QFileDialog.getOpenFileName(self, "Mở episode.json", str(Path(__file__).resolve().parent.parent / "projects"), "Episode (episode.json)")
        if not path: return
        try:
            self.episode = Episode(Path(path).parent); self.refresh()
        except Exception as exc: self.error(exc)

    def open_output(self):
        if self.episode: QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.episode.folder)))

    def open_voicevox_guide(self):
        guide = Path(__file__).resolve().parent.parent / "channel/VOICEVOX_GUIDE.md"
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(guide)))

    def select_topic(self, index):
        if not self.episode or index < 0: return
        state = self.episode.state
        if index >= len(state.get("topics", [])): return
        topic = state["topics"][index]
        self.topic_details.setPlainText(json.dumps(topic, ensure_ascii=False, indent=2))
        if state.get("selected_topic") != index:
            state["selected_topic"] = index; state["thumb_text"] = topic["thumb_text"]
            self.episode.invalidate("topics"); self.episode.save(); self.refresh()

    def save_brief(self):
        if not self.episode: return
        state = self.episode.state
        state.update(brief=self.brief.toPlainText(), sources=self.sources.toPlainText(), pillar=self.pillar.currentData())
        self.episode.invalidate("topics"); state["stages"].pop("topics", None)
        self.episode.save(); self.refresh()

    def save_assets(self):
        try:
            assets = self.assets(); int(assets["speaker"])
            save_settings({"JAPAN_CHANNEL_ASSETS": assets})
            if self.episode:
                previous = self.episode.state["assets"]
                affected = set()
                for key, stages in {"voicevox_url": ("voice",), "speaker": ("voice",), "font": ("thumbnails", "render"),
                                    "mascot_dir": ("thumbnails", "render"), "bgm": ("render",),
                                    "flow_project_id": ("images",), "flow_url": ("images",)}.items():
                    if previous.get(key) != assets.get(key): affected.update(stages)
                self.episode.state["assets"] = assets
                for stage in affected:
                    self.episode.invalidate(stage); self.episode.state["stages"].pop(stage, None)
                self.episode.save(); self.refresh()
            self.log.appendPlainText("Đã lưu tài sản kênh.")
        except Exception as exc: self.error(exc)

    def save_script(self):
        if not self.episode: return
        try:
            self.episode.save_script(json.loads(self.script_editor.toPlainText()))
            self.refresh()
        except Exception as exc: self.error(exc)

    def save_thumb(self):
        if not self.episode: return
        from channel.rules import thumb_issues
        lines = [field.text().strip() for field in self.thumb_fields if field.text().strip()]
        errors = thumb_issues(lines, self.episode.profile)
        if errors:
            self.error("\n".join(errors)); return
        self.episode.state["thumb_text"] = lines
        self.episode.invalidate("thumbnails")
        self.episode.state["stages"].pop("thumbnails", None)
        self.episode.save(); self.refresh()

    def set_reviewed(self, checked):
        if self.episode:
            self.episode.state["research_reviewed"] = checked; self.episode.save()

    def run_stage(self, stage):
        if not self.episode or self.is_busy(): return
        # Preserve edits only after explicit validation/save, avoiding silent loss on refresh.
        stored_script = self.episode.state.get("script_candidate", self.episode.state.get("scenes", []))
        if self.script_editor.toPlainText() != json.dumps(stored_script, ensure_ascii=False, indent=2):
            self.error("Có kịch bản đang sửa chưa lưu. Bấm 'Kiểm tra và lưu kịch bản' trước khi chạy bước tiếp theo."); return
        if self.assets() != {key: str(self.episode.state["assets"].get(key, "")) for key in self.asset_fields}:
            self.error("Tài sản đang sửa chưa lưu. Bấm 'Lưu tài sản kênh' trước."); return
        state = self.episode.state
        if (self.brief.toPlainText() != state["brief"] or self.sources.toPlainText() != state["sources"] or
                self.pillar.currentData() != state["pillar"]):
            self.error("Brief hoặc tài liệu nguồn đã thay đổi. Lưu brief / nguồn trước khi chạy."); return
        if [f.text().strip() for f in self.thumb_fields if f.text().strip()] != state.get("thumb_text", []):
            self.error("Chữ thumbnail đã thay đổi. Bấm 'Lưu chữ thumbnail' trước."); return
        self.worker = ChannelWorker(self.episode.folder, stage)
        self.worker.progress.connect(self.log.appendPlainText)
        self.worker.result.connect(self.log_result)
        self.worker.finished.connect(self.worker_finished)
        self.set_busy(True); self.worker.start()

    def log_result(self, error):
        self.log.appendPlainText("Lỗi: " + error if error else "Đã lưu kết quả.")

    def worker_finished(self):
        self.episode = Episode(self.episode.folder)
        self.set_busy(False); self.refresh()

    def stop_worker(self):
        if self.is_busy():
            self.worker.stop_event.set()
            self.log.appendPlainText("Đang dừng; chờ yêu cầu API hoặc clip FFmpeg hiện tại kết thúc.")

    def set_busy(self, busy):
        self.tabs.setEnabled(not busy)
        self.new_button.setEnabled(not busy); self.open_button.setEnabled(not busy)
        for button in self.stage_buttons.values(): button.setEnabled(not busy)
        self.stop_button.setEnabled(busy)

    def refresh(self):
        state = self.episode.state if self.episode else {}
        done = state.get("stages", {})
        for stage, button in self.stage_buttons.items():
            button.setEnabled(bool(self.episode) and not self.is_busy())
            marker = "✓ " if done.get(stage) == "done" else ("✕ " if done.get(stage) == "failed" else "")
            button.setText(marker + LABELS[stage])
        if not self.episode: return
        self.summary.setText(f"{state['id']}  ·  {state['pillar']}  ·  Bible {state['style_version']}  ·  {sum(v == 'done' for v in done.values())}/7 bước hoàn thành\n{self.episode.folder}")
        self.episode_id.setText(state["id"])
        self.pillar.setCurrentIndex(self.pillar.findData(state["pillar"]))
        self.brief.setPlainText(state["brief"]); self.sources.setPlainText(state["sources"])
        for key, field in self.asset_fields.items(): field.setText(str(state["assets"].get(key, "")))
        speaker_id = int(state["assets"].get("speaker", 0) or 0)
        index = self.voice_combo.findData(speaker_id)
        if index >= 0:
            self.voice_combo.blockSignals(True); self.voice_combo.setCurrentIndex(index); self.voice_combo.blockSignals(False)
        self.topic.blockSignals(True); self.topic.clear()
        self.topic_details.clear()
        for topic in state.get("topics", []): self.topic.addItem(topic["title_seed"])
        self.topic.setCurrentIndex(state.get("selected_topic", 0)); self.topic.blockSignals(False)
        self.select_topic(self.topic.currentIndex())
        self.script_editor.setPlainText(json.dumps(state.get("script_candidate", state.get("scenes", [])), ensure_ascii=False, indent=2))
        self.seo_output.setPlainText(json.dumps(state.get("seo", {}), ensure_ascii=False, indent=2))
        for index, field in enumerate(self.thumb_fields):
            lines = state.get("thumb_text", [])
            field.setText(lines[index] if index < len(lines) else "")
        for label in self.preview_labels:
            label.clear(); label.setText("Chưa có thumbnail được duyệt cho phiên bản này")
        for label, path in zip(self.preview_labels, state.get("thumbnails", []) if done.get("thumbnails") == "done" else []):
            pixmap = QPixmap(path)
            label.setPixmap(pixmap.scaled(420, 236, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        self.reviewed.blockSignals(True); self.reviewed.setChecked(state.get("research_reviewed", False)); self.reviewed.blockSignals(False)
        errors = scene_issues(state.get("scenes", []), self.episode.profile)
        report = ("Lỗi kịch bản:\n" + "\n".join(errors)) if errors else "Kịch bản vượt qua kiểm tra tự động. Cần nghe và đọc lại trước khi phát hành."
        report += "\n\nTrạng thái:\n" + json.dumps(done, ensure_ascii=False, indent=2)
        if state.get("last_error"): report += "\n\n" + state["last_error"]
        if state.get("voice_judgement"): report += "\n\nĐánh giá AI (cần người nghe lại):\n" + json.dumps(state["voice_judgement"], ensure_ascii=False, indent=2)
        report += "\n\nXuất bản thủ công: duyệt số liệu, quyền nhạc/mascot, khai báo AI phù hợp, nghe giọng Nhật và xem video."
        self.qc.setPlainText(report); self.bible.setPlainText(self.episode.profile["bible"])
