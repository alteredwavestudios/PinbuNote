# PinbuBoard v1.1 engineering assessment

The playable milestone now has a Windows launch guide, controls, tests and limitations. [Play the experimental draft](PLAYABLE.md)

18 November 2026 · `experiment/pinbuboard-v1.1` · Pinbu Note base `afbbfcfa0f1bb007b52a6e5e936899664d1bd098`

**Recommend a single board that opens on demand, using React Flow 13.0.2 and an in-memory Python model.** The two-node probe ran with both React Flow 12 and 13. Opening Chromium cost much more memory than loading the graph data. Keep the first integration read-only with respect to notebook sources. Make notebook-format work a separate milestone with its own backup and recovery tests.

The only executable work here is a standalone synthetic probe. There is no entry point from Pinbu Note. The directions below describe a proposed integration unless explicitly identified as measured or existing.

## 1. Architecture and ownership

```mermaid
flowchart TB
  subgraph desktop["Pinbu Note · Python and Qt"]
    window["MainWindow · explicit experimental action"]
    board["One board controller per open notebook"]
    bridge["Small QObject · validates requests and session"]
    graph["Python board model · edits, revision and history"]
    panes["Live ProjectPane models · page and reference IDs"]
    workers["Existing preview, PDFium and OCR workers"]
    save["Existing working copy, SafeSave and origin lease"]
    window --> board
    board --> bridge
    bridge --> graph
    bridge --> panes
    panes --> workers
    graph -. future versioned persistence .-> save
  end
  subgraph renderer["Local QWebEngineView · dedicated off-the-record profile"]
    assets["Packaged Qt resource · HTML, CSS, JS and Qt channel client"]
    flow["React Flow · graph, drag, selection, viewport"]
    assets --> flow
  end
  flow <-->|"QWebChannel · typed requests and replies"| bridge
```

A drag illustrates the boundary. React moves the card immediately under the pointer. On drop it sends one list of final positions. Python checks the current board revision, records one undoable edit and replies with the accepted revision. A lost reply can be recovered from Python. Drag frames, zoom, hover, selection and React Flow's measured dimensions stay in the view. A saved board would contain user-authored text, IDs, node positions and edges. Preview pixels, OCR jobs and clipboard contents have independent lifetimes.

### Where the existing code fits

| Inspected code | Integration consequence |
| --- | --- |
| `MainWindow.show_notebook`, `_attach_pane` and `_retire_notebook` | The window owns one notebook with multiple tab panes. Put the experimental action at window scope. Keep a single view across tab switches. Resolve a source against the owning live pane, including pending edits. `Notebook.project(tabid)` loads a project from disk, which can lag an editor. [Window](../../yomunote/window.py) · [Notebook](../../yomunote/notebook.py) |
| `Notebook.open_session`, `open_working_copy`, `NotebookLease` and `publish` | The app leases the origin locally, opens a private SQLite copy, and checks the origin's disk signature on explicit publish. The controller borrows that session and lifetime. Lookups require zero additional notebook opens or leases. [SafeSave session](../../yomunote/safe_session.py) · [Locking](../../yomunote/notebook_lock.py) |
| `_manifest`, `_safe_relative`, `_files`, `capture_save_snapshot`, `write_snapshot` | The root manifest is reconstructed. Save enumerates specific tab manifests and live assets, and the loader validates entry paths. Dropping `board.json` in the workspace could lose it on save. An arbitrary root entry could also fail to reopen. Both synchronous and background save paths matter. [Container](../../yomunote/notebook.py) · [Snapshot writer](../../yomunote/snapshot_save.py) |
| `effective_reference`, `effective_page_label`, `render_reference`, `to_plain` | Resolve explicit and inherited research records from the owning project's tree and research metadata. Return plain text. An explicitly cleared page citation must stay empty. [Research](../../yomunote/research.py) |
| `image_for_page`, `PDFIUM_LOCK`, `inspect_page`, `recognise_regions`, `start_task` | Request a bounded thumbnail from the current renderer. Use existing PDF text geometry where applicable. Keep optional recognition with the native OCR selection/review flow. PDFium's shared lock covers object creation through disposal. Queue work and return results on the GUI thread. [Rendering](../../yomunote/importers.py) · [PDF lock](../../yomunote/pdfium_guard.py) · [PDF text](../../yomunote/pdf_text_engine.py) · [OCR](../../yomunote/ocr_engine.py) · [Tasks](../../yomunote/tasks.py) |
| `UnifiedHistory`, `CallbackAction`, `MainWindow._history_target`, `RetiredNotebookQueue` | Use the existing bounded history implementation. In the disposable board, use a board-owned instance and route shortcuts by focus. Design integration with the notebook history clock before persistent shared editing. Include source-reading workers in the retirement barrier so old PDFs stay available until their workers finish. [History](../../yomunote/history.py) · [Lifecycle](../../yomunote/lifecycle.py) |
| `Notebook.transfer_pages` | Transfers allocate new page IDs, including on moves. Track the actual old/new mapping in a future integrated move transaction. Copies keep the original pin attached to the original. Deletion or an ambiguous move shows a missing-source card. Never reattach by title or page order. Older page IDs can be short strings. [Transfer](../../yomunote/notebook.py) · [Research regression tests](../../tests/test_v092a_research.py) |

