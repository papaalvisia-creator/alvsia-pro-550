package com.alvsia.pro.ui.profile

import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalUriHandler
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.alvsia.pro.BuildConfig
import com.alvsia.pro.ui.theme.*

private data class ModuleChip(val icon: String, val name: String)

@Composable
fun ProfileScreen(product: String, expiry: String, hwidShort: String, toolCount: Int, onBack: () -> Unit) {
    val uri = LocalUriHandler.current
    val accent = AlvisiaCyan
    val muted = AlvisiaSilver.copy(alpha = 0.52f)
    val modules = listOf(
        ModuleChip("📦","PAK Unpack"), ModuleChip("🔧","PAK Rebuild"), ModuleChip("🗜","PAK Compact"),
        ModuleChip("💾","OBB Tools"), ModuleChip("🌙","SMART LUA"), ModuleChip("🔍","File Scan"),
        ModuleChip("🗑","Workspace"), ModuleChip("📄","Export Report"), ModuleChip("🎨","Rebrand"),
        ModuleChip("🔬","SO Analyzer"), ModuleChip("🎯","Frida Tracer"), ModuleChip("🔑","XOR Suite"),
        ModuleChip("🔓","Decrypt Engine"), ModuleChip("📂","PAK Deep"), ModuleChip("🔤","String Recover"),
        ModuleChip("💉","Lua Inject"), ModuleChip("🛡","Anti-RE Audit"), ModuleChip("🔐","Lua Protector"),
        ModuleChip("⚙","ALVSIA PRIVATE TOOL")
    )
    Column(Modifier.fillMaxSize()
        .background(Brush.verticalGradient(listOf(Color(0xFF101D30), AlvisiaDeep, Color(0xFF07191D))))
        .verticalScroll(rememberScrollState())
        .padding(horizontal=16.dp, vertical=24.dp), horizontalAlignment=Alignment.CenterHorizontally) {
        Box(Modifier.size(58.dp).clip(CircleShape)
            .background(Brush.radialGradient(listOf(accent.copy(alpha=.28f), Color.Transparent)))
            .border(1.dp, accent.copy(alpha=.65f), CircleShape), contentAlignment=Alignment.Center) {
            Text("ALV", color=accent, fontSize=19.sp, fontWeight=FontWeight.Black)
        }
        Spacer(Modifier.height(8.dp))
        Text("ALVSIA PRO", color=accent, fontSize=21.sp, fontWeight=FontWeight.Black, letterSpacing=3.sp)
        Text("SECURE TOOL SYSTEM · ${BuildConfig.VERSION_NAME}", color=AlvisiaCyan.copy(alpha=.8f), fontSize=10.sp, letterSpacing=1.2.sp)
        Spacer(Modifier.height(15.dp))
        Row(Modifier.fillMaxWidth(), horizontalArrangement=Arrangement.spacedBy(7.dp)) {
            _InfoTile("PLAN", product.ifBlank { "PREMIUM" }, Modifier.weight(1f))
            _InfoTile("EXPIRES", expiry.ifBlank { "—" }, Modifier.weight(1f))
            _InfoTile("MODULES", "19", Modifier.weight(1f))
        }
        Spacer(Modifier.height(10.dp))
        Row(Modifier.fillMaxWidth(), horizontalArrangement=Arrangement.spacedBy(8.dp)) {
            _ActionTile("♙", "OWNER", "@OriginalOnwerALV", Modifier.weight(1f), Color(0xFF263B4C)) {
                uri.openUri("https://t.me/OriginalOnwerALV")
            }
            _ActionTile("✦", "CREATOR", "ALVSIA_PRO", Modifier.weight(1f), Color(0xFF263F35)) { }
        }
        Spacer(Modifier.height(8.dp))
        _ActionTile("✈", "OFFICIAL CHANNEL", "@ALVSIA_PRO", Modifier.fillMaxWidth(), Color(0xFF263F35)) {
            uri.openUri("https://t.me/ALVSIA_PRO")
        }
        Spacer(Modifier.height(8.dp))
        Row(Modifier.fillMaxWidth().clip(RoundedCornerShape(10.dp))
            .background(Color.White.copy(alpha=.035f)).border(.5.dp, Color.White.copy(alpha=.08f), RoundedCornerShape(10.dp))
            .padding(11.dp), horizontalArrangement=Arrangement.SpaceBetween, verticalAlignment=Alignment.CenterVertically) {
            Column {
                Text("DEVICE ID", color=muted, fontSize=9.sp, letterSpacing=.7.sp)
                Text(hwidShort.take(12).ifBlank { "—" } + "…", color=AlvisiaSilver, fontSize=11.sp, fontWeight=FontWeight.SemiBold)
            }
            Text("SESSION GATE  ·  INTEGRITY", color=accent.copy(alpha=.85f), fontSize=8.sp, textAlign=TextAlign.End)
        }
        Spacer(Modifier.height(15.dp))
        Row(Modifier.fillMaxWidth(), verticalAlignment=Alignment.CenterVertically) {
            Text("TOOL MODULES", color=muted, fontSize=10.sp, letterSpacing=1.5.sp)
            Spacer(Modifier.weight(1f))
            Text("${modules.size} / 19 MODULES", color=AlvisiaCyan, fontSize=9.sp)
        }
        Spacer(Modifier.height(7.dp))
        modules.chunked(3).forEach { items ->
            Row(Modifier.fillMaxWidth(), horizontalArrangement=Arrangement.spacedBy(7.dp)) {
                items.forEach { item ->
                    Column(Modifier.weight(1f).padding(bottom=7.dp).clip(RoundedCornerShape(9.dp))
                        .background(Color.White.copy(alpha=.035f))
                        .border(.5.dp, Color(0xFF879B69).copy(alpha=.20f), RoundedCornerShape(9.dp))
                        .padding(horizontal=4.dp, vertical=9.dp), horizontalAlignment=Alignment.CenterHorizontally) {
                        Text(item.icon, fontSize=16.sp)
                        Spacer(Modifier.height(4.dp))
                        Text(item.name, color=AlvisiaSilver, fontSize=9.sp, fontWeight=FontWeight.SemiBold,
                            textAlign=TextAlign.Center, maxLines=2, minLines=2, lineHeight=11.sp)
                    }
                }
                repeat(3-items.size) { Spacer(Modifier.weight(1f)) }
            }
        }
        Text("← BACK TO TOOL PANEL", color=muted, fontSize=10.sp, letterSpacing=.7.sp,
            modifier=Modifier.clip(RoundedCornerShape(8.dp)).clickable { onBack() }.padding(12.dp))
        Text("ALVSIA PRO © 2026", color=AlvisiaSilver.copy(alpha=.25f), fontSize=9.sp)
    }
}

