package com.ysafe.youthyaho.ui.auth

import com.ysafe.youthyaho.MainDispatcherRule
import com.ysafe.youthyaho.data.api.ApiException
import com.ysafe.youthyaho.data.api.dto.SignupResponseDto
import com.ysafe.youthyaho.data.repository.AuthRepository
import io.mockk.coEvery
import io.mockk.mockk
import kotlinx.coroutines.test.runTest
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Rule
import org.junit.Test

class SignupViewModelTest {

    @get:Rule
    val mainDispatcherRule = MainDispatcherRule()

    private val authRepository: AuthRepository = mockk()

    @Test
    fun `signup success marks state succeeded`() = runTest {
        coEvery { authRepository.signup(any(), any(), any(), any()) } returns
            Result.success(SignupResponseDto(user_id = "u1", email = "a@test.com", is_age_verified = false))
        val viewModel = SignupViewModel(authRepository)
        fillValidForm(viewModel)

        viewModel.signup()

        assertTrue(viewModel.uiState.value.signupSucceeded)
    }

    @Test
    fun `signup rejected for age over 39 surfaces backend message`() = runTest {
        coEvery { authRepository.signup(any(), any(), any(), any()) } returns
            Result.failure(ApiException(400, "청년 상한(만 39세)을 초과하여 가입할 수 없습니다(만 나이: 40세)."))
        val viewModel = SignupViewModel(authRepository)
        fillValidForm(viewModel)

        viewModel.signup()

        val state = viewModel.uiState.value
        assertFalse(state.signupSucceeded)
        assertEquals("청년 상한(만 39세)을 초과하여 가입할 수 없습니다(만 나이: 40세).", state.errorMessage)
    }

    @Test
    fun `signup blocked client-side for short password`() = runTest {
        val viewModel = SignupViewModel(authRepository)
        viewModel.onEmailChange("a@test.com")
        viewModel.onPasswordChange("short")
        viewModel.onBirthdateChange("2000-01-01")

        viewModel.signup()

        assertEquals("비밀번호는 8자 이상이어야 해요.", viewModel.uiState.value.errorMessage)
    }

    @Test
    fun `signup blocked client-side for malformed birthdate`() = runTest {
        val viewModel = SignupViewModel(authRepository)
        viewModel.onEmailChange("a@test.com")
        viewModel.onPasswordChange("password1234")
        viewModel.onBirthdateChange("2000/01/01")

        viewModel.signup()

        assertEquals("생년월일을 YYYY-MM-DD 형식으로 입력해주세요.", viewModel.uiState.value.errorMessage)
    }

    private fun fillValidForm(viewModel: SignupViewModel) {
        viewModel.onEmailChange("a@test.com")
        viewModel.onPasswordChange("password1234")
        viewModel.onBirthdateChange("2000-01-01")
    }
}
