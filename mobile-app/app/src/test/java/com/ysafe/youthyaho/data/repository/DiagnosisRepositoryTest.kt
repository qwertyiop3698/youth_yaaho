package com.ysafe.youthyaho.data.repository

import com.ysafe.youthyaho.data.api.CitizenApiService
import com.ysafe.youthyaho.data.api.dto.DiagnoseResponseDto
import com.ysafe.youthyaho.data.api.dto.ExplanationResponseDto
import com.ysafe.youthyaho.data.api.dto.HistoryEntryDto
import com.ysafe.youthyaho.data.api.dto.HistoryResponseDto
import com.ysafe.youthyaho.data.api.dto.RecommendationItemDto
import com.ysafe.youthyaho.data.api.dto.RecommendationsResponseDto
import io.mockk.coEvery
import io.mockk.mockk
import kotlinx.coroutines.test.runTest
import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.put
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.ResponseBody.Companion.toResponseBody
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test
import retrofit2.Response

class DiagnosisRepositoryTest {

    private val api: CitizenApiService = mockk()
    private val repository = DiagnosisRepository(api)

    @Test
    fun `diagnose returns success body`() = runTest {
        val expected = DiagnoseResponseDto(
            session_id = "s1",
            session_access_token = "secret-s1",
            domain_indices = mapOf("주거비압박지수" to 1.2f),
            cluster_membership = mapOf("주거비압박형" to 0.6f),
            risk_probability = 0.4f,
            diagnosis_mode = "approximate",
            approximation_notice = "간이 추정입니다.",
        )
        coEvery { api.diagnose(any()) } returns Response.success(expected)

        val result = repository.diagnose("25-29", "26440", "2500-3000", "월세", false)

        assertTrue(result.isSuccess)
        assertEquals("s1", result.getOrNull()?.session_id)
    }

    @Test
    fun `diagnose success caches result by session id`() = runTest {
        val expected = DiagnoseResponseDto(
            session_id = "s2",
            session_access_token = "secret-s2",
            domain_indices = mapOf("신용취약지수" to -0.3f),
            cluster_membership = mapOf("자산형성가능형" to 0.9f),
            risk_probability = 0.1f,
            diagnosis_mode = "approximate",
            approximation_notice = "간이 추정입니다.",
        )
        coEvery { api.diagnose(any()) } returns Response.success(expected)

        repository.diagnose("30-34", "26440", "3000-3500", "전세", true)

        assertEquals(expected, repository.getCachedResult("s2"))
    }

    @Test
    fun `diagnose failure does not populate cache`() = runTest {
        val errorBody = "{\"detail\": \"오류\"}".toResponseBody("application/json".toMediaType())
        coEvery { api.diagnose(any()) } returns Response.error(500, errorBody)

        repository.diagnose("25-29", "26440", "2500-3000", "월세", false)

        assertNull(repository.getCachedResult("nonexistent"))
    }

    @Test
    fun `getRecommendations returns response body on success`() = runTest {
        val items = listOf(
            RecommendationItemDto(
                policy = "청년월세지원",
                priority = 1,
                expected_effect = 0.1f,
                eligible = true,
                eligibility_confidence = "verified",
            ),
        )
        val expected = RecommendationsResponseDto(items)
        coEvery { api.recommendations("s1", null) } returns Response.success(expected)

        val result = repository.getRecommendations("s1")

        assertTrue(result.isSuccess)
        assertEquals(expected, result.getOrNull())
    }

    @Test
    fun `getRecommendations surfaces 404 for unknown session`() = runTest {
        val errorBody = "{\"detail\": \"session_id를 찾을 수 없습니다.\"}".toResponseBody("application/json".toMediaType())
        coEvery { api.recommendations("unknown", null) } returns Response.error(404, errorBody)

        val result = repository.getRecommendations("unknown")

        assertTrue(result.isFailure)
        assertEquals("session_id를 찾을 수 없습니다.", result.exceptionOrNull()?.message)
    }

    @Test
    fun `diagnose surfaces age-limit-exceeded 403 message for logged-in member`() = runTest {
        val errorBody = (
            "{\"detail\": \"청년 상한(만 39세)을 초과하여 신규 진단을 이용할 수 없습니다" +
                "(만 나이: 40세). 과거 진단 기록은 삭제되지 않고 그대로 보관됩니다.\"}"
            ).toResponseBody("application/json".toMediaType())
        coEvery { api.diagnose(any()) } returns Response.error(403, errorBody)

        val result = repository.diagnose("35-39", "26440", "2500-3000", "월세", false)

        assertTrue(result.isFailure)
        assertEquals(
            "청년 상한(만 39세)을 초과하여 신규 진단을 이용할 수 없습니다" +
                "(만 나이: 40세). 과거 진단 기록은 삭제되지 않고 그대로 보관됩니다.",
            result.exceptionOrNull()?.message,
        )
    }

    @Test
    fun `getExplanation returns success body`() = runTest {
        val expected = ExplanationResponseDto(
            session_id = "s1",
            explanation = "주거비 부담이 커서 이 정책을 추천했어요.",
            is_llm_generated = true,
        )
        coEvery { api.explanation("s1", null) } returns Response.success(expected)

        val result = repository.getExplanation("s1")

        assertTrue(result.isSuccess)
        assertEquals(expected, result.getOrNull())
    }

    @Test
    fun `getExplanation surfaces 404 for unknown session`() = runTest {
        val errorBody = "{\"detail\": \"session_id를 찾을 수 없습니다.\"}".toResponseBody("application/json".toMediaType())
        coEvery { api.explanation("unknown", null) } returns Response.error(404, errorBody)

        val result = repository.getExplanation("unknown")

        assertTrue(result.isFailure)
        assertEquals("session_id를 찾을 수 없습니다.", result.exceptionOrNull()?.message)
    }

    @Test
    fun `getHistory returns success body`() = runTest {
        val diagnosisResult = buildJsonObject {
            put("risk_probability", 0.4f)
        }
        val expected = HistoryResponseDto(
            session_id = "s1",
            history = listOf(HistoryEntryDto(created_at = "2026-07-10T00:00:00Z", diagnosis_result = diagnosisResult)),
            note = "현재는 session_id 기준 단일 진단만 저장됩니다.",
        )
        coEvery { api.history("s1", null) } returns Response.success(expected)

        val result = repository.getHistory("s1")

        assertTrue(result.isSuccess)
        assertEquals(expected, result.getOrNull())
    }

    @Test
    fun `getHistory surfaces 404 for unknown session`() = runTest {
        val errorBody = "{\"detail\": \"session_id를 찾을 수 없습니다.\"}".toResponseBody("application/json".toMediaType())
        coEvery { api.history("unknown", null) } returns Response.error(404, errorBody)

        val result = repository.getHistory("unknown")

        assertTrue(result.isFailure)
        assertEquals("session_id를 찾을 수 없습니다.", result.exceptionOrNull()?.message)
    }
}
