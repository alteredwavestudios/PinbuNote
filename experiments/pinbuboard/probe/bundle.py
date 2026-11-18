"""Build the standalone probe resource from Vite output. Run in the build venv."""
from pathlib import Path
import shutil
import subprocess
import tempfile
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parent


def build():
    compiler = shutil.which("pyside6-rcc")
    if not compiler:
        raise SystemExit("Activate the PySide6 build environment first.")
    dist = ROOT / "dist"
    if not (dist / "index.html").is_file():
        raise SystemExit("Build the frontend with npm run build first.")

    root = ET.Element("RCC")
    resource = ET.SubElement(root, "qresource", prefix="/pinbuboard")
    for asset in sorted(dist.rglob("*")):
        if asset.is_file():
            alias = asset.relative_to(dist).as_posix()
            ET.SubElement(resource, "file", alias=alias).text = asset.as_posix()

    with tempfile.TemporaryDirectory(dir=ROOT) as temporary:
        source = Path(temporary) / "probe.qrc"
        result = Path(temporary) / "probe.rcc"
        ET.ElementTree(root).write(source, encoding="utf-8", xml_declaration=True)
        subprocess.run([compiler, "--binary", source, "-o", result], check=True)
        result.replace(ROOT / "probe.rcc")


if __name__ == "__main__":
    build()
