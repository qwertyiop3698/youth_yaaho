package com.ysafe.youthyaho.ui.recommendation

import android.content.Intent
import android.net.Uri
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.itemsIndexed
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.LocalContentColor
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.CompositionLocalProvider
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.style.TextDecoration
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.ysafe.youthyaho.data.api.dto.OtherPolicyItemDto
import com.ysafe.youthyaho.data.api.dto.RecommendationItemDto
import kotlin.math.roundToInt

private fun safeHttpsUri(url: String?): Uri? = url
    ?.let(Uri::parse)
    ?.takeIf { it.scheme == "https" && !it.host.isNullOrBlank() }

private fun openSafeWebLink(context: android.content.Context, uri: Uri) {
    runCatching { context.startActivity(Intent(Intent.ACTION_VIEW, uri)) }
}

@Composable
fun RecommendationScreen(
    viewModel: RecommendationViewModel,
    onNextClick: () -> Unit,
    onPolicyDetail: (RecommendationItemDto) -> Unit,
    onPolicyDemand: (String) -> Unit,
    modifier: Modifier = Modifier,
) {
    val uiState by viewModel.uiState.collectAsStateWithLifecycle()

    CompositionLocalProvider(LocalContentColor provides Color.Black) {
        LazyColumn(
            modifier = modifier.fillMaxSize(),
            contentPadding = PaddingValues(24.dp),
            verticalArrangement = Arrangement.spacedBy(12.dp),
        ) {
        item {
            Column(modifier = Modifier.padding(bottom = 12.dp)) {
                Text(text = "정책 추천", style = MaterialTheme.typography.headlineMedium)
                Text(
                    text = "현재 입력정보와 정책 영역의 실험적 적합도를 비교한 결과예요. 최종 자격은 공고에서 확인해주세요.",
                    style = MaterialTheme.typography.bodyMedium,
                    modifier = Modifier.padding(top = 4.dp),
                )
            }
        }

        when {
            uiState.isLoading -> {
                item {
                    CircularProgressIndicator(modifier = Modifier.padding(top = 20.dp))
                }
            }
            uiState.errorMessage != null -> {
                item {
                    Column {
                        Text(
                            text = uiState.errorMessage ?: "",
                            color = MaterialTheme.colorScheme.error,
                            style = MaterialTheme.typography.bodyMedium,
                        )
                        Button(onClick = viewModel::retry, modifier = Modifier.padding(top = 16.dp)) {
                            Text("다시 시도")
                        }
                    }
                }
            }
            uiState.topRecommendations.isEmpty() -> {
                item {
                    Text(
                        text = "지금 조건에 딱 맞는 정책은 없지만, 상황이 바뀌면 다시 확인해볼 수 있어요.",
                        style = MaterialTheme.typography.bodyMedium,
                    )
                }
            }
            else -> {
                item {
                    Card(
                        modifier = Modifier.fillMaxWidth().padding(bottom = 4.dp),
                        colors = recommendationCardColors(),
                    ) {
                        Text(
                            text = "적합도는 실제 정책 효과나 위험 감소율이 아니라, 프록시 위험점수와 정책 대상 영역을 조합한 실험값입니다.",
                            style = MaterialTheme.typography.bodySmall,
                            modifier = Modifier.padding(12.dp),
                        )
                    }
                }
                itemsIndexed(
                    items = uiState.topRecommendations,
                    key = { index, item -> "$index:${item.policy}" },
                ) { index, item ->
                    PolicyCard(
                        rank = index + 1,
                        item = item,
                        onPolicyDetail = { onPolicyDetail(item) },
                        modifier = Modifier.fillMaxWidth(),
                    )
                }
            }
        }

        if (uiState.otherPolicies.isNotEmpty()) {
            item {
                OtherPoliciesSection(
                    policies = uiState.otherPolicies,
                    modifier = Modifier.padding(top = 12.dp),
                )
            }
        }

        uiState.demandTriggerReason?.let { reason ->
            item {
                Card(
                    modifier = Modifier.fillMaxWidth().padding(top = 8.dp),
                    colors = recommendationCardColors(),
                ) {
                    Column(modifier = Modifier.padding(16.dp)) {
                        Text(
                            text = if (uiState.topRecommendations.isEmpty()) "지금 필요한 지원을 알려주세요" else "찾으시는 지원과 다른가요?",
                            style = MaterialTheme.typography.titleMedium,
                        )
                        Text(
                            text = "필요한 지원을 짧게 알려주시면 익명 정책 개선 자료로 집계됩니다.",
                            style = MaterialTheme.typography.bodyMedium,
                            modifier = Modifier.padding(top = 4.dp),
                        )
                        uiState.demandRewardAmount?.let { Text("완료 시 동백전 Mock 리워드 ${it}원", modifier = Modifier.padding(top = 8.dp)) }
                        Button(onClick = { onPolicyDemand(reason) }, modifier = Modifier.padding(top = 12.dp)) { Text("필요한 지원 알려주기") }
                    }
                }
            }
        }
        uiState.demandCooldownUntil?.let {
            item {
                Text("동일한 수요는 재참여 제한 기간 이후 다시 작성할 수 있어요.", style = MaterialTheme.typography.bodySmall)
            }
        }

        item {
            Button(onClick = onNextClick, modifier = Modifier.fillMaxWidth().padding(top = 4.dp)) {
                Text("왜 추천했는지 보기")
            }
        }
    }
    }
}

