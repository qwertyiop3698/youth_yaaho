package com.ysafe.youthyaho.ui.recommendation

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
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
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.ysafe.youthyaho.data.api.dto.RecommendationItemDto
import kotlin.math.roundToInt

@Composable
fun RecommendationScreen(
    viewModel: RecommendationViewModel,
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
        Text(text = "정책 추천", style = MaterialTheme.typography.headlineMedium)
        Text(
            text = "이번 달 먼저 신청하면 좋은 정책이에요.",
            style = MaterialTheme.typography.bodyMedium,
            modifier = Modifier.padding(top = 4.dp, bottom = 24.dp),
        )

        when {
            uiState.isLoading -> {
                CircularProgressIndicator(modifier = Modifier.padding(top = 32.dp))
            }
            uiState.errorMessage != null -> {
                Text(
                    text = uiState.errorMessage ?: "",
                    color = MaterialTheme.colorScheme.error,
                    style = MaterialTheme.typography.bodyMedium,
                )
                Button(onClick = viewModel::retry, modifier = Modifier.padding(top = 16.dp)) {
                    Text("다시 시도")
                }
            }
            uiState.topRecommendations.isEmpty() -> {
                Text(
                    text = "지금 조건에 딱 맞는 정책은 없지만, 상황이 바뀌면 다시 확인해볼 수 있어요.",
                    style = MaterialTheme.typography.bodyMedium,
                )
            }
            else -> {
                uiState.topRecommendations.forEachIndexed { index, item ->
                    PolicyCard(
                        rank = index + 1,
                        item = item,
                        modifier = Modifier.fillMaxWidth().padding(bottom = 12.dp),
                    )
                }
            }
        }

        Button(onClick = onNextClick, modifier = Modifier.fillMaxWidth().padding(top = 16.dp)) {
            Text("왜 추천했는지 보기")
        }
    }
}

private fun confidenceLabel(confidence: String): String = when (confidence) {
    "verified" -> "확인됨"
    "assumed_unresolved_codebook" -> "잠정 (코드북 확정 전)"
    else -> confidence
}

@Composable
private fun PolicyCard(rank: Int, item: RecommendationItemDto, modifier: Modifier = Modifier) {
    Card(modifier = modifier) {
        Column(modifier = Modifier.padding(16.dp)) {
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically,
            ) {
                Text(text = "$rank. ${item.policy}", style = MaterialTheme.typography.titleLarge)
            }

            Text(
                text = if (item.eligible) "신청 가능" else "자격 조건 확인 필요",
                style = MaterialTheme.typography.bodyMedium,
                color = if (item.eligible) MaterialTheme.colorScheme.primary else MaterialTheme.colorScheme.error,
                modifier = Modifier.padding(top = 8.dp),
            )
            Text(
                text = "자격조건 근거: ${confidenceLabel(item.eligibility_confidence)}",
                style = MaterialTheme.typography.bodyMedium,
            )
            Text(
                text = "예상 위험 감소: ${(item.expected_effect * 100).roundToInt()}%p",
                style = MaterialTheme.typography.bodyMedium,
                modifier = Modifier.padding(top = 4.dp),
            )
        }
    }
}
