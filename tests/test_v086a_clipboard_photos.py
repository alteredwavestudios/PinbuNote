"""v0.8.6b image clipboard and photo model regression tests (headless)."""
import io
import copy
from pathlib import Path

import pytest
from PIL import Image

from yomunote.vector_marks import (
    make_photo, valid_photo, valid_vector, vector_bounds, translated_vector,
    resized_vector, add_mark, remove_stroke, restore_stroke, MAX_PHOTO_JPEG_BYTES,
)
from yomunote.project import Project
from yomunote.importers import blank_page
from yomunote import __version__

ROOT = Path(__file__).resolve().parents[1]


def jpeg(width=120, height=72):
    result = io.BytesIO()
    Image.new('RGB', (width, height), 'pink').save(result, 'JPEG', quality=77)
    return result.getvalue()


def example():
    return make_photo(jpeg(), (.15, .20, .5, .3))


def test_version_is_current_and_release_builders_not_mislabelled():
    assert __version__ == '0.8.7c'
    assert 'v0.8.7c' in (ROOT / '.github/workflows/release.yml').read_text()


def test_photo_validated_portable_and_undoable():
    photo = example()
    assert valid_photo(photo) and valid_photo(photo, verify_data=True)
    assert valid_vector(photo)
    assert vector_bounds(photo) == pytest.approx((.15,.20,.65,.50))
    assert add_mark([], photo) == [photo]
    assert remove_stroke([photo], photo['id']) == []
    assert restore_stroke([], 0, photo) == [photo]
    with pytest.raises(ValueError):
        make_photo(jpeg() + b'BAD', (.15,.2,.5,.3))
    with pytest.raises(ValueError):
        make_photo(jpeg(), (.9,.2,.5,.3))
    with pytest.raises(ValueError):
        make_photo(jpeg() * (MAX_PHOTO_JPEG_BYTES // len(jpeg())+1), (.1,.1,.3,.2))


def test_photo_move_and_resize_preserve_jpeg_and_bounds():
    photo = example()
    moved = translated_vector(photo, 1, -1)
    assert moved['x'] == pytest.approx(.5)
    assert moved['y'] == 0
    assert moved['data'] == photo['data']
    resized = resized_vector(photo, 'br', .8, .9)
    assert valid_photo(resized)
    assert resized['data'] == photo['data']
    assert resized['h']/resized['w'] == pytest.approx(photo['h']/photo['w'])
    centered = resized_vector(photo, 'tl', 0, 0, from_center=True)
    assert valid_photo(centered)


def test_reject_invalid_jpeg_and_decompression_bomb():
    mark = example()
    invalid = copy.deepcopy(mark)
    invalid['data'] = '/9j/NOTJPEGBODY=='
    assert not valid_photo(invalid, verify_data=True)
    invalid['data'] = ''
    assert not valid_photo(invalid)
    invalid = dict(mark, x=-1)
    assert not valid_photo(invalid)


def test_photo_survives_project_save_and_load(tmp_path):
    project = Project.create(tmp_path, 'Photo notebook')
    page = blank_page(project)
    project.pages.append(page)
    mark = example()
    project.annotations[page['id']] = [mark]
    project.save()
    restored = Project.load(project.path)
    assert restored.pages[0]['id'] == page['id']
    assert restored.annotations[page['id']] == [mark]


def test_photo_invalid_mark_is_recoverable_not_crash(tmp_path):
    project = Project.create(tmp_path, 'Photo notebook')
    page = blank_page(project)
    project.pages.append(page)
    mark = example()
    mark['data'] = '/9j/NOTJPEGBODY=='
    project.annotations[page['id']] = [mark]
    project.save()
    with pytest.raises(ValueError, match='Invalid photo annotation'):
        Project.load(project.path)
    warnings = []
    recovered = Project.load(project.path, recover_cosmetic=True,
                             recovery_warnings=warnings)
    assert recovered.annotations[page['id']] == []
    assert warnings


def test_clipboard_ui_is_scoped_and_existing_notes_paste_is_not_overridden():
    window = (ROOT / 'yomunote/window.py').read_text(encoding='utf-8')
    assert 'def paste_clipboard_page(self):' in window
    assert 'def paste_clipboard_photo(self):' in window
    assert 'QShortcut(QKeySequence(QKeySequence.StandardKey.Paste), widget)' in window
    assert 'self.pages_list, self.paste_clipboard_page' in window
    assert 'self.canvas, self.paste_clipboard_photo' in window
    assert 'self.notes.editor, self.paste_clipboard_photo' not in window
    assert "self.history.perform(CallbackAction(\n                'Paste Clipboard Page'" in window
    assert "self._add_vector(make_photo(jpeg, rect), 'Paste Photo'" in window


def test_photo_embedded_in_normal_image_page_survives_tab_transfer(tmp_path):
    """Cross-tab transfers need no extra photo source files or migrations."""
    from yomunote.notebook import Notebook
    from yomunote.importers import import_document
    nb = Notebook.create(tmp_path, 'Copy photo note')
    try:
        src = nb.active_id
        dest = nb.add_tab('Destination')
        project = nb.project(src)
        image_file = tmp_path / 'screenshot.jpg'
        image_file.write_bytes(jpeg(200, 100))
        page = import_document(project, image_file)[0]
        project.pages = [page]
        mark = example()
        project.annotations[page['id']] = [mark]
        project.save()
        nb.save()
        assert nb.transfer_pages(src, dest, [page['id']], move=True) == 1
        new_tab = nb.project(dest)
        assert len(new_tab.pages) == 1
        new_id = new_tab.pages[0]['id']
        assert new_tab.annotations[new_id] == [mark]
        assert nb.project(src).pages == []
        nb.save()
        path = nb.path
    finally:
        nb.close()
    reopened = Notebook.load(path)
    try:
        target = reopened.project(dest)
        assert len(target.pages) == 1
        assert target.annotations[target.pages[0]['id']] == [mark]
    finally:
        reopened.close()
