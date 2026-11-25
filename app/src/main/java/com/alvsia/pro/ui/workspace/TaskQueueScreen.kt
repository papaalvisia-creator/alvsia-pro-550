package com.alvsia.pro.ui.workspace

import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.statusBarsPadding
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.alvsia.pro.tool.LiveTask
import com.alvsia.pro.tool.TaskCenter
import com.alvsia.pro.tool.TaskStatus
import com.alvsia.pro.ui.theme.AlvisiaBlue
import com.alvsia.pro.ui.theme.AlvisiaCyan
import com.alvsia.pro.ui.theme.AlvisiaDeep
import com.alvsia.pro.ui.theme.AlvisiaSilver

@Composable
fun TaskQueueScreen(onBack: () -> Unit, onOpenTask: (LiveTask) -> Unit) {
    val tasks = TaskCenter.tasks
    Column(Modifier.fillMaxSize().background(AlvisiaDeep).statusBarsPadding().padding(12.dp)) {
        Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
            TextButton(onClick = onBack) { Text("← BACK", color = AlvisiaCyan, fontWeight = FontWeight.Bold) }
            Spacer(Modifier.weight(1f))
            TextButton(onClick = { TaskCenter.clearFinished() }) { Text("CLEAR FINISHED", color = AlvisiaSilver, fontSize = 10.sp) }
        }
        Text("BATCH JOB QUEUE", color = Color.White, fontSize = 17.sp, fontWeight = FontWeight.Black)
        Text("${TaskCenter.activeCount()} active · ${tasks.size} recorded tasks", color = AlvisiaSilver.copy(alpha = .6f), fontSize = 11.sp)
        Spacer(Modifier.height(10.dp))
        LazyColumn(verticalArrangement = Arrangement.spacedBy(6.dp)) {
            items(tasks, key = { it.id }) { task ->
                val statusColor = when (task.status) {
                    TaskStatus.RUNNING -> AlvisiaCyan
                    TaskStatus.COMPLETED -> Color(0xFF65D69A)
                    TaskStatus.ERROR -> Color(0xFFFF8B83)
                }
                Column(
                    Modifier.fillMaxWidth().clip(RoundedCornerShape(10.dp))
                        .background(Color(0xFF0C1622))
                        .border(1.dp, AlvisiaBlue.copy(alpha = .3f), RoundedCornerShape(10.dp))
                        .clickable { onOpenTask(task) }
                        .padding(10.dp)
                ) {
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        Text(task.title, color = AlvisiaSilver, fontSize = 11.sp, fontWeight = FontWeight.Bold, modifier = Modifier.weight(1f))
                        Text(task.status.name, color = statusColor, fontSize = 9.sp, fontWeight = FontWeight.Bold)
                    }
                    Text("${task.stage} · ${task.fileLabel.ifBlank { "NO FILE" }}", color = AlvisiaSilver.copy(alpha = .55f), fontSize = 9.sp)
                    task.progress?.let { Text("$it%", color = AlvisiaCyan, fontSize = 9.sp) }
                    Text("OPEN DETAILS →", color = AlvisiaCyan, fontSize = 9.sp, fontWeight = FontWeight.Bold)
                }
            }
            if (tasks.isEmpty()) item { Text("No jobs recorded in this session.", color = AlvisiaSilver.copy(alpha = .5f), fontSize = 10.sp) }
        }
    }
}
