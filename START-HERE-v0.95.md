# Pinbu Note v0.95 — stability test candidate

1. Make a copy of an existing notebook before testing.
2. On Windows, run `run-windows.bat`; on Apple Silicon, use `run-mac.command`
   or the documented macOS build instructions. This is SOURCE, not an .exe/.dmg.
3. Check File > Open, editing notes, annotations, offline OCR and saving.
4. Close, reopen and check data. Force a save failure only on disposable data.
5. Test a large PDF, rapid thumbnail scrolling, tab switching and repeated
   zoom; compare memory at start, peak and after closing the document.
6. Run `python -m pytest -q` to check the source tests.
7. A GitHub draft release requires the `v0.95` tag and green Windows + both
   macOS architecture jobs. Inspect installer files before publishing.

No PinbuBoard code or feature work is included.
