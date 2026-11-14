package com.alvsia.pro.ui.loading

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.clickable
import androidx.compose.foundation.clip
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.rememberInfiniteTransition
import androidx.compose.ui.Alignment
import androidx.compose.ui.platform.LocalUriHandler
import androidx.compose.ui.draw.alpha
import androidx.compose.ui.draw.scale
import androidx.compose.ui.graphics.Shadow
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.alvsia.pro.ui.fx.NeonPulseBackground
import com.alvsia.pro.ui.theme.AlvisiaCyan
import com.alvsia.pro.ui.theme.AlvisiaSilver
import com.alvsia.pro.ui.theme.AlvisiaBlue

@Composable
fun LoadingScreen(
    subtitle: String = "Initializing Smart Core...",
    progress: Float = -1f
) {
    val uriHandler = LocalUriHandler.current
    val transition = rememberInfiniteTransition(label = "welcome")
    val pulse by transition.animateFloat(initialValue = 0.96f, targetValue = 1.04f, animationSpec = infiniteRepeatable(tween(850), RepeatMode.Reverse), label = "welcome-scale")
    val glow by transition.animateFloat(initialValue = 0.55f, targetValue = 1f, animationSpec = infiniteRepeatable(tween(700), RepeatMode.Reverse), label = "welcome-alpha")
    Box(Modifier.fillMaxSize()) {
        NeonPulseBackground(Modifier.fillMaxSize())
        Column(
            Modifier.align(Alignment.Center).padding(24.dp),
            horizontalAlignment = Alignment.CenterHorizontally
        ) {
            Text(
                "HALLO MUKA BOKEP",
                color = AlvisiaCyan,
                fontWeight = FontWeight.Black,
                fontSize = 23.sp,
                modifier = Modifier.scale(pulse).alpha(glow),
                style = TextStyle(shadow = Shadow(AlvisiaBlue, blurRadius = 18f))
            )
            Spacer(Modifier.height(5.dp))
            Text(
                "JANGAN LUPA NGELOCO SEBELUM BERAKTIFITAS",
                color = AlvisiaSilver,
                fontWeight = FontWeight.Bold,
                fontSize = 10.sp,
                letterSpacing = 0.8.sp,
                modifier = Modifier.alpha(glow)
            )
            Spacer(Modifier.height(12.dp))
            Text(subtitle, color = AlvisiaSilver, fontSize = 13.sp)
            Spacer(Modifier.height(10.dp))
            Text(
                "✈  @ALVISIACHANEL  ·  OFFICIAL CHANNEL",
                color = AlvisiaCyan.copy(alpha = 0.86f),
                fontWeight = FontWeight.Bold,
                fontSize = 9.sp,
                modifier = Modifier.clip(RoundedCornerShape(8.dp)).clickable {
                    androidx.compose.ui.platform.LocalUriHandler.current.openUri("https://t.me/ALVISIACHANEL")
                }.padding(horizontal = 10.dp, vertical = 6.dp)
            )
            Spacer(Modifier.height(20.dp))
            CircularProgressIndicator(color = AlvisiaCyan)
        }
    }
}
