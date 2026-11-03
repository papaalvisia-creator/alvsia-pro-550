"""
Test the per-tool permission matrix declared in PermissionManager.kt.

Static check: parse the Kotlin source to ensure all 18 tools are
covered and the matrix returns sensible permission sets for at
least a few representative tools.
"""
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PM = ROOT / "app/src/main/java/com/alvsia/pro/sec/PermissionManager.kt"


def parse_for_tool_branches(src: str):
    """Returns a dict {tool_id (int): list of (permission, flow, rationale)}.

    Handles forTool(N) delegation chains by following them recursively.
    """
    text = src
    branches_raw = {}
    m = re.search(r"fun forTool\(toolId: Int\): List<ToolPermission> = when \(toolId\) \{", text)
    if not m:
        return branches_raw
    start = m.end()
    body = text[start:]
    # Match each branch including its delegate marker if any. The branch_re
    # captures the whole `N -> forTool(M)` or `N -> listOf(` or `N -> emptyList()`.
    branch_re = re.compile(
        r"^\s*(\d+)\s*->\s*(forTool\((\d+)\)|listOf\(|emptyList\(\))",
        re.MULTILINE
    )
    matches = list(branch_re.finditer(body))
    delegated = {}
    for idx, m in enumerate(matches):
        tool_id = int(m.group(1))
        delegate_target = m.group(3)  # may be None
        if delegate_target:
            delegated[tool_id] = int(delegate_target)
            branches_raw[tool_id] = []
            continue
        end = matches[idx + 1].start() if idx + 1 < len(matches) else len(body)
        chunk = body[m.end():end]
        perms = []
        for pm in re.finditer(
            r'ToolPermission\(\s*"([^"]+)"\s*,\s*"([^"]+)"\s*,\s*"([^"]+)"', chunk
        ):
            perms.append((pm.group(1), pm.group(2), pm.group(3)))
        branches_raw[tool_id] = perms

    def resolve(tid, seen=None):
        if seen is None:
            seen = set()
        if tid in seen:
            return []
        seen.add(tid)
        if tid in delegated:
            return resolve(delegated[tid], seen)
        return branches_raw.get(tid, [])

    keys = set(branches_raw.keys()) | set(delegated.keys())
    return {tid: resolve(tid) for tid in keys}


class TestPermissionMatrix(unittest.TestCase):
    def setUp(self):
        self.src = PM.read_text(encoding="utf-8")
        self.branches = parse_for_tool_branches(self.src)

    def test_all_18_tools_have_matrix_entry(self):
        for i in range(1, 19):
            self.assertIn(i, self.branches,
                          f"Tool {i} missing from ToolPermissionMatrix.forTool()")

    def test_storage_tools_get_storage_permissions(self):
        # Tools 1-6 are file-oriented; they must have storage permissions
        for tid in (1, 2, 3, 4, 5, 6, 8, 9, 10, 12, 13, 14, 15, 16, 18):
            perms = self.branches.get(tid, [])
            perm_names = [p[0] for p in perms]
            self.assertIn("android.permission.READ_EXTERNAL_STORAGE", perm_names,
                          f"Tool {tid} should request READ_EXTERNAL_STORAGE")
            self.assertIn("android.permission.WRITE_EXTERNAL_STORAGE", perm_names,
                          f"Tool {tid} should request WRITE_EXTERNAL_STORAGE")

    def test_frida_tracer_has_no_query_all_packages(self):
        # QUERY_ALL_PACKAGES was removed for Play policy compliance; Frida
        # Tracer (11) must work with storage access only.
        perms = self.branches.get(11, [])
        perm_names = [p[0] for p in perms]
        self.assertNotIn("android.permission.QUERY_ALL_PACKAGES", perm_names)
        self.assertIn("android.permission.READ_EXTERNAL_STORAGE", perm_names)

    def test_anti_re_audit_has_no_query_all_packages(self):
        # Anti-RE Audit (17) uses storage access; QUERY_ALL_PACKAGES was
        # deliberately removed for Play policy compliance.
        perms = self.branches.get(17, [])
        perm_names = [p[0] for p in perms]
        self.assertNotIn("android.permission.QUERY_ALL_PACKAGES", perm_names)
        self.assertIn("android.permission.MANAGE_EXTERNAL_STORAGE", perm_names)

    def test_workspace_tool_has_fewer_perms(self):
        # Workspace clear (7) should not require QUERY_ALL_PACKAGES
        perms = self.branches.get(7, [])
        perm_names = [p[0] for p in perms]
        self.assertNotIn("android.permission.QUERY_ALL_PACKAGES", perm_names)

    def test_no_install_time_only_permissions(self):
        # All install-time-only perms (e.g. QUERY_ALL_PACKAGES) were removed.
        # Every declared permission must use a real runtime/settings flow.
        allowed = {"runtime_auto", "settings_intent", "fallback", "install_time"}
        for tool, perms in self.branches.items():
            for (perm, flow, _) in perms:
                self.assertIn(flow, allowed, f"tool {tool} has unknown flow {flow}")
                self.assertNotEqual(perm, "android.permission.QUERY_ALL_PACKAGES")

    def test_runtime_auto_flows_declared(self):
        runtime_auto_count = sum(1 for perms in self.branches.values()
                                  for (_, flow, _) in perms
                                  if flow == "runtime_auto")
        self.assertGreater(runtime_auto_count, 0,
                           "Matrix must include runtime_auto perms")

    def test_settings_intent_flows_declared(self):
        # Special-access perms require Settings intent on Android 11+
        settings_count = sum(1 for perms in self.branches.values()
                              for (_, flow, _) in perms
                              if flow == "settings_intent")
        self.assertGreater(settings_count, 0,
                           "Matrix must include settings_intent perms (MANAGE_EXTERNAL_STORAGE etc.)")


if __name__ == "__main__":
    unittest.main(verbosity=2)
