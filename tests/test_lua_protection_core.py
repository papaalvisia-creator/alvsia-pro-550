from app.src.main.python.lua_engine.protection import protect_source

def test_balanced_renames_local_identifier():
    src = "local value = 3\nreturn value + 2\n"
    out = protect_source(src, "balanced")
    assert "return" in out
    assert "value" not in out

def test_strong_encodes_simple_string():
    src = 'local msg = "hello"\nreturn msg\n'
    out = protect_source(src, "strong")
    assert "string.char(" in out
    assert '"hello"' not in out
