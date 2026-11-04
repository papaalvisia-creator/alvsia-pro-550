package com.alvsia.pro.ui.home

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
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.remember
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.alvsia.pro.ui.theme.AlvisiaBlue
import com.alvsia.pro.ui.theme.AlvisiaCyan
import com.alvsia.pro.ui.theme.AlvisiaDeep
import com.alvsia.pro.ui.theme.AlvisiaSilver

@Composable
fun StudioScreen(
    studio: StudioItem,
    tools: List<ToolItem>,
    onBack: () -> Unit,
    onTool: (ToolItem) -> Unit
) {
    val studioTools = remember(studio.id, tools) {
        StudioCatalog.moduleIds(studio).mapNotNull { id -> tools.firstOrNull { it.id == id } }
    }

    Column(
        Modifier
            .fillMaxSize()
            .background(AlvisiaDeep)
            .statusBarsPadding()
            .padding(horizontal = 14.dp, vertical = 10.dp)
    ) {
        TextButton(onClick = onBack) {
            Text("← DASHBOARD", color = AlvisiaCyan, fontWeight = FontWeight.Bold, fontSize = 12.sp)
        }
        Row(
            Modifier.fillMaxWidth().padding(top = 4.dp, bottom = 8.dp),
            verticalAlignment = Alignment.CenterVertically
        ) {
            Text(studio.icon, fontSize = 32.sp)
            Column(Modifier.weight(1f).padding(start = 12.dp)) {
                Text(studio.title, color = Color.White, fontWeight = FontWeight.Black, fontSize = 21.sp)
                Text(studio.description, color = AlvisiaSilver.copy(alpha = 0.72f), fontSize = 11.sp)
            }
        }
        Row(
            Modifier.fillMaxWidth().clip(RoundedCornerShape(10.dp))
                .background(Color(0xFF101D28))
                .border(1.dp, AlvisiaCyan.copy(alpha = 0.25f), RoundedCornerShape(10.dp))
                .padding(12.dp),
            horizontalArrangement = Arrangement.SpaceBetween,
            verticalAlignment = Alignment.CenterVertically
        ) {
            Text("AVAILABLE MODULES", color = AlvisiaCyan, fontWeight = FontWeight.Bold, fontSize = 10.sp)
            Text(studioTools.size.toString(), color = Color.White, fontWeight = FontWeight.Black, fontSize = 16.sp)
        }
        Spacer(Modifier.height(12.dp))
        LazyColumn(verticalArrangement = Arrangement.spacedBy(8.dp)) {
            items(studioTools, key = { it.id }) { tool ->
                Row(
                    Modifier.fillMaxWidth()
                        .clip(RoundedCornerShape(14.dp))
                        .background(Color(0xFF0C1622))
                        .border(1.dp, AlvisiaBlue.copy(alpha = 0.36f), RoundedCornerShape(14.dp))
                        .clickable { onTool(tool) }
                        .padding(14.dp),
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    Column(Modifier.weight(1f)) {
                        Text(tool.title, color = Color.White, fontWeight = FontWeight.SemiBold, fontSize = 14.sp)
                        Text(tool.desc, color = AlvisiaSilver.copy(alpha = 0.65f), fontSize = 11.sp)
                    }
                    Text("OPEN  ›", color = AlvisiaCyan, fontWeight = FontWeight.Bold, fontSize = 10.sp)
                }
            }
        }
    }
}
