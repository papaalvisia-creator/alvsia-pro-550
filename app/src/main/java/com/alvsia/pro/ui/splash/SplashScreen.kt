package com.alvsia.pro.ui.splash

import android.media.MediaPlayer
import androidx.compose.animation.core.Animatable
import androidx.compose.animation.core.LinearEasing
import androidx.compose.animation.core.RepeatMode
import androidx.compose.animation.core.animateFloat
import androidx.compose.animation.core.infiniteRepeatable
import androidx.compose.animation.core.rememberInfiniteTransition
import androidx.compose.animation.core.tween
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.Image
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableFloatStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.runtime.withFrameNanos
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.alpha
import androidx.compose.ui.draw.clip
import androidx.compose.ui.draw.scale
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.Shadow
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.alvsia.pro.R
import com.alvsia.pro.ui.theme.AlvisiaBlue
import com.alvsia.pro.ui.theme.AlvisiaCyan
import com.alvsia.pro.ui.theme.AlvisiaDeep
import com.alvsia.pro.ui.theme.AlvisiaRed
import com.alvsia.pro.ui.theme.AlvisiaSilver
import kotlinx.coroutines.delay
import kotlin.math.sin
import kotlin.random.Random

@Composable
fun SplashScreen(onFinished: () -> Unit) {
    val context = LocalContext.current
    val logoAlpha = remember { Animatable(0f) }
    val logoScale = remember { Animatable(0.72f) }
    val textAlpha = remember { Animatable(0f) }
    var status by remember { mutableStateOf("INITIALIZING SMART CORE...") }
    var tick by remember { mutableFloatStateOf(0f) }

    val cols = remember {
        List(28) { i ->
            MatrixCol(
                xRatio = (i + 0.5f) / 28f,
                speed = 40f + Random.nextFloat() * 90f,
                offset = Random.nextFloat() * 800f,
                chars = (0 until 18).map {
                    "0123456789ABCDEF$#@%*+-"[Random.nextInt(22)]
                }.joinToString("")
            )
        }
    }

    DisposableEffect(Unit) {
        var mp: MediaPlayer? = null
        try {
            mp = MediaPlayer.create(context, R.raw.megatron_welcome)
            mp?.setVolume(1f, 1f)
            mp?.start()
        } catch (_: Exception) {
        }
        onDispose {
            try {
                mp?.stop()
                mp?.release()
            } catch (_: Exception) {
            }
        }
    }

    LaunchedEffect(Unit) {
        val t0 = System.nanoTime()
        // Frame loop: runs only while this composable is active
        try {
            while (true) {
                withFrameNanos { now ->
                    tick = ((now - t0) / 1_000_000_000f)
                }
            }
        } catch (_: kotlinx.coroutines.CancellationException) {
            // composable left; loop cancelled cleanly
        }
    }

    LaunchedEffect(Unit) {
        // Hard upper bound on splash duration so background init stalls cannot
        // ANR the launcher. Even if the LaunchedEffect above somehow keeps
        // running, this withTimeout will fire and advance to login.
        kotlinx.coroutines.withTimeout(8_500L) {
            logoAlpha.animateTo(1f, tween(900))
            logoScale.animateTo(1f, tween(1100))
            delay(400)
            textAlpha.animateTo(1f, tween(700))
            val steps = listOf(
                "ESTABLISHING UPLINK...",
                "HANDSHAKE TLS 1.3 ... OK",
                "VERIFYING INTEGRITY ... OK",
                "LOADING SMART ENGINES ...",
                "SMART PREMIUM ONLINE"
            )
            for (s in steps) {
                status = s
                delay(520)
            }
            delay(600)
        }
        onFinished()
    }

    Box(
        Modifier
            .fillMaxSize()
            .background(AlvisiaDeep)
    ) {
        // Matrix rain layer
        Canvas(Modifier.fillMaxSize()) {
            val w = size.width
            val h = size.height
            drawRect(Color(0xFF02050C))
            val colW = w / cols.size
            cols.forEachIndexed { idx, col ->
                val x = col.xRatio * w
                val yBase = ((tick * col.speed + col.offset) % (h + 200f)) - 100f
                for (j in 0 until 14) {
                    val y = yBase - j * 18f
                    if (y < -20f || y > h + 20f) continue
                    val a = (1f - j / 14f) * 0.55f
                    val c = when {
                        j == 0 -> AlvisiaCyan.copy(alpha = 0.95f)
                        j < 3 -> AlvisiaBlue.copy(alpha = a)
                        idx % 9 == 0 && j < 6 -> AlvisiaRed.copy(alpha = a * 0.5f)
                        else -> Color(0xFF00FF88).copy(alpha = a * 0.45f)
                    }
                    // small rect as "glyph" (no heavy text draw)
                    drawRect(
                        color = c,
                        topLeft = Offset(x - 2f, y),
                        size = androidx.compose.ui.geometry.Size(3f + (j % 2), 10f)
                    )
                }
            }
            // glass vignette
            drawRect(
                brush = Brush.radialGradient(
                    listOf(Color.Transparent, Color(0xAA02050C)),
                    center = Offset(w / 2f, h * 0.4f),
                    radius = w * 0.85f
                )
            )
        }

        Column(
            Modifier
                .align(Alignment.Center)
                .alpha(logoAlpha.value),
            horizontalAlignment = Alignment.CenterHorizontally
        ) {
            Box(
                Modifier
                    .size(148.dp)
                    .scale(logoScale.value)
                    .clip(CircleShape)
                    .background(
                        Brush.radialGradient(
                            listOf(
                                AlvisiaCyan.copy(alpha = 0.25f),
                                Color(0x4400A3FF),
                                Color.Transparent
                            )
                        )
                    )
                    .border(
                        1.5.dp,
                        Brush.sweepGradient(
                            listOf(AlvisiaCyan, AlvisiaBlue, AlvisiaRed, AlvisiaCyan)
                        ),
                        CircleShape
                    ),
                contentAlignment = Alignment.Center
            ) {
                Image(
                    painter = painterResource(R.drawable.logo_alvisia),
                    contentDescription = null,
                    contentScale = ContentScale.Crop,
                    modifier = Modifier
                        .size(120.dp)
                        .clip(CircleShape)
                )
            }
            Spacer(Modifier.height(22.dp))
            Text(
                "ALVSIA SMART PREMIUM",
                style = TextStyle(
                    color = AlvisiaSilver,
                    fontWeight = FontWeight.Black,
                    fontSize = 18.sp,
                    shadow = Shadow(AlvisiaCyan, Offset(0f, 0f), 12f)
                ),
                modifier = Modifier.alpha(textAlpha.value)
            )
            Spacer(Modifier.height(6.dp))
            Text(
                "SMART CORE  ·  7-LAYER SECURITY",
                color = AlvisiaBlue.copy(alpha = 0.85f),
                fontSize = 11.sp,
                fontFamily = FontFamily.Monospace,
                modifier = Modifier.alpha(textAlpha.value)
            )
        }

        // bottom status glass
        Box(
            Modifier
                .align(Alignment.BottomCenter)
                .padding(bottom = 48.dp, start = 24.dp, end = 24.dp)
                .clip(RoundedCornerShape(12.dp))
                .background(Color(0x6608121C))
                .border(1.dp, AlvisiaCyan.copy(alpha = 0.25f), RoundedCornerShape(12.dp))
                .padding(horizontal = 16.dp, vertical = 10.dp)
                .alpha(textAlpha.value)
        ) {
            Text(
                status,
                color = AlvisiaCyan,
                fontFamily = FontFamily.Monospace,
                fontSize = 11.sp
            )
        }
    }
}

private data class MatrixCol(
    val xRatio: Float,
    val speed: Float,
    val offset: Float,
    val chars: String
)
