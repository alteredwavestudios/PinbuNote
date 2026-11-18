import { createRoot } from 'react-dom/client';
import { ReactFlow, type Edge, type Node } from '@xyflow/react';
import '@xyflow/react/dist/style.css';
import './size.css';

type Probe = {
  fixture(receive: (label: string) => void): void;
  rendered(label: string): void;
};

declare const qt: { webChannelTransport: unknown };
declare const QWebChannel: new (
  transport: unknown,
  ready: (channel: { objects: { probe: Probe } }) => void,
) => unknown;

function mount(probe: Probe, label: string) {
  const nodes: Node[] = [
    { id: 'a', position: { x: 40, y: 40 }, data: { label } },
    { id: 'b', position: { x: 280, y: 160 }, data: { label: 'Disposable source' } },
  ];
  const edges: Edge[] = [{ id: 'example', source: 'a', target: 'b' }];

  function confirmGeometry() {
    const cards = document.querySelectorAll('.react-flow__node');
    const edge = document.querySelector<SVGPathElement>('.react-flow__edge-path');
    const first = cards[0];
    if (cards.length === 2 && first?.getBoundingClientRect().width &&
        first.textContent === label && edge && edge.getTotalLength() > 0) {
      probe.rendered(label);
    } else {
      requestAnimationFrame(confirmGeometry);
    }
  }

  createRoot(document.getElementById('root')!).render(
    <ReactFlow defaultNodes={nodes} defaultEdges={edges}
      onInit={() => requestAnimationFrame(confirmGeometry)} />,
  );
}

new QWebChannel(qt.webChannelTransport, ({ objects: { probe } }) => {
  probe.fixture(label => mount(probe, label));
});
