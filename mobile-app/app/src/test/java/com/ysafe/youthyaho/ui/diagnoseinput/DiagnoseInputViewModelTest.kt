package com.ysafe.youthyaho.ui.diagnoseinput

import com.ysafe.youthyaho.MainDispatcherRule
import com.ysafe.youthyaho.data.api.ApiException
import com.ysafe.youthyaho.data.api.dto.DiagnoseResponseDto
import com.ysafe.youthyaho.data.repository.DiagnosisRepository
import io.mockk.coEvery
import io.mockk.mockk
import kotlinx.coroutines.test.runTest
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Rule
import org.junit.Test

class DiagnoseInputViewModelTest {

    @get:Rule
    val mainDispatcherRule = MainDispatcherRule()

    private val diagnosisRepository: DiagnosisRepository = mockk()

    @Test
    fun `submit blocked client-side when fields incomplete`() = runTest {
        val viewModel = DiagnoseInputViewModel(diagnosisRepository)
        viewModel.onAgeGroupSelect("25-29")
        // dong_code/incomeBand/housingType 미입력 상태로 제출 시도

        viewModel.submit()

        assertEquals("모든 항목을 선택/입력해주세요.", viewModel.uiState.value.errorMessage)
        assertNull(viewModel.uiState.value.sessionId)
    }

    @Test
    fun `submit success stores session id`() = runTest {
        val response = DiagnoseResponseDto(
            session_id = "s1",
            domain_indices = emptyMap(),
            cluster_membership = emptyMap(),
            risk_probability = 0.3f,
            diagnosis_mode = "approximate",
            approximation_notice = "간이 추정입니다.",
        )
        coEvery {
            diagnosisRepository.diagnose("25-29", "26440", "2500-3000", "월세", false)
        } returns Result.success(response)

        val viewModel = fillValidForm(DiagnoseInputViewModel(diagnosisRepository))
        viewModel.submit()

        assertEquals("s1", viewModel.uiState.value.sessionId)
        assertNull(viewModel.uiState.value.errorMessage)
    }

    @Test
    fun `submit failure surfaces backend error message`() = runTest {
        coEvery { diagnosisRepository.diagnose(any(), any(), any(), any(), any()) } returns
            Result.failure(ApiException(401, "토큰이 만료되었습니다."))

        val viewModel = fillValidForm(DiagnoseInputViewModel(diagnosisRepository))
        viewModel.submit()

        assertEquals("토큰이 만료되었습니다.", viewModel.uiState.value.errorMessage)
        assertNull(viewModel.uiState.value.sessionId)
    }

    private fun fillValidForm(viewModel: DiagnoseInputViewModel): DiagnoseInputViewModel {
        viewModel.onAgeGroupSelect("25-29")
        viewModel.onDongCodeChange("26440")
        viewModel.onIncomeBandSelect("2500-3000")
        viewModel.onHousingTypeSelect("월세")
        viewModel.onHasDebtChange(false)
        return viewModel
    }
}
