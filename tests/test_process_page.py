from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
SCREEN = ROOT / "app/src/main/java/com/alvsia/pro/ui/tool/ToolWorkspaceScreen.kt"


class UnifiedProcessPageTests(unittest.TestCase):
    def test_simple_and_advanced_log_modes_are_available(self):
        source = SCREEN.read_text(encoding="utf-8")
        self.assertIn('var logMode by remember(operation.id) { mutableStateOf("simple") }', source)
        self.assertIn('onClick = { logMode = "simple" }', source)
        self.assertIn('onClick = { logMode = "advanced" }', source)
        self.assertIn('if (logMode == "advanced")', source)
        self.assertIn("LinearProgressIndicator(", source)


    def test_destructive_workspace_clear_requires_explicit_confirmation(self):
        source = SCREEN.read_text(encoding="utf-8")
        self.assertIn('var confirmClearWorkspace by remember(operation.id) { mutableStateOf(false) }', source)
        self.assertIn('if (operation.id == "clear_work")', source)
        self.assertIn('if (confirmClearWorkspace)', source)
        self.assertIn('This action permanently removes files in WORK and OUT', source)
        self.assertIn('Text("CANCEL"', source)


    def test_smart_submenu_has_no_nested_operation_picker_and_auto_routes(self):
        source = SCREEN.read_text(encoding="utf-8")
        planner = (ROOT / "app/src/main/java/com/alvsia/pro/tool/SmartEnginePlanner.kt").read_text(encoding="utf-8")
        self.assertNotIn("SELECT OPERATION", source)
        self.assertNotIn("showActionPicker", source)
        self.assertIn("SmartEnginePlanner.resolve", source)
        self.assertIn("fun resolve(", planner)
        for provider_id in range(1, 20):
            self.assertIn(f"            {provider_id} ->", planner)
        self.assertIn("detection?.suggestedSubtool", planner)
        self.assertIn("actions.associateBy", planner)

    def test_existing_run_config_and_log_export_paths_remain(self):
        source = SCREEN.read_text(encoding="utf-8")
        self.assertIn("onRun(uri, null)", source)
        self.assertIn("WorkPaths.dirWork()", source)
        self.assertIn("WorkPaths.dirOut()", source)
        self.assertIn('ClipData.newPlainText("ALVSIA log", logs.joinToString("\\n"))', source)
        self.assertIn('"LOG_${operation.id}_${System.currentTimeMillis()}.txt"', source)


if __name__ == "__main__":
    unittest.main()
