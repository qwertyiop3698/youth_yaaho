package com.ysafe.youthyaho.ui.policyfeedback

import android.content.Intent
import android.net.Uri
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
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.ysafe.youthyaho.ui.common.EmptyContent
import com.ysafe.youthyaho.ui.common.ErrorContent
import com.ysafe.youthyaho.ui.common.LoadingIndicator
import com.ysafe.youthyaho.ui.common.YouthYahoScaffold

@Composable
fun PolicyDetailRoute(
    viewModel: PolicyDetailViewModel,
    policyName: String,
    applicationUrl: String?,
    onBack: () -> Unit,
    onOpenRecords: () -> Unit,
    modifier: Modifier = Modifier,
) {
    val state by viewModel.uiState.collectAsStateWithLifecycle()
    val usage = state.usage
    val context = LocalContext.current
    YouthYahoScaffold(title = "정책 상세", onBack = onBack, modifier = modifier) { paddingValues ->
    Column(modifier = Modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(paddingValues).padding(24.dp)) {
        Text(policyName, style = MaterialTheme.typography.titleLarge)
        usage?.let {
            Text("현재 이용 상태: ${statusLabel(it.current_status)}", modifier = Modifier.padding(top = 8.dp))
        } ?: Text("아직 내 정책 기록에 추가되지 않았습니다.", modifier = Modifier.padding(top = 8.dp))
        state.errorMessage?.let { ErrorContent(message = it, modifier = Modifier.padding(top = 8.dp)) }
        state.message?.let { Text(it, color = MaterialTheme.colorScheme.primary, modifier = Modifier.padding(top = 8.dp)) }
        if (state.loading) LoadingIndicator()

        Button(onClick = viewModel::addToMyPolicies, modifier = Modifier.fillMaxWidth().padding(top = 20.dp)) {
            Text(if (usage == null) "내 정책에 추가" else "내 정책에 추가됨")
        }
        if (usage == null || "application_started" in usage.next_allowed_statuses) {
            Button(onClick = viewModel::recordApplicationStarted, modifier = Modifier.fillMaxWidth().padding(top = 8.dp)) {
                Text("신청 시작 기록")
            }
        }
        if (usage == null || "applied" in usage.next_allowed_statuses || usage.current_status == "recommended") {
            Button(onClick = viewModel::recordApplied, modifier = Modifier.fillMaxWidth().padding(top = 8.dp)) {
                Text("신청 완료했어요")
            }
        }
        val uri = applicationUrl?.let(Uri::parse)?.takeIf { it.scheme == "https" && !it.host.isNullOrBlank() }
        if (uri != null) {
            Button(
                onClick = {
                    viewModel.recordApplicationStarted()
                    runCatching { context.startActivity(Intent(Intent.ACTION_VIEW, uri)) }
                },
                modifier = Modifier.fillMaxWidth().padding(top = 8.dp),
            ) { Text("신청하러 가기") }
        }
        Button(onClick = onOpenRecords, modifier = Modifier.fillMaxWidth().padding(top = 16.dp)) {
            Text("내 정책 기록 보기")
        }
    }
    }
}

@Composable
fun PolicyRecordsRoute(
    viewModel: PolicyRecordsViewModel,
    onBack: () -> Unit,
    onOpenFeedback: (usageId: String, policyId: String, stage: String) -> Unit,
    onOpenRewards: () -> Unit,
    modifier: Modifier = Modifier,
) {
    val state by viewModel.uiState.collectAsStateWithLifecycle()
    YouthYahoScaffold(title = "내 정책 기록", onBack = onBack, modifier = modifier) { paddingValues ->
        when {
            state.loading -> LoadingIndicator(modifier = Modifier.padding(paddingValues).padding(24.dp))
            state.errorMessage != null -> ErrorContent(
                message = state.errorMessage ?: "",
                onRetry = viewModel::load,
                modifier = Modifier.padding(paddingValues).padding(24.dp),
            )
            else -> PolicyUsageHistoryScreen(
                usages = state.usages,
                onOpenFeedback = { usage ->
                    usage.available_feedback_stages.firstOrNull()?.let { stage ->
                        onOpenFeedback(usage.usage_id, usage.policy_id, stage)
                    }
                },
                onUpdateStatus = viewModel::updateStatus,
                onOpenRewards = onOpenRewards,
                modifier = Modifier.padding(paddingValues),
            )
        }
    }
}

