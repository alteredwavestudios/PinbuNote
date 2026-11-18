import { MarkerType, type Node, type Edge } from '@xyflow/react';

export const kinds = {
  note: ['Text note', '¶', '#7763ac'],
  index: ['Index card', '▤', '#3e7796'],
  claim: ['Claim', '◆', '#7851a2'],
  argument: ['Argument', '⇒', '#256f70'],
  counterargument: ['Counterargument', '⇄', '#a85457'],
  evidence: ['Evidence', '◈', '#347353'],
  plan: ['Assignment plan', '☷', '#a76625'],
} as const;
export type Kind = keyof typeof kinds;
export type Card = {
  id: string;
  kind: Kind;
  title: string;
  content: string;
  x: number;
  y: number;
  w: number;
  h: number;
};
export type Link = { id: string; source: string; target: string };
export type Graph = { id: string; name: string; nodes: Card[]; edges: Link[] };
export type Edit = { nodes: Card[]; edges: Link[]; dropNodes: string[]; dropEdges: string[] };
export type PatchNode = Node<{ kind: Kind; title: string; content: string }, 'patch'>;
export type Reply = {
  rev: number;
  active: string;
  undo: boolean;
  redo: boolean;
  boards?: { id: string; name: string }[];
  board?: Graph;
  edit?: Edit;
};

type Bridge = { request(raw: string, callback: (answer: string) => void): void };
declare const qt: { webChannelTransport: unknown };
declare const QWebChannel: new (
  transport: unknown,
  ready: (channel: { objects: { board: Bridge } }) => void,
) => unknown;

const bridge = new Promise<Bridge>((resolve, reject) => {
  if (typeof qt === 'undefined') {
    reject(new Error('Open PinbuBoard from the experimental Pinbu Note window.'));
  } else {
    new QWebChannel(qt.webChannelTransport, (channel) => resolve(channel.objects.board));
  }
});

let revision = 0;
export async function call(op: string, body: object = {}): Promise<Reply> {
  const api = await bridge;
  return new Promise((resolve, reject) => {
    api.request(JSON.stringify({ v: 1, rev: revision, op, body }), (raw) => {
      try {
        const answer = JSON.parse(raw);
        if (!answer.ok) throw new Error(answer.error);
        revision = answer.data.rev;
        resolve(answer.data);
      } catch (error) {
        reject(error);
      }
    });
  });
}

export function asNode(c: Card, selected = false): PatchNode {
  return {
    id: c.id,
    type: 'patch',
    position: { x: c.x, y: c.y },
    width: c.w,
    height: c.h,
    data: { kind: c.kind, title: c.title, content: c.content },
    selected,
  };
}
export function asCard(n: PatchNode): Card {
  return { id: n.id, ...n.data, ...n.position, w: n.width ?? 244, h: n.height ?? 154 };
}
export function asEdge(e: Link): Edge {
  return {
    ...e,
    type: 'smoothstep',
    markerEnd: { type: MarkerType.ArrowClosed, width: 16, height: 16 },
  };
}
export function bounded(c: Card): Card {
  return {
    ...c,
    x: Math.max(-4000, Math.min(4000 - c.w, c.x)),
    y: Math.max(-4000, Math.min(4000 - c.h, c.y)),
  };
}
export function edit(parts: Partial<Edit>): Edit {
  return { nodes: [], edges: [], dropNodes: [], dropEdges: [], ...parts };
}
export function id() {
  return Array.from(crypto.getRandomValues(new Uint32Array(4)), (n) =>
    n.toString(16).padStart(8, '0'),
  ).join('');
}
