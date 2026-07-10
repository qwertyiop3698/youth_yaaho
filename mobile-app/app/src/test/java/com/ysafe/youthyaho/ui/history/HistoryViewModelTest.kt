package com.ysafe.youthyaho.ui.history

import com.ysafe.youthyaho.MainDispatcherRule
import com.ysafe.youthyaho.data.api.ApiException
import com.ysafe.youthyaho.data.api.dto.HistoryEntryDto
import com.ysafe.youthyaho.data.api.dto.HistoryResponseDto
import com.ysafe.youthyaho.data.repository.DiagnosisRepository
import io.mockk.coEvery
import io.mockk.mockk
import kotlinx.coroutines.test.runTest
import kotlinx.serialization.json.JsonNull
import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.put
import kotlinx.serialization.json.putJsonObject
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Rule
import org.junit.Test

class HistoryViewModelTest {

    @get:Rule
    val mainDispatcherRule = MainDispatcherRule()

    private val diagnosisRepository: DiagnosisRepository = mockk()

    @Test
    fun `loads and extracts domain indices, cluster membership, risk from raw json`() = runTest {
        val diagnosisResult = buildJsonObject {
            putJsonObject("domain_indices") {
                put("주거비압박지수", 1.2f)
            }
            putJsonObject("cluster_membership") {
                put("주거비압박형", 0.6f)
            }
            put("risk_probability", 0.4f)
        }
        coEvery { diagnosisRepository.getHistory("s1") } returns Result.success(
            HistoryResponseDto(
                session_id = "s1",
                history = listOf(HistoryEntryDto(created_at = "2026-07-10T00:00:00Z", diagnosis_result = diagnosisResult)),
                note = "현재는 session_id 기준 단일 진단만 저장됩니다.",
            ),
        )

        val viewModel = HistoryViewModel(diagnosisRepository, "s1")

        val state = viewModel.uiState.value
        assertFalse(state.isLoading)
        assertEquals("2026-07-10T00:00:00Z", state.createdAt)
        assertEquals("현재는 session_id 기준 단일 진단만 저장됩니다.", state.note)
        assertEquals(1.2f, state.domainIndices["주거비압박지수"])
        assertEquals(0.6f, state.clusterMembership["주거비압박형"])
        assertEquals(0.4f, state.riskProbability)
    }

    @Test
    fun `failure surfaces backend error message`() = runTest {
        coEvery { diagnosisRepository.getHistory("s1") } returns
            Result.failure(ApiException(404, "session_id를 찾을 수 없습니다."))

        val viewModel = HistoryViewModel(diagnosisRepository, "s1")

        assertEquals("session_id를 찾을 수 없습니다.", viewModel.uiState.value.errorMessage)
    }

    @Test
    fun `missing cluster_membership and risk_probability keys yield empty state without crashing`() = runTest {
        // 표본부족으로 Layer2-A/B가 skip된 경우(정책사각지대 화면 때 확인한 패턴과
        // 동일) diagnosis_result에 domain_indices만 있고 나머지 키는 아예 없을 수
        // 있다 - 키 자체가 없는 경우다(null이 아니라).
        val diagnosisResult = buildJsonObject {
            putJsonObject("domain_indices") {
                put("주거비압박지수", 1.2f)
            }
        }
        coEvery { diagnosisRepository.getHistory("s1") } returns Result.success(
            HistoryResponseDto(
                session_id = "s1",
                history = listOf(HistoryEntryDto(created_at = "2026-07-10T00:00:00Z", diagnosis_result = diagnosisResult)),
                note = "현재는 session_id 기준 단일 진단만 저장됩니다.",
            ),
        )

        val viewModel = HistoryViewModel(diagnosisRepository, "s1")

        val state = viewModel.uiState.value
        assertFalse(state.isLoading)
        assertEquals(1.2f, state.domainIndices["주거비압박지수"])
        assertEquals(emptyMap<String, Float>(), state.clusterMembership)
        assertEquals(null, state.riskProbability)
    }

    @Test
    fun `explicit json null for risk_probability yields null without crashing`() = runTest {
        // diagnose_service.py는 risk_model_bundle이 없으면 risk_probability=None을
        // 반환하는데, 이게 JSON으로 직렬화되면 키가 없는 게 아니라 명시적 null로
        // 남는다 - 키 누락과 별개로 이 케이스도 크래시 없이 처리돼야 한다.
        val diagnosisResult = buildJsonObject {
            putJsonObject("cluster_membership") { }
            put("risk_probability", JsonNull)
        }
        coEvery { diagnosisRepository.getHistory("s1") } returns Result.success(
            HistoryResponseDto(
                session_id = "s1",
                history = listOf(HistoryEntryDto(created_at = "2026-07-10T00:00:00Z", diagnosis_result = diagnosisResult)),
                note = "현재는 session_id 기준 단일 진단만 저장됩니다.",
            ),
        )

        val viewModel = HistoryViewModel(diagnosisRepository, "s1")

        val state = viewModel.uiState.value
        assertFalse(state.isLoading)
        assertEquals(null, state.riskProbability)
        assertEquals(emptyMap<String, Float>(), state.clusterMembership)
    }

    @Test
    fun `empty history list yields empty state without crashing`() = runTest {
        coEvery { diagnosisRepository.getHistory("s1") } returns Result.success(
            HistoryResponseDto(session_id = "s1", history = emptyList(), note = "기록 없음"),
        )

        val viewModel = HistoryViewModel(diagnosisRepository, "s1")

        val state = viewModel.uiState.value
        assertFalse(state.isLoading)
        assertEquals(null, state.createdAt)
        assertEquals(emptyMap<String, Float>(), state.domainIndices)
    }
}
