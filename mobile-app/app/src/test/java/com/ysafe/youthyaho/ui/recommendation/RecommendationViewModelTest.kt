package com.ysafe.youthyaho.ui.recommendation

import com.ysafe.youthyaho.MainDispatcherRule
import com.ysafe.youthyaho.data.api.ApiException
import com.ysafe.youthyaho.data.api.dto.OtherPolicyItemDto
import com.ysafe.youthyaho.data.api.dto.RecommendationItemDto
import com.ysafe.youthyaho.data.api.dto.RecommendationsResponseDto
import com.ysafe.youthyaho.data.repository.DiagnosisRepository
import io.mockk.coEvery
import io.mockk.mockk
import kotlinx.coroutines.test.runTest
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Rule
import org.junit.Test

class RecommendationViewModelTest {

    @get:Rule
    val mainDispatcherRule = MainDispatcherRule()

    private val diagnosisRepository: DiagnosisRepository = mockk()

    private fun item(policy: String, priority: Int, eligible: Boolean = true) = RecommendationItemDto(
        policy = policy,
        priority = priority,
        expected_effect = 0.1f,
        eligible = eligible,
        eligibility_confidence = "verified",
    )

    @Test
    fun `loads and keeps only top 3 by priority`() = runTest {
        val all = listOf(
            item("F", priority = 6),
            item("A", priority = 1),
            item("C", priority = 3),
            item("B", priority = 2),
            item("E", priority = 5),
            item("D", priority = 4),
        )
        coEvery { diagnosisRepository.getRecommendations("s1") } returns
            Result.success(RecommendationsResponseDto(all))

        val viewModel = RecommendationViewModel(diagnosisRepository, "s1")

        val state = viewModel.uiState.value
        assertFalse(state.isLoading)
        assertEquals(listOf("A", "B", "C"), state.topRecommendations.map { it.policy })
    }

    @Test
    fun `loads other policies from response`() = runTest {
        val others = listOf(
            OtherPolicyItemDto(policy = "부산 청년두드림센터 운영", category = "일자리", agency = "부산광역시"),
        )
        coEvery { diagnosisRepository.getRecommendations("s1") } returns
            Result.success(RecommendationsResponseDto(listOf(item("A", priority = 1)), others))

        val viewModel = RecommendationViewModel(diagnosisRepository, "s1")

        assertEquals(others, viewModel.uiState.value.otherPolicies)
    }

    @Test
    fun `failure surfaces backend error message`() = runTest {
        coEvery { diagnosisRepository.getRecommendations("s1") } returns
            Result.failure(ApiException(404, "session_id를 찾을 수 없습니다."))

        val viewModel = RecommendationViewModel(diagnosisRepository, "s1")

        val state = viewModel.uiState.value
        assertFalse(state.isLoading)
        assertEquals("session_id를 찾을 수 없습니다.", state.errorMessage)
    }

    @Test
    fun `retry re-fetches and clears previous error`() = runTest {
        coEvery { diagnosisRepository.getRecommendations("s1") } returns
            Result.failure(ApiException(500, "서버 오류")) andThen
            Result.success(RecommendationsResponseDto(listOf(item("A", priority = 1))))

        val viewModel = RecommendationViewModel(diagnosisRepository, "s1")
        assertEquals("서버 오류", viewModel.uiState.value.errorMessage)

        viewModel.retry()

        assertTrue(viewModel.uiState.value.errorMessage == null)
        assertEquals(listOf("A"), viewModel.uiState.value.topRecommendations.map { it.policy })
    }
}
