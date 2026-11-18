"""Disposable board library. All notebook context arrives as an opaque identity."""
from __future__ import annotations

import hashlib
import json
import math
import os
from pathlib import Path
import re
import tempfile
from uuid import uuid4

from ..history import CallbackAction, UnifiedHistory

KINDS = ("note", "index", "claim", "argument", "counterargument", "evidence", "plan")
LIMIT = 4 * 1024 * 1024
BOUND = 4000


def require(condition, message):
    if not condition:
        raise ValueError(message)


def keys(value, fields):
    require(isinstance(value, dict) and set(value) == set(fields.split()), "Unexpected fields.")


def identifier(value):
    require(isinstance(value, str) and re.fullmatch(r"[a-zA-Z0-9_-]{1,64}", value), "Invalid ID.")


def string(value, limit):
    require(isinstance(value, str) and len(value) <= limit, "Text exceeds the limit.")


def number(value, low, high):
    require(type(value) in (int, float) and low <= value <= high and math.isfinite(value),
            "Patch is outside the canvas or size limits.")


def indexed(items, maximum):
    require(isinstance(items, list) and len(items) <= maximum, "Board limit exceeded.")
    result = {}
    for item in items:
        require(isinstance(item, dict) and "id" in item, "Missing ID.")
        identifier(item["id"])
        require(item["id"] not in result, "Duplicate ID.")
        result[item["id"]] = item
    return result


def validate(board):
    keys(board, "id name nodes edges")
    identifier(board["id"])
    string(board["name"], 64)
    require(board["name"].strip(), "Enter a board name.")
    nodes = indexed(board["nodes"], 400)
    for n in nodes.values():
        keys(n, "id kind title content x y w h")
        require(n["kind"] in KINDS, "Unknown patch type.")
        string(n["title"], 120)
        string(n["content"], 4000)
        number(n["w"], 160, 640)
        number(n["h"], 104, 480)
        number(n["x"], -BOUND, BOUND - n["w"])
        number(n["y"], -BOUND, BOUND - n["h"])
    pairs = set()
    for e in indexed(board["edges"], 800).values():
        keys(e, "id source target")
        identifier(e["source"])
        identifier(e["target"])
        pair = (e["source"], e["target"])
        require(e["source"] in nodes and e["target"] in nodes and e["source"] != e["target"],
                "Choose two different patches.")
        require(pair not in pairs, "These patches already have that connection.")
        pairs.add(pair)


def demo():
    def card(key, kind, x, y, title, content):
        return dict(id=key, kind=kind, x=x, y=y, w=244, h=154, title=title, content=content)
    return dict(id="first", name="The learning garden", nodes=[
        card("question", "index", 0, 120, "Can a garden teach?", "Explore how a school garden could change the way students learn."),
        card("claim", "claim", 340, 20, "Learning by growing", "Working with plants makes abstract science tangible."),
        card("field", "evidence", 680, 20, "Field observations", "Compare weekly growth logs with students’ explanations."),
        card("challenge", "counterargument", 340, 260, "Who has time?", "Maintenance can compete with lessons during busy terms."),
        card("outline", "plan", 680, 260, "Build the outline", "Introduce the question, weigh the evidence, then address the trade-off."),
    ], edges=[dict(id=a+"-"+b, source=a, target=b) for a, b in
              [("question","claim"), ("claim","field"), ("question","challenge"), ("challenge","outline")]])


def delta(before, after):
    result = {}
    for field, removed in (("nodes", "dropNodes"), ("edges", "dropEdges")):
        old = {v["id"]: v for v in before[field]}
        new = {v["id"]: v for v in after[field]}
        result[field] = [v for k, v in new.items() if old.get(k) != v]
        result[removed] = [k for k in old if k not in new]
    return result


def patched(board, edit):
    keys(edit, "nodes edges dropNodes dropEdges")
    result = dict(board)
    for field, removed, maximum in (("nodes", "dropNodes", 400), ("edges", "dropEdges", 800)):
        updated = indexed(edit[field], maximum)
        ids = edit[removed]
        require(isinstance(ids, list) and len(ids) <= maximum, "Invalid removal.")
        for key in ids:
            identifier(key)
        old = {v["id"]: v for v in board[field]}
        require(set(ids) <= old.keys() and not set(ids).intersection(updated), "Unknown removal.")
        for key in ids:
            del old[key]
        old.update(updated)
        result[field] = list(old.values())
    dropped = set(edit["dropNodes"])
    result["edges"] = [e for e in result["edges"] if not dropped.intersection((e["source"], e["target"]))]
    validate(result)
    return result


