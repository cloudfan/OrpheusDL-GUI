"""Make PyInstaller bundle everything the on-disk OrpheusDL modules import.

The platform modules (modules/*) and the orpheus core are shipped as plain .py
data files and imported at runtime, so PyInstaller never analyses them. Any
stdlib/site-packages module only they use (e.g. logging.handlers) is then
missing from the frozen exe. This scans their imports and injects them into
gui.spec as hidden imports. Run from the build root before PyInstaller.
"""
import ast
import importlib.util
import os
import sys

ROOT = os.getcwd()
SCAN_DIRS = [d for d in ("modules", "orpheus", "utils") if os.path.isdir(d)]
LOCAL_TOPS = {n for n in os.listdir(ROOT) if os.path.isdir(n) or n.endswith(".py")}
LOCAL_TOPS = {n[:-3] if n.endswith(".py") else n for n in LOCAL_TOPS} - {"vendor"}
EXCLUDE_TOPS = {"torch", "cuda", "pytorch", "matplotlib", "pandas", "numpy",
                "PyQt5", "PyQt6", "PySide2", "PySide6", "tests", "test"}

names = set()
for d in SCAN_DIRS:
    for root, dirs, files in os.walk(d):
        dirs[:] = [x for x in dirs if x not in (".git", "__pycache__")]
        for f in files:
            if not f.endswith(".py"):
                continue
            try:
                tree = ast.parse(open(os.path.join(root, f), encoding="utf-8", errors="replace").read())
            except SyntaxError:
                continue
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    names.update(a.name for a in node.names)
                elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                    names.add(node.module)
                    names.update(f"{node.module}.{a.name}" for a in node.names if a.name != "*")


def importable(name):
    try:
        return importlib.util.find_spec(name) is not None
    except Exception:
        return False


found = set()
for n in sorted(names):
    top = n.split(".")[0]
    if top in LOCAL_TOPS or top in EXCLUDE_TOPS:
        continue
    parts = n.split(".")
    for i in range(1, len(parts) + 1):
        sub = ".".join(parts[:i])
        if sub in found:
            continue
        if importable(sub):
            found.add(sub)
        else:
            break

found = sorted(found)
print(f"[hiddenimports] {len(found)} imports from {SCAN_DIRS}: {found}")

spec = open("gui.spec", encoding="utf-8").read()
marker = "    hiddenimports=[\n"
if marker not in spec:
    sys.exit("gui.spec layout changed: could not find hiddenimports=[")
spec = spec.replace(marker, f"    hiddenimports={found!r} + [\n", 1)
open("gui.spec", "w", encoding="utf-8").write(spec)
print("[hiddenimports] gui.spec patched")
