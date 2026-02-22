# qt_vlc_video_cutter

> **WARNING:** This repository may be unstable or non-functional. Use at your own risk.

PyQt5 desktop utility for quick video preview and FFmpeg-based clip cutting, using VLC as playback backend.

## Features

- Drag-and-drop video loading.
- VLC-based playback preview.
- Start/end selection and fragment loop mode.
- FFmpeg export of selected fragment.
- Automatic output file naming.

## Requirements

- Python 3.9+
- VLC player installed on the system.
- FFmpeg available in `PATH`.
- Python packages from `requirements.txt`:
  - `PyQt5`
  - `python-vlc`

## Install

```bash
make install
```

Or manually:

```bash
python -m pip install -r requirements.txt
```

## Run

```bash
make run
```

Or:

```bash
python main.py
```

## Notes

- Current implementation is Windows-oriented for VLC path detection.
- Output clips are saved to `VideoCutter_out/` next to source media.

## License

See `LICENSE`.
