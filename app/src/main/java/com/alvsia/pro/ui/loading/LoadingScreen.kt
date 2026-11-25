package com.alvsia.pro.ui.loading

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.alvsia.pro.ui.fx.NeonPulseBackground
import com.alvsia.pro.ui.theme.AlvisiaCyan
import com.alvsia.pro.ui.theme.AlvisiaSilver

@Composable
fun LoadingScreen(
    subtitle: String = "Preparing Smart Engine...",
    progress: Float = -1f
) {
    Box(Modifier.fillMaxSize()) {
        NeonPulseBackground(Modifier.fillMaxSize())
        Column(
            Modifier.align(Alignment.Center).padding(24.dp),
            horizontalAlignment = Alignment.CenterHorizontally
        ) {
            Text(
                "ALVSIA SMART PREMIUM",
                color = AlvisiaCyan,
                fontWeight = FontWeight.Black,
                fontSize = 22.sp
            )
            Spacer(Modifier.height(12.dp))
            Text("HALLO MUKA BOKEP", color = AlvisiaCyan, fontWeight = FontWeight.Black, fontSize = 20.sp)
            Spacer(Modifier.height(4.dp))
            Text("JANGAN LUPA NGELOCO SEBELUM BERAKTIVITAS", color = AlvisiaSilver, fontWeight = FontWeight.Bold, fontSize = 12.sp)
            Spacer(Modifier.height(10.dp))
            Text(subtitle, color = AlvisiaSilver.copy(alpha = 0.72f), fontSize = 10.sp)
            Spacer(Modifier.height(20.dp))
            CircularProgressIndicator(color = AlvisiaCyan)
        }
    }
}
