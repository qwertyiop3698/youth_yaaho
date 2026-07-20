package com.ysafe.youthyaho.ui.history

import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.ysafe.youthyaho.ui.common.ErrorContent
import com.ysafe.youthyaho.ui.common.LoadingIndicator
import com.ysafe.youthyaho.ui.common.YouthYahoScaffold
import com.ysafe.youthyaho.ui.result.ClusterMembershipBars
import com.ysafe.youthyaho.ui.result.DomainIndexRadarChart
import kotlin.math.roundToInt

@Composable
fun HistoryScreen(
    viewModel: HistoryViewModel,
    onBack: () -> Unit,
    onNextClick: () -> Unit,
    modifier: Modifier = Modifier,
) {
    val uiState by viewModel.uiState.collectAsStateWithLifecycle()

    YouthYahoScaffold(title = "히스토리", onBack = onBack, modifier = modifier) { paddingValues ->
    Column(
        modifier = Modifier
            .fillMaxSize()
            .verticalScroll(rememberScrollState())
            .padding(paddingValues)
            .padding(24.dp),
    ) {
        when {
            uiState.isLoading -> {
                LoadingIndicator()
            }
            uiState.errorMessage != null -> {
                ErrorContent(
                    message = uiState.errorMessage ?: "",
                    onRetry = viewModel::retry,
                    modifier = Modifier.padding(top = 16.dp),
                )
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
                        text = "프록시 위험점수 ${(risk * 100).roundToInt()}점",
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
}
