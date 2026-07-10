package com.ysafe.youthyaho.ui.result

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import kotlin.math.roundToInt

/** 위험유형 멤버십(%) 시각화 - 클러스터별 소속확률을 내림차순 막대로 보여준다. */
@Composable
fun ClusterMembershipBars(clusterMembership: Map<String, Float>, modifier: Modifier = Modifier) {
    val sorted = clusterMembership.entries.sortedByDescending { it.value }

    Column(modifier = modifier) {
        sorted.forEach { (label, value) ->
            Column(modifier = Modifier.fillMaxWidth().padding(vertical = 6.dp)) {
                Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
                    Text(text = label, style = MaterialTheme.typography.bodyMedium)
                    Text(text = "${(value * 100).roundToInt()}%", style = MaterialTheme.typography.bodyMedium)
                }
                LinearProgressIndicator(
                    progress = { value.coerceIn(0f, 1f) },
                    modifier = Modifier.fillMaxWidth().height(8.dp).padding(top = 4.dp),
                )
            }
        }
    }
}
