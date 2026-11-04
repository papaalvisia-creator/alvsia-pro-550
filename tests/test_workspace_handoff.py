from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class SharedWorkspaceHandoffTests(unittest.TestCase):
    def test_output_browser_can_handoff_an_artifact_to_any_studio(self):
        output = (ROOT / "app/src/main/java/com/alvsia/pro/ui/output/OutputBrowserScreen.kt").read_text(encoding="utf-8")
        self.assertIn("onUseWithStudio: (StudioItem, Uri) -> Unit", output)
        self.assertIn("StudioCatalog.all.forEach", output)
        self.assertIn("FileProvider.getUriForFile", output)
        self.assertIn("onUseWithStudio(studio, uri)", output)

    def test_dashboard_to_tool_handoff_prefills_the_selected_input(self):
        home = (ROOT / "app/src/main/java/com/alvsia/pro/ui/home/HomeScreen.kt").read_text(encoding="utf-8")
        main = (ROOT / "app/src/main/java/com/alvsia/pro/MainActivity.kt").read_text(encoding="utf-8")
        tool = (ROOT / "app/src/main/java/com/alvsia/pro/ui/tool/ToolWorkspaceScreen.kt").read_text(encoding="utf-8")
        self.assertIn('QuickAction("Outputs"', home)
        self.assertIn('onWorkspace = { screen = "output" }', main)
        self.assertIn("pendingInputUri = uri", main)
        self.assertIn("initialUri = pendingInputUri", main)
        self.assertIn("LaunchedEffect(initialUri)", tool)
        self.assertIn("FileMagic.detect(ctx, initialUri)", tool)

    def test_shared_output_browser_does_not_offer_one_tap_recursive_delete(self):
        output = (ROOT / "app/src/main/java/com/alvsia/pro/ui/output/OutputBrowserScreen.kt").read_text(encoding="utf-8")
        self.assertNotIn("deleteRecursively", output)
        self.assertNotIn("CLEAR ALL", output)
        self.assertIn("REFRESH", output)


if __name__ == "__main__":
    unittest.main()
