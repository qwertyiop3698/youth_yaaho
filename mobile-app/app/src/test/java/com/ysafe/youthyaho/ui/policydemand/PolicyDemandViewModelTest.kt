package com.ysafe.youthyaho.ui.policydemand

import com.ysafe.youthyaho.MainDispatcherRule
import com.ysafe.youthyaho.data.api.ApiException
import com.ysafe.youthyaho.data.api.dto.DemandFormDto
import com.ysafe.youthyaho.data.api.dto.DemandQuestionDto
import com.ysafe.youthyaho.data.api.dto.DemandRewardDto
import com.ysafe.youthyaho.data.api.dto.DemandSubmissionDto
import com.ysafe.youthyaho.data.repository.PolicyDemandRepository
import io.mockk.coEvery
import io.mockk.coVerify
import io.mockk.mockk
import kotlinx.coroutines.test.runTest
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotNull
import org.junit.Rule
import org.junit.Test

class PolicyDemandViewModelTest {
    @get:Rule val mainDispatcherRule = MainDispatcherRule()
    private val repository: PolicyDemandRepository = mockk()
    private fun form() = DemandFormDto(
        "2026-01", "익명으로 집계됩니다.", "필요한 지원을 알려주세요.", 1000, 90, 200,
        listOf(
            DemandQuestionDto("need_area", "지원", listOf("생활비", "기타"), true),
            DemandQuestionDto("duration", "기간", listOf("2~3개월"), true),
            DemandQuestionDto("amount", "금액", listOf("11~30만 원"), true),
            DemandQuestionDto("barrier", "장벽", listOf("지원내용 불일치"), true),
            DemandQuestionDto("companion_support", "함께", listOf("취업교육"), false, true),
            DemandQuestionDto("employment_status", "고용", listOf("구직 중"), false, true),
        ),
    )
    private fun vm(): PolicyDemandViewModel { coEvery { repository.form() } returns Result.success(form()); return PolicyDemandViewModel(repository, "s1", "user_reported_mismatch") }
    private fun required(viewModel: PolicyDemandViewModel) {
        viewModel.select("need_area", "생활비"); viewModel.select("duration", "2~3개월")
        viewModel.select("amount", "11~30만 원"); viewModel.select("barrier", "지원내용 불일치")
    }

    @Test fun `form exposes exactly four required questions`() = runTest {
        val state = vm().state.value
        assertFalse(state.loading); assertEquals(4, state.form?.questions?.count { it.required })
    }
    @Test fun `four required answers are validated`() = runTest {
        val viewModel = vm(); viewModel.submit()
        assertEquals("필수 4문항에 모두 응답해주세요.", viewModel.state.value.error)
    }
    @Test fun `other selection requires short text`() = runTest {
        val viewModel = vm(); required(viewModel); viewModel.select("need_area", "기타"); viewModel.submit()
        assertEquals("기타 선택 내용을 입력해주세요.", viewModel.state.value.error)
        viewModel.updateOther("교통 지원"); assertEquals("교통 지원", viewModel.state.value.otherText)
    }
    @Test fun `expected mock reward and cooldown are loaded`() = runTest {
        val state = vm().state.value
        assertEquals(1000, state.form?.expectedRewardAmount); assertEquals(90, state.form?.cooldownDays)
    }
    @Test fun `duplicate response shows cooldown guidance`() = runTest {
        val viewModel = vm(); required(viewModel)
        coEvery { repository.submit(any()) } returns Result.failure(ApiException(409, "duplicate"))
        viewModel.submit()
        assertEquals("동일한 수요는 90일 이후 다시 참여할 수 있습니다.", viewModel.state.value.error)
    }
    @Test fun `successful submission reaches completion with reward`() = runTest {
        val viewModel = vm(); required(viewModel)
        coEvery { repository.submit(any()) } returns Result.success(DemandSubmissionDto("r1", "2026-07-16", DemandRewardDto("g1", 1000, "mock_paid")))
        viewModel.submit()
        assertNotNull(viewModel.state.value.completed); assertEquals(1000, viewModel.state.value.completed?.reward?.amount)
        coVerify(exactly = 1) { repository.submit(any()) }
    }
}