@Composable
private fun recommendationCardColors() = CardDefaults.cardColors(
    containerColor = MaterialTheme.colorScheme.primary.copy(alpha = 0.12f),
    contentColor = Color.Black,
)

private fun confidenceLabel(confidence: String): String = when (confidence) {
    "verified" -> "확인됨"
    "assumed_unresolved_codebook" -> "잠정 (코드북 확정 전)"
    else -> confidence
}

@Composable
private fun PolicyCard(
    rank: Int,
    item: RecommendationItemDto,
    onPolicyDetail: () -> Unit,
    modifier: Modifier = Modifier,
) {
    Card(
        modifier = modifier,
        colors = recommendationCardColors(),
    ) {
        Column(modifier = Modifier.padding(16.dp)) {
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically,
            ) {
                Text(text = "$rank. ${item.policy}", style = MaterialTheme.typography.titleLarge)
            }

            Text(
                text = if (item.eligible && item.eligibility_confidence == "verified") {
                    "확인된 입력 기준 자격 충족"
                } else {
                    "공고에서 자격 조건 확인 필요"
                },
                style = MaterialTheme.typography.bodyMedium,
                color = Color.Black,
                modifier = Modifier.padding(top = 8.dp),
            )
            Text(
                text = "자격조건 근거: ${confidenceLabel(item.eligibility_confidence)}",
                style = MaterialTheme.typography.bodyMedium,
            )
            Text(
                text = "실험적 정책 적합도: ${(item.expected_effect * 100).roundToInt()}점",
                style = MaterialTheme.typography.bodyMedium,
                modifier = Modifier.padding(top = 4.dp),
            )
            TextButton(onClick = onPolicyDetail, modifier = Modifier.padding(top = 4.dp)) {
                Text("정책 상세 및 이용 기록")
            }

            val uri = safeHttpsUri(item.url)
            if (uri != null) {
                val context = LocalContext.current
                Text(
                    text = "신청하러 가기 ↗",
                    color = MaterialTheme.colorScheme.primary,
                    style = MaterialTheme.typography.bodyMedium,
                    textDecoration = TextDecoration.Underline,
                    modifier = Modifier
                        .padding(top = 12.dp, bottom = 8.dp)
                        .clickable(onClickLabel = "신청 페이지 열기") {
                            openSafeWebLink(context, uri)
                        },
                )
            }
        }
    }
}

// 6개 정밀매칭 정책(위험감소 %) 밖에서 온통청년 API로 거주지역(전국/부산시/구
// 단위)에 실시간 매칭된 정책들이다 - Δrisk 순위 정보가 없어 카테고리별 목록으로만
// 보여준다(docs/05 target_domains/effectiveness_prior 미보유).
@Composable
private fun OtherPoliciesSection(policies: List<OtherPolicyItemDto>, modifier: Modifier = Modifier) {
    Column(modifier = modifier) {
        Text(text = "그 외 지역 기준 탐색 정책", style = MaterialTheme.typography.titleLarge)
        Text(
            text = "거주 지역과 연령대 범위로 검색한 후보이며, 신청 자격을 보장하지 않아요. 총 ${policies.size}건",
            style = MaterialTheme.typography.bodyMedium,
            modifier = Modifier.padding(top = 4.dp, bottom = 16.dp),
        )

        policies.groupBy { it.category ?: "기타" }.forEach { (category, items) ->
            Text(
                text = category,
                style = MaterialTheme.typography.titleMedium,
                color = Color.Black,
                modifier = Modifier.padding(top = 12.dp, bottom = 4.dp),
            )
            items.forEach { item ->
                OtherPolicyRow(item = item, modifier = Modifier.fillMaxWidth().padding(bottom = 8.dp))
            }
        }
    }
}

@Composable
private fun OtherPolicyRow(item: OtherPolicyItemDto, modifier: Modifier = Modifier) {
    Card(
        modifier = modifier,
        colors = recommendationCardColors(),
    ) {
        Row(
            modifier = Modifier.fillMaxWidth().padding(horizontal = 16.dp, vertical = 12.dp),
            horizontalArrangement = Arrangement.SpaceBetween,
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Column(modifier = Modifier.weight(1f).padding(end = 8.dp)) {
                Text(text = item.policy, style = MaterialTheme.typography.bodyLarge)
                if (item.agency != null) {
                    Text(
                        text = item.agency,
                        style = MaterialTheme.typography.bodySmall,
                        color = Color.Black,
                    )
                }
                if (item.description != null) {
                    Text(
                        text = item.description,
                        style = MaterialTheme.typography.bodySmall,
                        color = Color.Black,
                        maxLines = 2,
                        overflow = TextOverflow.Ellipsis,
                        modifier = Modifier.padding(top = 4.dp),
                    )
                }
            }

            val uri = safeHttpsUri(item.url)
            if (uri != null) {
                val context = LocalContext.current
                TextButton(onClick = { openSafeWebLink(context, uri) }) {
                    Text("신청")
                }
            }
        }
    }
}
