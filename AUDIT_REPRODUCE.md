# Reproducing v1.0 verification

Use **copies** of notebooks, not your personal working material. These commands do not require a network connection after runtime/test dependencies have been installed.

```bash
python -m compileall -q main.py yomunote ocr_packaging scripts tests
python -m pytest -q
python YomuNote-Full-Test-Audit.py --per-file-timeout 90
```

For the security review, inspect all subprocess call sites in `yomunote/importers.py`, `yomunote/ocr_engine.py`, `yomunote/voice_transcription.py` and `scripts/verify_windows_frozen.py`; automated checks cannot establish whether a selected third-party converter is trustworthy. Native Qt operations require Windows or macOS with PySide6 installed and a desktop GUI smoke test.

See `V100_FINAL_AUDIT.md` and `RELEASE_READINESS.md`.
