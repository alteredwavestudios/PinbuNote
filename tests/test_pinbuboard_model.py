import json
from copy import deepcopy

import pytest

from yomunote.pinbuboard.model import BoardLibrary, KINDS, demo


def command(lib, op, **body):
    return lib.handle(dict(v=1, rev=lib.revision, op=op, body=body))


def change(lib, **parts):
    patch = dict(nodes=[], edges=[], dropNodes=[], dropEdges=[])
    return command(lib, "edit", label="Edit", edit={**patch, **parts})


@pytest.fixture
def library(tmp_path):
    return BoardLibrary(tmp_path / "boards" / "demo.json", "notebook")


def test_all_kinds_and_reopen_after_redo(library):
    lib = library
    cards = [dict(demo()["nodes"][0], id="test-" + kind, kind=kind) for kind in KINDS]
    change(lib, nodes=cards)
    first = deepcopy(lib.boards)
    assert command(lib, "undo")["redo"]
    assert lib.boards["first"] == demo()
    command(lib, "redo")
    assert lib.boards == first
    loaded = BoardLibrary(lib.path, "notebook")
    assert loaded.boards == first
    assert not command(loaded, "read")["undo"]


def test_delete_node_and_incident_edges_one_action(library):
    original = demo()
    answer = change(library, dropNodes=["question"])
    assert set(answer["edit"]["dropEdges"]) == {"question-claim", "question-challenge"}
    assert library.histories["first"].action_count == 1
    command(library, "undo")
    restored = library.boards["first"]
    for field in ("nodes", "edges"):
        assert sorted(restored[field], key=lambda x:x["id"]) == sorted(original[field], key=lambda x:x["id"])


def test_multiple_boards_rename_and_revisions(library):
    other = command(library, "create", name="Essay")["active"]
    command(library, "rename", name="Final plan")
    change(library, nodes=[demo()["nodes"][0]])
    command(library, "switch", id="first")
    assert not command(library, "read")["undo"]
    stale = library.revision - 1
    with pytest.raises(ValueError, match="changed"):
        library.handle(dict(v=1, rev=stale, op="switch", body=dict(id=other)))
    with pytest.raises(ValueError, match="exists"):
        command(library, "rename", name="Final plan")
    command(library, "switch", id=other)
    assert command(library, "read")["undo"]
    command(library, "reload")
    assert library.active == other
    assert library.boards[other]["name"] == "Final plan"


@pytest.mark.parametrize("value", [float("nan"), 3999, True])
def test_invalid_geometry_rejects_entire_batch(library, value):
    a,b = demo()["nodes"][:2]
    with pytest.raises(ValueError):
        change(library, nodes=[{**a,"title":"pending"},{**b,"x":value}])
    assert library.boards["first"] == demo()
    assert not library.path.exists()


def test_conflict_corruption_and_failed_undo_preserve_edits(library, monkeypatch):
    change(library, dropNodes=["question"])
    accepted = deepcopy(library.boards)
    def disk_full(*args):
        raise OSError("Out of space")

    with monkeypatch.context() as patch:
        patch.setattr("os.replace", disk_full)
        with pytest.raises(OSError):
            command(library, "undo")
    assert library.boards == accepted and library.histories["first"].can_undo
    assert json.loads(library.path.read_bytes())["boards"][0] == accepted["first"]
    library.path.write_bytes(b"{")
    with pytest.raises(ValueError):
        command(library, "reload")
    with pytest.raises(ValueError, match="changed"):
        command(library, "save")
    assert library.boards == accepted and library.path.read_bytes() == b"{"
