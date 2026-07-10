package com.ysafe.youthyaho.data.repository

import com.ysafe.youthyaho.data.api.CitizenApiService
import com.ysafe.youthyaho.data.api.dto.SignupResponseDto
import com.ysafe.youthyaho.data.api.dto.TokenResponseDto
import com.ysafe.youthyaho.data.local.TokenStore
import io.mockk.coEvery
import io.mockk.coVerify
import io.mockk.mockk
import kotlinx.coroutines.test.runTest
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.ResponseBody.Companion.toResponseBody
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test
import retrofit2.Response

class AuthRepositoryTest {

    private lateinit var api: CitizenApiService
    private lateinit var tokenStore: TokenStore
    private lateinit var repository: AuthRepository

    @Before
    fun setUp() {
        api = mockk()
        tokenStore = mockk(relaxed = true)
        repository = AuthRepository(api, tokenStore)
    }

    @Test
    fun `signup returns success body on 201`() = runTest {
        val expected = SignupResponseDto(user_id = "u1", email = "a@test.com", is_age_verified = false)
        coEvery { api.signup(any()) } returns Response.success(201, expected)

        val result = repository.signup("a@test.com", "password1234", "2000-01-01", null)

        assertTrue(result.isSuccess)
        assertEquals(expected, result.getOrNull())
    }

    @Test
    fun `signup surfaces backend detail message on 409 duplicate email`() = runTest {
        val errorBody = """{"detail": "이미 가입된 이메일입니다: a@test.com"}"""
            .toResponseBody("application/json".toMediaType())
        coEvery { api.signup(any()) } returns Response.error(409, errorBody)

        val result = repository.signup("a@test.com", "password1234", "2000-01-01", null)

        assertTrue(result.isFailure)
        assertEquals("이미 가입된 이메일입니다: a@test.com", result.exceptionOrNull()?.message)
    }

    @Test
    fun `signup surfaces backend detail message on 400 age limit exceeded`() = runTest {
        val errorBody = """{"detail": "청년 상한(만 39세)을 초과하여 가입할 수 없습니다(만 나이: 40세)."}"""
            .toResponseBody("application/json".toMediaType())
        coEvery { api.signup(any()) } returns Response.error(400, errorBody)

        val result = repository.signup("old@test.com", "password1234", "1985-01-01", null)

        assertTrue(result.isFailure)
        assertEquals(
            "청년 상한(만 39세)을 초과하여 가입할 수 없습니다(만 나이: 40세).",
            result.exceptionOrNull()?.message,
        )
    }

    @Test
    fun `login saves tokens on success`() = runTest {
        val tokens = TokenResponseDto(access_token = "access", refresh_token = "refresh", token_type = "bearer")
        coEvery { api.login(any()) } returns Response.success(tokens)

        val result = repository.login("a@test.com", "password1234")

        assertTrue(result.isSuccess)
        coVerify { tokenStore.saveTokens("access", "refresh") }
    }

    @Test
    fun `login does not save tokens on failure`() = runTest {
        val errorBody = """{"detail": "이메일 또는 비밀번호가 올바르지 않습니다."}"""
            .toResponseBody("application/json".toMediaType())
        coEvery { api.login(any()) } returns Response.error(401, errorBody)

        val result = repository.login("a@test.com", "wrong")

        assertTrue(result.isFailure)
        coVerify(exactly = 0) { tokenStore.saveTokens(any(), any()) }
    }

    @Test
    fun `logout clears token store`() = runTest {
        repository.logout()

        coVerify { tokenStore.clear() }
    }
}
