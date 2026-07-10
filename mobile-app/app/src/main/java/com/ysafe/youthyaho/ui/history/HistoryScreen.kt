package com.ysafe.youthyaho.ui.history

import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.ysafe.youthyaho.ui.result.ClusterMembershipBars
import com.ysafe.youthyaho.ui.result.DomainIndexRadarChart
import kotlin.math.roundToInt

@Composable
fun HistoryScreen(
    viewModel: HistoryViewModel,
    onNextClick: () -> Unit,
    modifier: Modifier = Modifier,
) {
    val uiState by viewModel.uiState.collectAsStateWithLifecycle()

    Column(
        modifier = modifier
            .fillMaxSize()
            .verticalScroll(rememberScrollState())
            .padding(24.dp),
    ) {
        Text(text = "히스토리", style = MaterialTheme.typography.headlineMedium)

        when {
            uiState.isLoading -> {
                CircularProgressIndicator(modifier = Modifier.padding(top = 32.dp))
            }
            uiState.errorMessage != null -> {
                Text(
                    text = uiState.errorMessage ?: "",
                    color = MaterialTheme.colorScheme.error,
                    style = MaterialTheme.typography.bodyMedium,
                    modifier = Modifier.padding(top = 16.dp),
                )
                Button(onClick = viewModel::retry, modifier = Modifier.padding(top = 16.dp)) {
                    Text("다시 시도")
                }
            }
            else -> {
                uiState.note?.let { note ->
                    Card(modifier = Modifier.fillMaxWidth().padding(top = 16.dp, bottom = 16.dp)) {
                        Text(
                            text = note,
                            style = MaterialTheme.typography.bodySmall,
                            modifier = Modifier.padding(16.dp),
                        )
                    }
                }

                uiState.createdAt?.let { createdAt ->
                    Text(
                        text = "진단 시각: $createdAt",
                        style = MaterialTheme.typography.bodyMedium,
                        modifier = Modifier.padding(bottom = 16.dp),
                    )
                }

                uiState.riskProbability?.let { risk ->
                    Text(
                        text = "경제위험 확률 약 ${(risk * 100).roundToInt()}%",
                        style = MaterialTheme.typography.titleLarge,
                        modifier = Modifier.padding(bottom = 16.dp),
                    )
                }

                if (uiState.domainIndices.isNotEmpty()) {
                    Text(text = "영역별 지수", style = MaterialTheme.typography.labelLarge)
                    DomainIndexRadarChart(
                        domainIndices = uiState.domainIndices,
                        modifier = Modifier.fillMaxWidth().padding(top = 8.dp, bottom = 24.dp),
                    )
                }

                if (uiState.clusterMembership.isNotEmpty()) {
                    Text(text = "가장 가까운 유형", style = MaterialTheme.typography.labelLarge)
                    ClusterMembershipBars(
                        clusterMembership = uiState.clusterMembership,
                        modifier = Modifier.fillMaxWidth().padding(top = 8.dp, bottom = 24.dp),
                    )
                }

                Button(onClick = onNextClick, modifier = Modifier.fillMaxWidth().padding(top = 8.dp)) {
                    Text("설정으로")
                }
            }
        }
    }
}
