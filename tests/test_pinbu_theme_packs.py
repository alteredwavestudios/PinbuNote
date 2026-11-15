"""Static test of palette coverage without requiring native Qt widgets."""
import ast
from pathlib import Path


def test_theme_pack_identifiers_are_complete_and_unique():
    source = (Path(__file__).parents[1] / 'yomunote/window.py').read_text()
    module = ast.parse(source)
    pack = next(ast.literal_eval(assign.value)
                for assign in module.body
                if isinstance(assign, ast.Assign) and any(
                    isinstance(t, ast.Name) and t.id == 'THEME_PACKS'
                    for t in assign.targets))
    assert tuple(pack) == ('Japanese & Kawaii', 'Pinbu Textiles',
                           'French Art Nouveau', 'Modern & System')
    ids = [key for group in pack.values() for key in group]
    assert len(ids) == len(set(ids))
    assert {'pinbu-quilt', 'pinbu-applique', 'pinbu-night-quilt',
            'nouveau-iris', 'nouveau-peacock', 'system'} <= set(ids)
    assert all(f"'{key}': {{" in source for key in ids if key != 'system')


def test_visual_panel_colours_are_distinct_for_new_palettes():
    source = (Path(__file__).parents[1] / 'yomunote/window.py').read_text()
    module = ast.parse(source)
    palettes = {}
    for node in ast.walk(module):
        if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
            continue
        if not (isinstance(node.func.value, ast.Name)
                and node.func.value.id == 'THEMES'
                and node.func.attr == 'update'):
            continue
        if node.args and isinstance(node.args[0], ast.Dict):
            palettes.update(ast.literal_eval(node.args[0]))
    for key in ('pinbu-applique', 'pinbu-peachwork', 'pinbu-night-quilt',
                'pinbu-moon-sampler', 'nouveau-iris', 'nouveau-ginkgo',
                'nouveau-peacock', 'nouveau-velvet'):
        colours = palettes[key]
        assert len({colours['panel'], colours['shelf'], colours['canvas']}) == 3
        assert colours['paper'] != colours['window']
