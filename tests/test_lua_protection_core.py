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

def test_local_scope_does_not_rename_global_after_block():
    src = "local x = 1\ndo local x = 2 print(x) end\nreturn x\n"
    out = protect_source(src, "balanced")
    assert "local _a" in out
    assert "return x" in out
    assert "print(_a" in out

def test_local_declaration_preserves_syntax_spacing():
    src = "local a, b = 1, 2\nreturn a + b\n"
    out = protect_source(src, "balanced")
    assert "local _a" in out
    assert "," in out
    assert "return _a" in out

def test_strong_preserves_escaped_strings_and_comments():
    src = '-- keep this comment\nlocal msg = "a\\n\\\""\nreturn msg\n'
    out = protect_source(src, "strong")
    assert "string.char(" in out
    assert "keep this comment" not in out
    assert "msg" not in out

def test_function_parameters_are_renamed_inside_function_only():
    src = "local function add(left, right)\n  local total = left + right\n  return total\nend\nreturn add\n"
    out = protect_source(src, "balanced")
    assert "function _a" in out
    assert "left" not in out
    assert "right" not in out
    assert "total" not in out
    assert "return _a" in out


def test_member_names_and_labels_are_not_renamed():
    src = "local value = 7\nobj.value = value\nobj:value()\n::value:: goto value\n"
    out = protect_source(src, "balanced")
    assert "obj.value" in out
    assert "obj:value" in out
    assert "::value::" in out


def test_strong_can_leave_one_character_strings_readable():
    src = 'local x = "a"\nreturn x\n'
    out = protect_source(src, "strong")
    assert '"a"' in out
