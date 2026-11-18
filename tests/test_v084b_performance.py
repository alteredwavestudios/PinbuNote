"""v0.8.4c: save coalescing, preview invalidation, PDF hit-test equivalence."""
from __future__ import annotations

import ast
import math
import random
from pathlib import Path
from types import SimpleNamespace

import pytest

from yomunote.pdf_text_engine import Glyph, TextPageGeometry

ROOT = Path(__file__).resolve().parents[1]
WINDOW = (ROOT / 'yomunote' / 'window.py').read_text(encoding='utf-8')
CODE = ast.parse(WINDOW)
MAIN = next(n for n in CODE.body if isinstance(n, ast.ClassDef)
            and n.name == 'MainWindow')
PANE = next(n for n in CODE.body if isinstance(n, ast.ClassDef)
            and n.name == 'ProjectPane')


def method(cls, name):
    return next(n for n in cls.body if isinstance(n, ast.FunctionDef)
                and n.name == name)


def isolated_method(cls, name):
    fn = method(cls, name)
    scope = {}
    exec(compile(ast.fix_missing_locations(
        ast.Module(body=[fn], type_ignores=[])), '<actual window method>', 'exec'), scope)
    return scope[name]


def brute_nearest(glyphs, x, y):
    if not glyphs or not math.isfinite(x) or not math.isfinite(y):
        return None
    best_idx, best = None, float('inf')
    for g in glyphs:
        cy = (g.y0+g.y1)*.5
        dy = max(0.0, abs(y-cy)-(g.y1-g.y0)*.5)
        if dy > .045:
            continue
        dx = max(g.x0-x, 0.0, x-g.x1)
        d = dx*dx+dy*dy*4
        if d < best:
            best, best_idx = d, g.index
    return best_idx


def test_index_matches_original_hit_test_for_many_columns_and_edges():
    rng = random.Random(812340)
    glyphs=[]
    for i in range(1700):
        x=rng.random()*.93
        y=rng.random()*.96
        w=rng.uniform(.001,.018)
        h=rng.uniform(.002,.08)
        glyphs.append(Glyph(i,x,y,min(1,x+w),min(1,y+h)))
    geom=TextPageGeometry(glyphs,'x'*len(glyphs),len(glyphs))
    for _ in range(380):
        x=rng.uniform(-.1,1.1)
        y=rng.uniform(-.045,1.045)
        assert geom.nearest(x,y)==brute_nearest(glyphs,x,y)
    # Data is indexed once, then reused during repeated mouse move events.
    old=geom._hit_buckets
    assert old is not None and len(old)==48
    assert geom.nearest(.2,.2) == brute_nearest(glyphs,.2,.2)
    assert geom._hit_buckets is old
    assert geom.nearest(float('nan'),.2) is None
    assert geom.nearest(.2,float('inf')) is None
    assert geom.nearest(.2,-.5) is None


def test_index_does_not_change_text_or_highlight_geometry():
    g=[Glyph(i, i*.01, .2, i*.01+.008, .21) for i in range(35)]
    geom=TextPageGeometry(g,'x'*35,35)
    before=(geom.selected_text(3,20),geom.boxes(3,20))
    geom.nearest(.1,.2)
    assert before==(geom.selected_text(3,20),geom.boxes(3,20))


class FakePane:
    def __init__(self, owner, fail=False):
        self.owner=owner
        self._closed=False
        self._dirty=True
        self.fail=fail
        self.saves=0
        self.retries=0

    def save(self):
        self.saves+=1
        if self.fail:
            raise OSError('manifest fail')
        if not getattr(self.owner,'_batching_pane_saves',False):
            self.owner.notebook.save()
        self._dirty=False

    def schedule_save(self):
        self._dirty=True
        self.retries+=1

class FakeNotebook:
    def __init__(self):
        self.saves=0
        self.fail=False
    def save(self):
        self.saves+=1
        if self.fail:
            raise OSError('injected sqlite error')
        return True


def fake_window():
    obj=SimpleNamespace(notebook=FakeNotebook(), _set_autosave_footer=lambda **kwargs: None)
    obj._save_panes_in_one_commit=isolated_method(MAIN,'_save_panes_in_one_commit').__get__(obj)
    return obj


