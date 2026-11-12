from pathlib import Path
import py_compile
import tempfile

ROOT = Path(__file__).resolve().parents[2]
targets = [
    ROOT / "app/src/main/python/smart_lua_engine.py",
    ROOT / "app/src/main/python/module_adapters.py",
]
for path in targets:
    py_compile.compile(str(path), doraise=True)

print("SMART_LUA_SYNTAX_OK")
