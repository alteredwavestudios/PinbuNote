import {
  createContext,
  memo,
  useCallback,
  useContext,
  useEffect,
  useLayoutEffect,
  useRef,
  useState,
  type CSSProperties,
  type ReactNode,
} from 'react';
import { createRoot } from 'react-dom/client';
import {
  ReactFlow,
  ReactFlowProvider,
  useReactFlow,
  Handle,
  Position,
  NodeResizer,
  Background,
  BackgroundVariant,
  MiniMap,
  SelectionMode,
  type NodeProps,
  type Viewport,
  type Edge,
  type CoordinateExtent,
  type SnapGrid,
} from '@xyflow/react';
import '@xyflow/react/style.css';
import './style.css';
import {
  asCard,
  asEdge,
  asNode,
  bounded,
  call,
  edit,
  id,
  kinds,
  type Card,
  type Edit,
  type Kind,
  type PatchNode,
  type Reply,
} from './graph';

const extent: CoordinateExtent = [
  [-4000, -4000],
  [4000, 4000],
];
const grid: SnapGrid = [16, 16];
const selectionKeys = ['Control', 'Meta', 'Shift'];
const cardKinds = Object.keys(kinds) as Kind[];
const PatchActions = createContext({
  resize: (_key: string, _box: { x: number; y: number; width: number; height: number }) => {},
});
const Patch = memo(function Patch({ id, selected, data }: NodeProps<PatchNode>) {
  const { resize } = useContext(PatchActions);
  const [name, glyph, accent] = kinds[data.kind];
  return (
    <article className={'patch ' + data.kind} style={{ '--accent': accent } as CSSProperties}>
      <NodeResizer
        isVisible={selected}
        minWidth={160}
        maxWidth={640}
        minHeight={104}
        maxHeight={480}
        onResizeEnd={(_, box) => resize(id, box)}
      />
      <Handle type="target" position={Position.Left} aria-label="Incoming connection" />
      <div className="patch-kind">
        <span aria-hidden>{glyph}</span>
        {name}
      </div>
      <h2>{data.title || 'Untitled patch'}</h2>
      <p>{data.content}</p>
      <Handle type="source" position={Position.Right} aria-label="Outgoing connection" />
    </article>
  );
});
const nodeTypes = { patch: Patch };

function Modal({ children, close }: { children: ReactNode; close: () => void }) {
  const ref = useRef<HTMLDialogElement>(null);
  useLayoutEffect(() => {
    ref.current?.showModal();
  }, []);
  return (
    <dialog
      ref={ref}
      onCancel={(e) => {
        e.preventDefault();
        close();
      }}
    >
      {children}
    </dialog>
  );
}

