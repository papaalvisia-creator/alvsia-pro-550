package com.alvsia.pro.ui.tool

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
import androidx.compose.foundation.layout.statusBarsPadding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.itemsIndexed
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.remember
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.alvsia.pro.tool.SubTool
import com.alvsia.pro.tool.UXStore
import com.alvsia.pro.ui.theme.AlvisiaBlue
import com.alvsia.pro.ui.theme.AlvisiaCyan
import com.alvsia.pro.ui.theme.AlvisiaDeep
import com.alvsia.pro.ui.theme.AlvisiaSilver

@Composable
fun SubMenuScreen(
    moduleTitle: String,
    moduleId: Int,
    items: List<SubTool>,
    onBack: () -> Unit,
    onSelect: (SubTool) -> Unit
) {
    val ctx = LocalContext.current
    val favorites = remember { UXStore.getFavoritesSet(ctx) }

    // Sort: favorites first, then original order
    val sortedItems = remember(items, favorites) {
        items.sortedByDescending { it.id in favorites }
    }

    Column(
        Modifier
            .fillMaxSize()
            .background(AlvisiaDeep)
            .statusBarsPadding()
            .padding(horizontal = 12.dp, vertical = 8.dp)
    ) {
        Row(verticalAlignment = Alignment.CenterVertically) {
            TextButton(onClick = onBack) {
                Text("← BACK", color = AlvisiaCyan, fontWeight = FontWeight.Bold, fontSize = 13.sp)
            }
            Spacer(Modifier.weight(1f))
            Text(
                "%02d".format(moduleId),
                color = AlvisiaCyan,
                fontFamily = FontFamily.Monospace,
                fontWeight = FontWeight.Bold
            )
        }
        Text(moduleTitle, color = Color.White, fontWeight = FontWeight.Bold, fontSize = 18.sp)
        Text("Select Smart Engine · ★ = favorite",
            color = AlvisiaSilver.copy(alpha = 0.55f), fontSize = 12.sp)
        Spacer(Modifier.height(12.dp))
        LazyColumn(verticalArrangement = Arrangement.spacedBy(8.dp)) {
            itemsIndexed(sortedItems) { index, item ->
                val isFav = item.id in favorites
                Row(
                    Modifier
                        .fillMaxWidth()
                        .clip(RoundedCornerShape(12.dp))
                        .background(
                            if (isFav) Color(0xFF0D1B2A) else Color(0xFF0C1622)
                        )
                        .border(
                            1.dp,
                            if (isFav) AlvisiaCyan.copy(alpha = 0.5f)
                            else AlvisiaBlue.copy(alpha = 0.35f),
                            RoundedCornerShape(12.dp)
                        )
                        .clickable { onSelect(item) }
                        .padding(14.dp),
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    // Favorite star — tap to toggle
                    Text(
                        text = if (isFav) "★" else "☆",
                        color = if (isFav) Color(0xFFFFD700) else AlvisiaSilver.copy(alpha = 0.3f),
                        fontSize = 16.sp,
                        modifier = Modifier.clickable {
                            UXStore.toggleFavorite(ctx, item.id)
                        }
                    )
                    Spacer(Modifier.width(8.dp))
                    Column(Modifier.weight(1f)) {
                        Text(item.title,
                            color = if (isFav) Color.White else AlvisiaSilver,
                            fontWeight = FontWeight.SemiBold, fontSize = 14.sp)
                        Text(item.desc, color = AlvisiaSilver.copy(alpha = 0.55f), fontSize = 11.sp)
                        Text(item.guide, color = AlvisiaSilver.copy(alpha = 0.4f), fontSize = 9.sp, maxLines = 2)
                    }
                    Text("→", color = AlvisiaCyan, fontSize = 18.sp)
                }
            }
        }
    }
}
