# PinbuBoard · Experimental v1.1

Open the generated **Study desk** notebook, press **PinbuBoard** in the top row, and explore **The learning garden**. Drag a claim away from its evidence, draw a new connection, then undo the change. Press **Study workspace** to return to the same three-pane editor. Switching views keeps the notebook, board selection, zoom and edit history alive.

## Run on Windows x64

Use a writable copy of the playable source and Python 3.12 x64. Open PowerShell in the extracted directory containing `main.py`. One-time dependency installation needs internet access or a prepared Python wheelhouse.

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r .\requirements.txt "PySide6==6.12.0" "PySide6-WebEngine==6.12.0.140"
.\.venv\Scripts\python.exe .\main.py --pinbuboard-demo
```

For subsequent offline launches, only the last command is needed. The checked-in `frontend/pinbuboard/board.rcc` contains the HTML, CSS and JavaScript. Node and npm are only used when rebuilding the frontend. Ordinary Pinbu Note startup keeps the board disabled.

## Try the controls

| Action | Gesture |
| --- | --- |
| Pan, zoom, fit | Drag empty space, scroll to zoom, press **F** to fit. Zoom ranges from 25% to 200%. **Overview** opens a pannable, zoomable map. |
| Add a patch | Click a type in **Add a patch** to place it at the view centre. Drag it anywhere on the canvas. **Insert** adds a text note. |
| Edit text | Double-click the patch or select it and press **F2**. Edit the title and content, then choose **Apply**. **Escape** cancels. |
| Select and move | Click a patch, toggle others with Ctrl/Cmd-click, or Shift-drag a selection rectangle. Ctrl/Cmd+A selects all patches. Arrow keys nudge the selection. Shift+arrow moves 16 units. |
| Resize and arrange | Drag a selected patch's corner or edge. **Snap** aligns dragging to a 16-unit grid. **Align left** and **Align top** use the leftmost/topmost selected patch. |
| Connect | Drag a patch's right port to another patch's left port. An arrow shows the direction. Click an edge to select it. |
| Duplicate or delete | Ctrl/Cmd+D duplicates the selection and connections between its selected patches. Delete or Backspace removes selected patches/edges. |
| Undo or redo | Ctrl/Cmd+Z undoes. Ctrl/Cmd+Shift+Z or Ctrl/Cmd+Y redoes. Each completed drag, resize, text edit or group operation is one board history entry. Text fields keep their own native editing shortcuts. |
| Organise boards | Use **＋ Board**, **Rename** and the board selector. Board history is local to each named board. |
| Save and reload | Each accepted edit saves automatically. **Save** or Ctrl/Cmd+S writes immediately. **Reload** reads the disposable file and clears board undo history. Relaunching the demo restores the active board. |

## Where the files go

The launcher creates `.pinbuboard-demo/` beside `main.py`. It contains the generated study notebook, private preferences, study working copies, study backups and `boards/<notebook-id>.json`. PinbuBoard's Python model writes that JSON through a temporary file and atomic replacement. If the file changed externally, the board reports a conflict. A failed command leaves the previous graph and undo history available. Use **Reload** to accept a valid externally edited file.

Board edits never enter the notebook container. Study work in the generated notebook continues to use Pinbu Note's existing SafeSave and locking. The study workspace has its usual open/import controls. Use the generated notebook for this trial. The board button is bound to that notebook.

## Changelog

- Added an opt-in top-row workspace switch and a five-patch starter board.
- Added seven patch types, editable text, bounded pan/zoom, overview, selection, resizing, alignment, snapping, duplication and directional edges.
- Added per-board undo/redo and named boards saved in a disposable notebook-scoped JSON file.
- Bundled the offline frontend with exact dependency versions and third-party notices. [JavaScript notices](../../frontend/pinbuboard/THIRD_PARTY.md)

## Tests

From the same PowerShell directory with the demo closed:

```powershell
.\.venv\Scripts\python.exe -m pip install pytest
.\.venv\Scripts\python.exe -m pytest -q tests/test_pinbuboard_model.py tests/test_pinbuboard_playable_qt.py
```

The model tests cover validation, atomic failure, conflicts, multiple boards and undo/redo. The Qt test opens a generated notebook under a temporary directory. It exercises the actual embedded bundle, including a pointer drag, resize, a new directional connection, title/content editing, shortcuts, alignment, switching workspaces and JSON save/reload. It checks that board edits preserve the original notebook bytes.

For frontend development only, use Node 24.22.1 and npm 11.9.0. Rebuild the resource and notices from the locked dependency tree:

```powershell
Push-Location .\frontend\pinbuboard
npm ci --no-audit --no-fund
npm run build
..\..\.venv\Scripts\python.exe .\bundle.py
Pop-Location
```

## Known limitations

- This is a source-run demo. Native Windows and Apple Silicon installer and GPU acceptance tests are pending. Linux interaction testing used an offscreen software renderer and a test-process-only Chromium sandbox override. The launcher uses normal platform security.
- Each notebook library supports 16 boards, 400 patches and 800 connections per board, an 8,000 × 8,000 logical canvas and a 4 MiB JSON file. Performance at those limits has not been benchmarked.
- The board stores typed patches. Links to notebook pages, citations, rendered PDF previews and OCR results belong to later milestones. Copying or restoring a notebook alone does not transfer its experimental board library.
- A restart or explicit reload clears undo history. Viewport and selection are session state. The demo saves on completed gestures. Use **Apply** to commit text before leaving its editor.
