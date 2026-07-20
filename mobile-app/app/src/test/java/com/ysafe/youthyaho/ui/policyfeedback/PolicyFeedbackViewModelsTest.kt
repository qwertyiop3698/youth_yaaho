package com.ysafe.youthyaho.ui.policyfeedback

import com.ysafe.youthyaho.MainDispatcherRule
import com.ysafe.youthyaho.data.api.ApiException
import com.ysafe.youthyaho.data.api.dto.FeedbackCreatedDto
import com.ysafe.youthyaho.data.api.dto.FeedbackFormDto
import com.ysafe.youthyaho.data.api.dto.FeedbackQuestionDto
import com.ysafe.youthyaho.data.api.dto.FeedbackSubmissionDto
import com.ysafe.youthyaho.data.api.dto.PolicyUsageDto
import com.ysafe.youthyaho.data.api.dto.RewardGrantDto
import com.ysafe.youthyaho.data.repository.PolicyFeedbackRepository
import io.mockk.coEvery
import io.mockk.coVerify
import io.mockk.mockk
import kotlinx.coroutines.test.runTest
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Rule
import org.junit.Test

class PolicyFeedbackViewModelsTest {
    @get:Rule
    val mainDispatcherRule = MainDispatcherRule()

    private val repository: PolicyFeedbackRepository = mockk()

    private fun usage(
        status: String = "recommended",
        next: List<String> = listOf("application_started", "cancelled"),
        available: List<String> = emptyList(),
    ) = PolicyUsageDto(
        usage_id = "u1",
        policy_id = "청년월세지원",
        policy_name = "청년월세지원",
        policy_source = "layer3_catalog",
        current_status = status,
        created_at = "2026-07-16T00:00:00",
        updated_at = "2026-07-16T00:00:00",
        next_allowed_statuses = next,
        available_feedback_stages = available,
    )

    private fun completedForm() = FeedbackFormDto(
        policy_id = "청년월세지원",
        stage = "completed",
        form_version = "2026-01",
        notice = REQUIRED_FEEDBACK_NOTICE,
        other_text_max_length = 200,
        expected_reward_amount = 1000,
        questions = listOf(
            FeedbackQuestionDto("effect", "효과", listOf("좋아짐", "비슷함"), true, false),
            FeedbackQuestionDto("improvement", "개선", listOf("지원 확대", "기타"), true, true),
        ),
    )

    @Test
    fun `policy usage is created once`() = runTest {
        coEvery { repository.getUsages() } returns Result.success(emptyList())
        coEvery { repository.createUsage("청년월세지원") } returns Result.success(usage())
        val viewModel = PolicyDetailViewModel(repository, "청년월세지원")

        viewModel.addToMyPolicies()

        assertEquals("u1", viewModel.uiState.value.usage?.usage_id)
        coVerify(exactly = 1) { repository.createUsage("청년월세지원") }
    }

    @Test
    fun `existing usage is not created again`() = runTest {
        coEvery { repository.getUsages() } returns Result.success(listOf(usage()))
        val viewModel = PolicyDetailViewModel(repository, "청년월세지원")

        viewModel.addToMyPolicies()

        coVerify(exactly = 0) { repository.createUsage(any()) }
        assertEquals("내 정책 기록에 추가했습니다.", viewModel.uiState.value.message)
    }

    @Test
    fun `records expose only server allowed next statuses and available survey`() = runTest {
        val applied = usage(
            status = "applied",
            next = listOf("selected", "rejected", "cancelled"),
            available = listOf("applied"),
        )
        coEvery { repository.getUsages() } returns Result.success(listOf(applied))

        val viewModel = PolicyRecordsViewModel(repository)

        assertEquals(listOf("selected", "rejected", "cancelled"), viewModel.uiState.value.usages[0].next_allowed_statuses)
        assertEquals(listOf("applied"), viewModel.uiState.value.usages[0].available_feedback_stages)
    }

    @Test
    fun `unanswered survey cannot submit and other requires text`() = runTest {
        coEvery { repository.getForm(any(), any()) } returns Result.success(completedForm())
        val viewModel = FeedbackFormViewModel(repository, "u1", "청년월세지원", "completed")

        assertFalse(viewModel.uiState.value.canSubmit)
        viewModel.select("effect", "좋아짐")
        viewModel.select("improvement", "기타")
        assertFalse(viewModel.uiState.value.canSubmit)
        viewModel.changeOtherText("신청 안내를 더 쉽게 해주세요")
        assertTrue(viewModel.uiState.value.canSubmit)
    }

    @Test
    fun `feedback submission shows mock reward state`() = runTest {
        val form = completedForm()
        coEvery { repository.getForm(any(), any()) } returns Result.success(form)
        coEvery { repository.submit(any(), any(), any()) } returns Result.success(
            FeedbackSubmissionDto(
                feedback = FeedbackCreatedDto("f1", "completed", "2026-01", "2026-07-16"),
                reward = RewardGrantDto("r1", "청년월세지원", "completed", 1000, "mock_paid"),
            ),
        )
        val viewModel = FeedbackFormViewModel(repository, "u1", "청년월세지원", "completed")
        viewModel.select("effect", "좋아짐")
        viewModel.select("improvement", "지원 확대")

        viewModel.submit()

        assertEquals("mock_paid", viewModel.uiState.value.submission?.reward?.status)
        assertEquals(1000, viewModel.uiState.value.submission?.reward?.amount)
    }

    @Test
    fun `api errors are converted to user friendly messages`() {
        assertEquals(
            "이미 내 정책에 추가되었거나 작성한 의견입니다. 내 정책 기록을 확인해 주세요.",
            policyFeedbackErrorMessage(ApiException(409, "DB unique constraint failed")),
        )
        assertEquals(
            "현재 이용 단계에서는 요청한 작업을 진행할 수 없습니다.",
            policyFeedbackErrorMessage(ApiException(422, "허용되지 않는 상태 전이입니다")),
        )
    }
}
