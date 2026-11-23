from pathlib import Path
import importlib.util
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1] / "app" / "src" / "main" / "python"
sys.path.insert(0, str(ROOT))

import smart_premium_source_fusion as fusion


class SmartPremiumSourceFusionTests(unittest.TestCase):
    def test_three_source_families_are_registered(self):
        inventory = fusion.source_inventory()
        self.assertEqual(
            inventory["sources"],
            [
                "IkramTool_V130_4.7.zip",
                "TOOL.zip",
                "RegulerResault_ALVSIA_tool_no_on_vip_engine.zip",
            ],
        )
        self.assertFalse(inventory["regression_corpus_is_runtime_data"])
        self.assertFalse(inventory["login_bypass_source_import"])

    def test_required_backends_exist(self):
        for group, contracts in fusion.REQUIRED_BACKENDS.items():
            for module_name, attr in contracts:
                module = __import__(module_name, fromlist=[attr])
                self.assertTrue(callable(getattr(module, attr)), (group, module_name, attr))

    def test_bgmi_engine_has_both_directions(self):
        from lua_engine.bgmi import transform_bgmi_lua
        self.assertTrue(callable(transform_bgmi_lua))
        # A malformed payload must fail closed instead of fabricating bytecode.
        with self.assertRaises(ValueError):
            transform_bgmi_lua(b"not-a-lua-chunk", decrypt=True)

    def test_adapter_registry_is_explicit(self):
        import module_adapters
        ops = {(x["module"], x["operation"]) for x in module_adapters.list_adapters()}
        required = {
            ("lua", "decompile"),
            ("lua", "protect"),
            ("lua", "compile"),
            ("lua", "inject"),
            ("archive", "inspect"),
            ("archive", "extract"),
            ("archive", "rebuild"),
            ("archive", "integrity"),
            ("data", "recover"),
            ("data", "xor"),
            ("data", "sm4"),
            ("data", "metadata"),
        }
        self.assertTrue(required.issubset(ops))


if __name__ == "__main__":
    unittest.main()