@Composable
fun FeedbackFormRoute(
    viewModel: FeedbackFormViewModel,
    onBack: () -> Unit,
    onDone: () -> Unit,
    modifier: Modifier = Modifier,
) {
    val state by viewModel.uiState.collectAsStateWithLifecycle()
    val submission = state.submission
    YouthYahoScaffold(title = "정책 피드백", onBack = onBack, modifier = modifier) { paddingValues ->
        if (submission != null) {
            Column(modifier = Modifier.fillMaxSize().padding(paddingValues).padding(24.dp)) {
                Text("의견 제출 완료", style = MaterialTheme.typography.headlineMedium)
                Card(modifier = Modifier.fillMaxWidth().padding(top = 20.dp)) {
                    Column(modifier = Modifier.padding(16.dp)) {
                        Text("지급 예정 동백전 모의 금액: ${submission.reward.amount}원")
                        Text(
                            if (submission.reward.status == "mock_paid") "지급 상태: Mock 지급 완료"
                            else "지급 상태: 동백전 지급 예정(Mock)",
                            modifier = Modifier.padding(top = 8.dp),
                        )
                        Text("다음 이용 단계에 도달하면 새 의견을 작성할 수 있습니다.", modifier = Modifier.padding(top = 8.dp))
                    }
                }
                Button(onClick = onDone, modifier = Modifier.fillMaxWidth().padding(top = 24.dp)) {
                    Text("내 정책 기록으로 돌아가기")
                }
            }
            return@YouthYahoScaffold
        }
        when {
            state.loading -> LoadingIndicator(modifier = Modifier.padding(paddingValues).padding(24.dp))
            state.errorMessage != null && state.form == null -> ErrorContent(
                message = state.errorMessage ?: "",
                modifier = Modifier.padding(paddingValues).padding(24.dp),
            )
            state.form != null -> state.form?.let { form -> Column(modifier = Modifier.padding(paddingValues)) {
                state.errorMessage?.let {
                    ErrorContent(message = it, modifier = Modifier.padding(horizontal = 24.dp))
                }
                PolicyFeedbackSurveyScreen(
                    form = form,
                    selections = state.selections,
                    otherText = state.otherText,
                    onSelect = viewModel::select,
                    onOtherTextChange = viewModel::changeOtherText,
                    onSubmit = viewModel::submit,
                    submitting = state.submitting,
                    modifier = Modifier,
                )
            } }
        }
    }
}

@Composable
fun RewardsRoute(viewModel: RewardsViewModel, onBack: () -> Unit, modifier: Modifier = Modifier) {
    val state by viewModel.uiState.collectAsStateWithLifecycle()
    YouthYahoScaffold(title = "내 모의 리워드", onBack = onBack, modifier = modifier) { paddingValues ->
    Column(modifier = Modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(paddingValues).padding(24.dp)) {
        Text("실제 동백전 지급이 아닌 개발용 Mock 내역입니다.", modifier = Modifier.padding(top = 8.dp))
        Text("지급 예정 ${state.pendingAmount}원 · Mock 지급 완료 ${state.mockPaidAmount}원", modifier = Modifier.padding(top = 16.dp))
        if (state.loading) LoadingIndicator()
        state.errorMessage?.let { ErrorContent(message = it, modifier = Modifier.padding(top = 12.dp)) }
        if (!state.loading && state.errorMessage == null && state.rewards.isEmpty()) {
            EmptyContent("아직 지급 예정이거나 지급된 리워드가 없습니다.")
        }
        state.rewards.forEach { reward ->
            Card(modifier = Modifier.fillMaxWidth().padding(top = 12.dp)) {
                Column(modifier = Modifier.padding(16.dp)) {
                    Text(reward.policy_id ?: "정책 리워드", style = MaterialTheme.typography.titleMedium)
                    Text("${feedbackStageLabel(reward.stage ?: "")} · ${reward.amount}원")
                    Text(if (reward.status == "mock_paid") "Mock 지급 완료" else "지급 대기(Mock)")
                    reward.created_at?.let { Text("생성일: $it", style = MaterialTheme.typography.bodySmall) }
                }
            }
        }
    }
    }
}
