package com.ysafe.youthyaho.ui.result

import com.ysafe.youthyaho.MainDispatcherRule
import com.ysafe.youthyaho.data.api.dto.DiagnoseResponseDto
import com.ysafe.youthyaho.data.repository.DiagnosisRepository
import io.mockk.every
import io.mockk.mockk
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Rule
import org.junit.Test

class ResultViewModelTest {

    @get:Rule
    val mainDispatcherRule = MainDispatcherRule()

    private val diagnosisRepository: DiagnosisRepository = mockk()

    @Test
    fun `loads cached diagnose result when present`() {
        val cached = DiagnoseResponseDto(
            session_id = "s1",
            domain_indices = mapOf("주거비압박지수" to 1.5f),
            cluster_membership = mapOf("주거비압박형" to 0.7f),
            risk_probability = 0.5f,
            diagnosis_mode = "approximate",
            approximation_notice = "간이 추정입니다.",
        )
        every { diagnosisRepository.getCachedResult("s1") } returns cached

        val viewModel = ResultViewModel(diagnosisRepository, "s1")

        assertEquals(cached, viewModel.uiState.value.result)
        assertTrue(!viewModel.uiState.value.notFound)
    }

    @Test
    fun `marks not found when cache misses`() {
        every { diagnosisRepository.getCachedResult("unknown") } returns null

        val viewModel = ResultViewModel(diagnosisRepository, "unknown")

        assertNull(viewModel.uiState.value.result)
        assertTrue(viewModel.uiState.value.notFound)
    }
}
