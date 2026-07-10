package com.ysafe.youthyaho.ui.auth

import com.ysafe.youthyaho.MainDispatcherRule
import com.ysafe.youthyaho.data.api.ApiException
import com.ysafe.youthyaho.data.repository.AuthRepository
import io.mockk.coEvery
import io.mockk.mockk
import kotlinx.coroutines.test.runTest
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Rule
import org.junit.Test

class LoginViewModelTest {

    @get:Rule
    val mainDispatcherRule = MainDispatcherRule()

    private val authRepository: AuthRepository = mockk()

    @Test
    fun `login success updates state and clears error`() = runTest {
        coEvery { authRepository.login("a@test.com", "password1234") } returns Result.success(Unit)
        val viewModel = LoginViewModel(authRepository)
        viewModel.onEmailChange("a@test.com")
        viewModel.onPasswordChange("password1234")

        viewModel.login()

        val state = viewModel.uiState.value
        assertTrue(state.loginSucceeded)
        assertFalse(state.isLoading)
        assertNull(state.errorMessage)
    }

    @Test
    fun `login failure surfaces backend error message`() = runTest {
        coEvery { authRepository.login(any(), any()) } returns
            Result.failure(ApiException(401, "이메일 또는 비밀번호가 올바르지 않습니다."))
        val viewModel = LoginViewModel(authRepository)
        viewModel.onEmailChange("a@test.com")
        viewModel.onPasswordChange("wrong-password")

        viewModel.login()

        val state = viewModel.uiState.value
        assertFalse(state.loginSucceeded)
        assertEquals("이메일 또는 비밀번호가 올바르지 않습니다.", state.errorMessage)
    }

    @Test
    fun `login blocked client-side when fields blank`() = runTest {
        val viewModel = LoginViewModel(authRepository)

        viewModel.login()

        assertEquals("이메일과 비밀번호를 모두 입력해주세요.", viewModel.uiState.value.errorMessage)
        assertFalse(viewModel.uiState.value.loginSucceeded)
    }
}
