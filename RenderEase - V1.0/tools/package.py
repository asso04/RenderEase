"""Build an installable legacy add-on ZIP using the standard library."""
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED

root = Path(__file__).resolve().parents[1]
destination = root / 'dist' / 'renderease.zip'
destination.parent.mkdir(exist_ok=True)
with ZipFile(destination, 'w', ZIP_DEFLATED) as archive:
    for path in sorted((root / 'renderease').rglob('*')):
        if path.is_file() and '__pycache__' not in path.parts and path.suffix in ('.py', '.md'):
            archive.write(path, path.relative_to(root))
print(destination)
