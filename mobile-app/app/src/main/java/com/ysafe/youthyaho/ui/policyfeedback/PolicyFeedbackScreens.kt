package com.ysafe.youthyaho.ui.policyfeedback

import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.RadioButton
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import com.ysafe.youthyaho.data.api.dto.FeedbackFormDto
import com.ysafe.youthyaho.data.api.dto.PolicyUsageDto

const val REQUIRED_FEEDBACK_NOTICE =
    "작성해 주신 의견은 익명으로 집계되어 부산시 청년정책 개선 자료로 전달됩니다. " +
        "여러분의 경험이 다음 정책을 바꾸는 근거가 됩니다."

/** 정책 상세에서 현재 이용 단계와 다음 행동을 명시하는 기반 카드. */
@Composable
fun PolicyDetailFeedbackCard(
    policyName: String,
    currentStatus: String?,
    onRecordUsage: () -> Unit,
    modifier: Modifier = Modifier,
) {
    Card(modifier = modifier.fillMaxWidth()) {
        Column(modifier = Modifier.padding(16.dp)) {
            Text(policyName, style = MaterialTheme.typography.titleLarge)
            Text(
                text = currentStatus?.let { "내 정책 기록 상태: $it" }
                    ?: "실제 신청을 시작한 정책만 내 정책 기록에 추가해 주세요.",
                style = MaterialTheme.typography.bodyMedium,
                modifier = Modifier.padding(top = 8.dp),
            )
            Button(onClick = onRecordUsage, modifier = Modifier.padding(top = 12.dp)) {
                Text(if (currentStatus == null) "내 정책 기록에 추가" else "이용 단계 업데이트")
            }
        }
    }
}

/** 종료 정책을 별도 추천하지 않고, 서버가 돌려준 실제 이용 이력만 표시한다. */
@Composable
fun PolicyUsageHistoryScreen(
    usages: List<PolicyUsageDto>,
    onOpenFeedback: (PolicyUsageDto) -> Unit,
    onUpdateStatus: (PolicyUsageDto, String) -> Unit,
    onOpenRewards: () -> Unit,
    modifier: Modifier = Modifier,
) {
    Column(modifier = modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(24.dp)) {
        Text("내 정책 기록", style = MaterialTheme.typography.headlineMedium)
        TextButton(onClick = onOpenRewards, modifier = Modifier.padding(top = 8.dp)) {
            Text("내 모의 리워드 확인")
        }
        if (usages.isEmpty()) {
            Text("아직 신청하거나 이용한 것으로 기록된 정책이 없습니다.", modifier = Modifier.padding(top = 24.dp))
        }
        val grouped = usages.groupBy { statusLabel(it.current_status) }
        listOf("신청 준비", "신청 완료", "선정", "탈락", "이용 중", "이용 완료", "취소").forEach { groupLabel ->
            val group = grouped[groupLabel].orEmpty()
            if (group.isNotEmpty()) {
                Text(groupLabel, style = MaterialTheme.typography.titleMedium, modifier = Modifier.padding(top = 20.dp))
            }
            group.forEach { usage ->
            Card(modifier = Modifier.fillMaxWidth().padding(top = 12.dp)) {
                Column(modifier = Modifier.padding(16.dp)) {
                    Text(usage.policy_name, style = MaterialTheme.typography.titleMedium)
                    Text("현재 단계: ${statusLabel(usage.current_status)}", modifier = Modifier.padding(top = 4.dp))
                    Text(
                        "최근 변경: ${usage.updated_at} · 작성 완료 ${usage.feedback_completed_stages.size}단계",
                        style = MaterialTheme.typography.bodySmall,
                    )
                    val availableStage = usage.available_feedback_stages.firstOrNull()
                    if (availableStage != null) {
                        Button(onClick = { onOpenFeedback(usage) }, modifier = Modifier.padding(top = 12.dp)) {
                            Text("다음 작성 가능한 의견: ${feedbackStageLabel(availableStage)}")
                        }
                    }
                    if (usage.reward_summary.pending_amount > 0 || usage.reward_summary.mock_paid_amount > 0) {
                        Text(
                            "리워드: 대기 ${usage.reward_summary.pending_amount}원 · Mock 완료 ${usage.reward_summary.mock_paid_amount}원",
                            style = MaterialTheme.typography.bodySmall,
                            modifier = Modifier.padding(top = 8.dp),
                        )
                    }
                    usage.next_allowed_statuses.forEach { next ->
                        TextButton(onClick = { onUpdateStatus(usage, next) }) {
                            Text(statusActionLabel(next))
                        }
                    }
                }
            }
            }
        }
    }
}

