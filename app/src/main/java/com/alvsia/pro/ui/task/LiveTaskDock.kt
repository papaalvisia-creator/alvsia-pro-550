package com.alvsia.pro.ui.task

import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.layout.statusBarsPadding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.alvsia.pro.tool.LiveTask
import com.alvsia.pro.tool.TaskStatus
import com.alvsia.pro.ui.theme.AlvisiaBlue
import com.alvsia.pro.ui.theme.AlvisiaCyan
import com.alvsia.pro.ui.theme.AlvisiaDeep
import com.alvsia.pro.ui.theme.AlvisiaRed
import com.alvsia.pro.ui.theme.AlvisiaSilver

@Composable
fun LiveTaskDock(
    tasks: List<LiveTask>,
    modifier: Modifier = Modifier,
    onOpenTask: (LiveTask) -> Unit
) {
    val active = tasks.count { it.status == TaskStatus.RUNNING }
    Box(
        modifier = modifier
            .fillMaxWidth()
            .statusBarsPadding()
            .background(Color(0xF20A111A))
            .padding(horizontal = 8.dp, vertical = 6.dp)
    ) {
        Column {
            Row {
                Text("● LIVE TASKS", color = AlvisiaCyan, fontSize = 9.sp, fontWeight = FontWeight.Black, fontFamily = FontFamily.Monospace)
                Spacer(Modifier.width(8.dp))
                Text("$active ACTIVE  /  ${tasks.size} TOTAL", color = AlvisiaSilver, fontSize = 8.sp, fontFamily = FontFamily.Monospace)
            }
            Spacer(Modifier.height(5.dp))
            Row(
                modifier = Modifier.fillMaxWidth().horizontalScroll(rememberScrollState()),
                horizontalArrangement = Arrangement.spacedBy(6.dp)
            ) {
                tasks.take(8).forEach { task ->
                    val statusColor = when (task.status) {
                        TaskStatus.RUNNING -> AlvisiaCyan
                        TaskStatus.COMPLETED -> Color(0xFF63E6A6)
                        TaskStatus.ERROR -> AlvisiaRed
                    }
                    Column(
                        modifier = Modifier
                            .width(190.dp)
                            .clip(RoundedCornerShape(10.dp))
                            .background(AlvisiaDeep)
                            .clickable { onOpenTask(task) }
                            .padding(8.dp)
                    ) {
                        Row {
                            Text(statusIcon(task.status), color = statusColor, fontSize = 10.sp)
                            Spacer(Modifier.width(4.dp))
                            Text(task.title, color = Color.White, fontSize = 10.sp, fontWeight = FontWeight.Bold, maxLines = 1)
                            Spacer(Modifier.weight(1f))
                            Text(task.progress?.let { "$it%" } ?: "LIVE", color = statusColor, fontSize = 9.sp, fontFamily = FontFamily.Monospace)
                        }
                        Spacer(Modifier.height(4.dp))
                        if (task.progress != null) LinearProgressIndicator(progress = { task.progress.coerceIn(0,100) / 100f }, modifier = Modifier.fillMaxWidth(), color = statusColor)
                        else LinearProgressIndicator(modifier = Modifier.fillMaxWidth(), color = statusColor)
                        Spacer(Modifier.height(3.dp))
                        Text(task.stage, color = AlvisiaSilver, fontSize = 8.sp, fontFamily = FontFamily.Monospace, maxLines = 1)
                    }
                }
            }
        }
    }
}

private fun statusIcon(status: TaskStatus): String = when (status) {
    TaskStatus.RUNNING -> "●"
    TaskStatus.COMPLETED -> "✓"
    TaskStatus.ERROR -> "✕"
}