type Form = { mode: 'card'; card: Card } | { mode: 'create' | 'rename'; name: string };
type Memory = { viewport: Viewport; selected: Set<string>; edges: Set<string> };
function Workspace() {
  const flow = useReactFlow<PatchNode, Edge>();
  const canvas = useRef<HTMLDivElement>(null);
  const [meta, setMeta] = useState({
    active: '',
    boards: [] as { id: string; name: string }[],
    undo: false,
    redo: false,
  });
  const [ready, setReady] = useState(false);
  const [snap, setSnap] = useState(false);
  const [overview, setOverview] = useState(false);
  const [selection, setSelection] = useState({ nodes: 0, edges: 0 });
  const [status, setStatus] = useState('Opening demo…');
  const [error, setError] = useState('');
  const [form, setForm] = useState<Form | null>(null);
  const [zoom, setZoom] = useState(100);
  const active = useRef('');
  const memory = useRef(new Map<string, Memory>());
  const queue = useRef(Promise.resolve());
  const pending = useRef(0);
  const [busy, setBusy] = useState(false);

  function remember() {
    memory.current.set(active.current, {
      viewport: flow.getViewport(),
      selected: new Set(
        flow
          .getNodes()
          .filter((n) => n.selected)
          .map((n) => n.id),
      ),
      edges: new Set(
        flow
          .getEdges()
          .filter((e) => e.selected)
          .map((e) => e.id),
      ),
    });
  }

  function display(r: Reply, picked?: Set<string>, restore = false) {
    setMeta((prev) => ({
      active: r.active,
      boards: r.boards ?? prev.boards,
      undo: r.undo,
      redo: r.redo,
    }));
    if (r.board) {
      const saved = memory.current.get(r.active);
      const nodes = r.board.nodes.map((c) => asNode(c, saved?.selected.has(c.id)));
      flow.setNodes(nodes);
      flow.setEdges(r.board.edges.map((e) => ({ ...asEdge(e), selected: saved?.edges.has(e.id) })));
      if (active.current !== r.active || restore) {
        if (saved) void flow.setViewport(saved.viewport);
        else if (nodes.length) void flow.fitView({ nodes, padding: '64px', maxZoom: 1.1 });
        else void flow.setViewport({ x: 120, y: 100, zoom: 1 });
      }
      active.current = r.active;
    } else if (r.edit) {
      const change = r.edit;
      const update = new Map(change.nodes.map((c) => [c.id, c]));
      const gone = new Set(change.dropNodes);
      flow.setNodes((old) => {
        const next: PatchNode[] = [];
        const existing = new Set(old.map((n) => n.id));
        for (const n of old) {
          if (gone.has(n.id)) continue;
          const card = update.get(n.id);
          const selected = picked ? picked.has(n.id) : !!n.selected;
          if (card) next.push({ ...n, ...asNode(card, selected) });
          else next.push(selected === !!n.selected ? n : { ...n, selected });
        }
        for (const c of update.values())
          if (!existing.has(c.id)) next.push(asNode(c, picked?.has(c.id)));
        return next;
      });
      if (change.edges.length || change.dropEdges.length || picked) {
        const drop = new Set([...change.dropEdges, ...change.edges.map((e) => e.id)]);
        flow.setEdges((old) => [
          ...old
            .filter((e) => !drop.has(e.id))
            .map((e) => (picked && e.selected ? { ...e, selected: false } : e)),
          ...change.edges.map(asEdge),
        ]);
      }
    }
    setReady(true);
  }

  function send(op: string, body: object = {}, picked?: Set<string>, after?: () => void) {
    const origin = active.current;
    pending.current++;
    setBusy(true);
    queue.current = queue.current
      .then(async () => {
        if (origin && origin !== active.current) return;
        try {
          const r = await call(op, body);
          if (op === 'save') {
            setStatus('Saved to demo file');
          } else {
            display(r, picked, op === 'reload');
            setStatus(
              op === 'reload'
                ? 'Reloaded from file'
                : op === 'read'
                  ? 'Demo workspace'
                  : 'Saved locally',
            );
          }
          setError('');
          after?.();
        } catch (err) {
          setError(err instanceof Error ? err.message : 'The board command failed.');
          // A failed drag may already have moved the local graphic. Restore the accepted graph.
          if (op !== 'read') {
            remember();
            try {
              display(await call('read'));
            } catch {
              /* keep the last visible graph */
            }
          }
        }
      })
      .finally(() => {
        if (--pending.current === 0) setBusy(false);
      });
  }
  const commit = (label: string, change: Partial<Edit>, picked?: Set<string>, after?: () => void) =>
    send('edit', { label, edit: edit(change) }, picked, after);

  const currentActions = useRef({
    resize: (key: string, box: { x: number; y: number; width: number; height: number }) => {
      const n = flow.getNode(key);
      if (n)
        commit('Resize patch', {
          nodes: [bounded({ ...asCard(n), x: box.x, y: box.y, w: box.width, h: box.height })],
        });
    },
  });
  function selected() {
    return flow.getNodes().filter((n) => n.selected);
  }
  function center() {
    const rect = canvas.current!.getBoundingClientRect();
    return flow.screenToFlowPosition({
      x: rect.left + rect.width / 2,
      y: rect.top + rect.height / 2,
    });
  }
  function add(kind: Kind, point = center()) {
    const newId = id();
    const adjust = (v: number) => (snap ? Math.round(v / 16) * 16 : Math.round(v));
    const c = bounded({
      id: newId,
      kind,
      title: 'New ' + kinds[kind][0].toLowerCase(),
      content: '',
      x: adjust(point.x - 122),
      y: adjust(point.y - 77),
      w: 244,
      h: 154,
    });
    commit('Add patch', { nodes: [c] }, new Set([newId]));
  }
  function duplicate() {
    const source = selected();
    if (!source.length) return;
    const ids = new Map(source.map((n) => [n.id, id()]));
    const nodes = source.map((n) =>
      bounded({ ...asCard(n), id: ids.get(n.id)!, x: n.position.x + 32, y: n.position.y + 32 }),
    );
    const edges = flow
      .getEdges()
      .filter((e) => ids.has(e.source) && ids.has(e.target))
      .map((e) => ({ id: id(), source: ids.get(e.source)!, target: ids.get(e.target)! }));
    commit('Duplicate selection', { nodes, edges }, new Set(ids.values()));
  }
  function remove() {
    const dropNodes = selected().map((n) => n.id),
      dropEdges = flow
        .getEdges()
        .filter((e) => e.selected)
        .map((e) => e.id);
    if (dropNodes.length || dropEdges.length) commit('Delete selection', { dropNodes, dropEdges });
  }
  function align(axis: 'x' | 'y') {
    const nodes = selected();
    if (nodes.length < 2) return;
    const value = Math.min(...nodes.map((n) => n.position[axis]));
    commit('Align patches', { nodes: nodes.map((n) => bounded({ ...asCard(n), [axis]: value })) });
  }
  function openEditor() {
    const nodes = selected();
    if (nodes.length === 1) setForm({ mode: 'card', card: asCard(nodes[0]) });
  }
  function fit() {
    void flow.fitView({ padding: '48px', maxZoom: 1.15, duration: 160 });
  }
  function moved(nodes: PatchNode[]) {
    if (nodes.length) commit('Move patches', { nodes: nodes.map((n) => bounded(asCard(n))) });
  }
  const onSelect = useCallback(({ nodes, edges }: { nodes: PatchNode[]; edges: Edge[] }) => {
    setSelection((prev) =>
      prev.nodes === nodes.length && prev.edges === edges.length
        ? prev
        : { nodes: nodes.length, edges: edges.length },
    );
  }, []);
  const keyHandler = useRef<(e: KeyboardEvent) => void>(() => {});
  keyHandler.current = (e) => {
    if (
      !ready ||
      form ||
      e.altKey ||
      (e.target instanceof HTMLElement &&
        e.target.closest('input,textarea,select,[contenteditable=true]'))
    )
      return;
    const k = e.key.toLowerCase(),
      mod = e.ctrlKey || e.metaKey;
    if (mod && k === 's') send('save');
    else if (mod && k === 'z') send(e.shiftKey ? 'redo' : 'undo');
    else if (mod && k === 'y') send('redo');
    else if (mod && k === 'd') duplicate();
    else if (mod && k === 'a')
      flow.setNodes((ns) => ns.map((n) => (n.selected ? n : { ...n, selected: true })));
    else if (k === 'delete' || k === 'backspace') remove();
    else if (k === 'f2') openEditor();
    else if (k === 'insert') add('note');
    else if (k === 'f' && !mod) fit();
    else if (k.startsWith('arrow') && !mod && selected().length) {
      const step = snap || e.shiftKey ? 16 : 1;
      const dx = k === 'arrowleft' ? -step : k === 'arrowright' ? step : 0;
      const dy = k === 'arrowup' ? -step : k === 'arrowdown' ? step : 0;
      commit('Nudge selection', {
        nodes: selected().map((n) =>
          bounded({ ...asCard(n), x: n.position.x + dx, y: n.position.y + dy }),
        ),
      });
    } else return;
    e.preventDefault();
    e.stopImmediatePropagation();
  };
  useEffect(() => {
    const handler = (e: KeyboardEvent) => keyHandler.current(e);
    document.addEventListener('keydown', handler, true);
    return () => document.removeEventListener('keydown', handler, true);
  }, []);
  const menuName = meta.boards.find((b) => b.id === meta.active)?.name ?? '';
  return (
    <PatchActions.Provider value={currentActions.current}>
      <main>
        <header className="appbar">
          <div className="wordmark">
            <span className="brand-mark" aria-hidden>
              ⌘
            </span>
            PinbuBoard
          </div>
          <span className="experimental">Experimental v1.1</span>
          <div className="library">
            <select
              aria-label="Active board"
              value={meta.active}
              disabled={!ready || busy}
              onChange={(e) => {
                remember();
                send('switch', { id: e.target.value });
              }}
            >
              {meta.boards.map((b) => (
                <option key={b.id} value={b.id}>
                  {b.name}
                </option>
              ))}
            </select>
            <button onClick={() => setForm({ mode: 'create', name: '' })} disabled={!ready || busy}>
              ＋ Board
            </button>
            <button
              className="quiet"
              title="Rename active board"
              disabled={!ready || busy}
              onClick={() => setForm({ mode: 'rename', name: menuName })}
            >
              Rename
            </button>
          </div>
          <div className="file">
            <button disabled={!ready || busy} onClick={() => send('save')}>
              Save
            </button>
            <button
              disabled={!ready || busy}
              onClick={() => {
                remember();
                send('reload');
              }}
            >
              Reload
            </button>
          </div>
        </header>
        <div className="body">
          <aside>
            <h2>Add a patch</h2>
            <div className="palette">
              {cardKinds.map((kind) => (
                <button
                  disabled={!ready || busy}
                  key={kind}
                  onClick={() => add(kind)}
                  style={{ '--accent': kinds[kind][2] } as CSSProperties}
                >
                  <i aria-hidden>{kinds[kind][1]}</i>
                  {kinds[kind][0]}
                </button>
              ))}
            </div>
            <section className="instructions">
              <h2>Canvas controls</h2>
              <p>Drag the background to pan. Scroll to zoom.</p>
              <p>Shift-drag to select. Double-click a patch to edit it.</p>
              <p>Drag a right port to a left port to connect patches.</p>
            </section>
            <div className={'save-state' + (error ? ' failed' : '')} role="status">
              {error || (busy ? 'Working…' : status)}
            </div>
          </aside>
          <section className="canvas" ref={canvas} aria-label="Board canvas">
            <div className="tools">
              <button
                title="Undo (Ctrl/Cmd+Z)"
                disabled={!meta.undo || busy}
                onClick={() => send('undo')}
              >
                ↶ Undo
              </button>
              <button
                title="Redo (Ctrl/Cmd+Shift+Z)"
                disabled={!meta.redo || busy}
                onClick={() => send('redo')}
              >
                ↷ Redo
              </button>
              <b />
              <button disabled={selection.nodes !== 1} onClick={openEditor}>
                Edit
              </button>
              <button disabled={!selection.nodes} onClick={duplicate}>
                Duplicate
              </button>
              <button disabled={!selection.nodes && !selection.edges} onClick={remove}>
                Delete
              </button>
              <b />
              <button disabled={selection.nodes < 2} onClick={() => align('x')}>
                Align left
              </button>
              <button disabled={selection.nodes < 2} onClick={() => align('y')}>
                Align top
              </button>
            </div>
            <ReactFlow<PatchNode, Edge>
              defaultNodes={[]}
              defaultEdges={[]}
              nodeTypes={nodeTypes}
              onInit={() => send('read')}
              onSelectionChange={onSelect}
              deleteKeyCode={null}
              disableKeyboardA11y
              multiSelectionKeyCode={selectionKeys}
              selectionKeyCode="Shift"
              selectionMode={SelectionMode.Partial}
              snapToGrid={snap}
              snapGrid={grid}
              nodeExtent={extent}
              translateExtent={extent}
              minZoom={0.25}
              maxZoom={2}
              zoomOnDoubleClick={false}
              onNodeDoubleClick={(_, n) => setForm({ mode: 'card', card: asCard(n) })}
              onNodeDragStop={(_, n, ns) => moved(ns.length ? ns : [n])}
              onSelectionDragStop={(_, ns) => moved(ns)}
              onConnect={(c) =>
                commit('Connect patches', {
                  edges: [{ id: id(), source: c.source, target: c.target }],
                })
              }
              onMoveEnd={(_, v) => setZoom(Math.round(v.zoom * 100))}
            >
              <Background variant={BackgroundVariant.Dots} gap={16} size={1.3} color="#c6bfd3" />
              {overview && (
                <MiniMap
                  position="bottom-right"
                  pannable
                  zoomable
                  nodeColor={(n) => kinds[(n as PatchNode).data.kind][2]}
                />
              )}
            </ReactFlow>
            <div className="viewtools">
              <button title="Zoom out" aria-label="Zoom out" onClick={() => void flow.zoomOut()}>
                −
              </button>
              <output>{zoom}%</output>
              <button title="Zoom in" aria-label="Zoom in" onClick={() => void flow.zoomIn()}>
                ＋
              </button>
              <button onClick={fit}>Fit</button>
              <b />
              <button aria-pressed={snap} onClick={() => setSnap(!snap)}>
                Snap
              </button>
              <button aria-pressed={overview} onClick={() => setOverview(!overview)}>
                Overview
              </button>
            </div>
            {error && (
              <div className="error" role="alert">
                {error}
                <button onClick={() => setError('')} aria-label="Dismiss error">
                  ×
                </button>
              </div>
            )}
          </section>
        </div>
        {form && (
          <Modal close={() => setForm(null)}>
            <form
              onSubmit={(e) => {
                e.preventDefault();
                if (busy) return;
                if (form.mode === 'card')
                  commit('Edit patch', { nodes: [form.card] }, undefined, () => setForm(null));
                else send(form.mode, { name: form.name }, undefined, () => setForm(null));
              }}
            >
              <h2>
                {form.mode === 'card'
                  ? 'Edit ' + kinds[form.card.kind][0].toLowerCase()
                  : form.mode === 'rename'
                    ? 'Rename board'
                    : 'New board'}
              </h2>
              {form.mode === 'card' ? (
                <>
                  <label>
                    Title
                    <input
                      autoFocus
                      maxLength={120}
                      value={form.card.title}
                      onChange={(e) =>
                        setForm({ ...form, card: { ...form.card, title: e.target.value } })
                      }
                    />
                  </label>
                  <label>
                    Content
                    <textarea
                      maxLength={4000}
                      rows={6}
                      value={form.card.content}
                      onChange={(e) =>
                        setForm({ ...form, card: { ...form.card, content: e.target.value } })
                      }
                    />
                  </label>
                </>
              ) : (
                <label>
                  Board name
                  <input
                    autoFocus
                    required
                    maxLength={64}
                    value={form.name}
                    onChange={(e) => setForm({ ...form, name: e.target.value })}
                  />
                </label>
              )}
              {error && <p role="alert">{error}</p>}
              <footer>
                <button type="button" onClick={() => setForm(null)}>
                  Cancel
                </button>
                <button className="primary" disabled={busy}>
                  {form.mode === 'create' ? 'Create board' : 'Apply'}
                </button>
              </footer>
            </form>
          </Modal>
        )}
      </main>
    </PatchActions.Provider>
  );
}
createRoot(document.getElementById('root')!).render(
  <ReactFlowProvider>
    <Workspace />
  </ReactFlowProvider>,
);
