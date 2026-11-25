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
        self.assertIn('QuickAction("OUTPUTS"', home)
        self.assertIn('onWorkspace = { outputReturnScreen = "home"; screen = "output" }', main)
        self.assertIn("pendingInputUri = uri", main)
        self.assertIn("initialUri = pendingInputUri", main)
        self.assertIn("LaunchedEffect(initialUri)", tool)
        self.assertIn("FileMagic.detect(ctx, initialUri)", tool)

    def test_workspace_recent_files_and_favorites_refresh_after_interaction(self):
        tool = (ROOT / "app/src/main/java/com/alvsia/pro/ui/tool/ToolWorkspaceScreen.kt").read_text(encoding="utf-8")
        self.assertIn("var recentFiles by remember { mutableStateOf(UXStore.getRecentDisplayNames(ctx)) }", tool)
        self.assertIn("recentFiles = UXStore.getRecentDisplayNames(ctx)", tool)
        self.assertIn("var isFav by remember(sub.id) { mutableStateOf(UXStore.isFavorite(ctx, sub.id)) }", tool)
        self.assertIn("isFav = UXStore.isFavorite(ctx, sub.id)", tool)


    def test_workspace_hub_and_task_queue_are_native_destinations(self):
        main = (ROOT / "app/src/main/java/com/alvsia/pro/MainActivity.kt").read_text(encoding="utf-8")
        router = (ROOT / "app/src/main/java/com/alvsia/pro/tool/SmartModuleRouter.kt").read_text(encoding="utf-8")
        hub = (ROOT / "app/src/main/java/com/alvsia/pro/ui/workspace/WorkspaceHubScreen.kt").read_text(encoding="utf-8")
        queue = (ROOT / "app/src/main/java/com/alvsia/pro/ui/workspace/TaskQueueScreen.kt").read_text(encoding="utf-8")
        ux = (ROOT / "app/src/main/java/com/alvsia/pro/tool/UXStore.kt").read_text(encoding="utf-8")
        self.assertIn('"workspace_recent_files_favorites" -> "workspace"', router)
        self.assertIn('"workspace_batch_job_queue" -> "tasks"', router)
        self.assertIn('"workspace_output_browser_history" -> "output"', router)
        self.assertIn('"workspace" -> WorkspaceHubScreen(', main)
        self.assertIn('"tasks" -> TaskQueueScreen(', main)
        self.assertIn("UXStore.getRecentDisplayNames(ctx)", hub)
        self.assertIn("UXStore.getFavoritesSet(ctx)", hub)
        self.assertIn("UXStore.removeRecent(ctx, uriString)", hub)
        self.assertIn("legacyAliases", ux)
        self.assertIn("TaskCenter.tasks", queue)

    def test_shared_output_browser_does_not_offer_one_tap_recursive_delete(self):
        output = (ROOT / "app/src/main/java/com/alvsia/pro/ui/output/OutputBrowserScreen.kt").read_text(encoding="utf-8")
        self.assertNotIn("deleteRecursively", output)
        self.assertNotIn("CLEAR ALL", output)
        self.assertIn("REFRESH", output)


if __name__ == "__main__":
    unittest.main()
