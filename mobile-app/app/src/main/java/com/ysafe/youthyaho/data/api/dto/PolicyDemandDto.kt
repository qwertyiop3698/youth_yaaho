package com.ysafe.youthyaho.data.api.dto

import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable

@Serializable data class DemandEligibilityDto(
    val eligible: Boolean,
    @SerialName("trigger_reason") val triggerReason: String,
    @SerialName("expected_reward_amount") val expectedRewardAmount: Int,
    @SerialName("cooldown_until") val cooldownUntil: String? = null,
    val explanation: String,
)
@Serializable data class DemandQuestionDto(
    val code: String, val prompt: String, val options: List<String>, val required: Boolean,
    val conditional: Boolean = false,
)
@Serializable data class DemandFormDto(
    @SerialName("form_version") val formVersion: String,
    val notice: String,
    @SerialName("exposure_message") val exposureMessage: String,
    @SerialName("expected_reward_amount") val expectedRewardAmount: Int,
    @SerialName("cooldown_days") val cooldownDays: Int,
    @SerialName("other_text_max_length") val otherTextMaxLength: Int,
    val questions: List<DemandQuestionDto>,
)
@Serializable data class SubmitDemandRequestDto(
    @SerialName("session_id") val sessionId: String,
    @SerialName("trigger_reason") val triggerReason: String,
    @SerialName("need_area") val needArea: String,
    val duration: String,
    val amount: String,
    val barrier: String,
    @SerialName("companion_support") val companionSupport: String? = null,
    @SerialName("employment_status") val employmentStatus: String? = null,
    @SerialName("other_text") val otherText: String? = null,
)
@Serializable data class DemandRewardDto(
    @SerialName("reward_id") val rewardId: String, val amount: Int, val status: String,
)
@Serializable data class DemandSubmissionDto(
    @SerialName("response_id") val responseId: String,
    @SerialName("submitted_at") val submittedAt: String,
    val reward: DemandRewardDto,
)

