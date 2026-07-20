package com.ysafe.youthyaho.ui.result

import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Button
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.ysafe.youthyaho.ui.common.YouthYahoScaffold
import kotlin.math.roundToInt

@Composable
fun ResultScreen(
    viewModel: ResultViewModel,
    onNextClick: () -> Unit,
    onRetryDiagnose: () -> Unit,
    modifier: Modifier = Modifier,
) {
    val uiState by viewModel.uiState.collectAsStateWithLifecycle()

    YouthYahoScaffold(title = "진단 결과", modifier = modifier) { paddingValues ->
        if (uiState.notFound) {
            Column(modifier = Modifier.fillMaxSize().padding(paddingValues).padding(24.dp)) {
                Text(text = "진단 결과를 찾을 수 없어요.", style = MaterialTheme.typography.titleLarge)
                Text(
                    text = "다시 처음부터 진단을 시작해주세요.",
                    style = MaterialTheme.typography.bodyMedium,
                    modifier = Modifier.padding(top = 8.dp),
                )
                Button(onClick = onRetryDiagnose, modifier = Modifier.fillMaxWidth().padding(top = 16.dp)) {
                    Text("다시 진단하기")
                }
            }
            return@YouthYahoScaffold
        }

        val result = uiState.result ?: return@YouthYahoScaffold

        Column(
            modifier = Modifier
                .fillMaxSize()
                .verticalScroll(rememberScrollState())
                .padding(paddingValues)
                .padding(24.dp),
        ) {
            Text(
                text = result.approximation_notice,
                style = MaterialTheme.typography.bodyMedium,
                modifier = Modifier.padding(bottom = 16.dp),
            )

            result.risk_probability?.let { risk ->
                Text(
                    text = "프록시 위험점수 ${(risk * 100).roundToInt()}점",
                    style = MaterialTheme.typography.titleLarge,
                    modifier = Modifier.padding(bottom = 16.dp),
                )
            }

            if (result.domain_indices.isNotEmpty()) {
                Text(text = "영역별 지수", style = MaterialTheme.typography.labelLarge)
                DomainIndexRadarChart(
                    domainIndices = result.domain_indices,
                    modifier = Modifier.fillMaxWidth().padding(top = 8.dp, bottom = 24.dp),
                )
            }

            if (result.cluster_membership.isNotEmpty()) {
                Text(text = "가장 가까운 유형", style = MaterialTheme.typography.labelLarge)
                ClusterMembershipBars(
                    clusterMembership = result.cluster_membership,
                    modifier = Modifier.fillMaxWidth().padding(top = 8.dp, bottom = 24.dp),
                )
            }

            if (result.domain_indices.isEmpty() && result.cluster_membership.isEmpty()) {
                Text(
                    text = "표본이 부족해 아직 상세 지표를 계산할 수 없어요.",
                    style = MaterialTheme.typography.bodyMedium,
                    modifier = Modifier.padding(bottom = 24.dp),
                )
            }

            Button(onClick = onNextClick, modifier = Modifier.fillMaxWidth().padding(top = 8.dp)) {
                Text("정책 추천 보기")
            }
        }
    }
}