/** 단계별 문항만 표시하는 설문 화면. 공통 안내 문구는 서버 값과 무관하게 항상 노출한다. */
@Composable
fun PolicyFeedbackSurveyScreen(
    form: FeedbackFormDto,
    selections: Map<String, String>,
    otherText: String,
    onSelect: (questionCode: String, choice: String) -> Unit,
    onOtherTextChange: (String) -> Unit,
    onSubmit: () -> Unit,
    submitting: Boolean,
    modifier: Modifier = Modifier,
) {
    Column(modifier = modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(24.dp)) {
        Text("정책 이용 피드백", style = MaterialTheme.typography.headlineMedium)
        val answered = form.questions.count { selections[it.question_code] != null }
        Text(
            "진행률 $answered/${form.questions.size}",
            style = MaterialTheme.typography.bodyMedium,
            modifier = Modifier.padding(top = 12.dp),
        )
        LinearProgressIndicator(
            progress = { if (form.questions.isEmpty()) 0f else answered.toFloat() / form.questions.size },
            modifier = Modifier.fillMaxWidth().padding(top = 8.dp),
        )
        Card(modifier = Modifier.fillMaxWidth().padding(top = 16.dp, bottom = 16.dp)) {
            Text(
                text = REQUIRED_FEEDBACK_NOTICE,
                style = MaterialTheme.typography.bodyMedium,
                modifier = Modifier.padding(16.dp),
            )
        }
        Card(modifier = Modifier.fillMaxWidth().padding(top = 16.dp)) {
            Column(modifier = Modifier.padding(16.dp)) {
                Text("예상 리워드 ${form.expected_reward_amount}원 (동백전 지급 예정 Mock)")
                Text(
                    "솔직한 의견을 남겨주세요. 좋은 평가와 아쉬운 평가 모두 동일한 리워드가 지급됩니다.",
                    style = MaterialTheme.typography.bodySmall,
                    modifier = Modifier.padding(top = 4.dp),
                )
            }
        }
        form.questions.forEach { question ->
            Text(question.prompt, style = MaterialTheme.typography.titleMedium, modifier = Modifier.padding(top = 16.dp))
            question.options.forEach { option ->
                Row(verticalAlignment = Alignment.CenterVertically) {
                    RadioButton(
                        selected = selections[question.question_code] == option,
                        onClick = { onSelect(question.question_code, option) },
                    )
                    Text(option)
                }
            }
            if (question.allows_other_text && selections[question.question_code] == "기타") {
                OutlinedTextField(
                    value = otherText,
                    onValueChange = { if (it.length <= form.other_text_max_length) onOtherTextChange(it) },
                    label = { Text("기타 의견 (${form.other_text_max_length}자 이하)") },
                    modifier = Modifier.fillMaxWidth(),
                )
                Text(
                    "${otherText.length}/${form.other_text_max_length}자",
                    style = MaterialTheme.typography.bodySmall,
                    modifier = Modifier.fillMaxWidth(),
                )
            }
        }
        val complete = form.questions.all { selections[it.question_code] != null } &&
            form.questions.none {
                it.allows_other_text && selections[it.question_code] == "기타" && otherText.isBlank()
            }
        Button(
            onClick = onSubmit,
            enabled = complete && !submitting,
            modifier = Modifier.fillMaxWidth().padding(top = 24.dp),
        ) {
            Text(if (submitting) "제출 중..." else "피드백 제출")
        }
    }
}

fun feedbackStageLabel(stage: String): String = when (stage) {
    "applied" -> "신청 과정 피드백"
    "selected" -> "선정 결과 피드백"
    "rejected" -> "탈락 결과 피드백"
    "using" -> "이용 중간 피드백"
    "completed" -> "최종 효과 피드백"
    else -> "정책 이용 피드백"
}

fun statusLabel(status: String): String = when (status) {
    "recommended" -> "신청 준비"
    "application_started" -> "신청 준비"
    "applied" -> "신청 완료"
    "selected" -> "선정"
    "rejected" -> "탈락"
    "using" -> "이용 중"
    "completed" -> "이용 완료"
    "cancelled" -> "취소"
    else -> "정책 이용 중"
}

fun statusActionLabel(status: String): String = when (status) {
    "application_started" -> "신청 시작 기록"
    "applied" -> "신청 완료했어요"
    "selected" -> "선정되었어요"
    "rejected" -> "선정되지 않았어요"
    "using" -> "이용을 시작했어요"
    "completed" -> "이용을 완료했어요"
    "cancelled" -> "이 기록 취소"
    else -> "상태 업데이트"
}