## 2. Dependency decision

| Component | Experimental baseline | Reason |
| --- | --- | --- |
| Python / PySide6 | Python 3.12.14, PySide6 6.12.0 | Matches the project's Python 3.12 CI line and fits its Qt range. The resolved wheel set included PySide6-WebEngine 6.12.0.140, Qt WebEngine 6.140.0, Chromium 140.0.7339.225 and Shiboken6 6.12.0. Record the actual Chromium and security-patch versions per build. [Project requirements](../../requirements.txt) · [Qt wheel](https://pypi.org/project/PySide6-WebEngine/6.12.0.140/) |
| Graph | `@xyflow/react` **13.0.2**. Comparison baseline **12.12.1** | Both loaded from Qt resources. This is a new UI, so it can adopt v13 changesets and finer-grained subscriptions immediately. v12 delivers a smaller sample bundle. Keep the protocol independent of both versions. [Registry](https://registry.npmjs.org/@xyflow%2freact) · [Upstream migration guide](https://reactflow.dev/learn/troubleshooting/migrate-to-v13) |
| UI | `react` and `react-dom` **19.3.1**. Both React type packages **19.3.0** | Matched versions for the renderer and the tested exact build. v13 requires React 18+ and uses Zustand 5 internally. No direct store dependency is needed for this probe. [Frontend lock](probe/package-lock.json) |
| Build only | Node **24.22.1**, npm **11.9.0**, TypeScript **7.0.2**, Vite **8.3.8** | Use the checked-in npm lock and a production build with relative asset URLs. Set a deliberate browser target (`chrome120` in the probe). Syntax targeting alone cannot supply missing browser APIs or validate Qt resource handling. [Vite production builds](https://vite.dev/guide/build) |
| Existing native tools | Keep the project's pypdfium2 and Pillow constraints. Probe regression environment resolved **5.15.2** and **12.3.0**. Use the existing PyInstaller 6.x build path, starting native trials at **6.22.3**. | Keep board pins in the experiment. The 6.12 WebEngine wheels advertise Windows x64 and macOS 14+ universal2. If Pinbu Note supports an earlier macOS baseline, gate the board separately. [PySide6](https://pypi.org/project/PySide6/6.12.0/) · [Windows build](../../build-windows.ps1) · [macOS build](../../build-mac.command) |

v13 changes the node/edge change callback payload and CSS layering. A v12 controlled view uses change arrays and `applyNodeChanges`. In v13 a changeset has `applyTo()`. Keep that difference inside the frontend adapter. Pan, zoom, selection, dragging, connecting handles, custom nodes and rendering edges use the public library. For undo, capture inverse board commands in Python, group a multi-card drag once, remove incident edges atomically with a node, and clear redo after a new edit. Keep native text undo in a focused editor. The upstream undo/redo **example** has a separate Pro licence. This design uses independently written commands. [Free library](https://reactflow.dev/) · [Undo/redo example terms](https://reactflow.dev/examples/interaction/undo-redo)

## 3. Proposed directories

```text
experiments/pinbuboard/
  README.md                         this assessment
  probe/                            implemented standalone compatibility check
    host.py, bundle.py              Qt host and build-time resource compiler
    index.html, probe.tsx, size.css  disposable two-node graph
    package*.json, tsconfig.json    exact JS versions and build settings

# Proposed for later milestones on this experimental branch
frontend/pinbuboard/                TypeScript UI, protocol types, Vite config and lock
yomunote/pinbuboard/
  host.py                           lazy view, profile, request filter and lifetime
  bridge.py                         small QObject and protocol validation
  model.py                          graph state, revision and reversible commands
  sources.py                        adapter to existing panes and native services
assets/pinbuboard/                  build output: resource bundle and licence texts
tests/pinbuboard/                   protocol, teardown, compatibility and safety fixtures
```

Keep future QtWebEngine imports behind both a developer opt-in and an explicit open action. The experiment launcher should create its own temporary settings, working-copy and backup roots and generate its notebook there. Do not consult recent files or recovery history from normal Pinbu Note. The standalone probe has no Pinbu Note imports or notebook argument.

## 4. Proposed QWebChannel v1 contract

Expose one QObject named `board` with a single application slot `submit(str)` and one outbound signal `message(str)`. Both carry UTF-8 JSON. Keep the Qt channel client local. Construct one channel per transport, connect the signal handler before sending `hello`, and make the board unavailable until `welcome`. The probe's two synthetic methods only test transport. [Qt JavaScript client lifecycle](https://doc.qt.io/qt-6/qtwebchannel-javascript.html)

| Direction and type | Required payload and result |
| --- | --- |
| JS → Python `hello` | Initial envelope `{v:1,id,type:"hello",payload:{}}`. Python binds this already-approved page to its current notebook and replies `welcome` with a fresh opaque session, revision and capabilities. A repeated hello on an established page returns its current binding. |
| JS → Python `graph.read` | Empty payload plus session. Python replies with `revision`, `nodes` and `edges`. A node has `id,kind,x,y`, plus plain `text` for an idea or an opaque `sourceId` for a pin. An edge has `id,from,to`. A source ID is minted by Python for this session. |
| JS → Python `graph.edit` | Session and integer `baseRevision` required. A discriminated payload contains exactly one of `moveNodes {moves:[{id,x,y}]}`, `addIdea {text,x,y}`, `link {from,to}` or `remove {nodeIds,edgeIds}`. Python allocates new IDs and returns the canonical patch and revision. Validate the entire batch before applying it. |
| JS → Python `history.undo` / `history.redo` | Empty payload, session and base revision. A board-focused command gets the same canonical patch/revision response. A failed or unavailable command leaves graph and history intact. |
| JS → Python `source.reference` / `source.preview` | `{sourceId}` or `{sourceId,width:160\|320}`. Resolve against the current session. Return bounded plain citation/locator strings or `{mime:"image/png",width,height,base64}`. Revocation, missing sources and oversized results produce typed errors. An explicit native “Open source” action can bring the owning pane to its page and existing OCR tools. |
| Python → JS replies/events | Reply `{v,id,session,type:"ok",revision,payload}` or `{v,id,session,type:"error",code,revision}`. A pre-handshake version error can omit session. An unsolicited `invalidated` event has session and current revision, no request ID. Discard stale replies and re-read after gaps. Show the failed edit as unconfirmed. |

For example, a drag request and its reply could look like this.

```json
{"v":1,"id":"r17","session":"example-session","type":"graph.edit","baseRevision":4,"payload":{"op":"moveNodes","moves":[{"id":"n2","x":184,"y":96}]}}
```

```json
{"v":1,"id":"r17","session":"example-session","type":"ok","revision":5,"payload":{"upsertNodes":[{"id":"n2","kind":"idea","text":"Compare sources","x":184,"y":96}],"removeNodeIds":[],"upsertEdges":[],"removeEdgeIds":[]}}
```

Initial proposed limits for testing are 64 KiB per inbound request, 4 KiB of UTF-8 per idea, 128 moves per command, 128 characters per ID, finite coordinates within ±1,000,000 and 128 KiB per compressed thumbnail before base64. Cap decoded image dimensions at 320 × 320. Limit graph replies to 1 MiB and reject an oversized in-memory edit before accepting it if it would make the graph unreadable. Introduce revision-bound pagination before raising that limit. Cap outstanding reads at eight per page, with two preview workers and cancellation on close. Reject unknown fields and types, duplicate IDs, dangling edge endpoints and invalid object references. Use stable error codes such as `unsupported_version`, `invalid_request`, `stale_session`, `revision_conflict`, `source_missing`, `too_large` and `busy`. Keep local paths and exception traces out of replies.

Serialize edits on Python's GUI thread. Check the duplicate request cache **before** checking the revision. A retry with the same session, ID and payload receives its prior response. A reused ID with different content fails. Use one outstanding mutation per client, a monotonic request counter and a bounded replay window. Once evicted, reject an old counter and require a snapshot. A switch, reload, close or renderer crash revokes the binding and outstanding jobs. Destroy the old page and channel, then create a new binding for the trusted entry point. Tag every worker completion with the captured session, source identity and source generation. Discard late results, including when a referenced page is deleted during rendering.

## 5. Security, packaging and data safety

**Local assets.** Vite writes a relative production bundle. At build time, `pyside6-rcc --binary` compiles it into one resource. Load the installed, application-owned resource at `qrc:/pinbuboard/index.html` and Qt's matching `qrc:///qtwebchannel/qwebchannel.js`. Package only the generated resource, notices and native dependencies. Node, localhost, Vite's development server and npm are build tools only. Offline builders can pre-stage the locked npm cache and wheelhouse. [Qt WebChannel](https://doc.qt.io/qt-6/qtwebchannel-javascript.html) · [Vite](https://vite.dev/guide/build)

**Web permissions.** Put the page and channel on a dedicated off-the-record profile. Install the interceptor before loading. Allow GET for the exact packaged assets and channel client. Limit top-level navigation to the entry page. Reject other schemes, external navigation, frames, pop-ups, downloads, file pickers, OS URL handoff and device/clipboard permissions in the integrated host. Keep local-file and remote-content access off. Restrict scripts to packaged resources, prohibit connections and plug-ins, and allow inline styles only for graph layout. Render labels and OCR results as plain text. For thumbnails, construct a Blob URL only from a bounded, Python-produced image, allow `blob:` for images alone, and revoke it on eviction. Preserve platform sandbox defaults and keep remote debugging off. A broken resource should close the board with a native error while the notebook stays usable.

**Persistence.** The probe uses a random label in memory. In the next editing milestone, label the board “temporary” and confirm discarding unsaved board work on close. A later portable design can add a bounded, versioned `board` section to a **new notebook container format**, leaving per-tab project v5 alone. Write the new format only on explicit creation of a disposable board-enabled copy. Existing v5/v6/v7 files and v2–v4 folder migrations use the established paths. Keep v7 output for ordinary edits where that is today's behaviour. Avoid storing a portable board in QSettings, a file beside the cloud original, or an extra SQLite table outside SafeSave's snapshot model.

Before enabling durable editing, wire the board through manifest validation/serialization, immutable background snapshots, dirty/generation tracking, the synchronous fallback, local backup/restore and explicit publish. A failed write must retain recoverable local edits and a clean previous snapshot. Handle Save Copy As, clean-share exports, tab transfer/import and older-reader refusal explicitly. Bind persisted sources to notebook-scoped tab/page IDs. A live source handle is session-specific. Regenerate handles after reopen. Duplicated notebook IDs in a copied file must never authorize cross-session access. Require a full round trip and a verified restore before claiming a saved board is recoverable. [SafeSave](../../docs/SAFE_SAVE.md) · [Backup implementation](../../yomunote/safe_backup.py) · [Health checks](../../yomunote/backup_health.py)

**Windows and Apple Silicon.** Keep the branch's PyInstaller one-directory flow. For an experimental bundle, collect QtWebEngineWidgets/Core, QtWebChannel, their matching wheels, QtWebEngineProcess, resources and locale packs, ICU data and the correct V8 snapshot. Confirm the JS resource and Qt channel client load from the installed app with network disconnected and build tools absent. On Windows x64, run the existing frozen SQLite startup check and bundled OCR verifier, then open and close the board from a path containing spaces and non-ASCII characters. On a native arm64 Mac, inspect each helper/framework architecture, its bundle location and the arm64 V8 snapshot. Check helper signatures, entitlements and launch after copying the app to a clean machine. The existing macOS script applies an ad-hoc signature. Developer ID signing and notarization would be separate distribution work. Preserve the packaged Tesseract assets and verify OCR with the board open. [Qt deployment](https://doc.qt.io/qt-6/qtwebengine-deploying.html) · [Platform notes](https://doc.qt.io/qt-6/qtwebengine-platform-notes.html) · [macOS build](../../build-mac.command) · [Windows build](../../build-windows.ps1)

**Licences.** The installed `@xyflow/react` package carries the MIT licence and webkid copyright. Retain its notice and licence text. Keep React Flow attribution in the probe. Inventory the exact shipped JS transitives from the lock and bundle, including React, React DOM, xyflow system, Zustand and D3 components as applicable. Collect each package's actual licence and required notices. Also inventory Qt WebEngine, Chromium's bundled libraries and the distributed Qt channel client under their individual terms. Extend the existing GPL-3.0-or-later project's notices and distribute the required texts and corresponding-source information with each experimental binary. The lockfile alone cannot fulfil those obligations. [Project notices](../../THIRD_PARTY_NOTICES.md) · [xyflow licence](https://github.com/xyflow/xyflow/blob/main/LICENSE) · [Qt WebEngine licensing](https://doc.qt.io/qt-6/qtwebengine-licensing.html)

## 6. Performance feasibility

**The bridge works in the tested Linux configuration. Memory is the first constraint.** Each trial used a fresh Python process, the same two nodes, one SVG edge, an 800 × 600 view and software rendering. An instrumented host sampled proportional set size (PSS) across Python and its child processes. PSS apportions shared pages between processes. The baseline was a running Qt Widgets application before WebEngine imports. Time covers those imports through the callback that verified both the card label and edge geometry. Three alternating runs per version used a warm filesystem cache.

| React Flow | JS + CSS, uncompressed | Baseline PSS | PSS at callback | Paired increase | Time to callback |
| --- | ---: | ---: | ---: | ---: | ---: |
| 12.12.1 | 419,418 bytes | 44.8–47.5 MiB | 316.0–319.0 MiB | 269.6–274.2 MiB | 160–198 ms |
| 13.0.2 | 483,536 bytes | 44.8–47.8 MiB | 332.6–334.7 MiB | 285.7–288.8 MiB | 164–199 ms |

The normal Linux launch stopped at Chromium sandbox startup because the container's helper ownership was incompatible. Measurements used a **test-process-only sandbox override** on the isolated synthetic page. The probe itself supplies no override. One traced v13 run showed no IPv4/IPv6 destinations in `connect/sendto/sendmsg/sendmmsg` across its process tree. Hardware acceleration, protected native launch, installed size, OS-wide offline behaviour, cold launch and large-board responsiveness still need target measurements. A two-node timing cannot distinguish the versions' large-graph speed.

Open the board lazily and keep at most one live view. Use memoized custom nodes and stable callbacks, avoid whole-graph subscriptions during drags, request previews only for visible cards, and bound the thumbnail cache by bytes. For scale, a 320 × 320 decoded RGBA image occupies 400 KiB before other copies. A hundred resident images would take roughly 39 MiB per copy. Measure viewport culling with representative graphs because its bookkeeping also costs time. [React Flow performance guidance](https://reactflow.dev/learn/advanced-use/performance)

## 7. Milestones and acceptance tests

| Stage | Work and acceptance evidence |
| --- | --- |
| **A. Standalone probe — completed on Linux with the limitation above** | Use a fresh nonce as a node label. Assert two rendered cards and nonzero edge geometry, then round-trip the actual displayed value to Python. Both exact version candidates passed in an isolated diagnostic. The checked-in probe uses v13. |
| **B. Native packaging and offline gate** | On Windows x64 and macOS arm64, launch the frozen probe under normal platform security with networking disconnected. Verify real drag, selection, keyboard focus, fit/zoom, HiDPI, correct CSS and a channel reply. Test missing helper, resource or locale and verify the notebook remains usable after a clear error. Inspect connections, helper versions, installer size and required notices. |
| **C. Fixture-only sources and lifecycle** | Use a generated multi-tab notebook with an inherited reference, a short legacy page ID and a tiny PDF/image. Compare native vs board citation and thumbnail. Exercise source copies/moves/deletes, tab switch, notebook replacement, worker cancellation, late replies and renderer termination. Verify zero host file paths in messages, reject invalid requests and external navigation, and deny file/clipboard/device access. Off-by-default launch creates no WebEngine view or helper and performs no board writes. |
| **D. Temporary graph editing** | Test drag, multi-drag, connect, delete and restore incident edges, edit-after-undo, focus changes, Ctrl/Cmd+Z, redo, duplicate/stale requests and a crash between commit and reply. One drag produces one history entry. Failed commands leave revision, edges and undo state consistent. Simulate missing WebEngine and confirm the editor still works. |
| **E. Durable format investigation** | Generate v5/v6/v7 and legacy-folder fixtures. Compare file hashes before and after inspection. Test local autosave, verified backup/restore, publish conflict, two opens, Save Copy As and clean share. Interrupt a background save and simulate disk full. Validate older-reader rejection of a board-enabled copy, future-version refusal, data preservation in regular notebooks and equivalent board data after recovery. Re-run the existing full audit on disposable roots. |
| **F. Native performance decision** | Compare app alone, empty board, 100/200, 500/1,000 and 2,000/4,000 nodes/edges, first text-only and then preview-heavy. Include open/close ×10 and a drag while native PDF/OCR and autosave are active. Record hardware, DPI, zoom, visible count, process-tree private memory, GPU usage, startup, p95 frame time, input latency, and preview queue/memory after close. Proposed decision targets for a representative 500-node board are p95 drag frames ≤33 ms, visible response ≤100 ms, first usable board ≤2 s, and a plateau across repeated opens. Record PSS/private-memory differences by OS. Set the supported board size from the slowest target machine that meets the targets. |

Targeted baseline on Linux with isolated settings, working and backup roots: **71 passed** across `test_safesave_session`, `test_v091_backup_health`, `test_v092a_research`, `test_v060_ocr_engine`, `test_v083a_pdf_text`, `test_notebook_v5`, `test_v2_migration` and `test_v100_final_release`. This was a selected regression run. Windows/macOS packages, full application acceptance and the proposed production contracts are pending.

### Reproduce the standalone probe

From `experiments/pinbuboard/probe`, use an activated disposable Python 3.12 environment and the Node/npm versions above. These build steps fetch dependencies on the build machine. Only the final command runs the synthetic UI.

```sh
python -m pip install PySide6==6.12.0
npm ci --no-audit --no-fund
npm run build
python bundle.py
python host.py
```

The runtime needs the matching Qt environment, `host.py` and `probe.rcc`. It opens a two-card window, checks the node and edge geometry and channel echo, prints PASS, and closes. A missing response times out with a failing exit code. Use a native graphical session with the platform's normal sandbox for acceptance.
