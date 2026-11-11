package com.alvsia.pro.ui.output

import android.content.Intent
import android.net.Uri
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.statusBarsPadding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.core.content.FileProvider
import com.alvsia.pro.ui.theme.AlvisiaBlue
import com.alvsia.pro.ui.theme.AlvisiaCyan
import com.alvsia.pro.ui.theme.AlvisiaDeep
import com.alvsia.pro.ui.theme.AlvisiaSilver
import com.alvsia.pro.tool.WorkPaths
import com.alvsia.pro.ui.home.StudioCatalog
import com.alvsia.pro.ui.home.StudioItem
import java.io.File
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale

@Composable
fun OutputBrowserScreen(onBack: () -> Unit, onUseWithStudio: (StudioItem, Uri) -> Unit) {
    val ctx = LocalContext.current
    var files by remember { mutableStateOf<List<Pair<File, String>>>(emptyList()) }
    var selectedFile by remember { mutableStateOf<File?>(null) }
    var previewText by remember { mutableStateOf("") }

    val refreshFiles = {
        WorkPaths.bindApp(ctx)
        val root = WorkPaths.alvsiaRoot()
        val outputRoots = mutableListOf<Pair<File, String>>()

        // Legacy output tree remains readable for older app versions.
        val legacyOut = File(root, "OUT")
        if (legacyOut.isDirectory) outputRoots.add(legacyOut to "OUT")

        // Current task-isolated engine writes to TASKS/<task-id>/OUT/<MODULE>.
        // Index these files too; scanning only OUT/ hid every new task result.
        val tasksRoot = File(root, "TASKS")
        tasksRoot.listFiles()?.filter { it.isDirectory }?.forEach { task ->
            val taskOut = File(task, "OUT")
            if (taskOut.isDirectory) {
                outputRoots.add(taskOut to "TASKS/${task.name}/OUT")
            }
        }

        val discovered = outputRoots.flatMap { (base, label) ->
            base.walkTopDown()
                .filter { it.isFile && it.length() > 0 }
                .map { file ->
                    val rel = file.relativeTo(base).path
                    val date = SimpleDateFormat("MM-dd HH:mm", Locale.US).format(Date(file.lastModified()))
                    file to "$label/$rel  (${file.length()} B)  $date"
                }.toList()
        }
        files = discovered
            .distinctBy { it.first.absolutePath }
            .sortedByDescending { it.first.lastModified() }
            .take(500)
    }
    LaunchedEffect(Unit) { refreshFiles() }

    Column(
        Modifier.fillMaxSize().background(AlvisiaDeep).statusBarsPadding().padding(12.dp)
    ) {
        Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween, verticalAlignment = Alignment.CenterVertically) {
            TextButton(onClick = onBack) { Text("← BACK", color = AlvisiaCyan, fontWeight = FontWeight.Bold, fontSize = 12.sp) }
            TextButton(onClick = { refreshFiles() }) { Text("REFRESH", color = AlvisiaCyan, fontWeight = FontWeight.Bold, fontSize = 11.sp) }
        }
        Text("OUTPUT BROWSER", color = Color.White, fontWeight = FontWeight.Bold, fontSize = 16.sp)
        Text("${files.size} files in OUT/ + TASKS/*/OUT/", color = AlvisiaSilver.copy(alpha = 0.5f), fontSize = 11.sp)
        Spacer(Modifier.height(8.dp))

        LazyColumn(Modifier.fillMaxWidth().weight(1f), verticalArrangement = Arrangement.spacedBy(4.dp)) {
            items(files) { (file, display) ->
                Row(
                    Modifier.fillMaxWidth().clip(RoundedCornerShape(8.dp))
                        .background(if (selectedFile == file) Color(0xFF0D1B2A) else Color(0xFF070D14))
                        .border(1.dp, if (selectedFile == file) AlvisiaCyan.copy(alpha = 0.5f) else AlvisiaBlue.copy(alpha = 0.2f), RoundedCornerShape(8.dp))
                        .clickable {
                            selectedFile = file
                            val ext = file.extension.lowercase()
                            previewText = if (ext in listOf("txt","lua","json","csv","xml","log","py","md") && file.length() <= 5_000_000) {
                                try { file.readText(Charsets.UTF_8).take(2000) } catch (_: Exception) { "(error reading)" }
                            } else "(binary — use OPEN)"
                        }.padding(8.dp)
                ) {
                    Text(display, color = AlvisiaSilver, fontFamily = FontFamily.Monospace, fontSize = 10.sp, modifier = Modifier.weight(1f))
                    Text("OPEN", color = AlvisiaCyan, fontSize = 10.sp, fontWeight = FontWeight.Bold, modifier = Modifier.clickable {
                        try { val uri = FileProvider.getUriForFile(ctx, "${ctx.packageName}.provider", file)
                            ctx.startActivity(Intent.createChooser(Intent(Intent.ACTION_VIEW).setDataAndType(uri, "application/octet-stream").addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION), "Open with"))
                        } catch (_: Exception) {} })
                    Spacer(Modifier.width(8.dp))
                    Text("SHARE", color = AlvisiaCyan, fontSize = 10.sp, fontWeight = FontWeight.Bold, modifier = Modifier.clickable {
                        try { val uri = FileProvider.getUriForFile(ctx, "${ctx.packageName}.provider", file)
                            ctx.startActivity(Intent.createChooser(Intent(Intent.ACTION_SEND).setType("application/octet-stream").putExtra(Intent.EXTRA_STREAM, uri).addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION), "Share"))
                        } catch (_: Exception) {} })
                }
            }
        }
        if (previewText.isNotEmpty()) {
            Spacer(Modifier.height(4.dp))
            Text("PREVIEW", color = AlvisiaSilver.copy(alpha = 0.4f), fontSize = 9.sp)
            Spacer(Modifier.height(2.dp))
            LazyColumn(Modifier.fillMaxWidth().height(200.dp).clip(RoundedCornerShape(8.dp)).background(Color(0xFF070D14)).padding(8.dp)) {
                items(previewText.lines().take(40)) { line -> Text(line, color = AlvisiaSilver, fontFamily = FontFamily.Monospace, fontSize = 9.sp) }
            }
        }
        if (selectedFile?.isFile == true) {
            Spacer(Modifier.height(8.dp))
            Text("CONTINUE IN ANOTHER STUDIO", color = AlvisiaCyan, fontWeight = FontWeight.Bold, fontSize = 10.sp)
            Text("The selected output will be passed as the next tool's input.", color = AlvisiaSilver.copy(alpha = 0.6f), fontSize = 10.sp)
            Row(
                Modifier.fillMaxWidth().horizontalScroll(rememberScrollState()),
                horizontalArrangement = Arrangement.spacedBy(6.dp)
            ) {
                StudioCatalog.all.forEach { studio ->
                    TextButton(onClick = {
                        try {
                            val uri = FileProvider.getUriForFile(ctx, "${ctx.packageName}.provider", selectedFile!!)
                            onUseWithStudio(studio, uri)
                        } catch (_: Exception) {
                            previewText = "Unable to share this output through the app file provider."
                        }
                    }) {
                        Text("${studio.icon} ${studio.title}", color = AlvisiaCyan, fontSize = 10.sp, fontWeight = FontWeight.Bold)
                    }
                }
            }
        }
    }
}
