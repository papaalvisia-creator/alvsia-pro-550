from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
MAIN = ROOT / 'app/src/main/java/com/alvsia/pro/MainActivity.kt'
TASK = ROOT / 'app/src/main/java/com/alvsia/pro/tool/TaskCenter.kt'
DOCK = ROOT / 'app/src/main/java/com/alvsia/pro/ui/task/LiveTaskDock.kt'
ENGINE = ROOT / 'app/src/main/java/com/alvsia/pro/tool/ToolEngine.kt'
WORKSPACE = ROOT / 'app/src/main/java/com/alvsia/pro/ui/tool/ToolWorkspaceScreen.kt'

class LiveWorkspaceTests(unittest.TestCase):
    def test_tasks_are_independent_and_reopenable(self):
        main = MAIN.read_text(encoding='utf-8')
        task = TASK.read_text(encoding='utf-8')
        self.assertIn('TaskCenter.start(', main)
        self.assertIn('TaskCenter.find(activeTaskId)', main)
        self.assertIn('activeTaskId = TaskCenter.tasks.lastOrNull', main)
        self.assertIn('val active = tasks.count { it.status == TaskStatus.RUNNING }', DOCK.read_text(encoding='utf-8'))
        self.assertIn('mutableStateListOf<LiveTask>()', task)

    def test_live_task_dock_is_visible_across_screens(self):
        main = MAIN.read_text(encoding='utf-8')
        self.assertIn('if (TaskCenter.tasks.isNotEmpty())', main)
        self.assertIn('LiveTaskDock(', main)
        self.assertIn('onOpenTask = { live ->', main)

    def test_workspace_roots_do_not_precreate_57_empty_module_folders(self):
        paths = (ROOT / 'app/src/main/java/com/alvsia/pro/tool/WorkPaths.kt').read_text(encoding='utf-8')
        ensure = paths.split('fun ensureTree()', 1)[1].split('fun readme(', 1)[0]
        self.assertIn('dirIn(); dirWork(); dirOut()', ensure)
        self.assertNotIn('for (id in 1..19)', ensure)

    def test_output_browser_indexes_task_isolated_outputs(self):
        browser = (ROOT / 'app/src/main/java/com/alvsia/pro/ui/output/OutputBrowserScreen.kt').read_text(encoding='utf-8')
        self.assertIn('val tasksRoot = File(root, "TASKS")', browser)
        self.assertIn('val taskOut = File(task, "OUT")', browser)
        self.assertIn('TASKS/${task.name}/OUT', browser)
        self.assertIn('distinctBy { it.first.absolutePath }', browser)

    def test_inline_configs_are_staged_into_each_task_workspace(self):
        engine = ENGINE.read_text(encoding='utf-8')
        self.assertIn('stageTaskConfigs(taskId, subId, lines)', engine)
        self.assertIn('subToolConfig(subId)', engine)
        self.assertIn('val legacyWork = WorkPaths.dirWork()', engine)
        self.assertIn('File(WorkPaths.taskRoot(taskId), "WORK")', engine)
        self.assertIn('CONFIG integrity check failed', engine)

    def test_five_gb_limit_is_per_file_not_cumulative(self):
        engine = ENGINE.read_text(encoding='utf-8')
        workspace = WORKSPACE.read_text(encoding='utf-8')
        self.assertIn('MAX_DIRECT_FILE_BYTES = 5L * 1024L * 1024L * 1024L', engine)
        self.assertIn('MAX_DIRECT_FILE_BYTES', workspace)
        self.assertIn('declaredSize', engine)
        self.assertNotIn('totalImportedBytes', engine)
        self.assertNotIn('cumulative', engine.lower())

if __name__ == '__main__':
    unittest.main()