def test_saves_one_container_commit_for_many_panes():
    owner=fake_window()
    panes=[FakePane(owner) for _ in range(90)]
    owner._save_panes_in_one_commit(panes)
    assert owner.notebook.saves==1
    assert all(p.saves==1 and not p._dirty for p in panes)
    assert owner._batching_pane_saves is False


def test_failed_final_sqlite_commit_restores_dirty_panes():
    owner=fake_window()
    owner.notebook.fail=True
    panes=[FakePane(owner) for _ in range(5)]
    with pytest.raises(OSError, match='sqlite'):
        owner._save_panes_in_one_commit(panes)
    assert owner.notebook.saves==1
    assert all(p._dirty and p.retries==1 for p in panes)
    assert owner._batching_pane_saves is False
    owner.notebook.fail=False
    owner._save_panes_in_one_commit(panes)
    assert owner.notebook.saves==2


def test_failed_intermediate_manifest_restores_previously_saved_panes():
    owner=fake_window()
    panes=[FakePane(owner),FakePane(owner,fail=True),FakePane(owner)]
    with pytest.raises(OSError, match='manifest'):
        owner._save_panes_in_one_commit(panes)
    assert owner.notebook.saves==0
    assert panes[0]._dirty and panes[0].retries==1
    assert panes[1]._dirty and panes[2].saves==0
    assert owner._batching_pane_saves is False


def test_preview_clear_is_explicit_when_no_page_is_selected():
    src=ast.get_source_segment(WINDOW,method(PANE,'load_pages'))
    assert 'if self.current_page() is None:' in src
    assert 'self.project.selected_page = None' in src
    assert "self.page_title.setText('PAGE PREVIEW')" in src
    assert 'self.display_current()' in src
    # display_current invalidates in-flight preview and clears the canvas.
    display=ast.get_source_segment(WINDOW,method(PANE,'display_current'))
    assert 'self._preview_token += 1' in display
    assert 'self.canvas.show_image(None)' in display


def test_batched_main_window_call_sites_cover_close_export_exchange_transfer():
    for method_name in ('closeEvent','show_notebook','close_current',
                        '_save_tabs_for_exchange','export_clean_notebook',
                        '_replay_tab_page_transfer','_transfer_tab_pages'):
        src=ast.get_source_segment(WINDOW,method(MAIN,method_name))
        assert 'self._save_panes_in_one_commit(' in src, method_name
    callback=ast.get_source_segment(WINDOW,method(MAIN,'_attach_pane'))
    helper = ast.get_source_segment(WINDOW, method(MAIN, '_on_pane_container_save'))
    assert "getattr(self, '_batching_pane_saves', False)" in helper
    assert "self._on_pane_container_save(p)" in callback


def test_empty_tab_transfer_undo_clears_preview_without_tab_switch():
    """Execute the real load_pages method with a Qt-free empty navigator stub."""
    fn=isolated_method(PANE, 'load_pages')
    class Counter:
        def __init__(self):self.items=[]
        def clear(self):self.items.clear()
        def currentItem(self):return None
    class TextLabel:
        def __init__(self):self.text=None
        def setText(self,t):self.text=t
    class Signal:
        def __init__(self):self.count=0
        def emit(self):self.count+=1
    class Pane:
        def __init__(self):
            self.project=SimpleNamespace(pages=[],selected_page='previous-page')
            self._loading=False
            self._generation=0
            self._thumb_pending=set()
            self._thumb_failed=set()
            self._loaded_thumb_rows=set()
            self._group_thumb_pending=set()
            self.pages_list=Counter()
            self.counter=TextLabel()
            self.page_title=TextLabel()
            self.page_position=TextLabel()
            self.readingChanged=Signal()
            self._active=True
            self.clear_calls=0
        def current_page(self):return None
        def display_current(self):self.clear_calls+=1
        def schedule_thumbnails(self):pass
    pane=Pane()
    fn(pane)
    assert pane.clear_calls==1
    assert pane.project.selected_page is None
    assert pane.page_title.text=='PAGE PREVIEW'
    assert pane.page_title._has_page is False
    assert pane.page_position.text=='No page selected'
    assert pane.counter.text=='0 pages'
    assert pane._loading is False
    assert pane.readingChanged.count==1