class BoardLibrary:
    def __init__(self, path: Path, notebook: str):
        self.path = path
        self.notebook = notebook
        self.revision = 0
        self.histories = {}
        self.reload()

    def _read(self):
        if not self.path.exists():
            return None
        with self.path.open("rb") as stream:
            raw = stream.read(LIMIT + 1)
        require(len(raw) <= LIMIT, "Board file exceeds the size limit.")
        return raw

    def reload(self):
        raw = self._read()
        if raw is None:
            require(not getattr(self, "digest", None), "Board file was removed.")
            boards, active = [demo()], "first"
        else:
            obj = json.loads(raw)
            keys(obj, "version notebook active boards")
            require(type(obj["version"]) is int and obj["version"] == 1 and obj["notebook"] == self.notebook, "Incompatible board file.")
            boards, active = obj["boards"], obj["active"]
            by_id = indexed(boards, 16)
            identifier(active)
            require(active in by_id, "Missing active board.")
            for board in boards:
                validate(board)
        self.boards = {b["id"]: b for b in boards}
        self.active = active
        self.digest = hashlib.sha256(raw).digest() if raw is not None else None
        self.histories.clear()
        self.revision += 1

    def persist(self, boards, active):
        raw = json.dumps(dict(version=1, notebook=self.notebook, active=active,
                              boards=list(boards.values())), ensure_ascii=False).encode()
        require(len(raw) <= LIMIT, "Board library is full.")
        current = self._read()
        signature = hashlib.sha256(current).digest() if current is not None else None
        require(signature == self.digest, "File changed on disk. Reload before editing.")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = None
        try:
            with tempfile.NamedTemporaryFile(dir=self.path.parent, delete=False) as stream:
                temporary = Path(stream.name)
                stream.write(raw)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, self.path)
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)
        self.boards, self.active = boards, active
        self.digest = hashlib.sha256(raw).digest()
        self.revision += 1

    def _apply(self, board_id, edit):
        updated = patched(self.boards[board_id], edit)
        self.persist({**self.boards, board_id: updated}, self.active)

    def handle(self, request):
        keys(request, "v op rev body")
        require(type(request["v"]) is int and request["v"] == 1, "Unsupported protocol.")
        op, body = request["op"], request["body"]
        require(isinstance(body, dict), "Invalid payload.")
        if op != "read":
            require(type(request["rev"]) is int and request["rev"] == self.revision,
                    "Board changed. Refresh and try again.")
        key = self.active
        before = self.boards[key]
        history = self.histories.setdefault(key, UnifiedHistory(100, 2 * 1024 * 1024))
        if op == "edit":
            keys(body, "label edit")
            string(body["label"], 80)
            after = patched(before, body["edit"])
            forward, inverse = delta(before, after), delta(after, before)
            if any(forward.values()):
                history.perform(CallbackAction(body["label"], lambda: self._apply(key, inverse),
                                               lambda: self._apply(key, forward),
                                               len(json.dumps([forward, inverse]))))
        elif op in ("undo", "redo"):
            keys(body, "")
            (history.undo if op == "undo" else history.redo)()
        elif op in ("create", "rename"):
            keys(body, "name")
            string(body["name"], 64)
            name = body["name"].strip()
            require(name, "Enter a board name.")
            require(all(b["name"].casefold() != name.casefold() for b in self.boards.values()
                        if op == "create" or b["id"] != key), "Board name already exists.")
            if op == "create":
                require(len(self.boards) < 16, "Limit of 16 boards reached.")
                key = uuid4().hex
                updated = dict(id=key, name=name, nodes=[], edges=[])
            else:
                updated = {**before, "name": name}
            self.persist({**self.boards, key: updated}, key)
        elif op == "switch":
            keys(body, "id")
            identifier(body["id"])
            require(body["id"] in self.boards, "Board is unavailable.")
            self.persist(self.boards, body["id"])
        elif op in ("read", "reload", "save"):
            keys(body, "")
            if op == "reload":
                self.reload()
            if op == "save":
                self.persist(self.boards, key)
        else:
            raise ValueError("Unknown request.")
        current = self.boards[self.active]
        hist = self.histories.get(self.active)
        reply = dict(rev=self.revision, active=self.active, undo=bool(hist and hist.can_undo),
                     redo=bool(hist and hist.can_redo))
        if op in ("edit", "undo", "redo"):
            reply["edit"] = delta(before, current)
        else:
            reply.update(board=current, boards=[dict(id=b["id"], name=b["name"]) for b in self.boards.values()])
        return reply