@Composable
private fun _InfoTile(label: String, value: String, modifier: Modifier = Modifier) {
    Column(modifier.background(Color.White.copy(alpha=.035f), RoundedCornerShape(9.dp))
        .border(.5.dp, Color.White.copy(alpha=.08f), RoundedCornerShape(9.dp)).padding(7.dp),
        horizontalAlignment=Alignment.CenterHorizontally) {
        Text(label, color=AlvisiaSilver.copy(alpha=.42f), fontSize=9.sp)
        Spacer(Modifier.height(4.dp))
        Text(value, color=AlvisiaSilver, fontSize=10.sp, fontWeight=FontWeight.SemiBold, maxLines=1)
    }
}

@Composable
private fun _ActionTile(icon: String, label: String, value: String, modifier: Modifier, tint: Color, onClick: () -> Unit) {
    Row(modifier.clip(RoundedCornerShape(11.dp))
        .background(Brush.horizontalGradient(listOf(tint.copy(alpha=.95f), tint.copy(alpha=.58f))))
        .border(.7.dp, Color.White.copy(alpha=.12f), RoundedCornerShape(11.dp))
        .clickable(onClick=onClick).padding(horizontal=10.dp, vertical=12.dp),
        verticalAlignment=Alignment.CenterVertically, horizontalArrangement=Arrangement.spacedBy(7.dp)) {
        Text(icon, color=Color.White, fontSize=16.sp)
        Column(Modifier.weight(1f)) {
            Text(label, color=Color.White.copy(alpha=.7f), fontSize=8.sp, letterSpacing=.6.sp)
            Text(value, color=Color.White, fontSize=10.sp, fontWeight=FontWeight.Bold, maxLines=1)
        }
        Text("›", color=Color.White.copy(alpha=.7f), fontSize=18.sp)
    }
}
