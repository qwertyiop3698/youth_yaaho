package com.ysafe.youthyaho.ui.explanation

import com.ysafe.youthyaho.MainDispatcherRule
import com.ysafe.youthyaho.data.api.ApiException
import com.ysafe.youthyaho.data.api.dto.ExplanationResponseDto
import com.ysafe.youthyaho.data.repository.DiagnosisRepository
import io.mockk.coEvery
import io.mockk.mockk
import kotlinx.coroutines.test.runTest
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Rule
import org.junit.Test

class ExplanationViewModelTest {

    @get:Rule
    val mainDispatcherRule = MainDispatcherRule()

    private val diagnosisRepository: DiagnosisRepository = mockk()

    @Test
    fun `loads explanation and llm flag`() = runTest {
        coEvery { diagnosisRepository.getExplanation("s1") } returns Result.success(
            ExplanationResponseDto(session_id = "s1", explanation = "설명 문장입니다.", is_llm_generated = true),
        )

        val viewModel = ExplanationViewModel(diagnosisRepository, "s1")

        val state = viewModel.uiState.value
        assertFalse(state.isLoading)
        assertEquals("설명 문장입니다.", state.explanation)
        assertTrue(state.isLlmGenerated)
    }

    @Test
    fun `failure surfaces backend error message`() = runTest {
        coEvery { diagnosisRepository.getExplanation("s1") } returns
            Result.failure(ApiException(404, "session_id를 찾을 수 없습니다."))

        val viewModel = ExplanationViewModel(diagnosisRepository, "s1")

        assertEquals("session_id를 찾을 수 없습니다.", viewModel.uiState.value.errorMessage)
    }

    @Test
    fun `retry clears previous error and reloads`() = runTest {
        coEvery { diagnosisRepository.getExplanation("s1") } returns
            Result.failure(ApiException(500, "서버 오류")) andThen
            Result.success(ExplanationResponseDto(session_id = "s1", explanation = "다시 성공", is_llm_generated = false))

        val viewModel = ExplanationViewModel(diagnosisRepository, "s1")
        assertEquals("서버 오류", viewModel.uiState.value.errorMessage)

        viewModel.retry()

        assertEquals("다시 성공", viewModel.uiState.value.explanation)
        assertEquals(null, viewModel.uiState.value.errorMessage)
    }
}
