package com.alvsia.pro.ui.workspace

import android.net.Uri
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
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.alvsia.pro.tool.SubMenus
import com.alvsia.pro.tool.SubTool
import com.alvsia.pro.tool.UXStore
import com.alvsia.pro.ui.theme.AlvisiaBlue
import com.alvsia.pro.ui.theme.AlvisiaCyan
import com.alvsia.pro.ui.theme.AlvisiaDeep
import com.alvsia.pro.ui.theme.AlvisiaSilver

@Composable
fun WorkspaceHubScreen(
    onBack: () -> Unit,
    onUseRecent: (Uri) -> Unit,
    onOpenFavorite: (Int, SubTool) -> Unit
) {
    val ctx = LocalContext.current
    var recent by remember { mutableStateOf(UXStore.getRecentDisplayNames(ctx)) }
    var favorites by remember { mutableStateOf(UXStore.getFavoritesSet(ctx)) }
    val allTools = remember { (1..10).flatMap { module -> SubMenus.forModule(module).map { module to it } } }
    val favoriteTools = allTools.filter { it.second.id in favorites }

    fun refresh() {
        recent = UXStore.getRecentDisplayNames(ctx)
        favorites = UXStore.getFavoritesSet(ctx)
    }

    Column(
        Modifier.fillMaxSize().background(AlvisiaDeep).padding(12.dp)
    ) {
        Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
            TextButton(onClick = onBack) { Text("← BACK", color = AlvisiaCyan, fontWeight = FontWeight.Bold) }
            Spacer(Modifier.weight(1f))
            TextButton(onClick = { refresh() }) { Text("REFRESH", color = AlvisiaCyan, fontWeight = FontWeight.Bold) }
        }
        Text("RECENT FILES & FAVORITES", color = Color.White, fontSize = 17.sp, fontWeight = FontWeight.Black)
        Text("Recent file references and saved Smart Engine shortcuts.", color = AlvisiaSilver.copy(alpha = .6f), fontSize = 11.sp)
        Spacer(Modifier.height(10.dp))

        Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
            Text("RECENT FILES · ${recent.size}", color = AlvisiaCyan, fontSize = 11.sp, fontWeight = FontWeight.Bold)
            Spacer(Modifier.weight(1f))
            TextButton(onClick = { UXStore.clearRecent(ctx); refresh() }) {
                Text("CLEAR ALL", color = AlvisiaSilver, fontSize = 10.sp)
            }
        }
        LazyColumn(Modifier.fillMaxWidth().weight(1f, fill = false), verticalArrangement = Arrangement.spacedBy(5.dp)) {
            items(recent, key = { it.second }) { (displayName, uriString) ->
                Row(
                    Modifier.fillMaxWidth().clip(RoundedCornerShape(9.dp))
                        .background(Color(0xFF0C1622))
                        .border(1.dp, AlvisiaBlue.copy(alpha = .3f), RoundedCornerShape(9.dp))
                        .padding(horizontal = 10.dp, vertical = 8.dp),
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    Column(Modifier.weight(1f)) {
                        Text(displayName, color = AlvisiaSilver, fontSize = 11.sp, fontWeight = FontWeight.SemiBold)
                        Text(uriString.take(72), color = AlvisiaSilver.copy(alpha = .42f), fontSize = 8.sp, maxLines = 1)
                    }
                    Text("USE", color = AlvisiaCyan, fontSize = 10.sp, fontWeight = FontWeight.Bold,
                        modifier = Modifier.clickable { onUseRecent(Uri.parse(uriString)) }.padding(6.dp))
                    Spacer(Modifier.width(4.dp))
                    Text("×", color = Color(0xFFFFC66D), fontSize = 17.sp,
                        modifier = Modifier.clickable { UXStore.removeRecent(ctx, uriString); refresh() }.padding(4.dp))
                }
            }
            if (recent.isEmpty()) item { Text("No recent files yet. Select a file in any enabled tool to add it here.", color = AlvisiaSilver.copy(alpha = .5f), fontSize = 10.sp) }
        }

        Spacer(Modifier.height(10.dp))
        Text("FAVORITES · ${favoriteTools.size}", color = AlvisiaCyan, fontSize = 11.sp, fontWeight = FontWeight.Bold)
        Spacer(Modifier.height(5.dp))
        LazyColumn(Modifier.fillMaxWidth().weight(1f), verticalArrangement = Arrangement.spacedBy(5.dp)) {
            items(favoriteTools, key = { it.second.id }) { (moduleId, sub) ->
                Row(
                    Modifier.fillMaxWidth().clip(RoundedCornerShape(9.dp))
                        .background(Color(0xFF0C1622))
                        .border(1.dp, AlvisiaBlue.copy(alpha = .3f), RoundedCornerShape(9.dp))
                        .padding(horizontal = 10.dp, vertical = 8.dp),
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    Column(Modifier.weight(1f)) {
                        Text(sub.title, color = AlvisiaSilver, fontSize = 11.sp, fontWeight = FontWeight.SemiBold)
                        Text(SubMenus.title(moduleId), color = AlvisiaSilver.copy(alpha = .48f), fontSize = 8.sp)
                    }
                    Text(if (sub.enabled) "OPEN" else "PENDING",
                        color = if (sub.enabled) AlvisiaCyan else Color(0xFFFFC66D),
                        fontSize = 9.sp, fontWeight = FontWeight.Bold,
                        modifier = Modifier.clickable(enabled = sub.enabled) { onOpenFavorite(moduleId, sub) }.padding(6.dp))
                    Spacer(Modifier.width(4.dp))
                    Text("★", color = Color(0xFFFFD700), fontSize = 14.sp,
                        modifier = Modifier.clickable { UXStore.toggleFavorite(ctx, sub.id); refresh() }.padding(4.dp))
                }
            }
            if (favoriteTools.isEmpty()) item { Text("Star a submenu to pin it here.", color = AlvisiaSilver.copy(alpha = .5f), fontSize = 10.sp) }
        }
    }
}
