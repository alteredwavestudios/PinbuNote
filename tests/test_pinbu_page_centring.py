"""Pinbu v0.8.7c: lossless scene padding and opt-in group behaviour."""
from copy import deepcopy

from yomunote.page_groups import (
    group_node, page_node, validate, reconcile,
    group_extra_vertical_scroll, page_extra_vertical_scroll,
    set_group_extra_vertical_scroll,
)
from yomunote.reading_view import (
    extra_vertical_scene_padding, normalise_position, clean_reading_view,
)


def structure():
    child = group_node('Slides', [page_node('slide1'), page_node('slide2')])
    root = group_node('Lectures', [child, page_node('essay')])
    return [root, page_node('loose')], root['id'], child['id']


def test_disabled_by_default_and_only_selected_group_changes():
    tree, root, child = structure()
    assert not page_extra_vertical_scroll(tree, 'slide1')
    changed = set_group_extra_vertical_scroll(tree, child, True)
    assert page_extra_vertical_scroll(changed, 'slide1')
    assert page_extra_vertical_scroll(changed, 'slide2')
    assert not page_extra_vertical_scroll(changed, 'essay')
    assert not page_extra_vertical_scroll(changed, 'loose')
    assert not group_extra_vertical_scroll(tree, child)
    assert group_extra_vertical_scroll(changed, child)
    assert changed != tree
    assert set_group_extra_vertical_scroll(changed, child, False) == tree


def test_root_inheritance_and_preservation_when_reordering():
    tree, root, child = structure()
    changed = set_group_extra_vertical_scroll(tree, root, True)
    assert page_extra_vertical_scroll(changed, 'slide1')
    assert page_extra_vertical_scroll(changed, 'essay')
    validate(changed, ['slide1', 'slide2', 'essay', 'loose'])
    reordered = reconcile(deepcopy(changed), ['essay', 'slide1', 'slide2', 'loose'])
    validate(reordered, ['essay', 'slide1', 'slide2', 'loose'])
    assert page_extra_vertical_scroll(reordered, 'essay')
    assert page_extra_vertical_scroll(reordered, 'slide1')


def test_padding_supports_short_landscape_slides_without_new_pixmaps():
    assert extra_vertical_scene_padding(460, 795) > 397
    assert extra_vertical_scene_padding(1200, 795) >= 556
    assert extra_vertical_scene_padding(0, 795) == 0
    assert extra_vertical_scene_padding(float('nan'), 795) == 0


def test_overscrolled_position_survives_save_sanitisation():
    original = {'x': 0.13, 'y': 0.0, 'bottom': False, 'overscroll_y': -0.37}
    assert normalise_position(original) == original
    tree, root, child = structure()
    cleaned = clean_reading_view({'positions': {'slide1': original}},
                                ['slide1', 'slide2', 'essay', 'loose'], tree)
    assert cleaned['positions']['slide1']['overscroll_y'] == -0.37
    legacy = {'x': 0.13, 'y': 0.0, 'bottom': False}
    assert normalise_position(legacy) == legacy
    assert 'overscroll_y' not in normalise_position(
        {'x': 0.1, 'y': .2, 'overscroll_y': float('nan')})
