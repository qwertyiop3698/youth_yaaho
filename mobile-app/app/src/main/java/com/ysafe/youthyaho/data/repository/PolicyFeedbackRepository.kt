package com.ysafe.youthyaho.data.repository

import com.ysafe.youthyaho.data.api.CitizenApiService
import com.ysafe.youthyaho.data.api.apiResultOf
import com.ysafe.youthyaho.data.api.dto.CreatePolicyUsageRequestDto
import com.ysafe.youthyaho.data.api.dto.FeedbackAnswerRequestDto
import com.ysafe.youthyaho.data.api.dto.FeedbackFormDto
import com.ysafe.youthyaho.data.api.dto.FeedbackSubmissionDto
import com.ysafe.youthyaho.data.api.dto.PolicyUsageDto
import com.ysafe.youthyaho.data.api.dto.RewardGrantDto
import com.ysafe.youthyaho.data.api.dto.SubmitFeedbackRequestDto
import com.ysafe.youthyaho.data.api.dto.UpdatePolicyUsageStatusRequestDto

/** 피드백 도메인 API만 담당하며 기존 진단/추천 Repository와 상태를 공유하지 않는다. */
class PolicyFeedbackRepository(private val api: CitizenApiService) {
    suspend fun createUsage(policyId: String): Result<PolicyUsageDto> =
        apiResultOf { api.createPolicyUsage(CreatePolicyUsageRequestDto(policyId)) }

    suspend fun updateStatus(usageId: String, status: String): Result<PolicyUsageDto> =
        apiResultOf { api.updatePolicyUsageStatus(usageId, UpdatePolicyUsageStatusRequestDto(status)) }

    suspend fun getUsages(): Result<List<PolicyUsageDto>> = apiResultOf { api.policyUsages() }

    suspend fun getForm(policyId: String, stage: String): Result<FeedbackFormDto> =
        apiResultOf { api.feedbackForm(policyId, stage) }

    suspend fun submit(
        usageId: String,
        stage: String,
        answers: List<FeedbackAnswerRequestDto>,
    ): Result<FeedbackSubmissionDto> =
        apiResultOf { api.submitFeedback(usageId, SubmitFeedbackRequestDto(stage, answers)) }

    suspend fun getRewards(): Result<List<RewardGrantDto>> = apiResultOf { api.rewards() }
}
