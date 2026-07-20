package com.ysafe.youthyaho.data.api.dto

import kotlinx.serialization.Serializable

@Serializable
data class CreatePolicyUsageRequestDto(val policy_id: String)

@Serializable
data class UpdatePolicyUsageStatusRequestDto(val status: String)

@Serializable
data class PolicyUsageStatusHistoryDto(val status: String, val changed_at: String)

@Serializable
data class PolicyUsageDto(
    val usage_id: String,
    val policy_id: String,
    val policy_name: String,
    val policy_source: String,
    val current_status: String,
    val created_at: String,
    val updated_at: String,
    val status_history: List<PolicyUsageStatusHistoryDto> = emptyList(),
    val feedback_completed_stages: List<String> = emptyList(),
    val available_feedback_stages: List<String> = emptyList(),
    val next_allowed_statuses: List<String> = emptyList(),
    val expected_reward_amount: Int? = null,
    val reward_summary: UsageRewardSummaryDto = UsageRewardSummaryDto(),
)

@Serializable
data class UsageRewardSummaryDto(
    val pending_amount: Int = 0,
    val mock_paid_amount: Int = 0,
)

@Serializable
data class FeedbackQuestionDto(
    val question_code: String,
    val prompt: String,
    val options: List<String>,
    val required: Boolean,
    val allows_other_text: Boolean,
)

@Serializable
data class FeedbackFormDto(
    val policy_id: String,
    val stage: String,
    val form_version: String,
    val notice: String,
    val other_text_max_length: Int,
    val expected_reward_amount: Int,
    val questions: List<FeedbackQuestionDto>,
)

@Serializable
data class FeedbackAnswerRequestDto(
    val question_code: String,
    val choice: String,
    val other_text: String? = null,
)

@Serializable
data class SubmitFeedbackRequestDto(
    val stage: String,
    val answers: List<FeedbackAnswerRequestDto>,
)

@Serializable
data class FeedbackCreatedDto(
    val feedback_id: String,
    val stage: String,
    val form_version: String,
    val submitted_at: String,
)

@Serializable
data class RewardGrantDto(
    val reward_id: String,
    val policy_id: String? = null,
    val stage: String? = null,
    val amount: Int,
    val status: String,
    val created_at: String? = null,
    val updated_at: String? = null,
)

@Serializable
data class FeedbackSubmissionDto(
    val feedback: FeedbackCreatedDto,
    val reward: RewardGrantDto,
)
