#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import subprocess
import sys
from pathlib import Path

from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtWidgets import (
    QApplication,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSlider,
    QVBoxLayout,
    QWidget,
)

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")


class FileDropLineEdit(QLineEdit):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)

    def dragEnterEvent(self, event):  # noqa: N802
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(self, event):  # noqa: N802
        urls = event.mimeData().urls()
        if urls and urls[0].isLocalFile():
            self.setText(urls[0].toLocalFile())
            event.acceptProposedAction()
        else:
            event.ignore()


class SeekSlider(QSlider):
    def mousePressEvent(self, event):  # noqa: N802
        if event.button() == Qt.LeftButton:
            value = QSlider.sliderValueFromPosition(
                self.minimum(),
                self.maximum(),
                event.x(),
                self.width(),
            )
            self.setValue(value)
            self.sliderMoved.emit(value)
            event.accept()
            return
        super().mousePressEvent(event)


def _import_vlc_or_exit():
    vlc_paths = [
        r"C:\Program Files (x86)\VideoLAN\VLC",
        r"C:\Program Files\VideoLAN\VLC",
        r"C:\VideoLAN\VLC",
    ]

    for base in vlc_paths:
        if not os.path.isdir(base):
            continue
        os.environ["PATH"] = base + os.pathsep + os.environ.get("PATH", "")
        os.environ["VLC_PLUGIN_PATH"] = os.path.join(base, "plugins")
        try:
            import vlc as _vlc  # pylint: disable=import-outside-toplevel

            _ = _vlc.Instance()
            print(f"VLC loaded from: {base}")
            return _vlc
        except Exception as exc:  # noqa: BLE001
            print(f"VLC load failed from {base}: {exc}")

    try:
        import vlc as _vlc  # pylint: disable=import-outside-toplevel

        _ = _vlc.Instance()
        print("VLC loaded via default path")
        return _vlc
    except Exception as exc:  # noqa: BLE001
        print("=" * 60)
        print("CRITICAL ERROR: VLC media player was not found")
        print("Install VLC from https://www.videolan.org/vlc/")
        print(f"Import error: {exc}")
        print("=" * 60)
        input("Press Enter to exit...")
        raise SystemExit(1)


vlc = _import_vlc_or_exit()


class MainWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("qt_vlc_video_cutter")
        self.resize(980, 760)

        self.file_path = ""
        self.video_duration_ms = 0
        self.selection_start_ms = 0
        self.selection_end_ms = 0
        self.fragment_loop_mode = False

        self.vlc_instance = vlc.Instance()
        self.vlc_player = self.vlc_instance.media_player_new()

        self.position_timer = QTimer(self)
        self.position_timer.timeout.connect(self.update_position)
        self.position_timer.start(100)

        self._build_ui()
        self._connect_signals()
        self._attach_vlc_events()

    def _build_ui(self):
        root = QVBoxLayout(self)

        path_row = QHBoxLayout()
        self.file_edit = FileDropLineEdit()
        self.file_edit.setPlaceholderText("Drop video here or choose file...")
        self.open_button = QPushButton("Open")
        path_row.addWidget(QLabel("Video:"))
        path_row.addWidget(self.file_edit)
        path_row.addWidget(self.open_button)
        root.addLayout(path_row)

        self.vlc_frame = QFrame()
        self.vlc_frame.setMinimumHeight(420)
        self.vlc_frame.setStyleSheet("QFrame { background: #111; }")
        root.addWidget(self.vlc_frame)

        time_row = QHBoxLayout()
        self.current_time_label = QLabel("00:00:00")
        self.timeline = SeekSlider(Qt.Horizontal)
        self.timeline.setRange(0, 1000)
        self.total_time_label = QLabel("00:00:00")
        time_row.addWidget(self.current_time_label)
        time_row.addWidget(self.timeline)
        time_row.addWidget(self.total_time_label)
        root.addLayout(time_row)

        transport = QHBoxLayout()
        self.play_button = QPushButton("Play")
        self.stop_button = QPushButton("Stop")
        self.set_start_button = QPushButton("Set Start")
        self.set_end_button = QPushButton("Set End")
        self.play_fragment_button = QPushButton("Play Fragment")
        transport.addWidget(self.play_button)
        transport.addWidget(self.stop_button)
        transport.addWidget(self.set_start_button)
        transport.addWidget(self.set_end_button)
        transport.addWidget(self.play_fragment_button)
        root.addLayout(transport)

        export_row = QHBoxLayout()
        self.process_button = QPushButton("Process Video")
        self.info_label = QLabel("Ready")
        export_row.addWidget(self.process_button)
        export_row.addWidget(self.info_label, 1)
        root.addLayout(export_row)

    def _connect_signals(self):
        self.open_button.clicked.connect(self.open_file_dialog)
        self.file_edit.editingFinished.connect(self.load_video_from_edit)

        self.play_button.clicked.connect(self.toggle_play)
        self.stop_button.clicked.connect(self.stop_video)
        self.set_start_button.clicked.connect(self.set_selection_start)
        self.set_end_button.clicked.connect(self.set_selection_end)
        self.play_fragment_button.clicked.connect(self.toggle_fragment_loop)
        self.process_button.clicked.connect(self.process_video)

        self.timeline.sliderMoved.connect(self.seek_video)

    def _attach_vlc_events(self):
        try:
            events = self.vlc_player.event_manager()
            events.event_attach(
                vlc.EventType.MediaPlayerEndReached, self._on_end_reached
            )
            events.event_attach(vlc.EventType.MediaPlayerPlaying, self._on_playing)
            events.event_attach(vlc.EventType.MediaPlayerPaused, self._on_paused)
            events.event_attach(vlc.EventType.MediaPlayerStopped, self._on_stopped)
        except Exception as exc:  # noqa: BLE001
            print(f"Failed to attach VLC events: {exc}")

    def showEvent(self, event):  # noqa: N802
        super().showEvent(event)
        if sys.platform.startswith("win"):
            self.vlc_player.set_hwnd(int(self.vlc_frame.winId()))

    def dragEnterEvent(self, event):  # noqa: N802
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(self, event):  # noqa: N802
        urls = event.mimeData().urls()
        if urls and urls[0].isLocalFile():
            path = urls[0].toLocalFile()
            self.file_edit.setText(path)
            self.load_video(path)
            event.acceptProposedAction()
        else:
            event.ignore()

    def open_file_dialog(self):
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Open video",
            "",
            "Video Files (*.mp4 *.mkv *.avi *.mov *.wmv *.webm *.m4v);;All Files (*)",
        )
        if path:
            self.file_edit.setText(path)
            self.load_video(path)

    def load_video_from_edit(self):
        path = self.file_edit.text().strip().strip('"')
        if path:
            self.load_video(path)

    def load_video(self, path: str):
        if not os.path.isfile(path):
            self.info_label.setText("File not found")
            return

        self.file_path = path
        media = self.vlc_instance.media_new(path)
        self.vlc_player.set_media(media)

        self.fragment_loop_mode = False
        self.play_fragment_button.setText("Play Fragment")
        self.selection_start_ms = 0
        self.selection_end_ms = 0

        self.vlc_player.play()
        self.play_button.setText("Pause")
        self.info_label.setText(f"Loaded: {os.path.basename(path)}")

    def toggle_play(self):
        if not self.file_path:
            self.info_label.setText("Load a video first")
            return

        state = self.vlc_player.get_state()
        if state in (vlc.State.Playing, vlc.State.Buffering):
            self.vlc_player.pause()
            self.play_button.setText("Play")
            self.info_label.setText("Paused")
        else:
            self.vlc_player.play()
            self.play_button.setText("Pause")
            self.info_label.setText("Playing")

    def stop_video(self):
        self.vlc_player.stop()
        self.play_button.setText("Play")
        self.timeline.setValue(0)
        self.current_time_label.setText("00:00:00")
        self.info_label.setText("Stopped")

    def seek_video(self, slider_value: int):
        if self.video_duration_ms <= 0:
            return
        ms = int((slider_value / 1000.0) * self.video_duration_ms)
        self.vlc_player.set_time(ms)

    def set_selection_start(self):
        t = max(0, self.vlc_player.get_time())
        self.selection_start_ms = t
        if self.selection_end_ms and self.selection_end_ms < self.selection_start_ms:
            self.selection_end_ms = self.selection_start_ms
        self.info_label.setText(f"Start: {self._fmt_ms(self.selection_start_ms)}")

    def set_selection_end(self):
        t = max(0, self.vlc_player.get_time())
        self.selection_end_ms = t
        if self.selection_end_ms < self.selection_start_ms:
            self.selection_start_ms = self.selection_end_ms
        self.info_label.setText(f"End: {self._fmt_ms(self.selection_end_ms)}")

    def toggle_fragment_loop(self):
        if self.selection_end_ms <= self.selection_start_ms:
            self.info_label.setText("Set valid Start/End first")
            return

        self.fragment_loop_mode = not self.fragment_loop_mode
        if self.fragment_loop_mode:
            self.play_fragment_button.setText("Stop Fragment")
            self.vlc_player.set_time(self.selection_start_ms)
            self.vlc_player.play()
            self.play_button.setText("Pause")
            self.info_label.setText(
                "Fragment loop: "
                f"{self._fmt_ms(self.selection_start_ms)} - {self._fmt_ms(self.selection_end_ms)}"
            )
        else:
            self.play_fragment_button.setText("Play Fragment")
            self.info_label.setText("Fragment loop disabled")

    def process_video(self):
        if not self.file_path:
            self.info_label.setText("Load a video first")
            return

        if self.selection_end_ms <= self.selection_start_ms:
            self.info_label.setText("Set valid Start/End first")
            return

        src = Path(self.file_path)
        out_dir = src.parent / "VideoCutter_out"
        out_dir.mkdir(parents=True, exist_ok=True)

        start_sec = self.selection_start_ms / 1000.0
        end_sec = self.selection_end_ms / 1000.0

        out_name = (
            f"{src.stem}_{self._fmt_ms(self.selection_start_ms).replace(':', '-')}_"
            f"{self._fmt_ms(self.selection_end_ms).replace(':', '-')}{src.suffix}"
        )
        out_file = out_dir / out_name

        cmd = [
            "ffmpeg",
            "-y",
            "-ss",
            f"{start_sec:.3f}",
            "-to",
            f"{end_sec:.3f}",
            "-i",
            str(src),
            "-c",
            "copy",
            str(out_file),
        ]

        self.info_label.setText("Processing fragment...")
        QApplication.processEvents()

        try:
            completed = subprocess.run(
                cmd,
                check=False,
                capture_output=True,
                text=True,
            )
        except FileNotFoundError:
            self.info_label.setText("ffmpeg was not found in PATH")
            return

        if completed.returncode == 0:
            self.info_label.setText(f"Saved: {out_file}")
            print(f"Saved fragment: {out_file}")
        else:
            self.info_label.setText("FFmpeg failed. See console log")
            print("FFmpeg command failed")
            print(completed.stdout)
            print(completed.stderr)

    def update_position(self):
        if not self.vlc_player:
            return

        length = self.vlc_player.get_length()
        if length and length > 0:
            self.video_duration_ms = length
            self.total_time_label.setText(self._fmt_ms(length))

        current = self.vlc_player.get_time()
        if current is None or current < 0:
            return

        self.current_time_label.setText(self._fmt_ms(current))

        if self.video_duration_ms > 0:
            slider_value = int((current / self.video_duration_ms) * 1000)
            self.timeline.blockSignals(True)
            self.timeline.setValue(max(0, min(1000, slider_value)))
            self.timeline.blockSignals(False)

        if self.fragment_loop_mode and self.selection_end_ms > self.selection_start_ms:
            if current >= self.selection_end_ms:
                self.vlc_player.set_time(self.selection_start_ms)

    def _on_end_reached(self, _event):
        self.play_button.setText("Play")
        if self.fragment_loop_mode and self.selection_end_ms > self.selection_start_ms:
            self.vlc_player.set_time(self.selection_start_ms)
            self.vlc_player.play()

    def _on_playing(self, _event):
        self.play_button.setText("Pause")

    def _on_paused(self, _event):
        self.play_button.setText("Play")

    def _on_stopped(self, _event):
        self.play_button.setText("Play")

    @staticmethod
    def _fmt_ms(ms: int) -> str:
        seconds = max(0, int(ms // 1000))
        h = seconds // 3600
        m = (seconds % 3600) // 60
        s = seconds % 60
        return f"{h:02d}:{m:02d}:{s:02d}"


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())
