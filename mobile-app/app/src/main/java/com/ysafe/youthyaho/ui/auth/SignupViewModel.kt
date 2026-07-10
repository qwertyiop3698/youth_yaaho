package com.ysafe.youthyaho.ui.auth

import androidx.lifecycle.ViewModel
import androidx.lifecycle.ViewModelProvider
import androidx.lifecycle.viewModelScope
import androidx.lifecycle.viewmodel.initializer
import androidx.lifecycle.viewmodel.viewModelFactory
import com.ysafe.youthyaho.data.api.ApiException
import com.ysafe.youthyaho.data.repository.AuthRepository
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch

private val BIRTHDATE_REGEX = Regex("""^\d{4}-\d{2}-\d{2}$""")
private const val MIN_PASSWORD_LENGTH = 8 // backend SignupRequest.password min_length=8와 일치시킴

data class SignupUiState(
    val email: String = "",
    val password: String = "",
    val birthdate: String = "", // "YYYY-MM-DD" - MVP라 DatePicker 대신 텍스트 입력(placeholder로 형식 안내)
    val dongCode: String = "",
    val isLoading: Boolean = false,
    val errorMessage: String? = null,
    val signupSucceeded: Boolean = false,
)

class SignupViewModel(private val authRepository: AuthRepository) : ViewModel() {

    private val _uiState = MutableStateFlow(SignupUiState())
    val uiState: StateFlow<SignupUiState> = _uiState.asStateFlow()

    fun onEmailChange(value: String) {
        _uiState.value = _uiState.value.copy(email = value, errorMessage = null)
    }

    fun onPasswordChange(value: String) {
        _uiState.value = _uiState.value.copy(password = value, errorMessage = null)
    }

    fun onBirthdateChange(value: String) {
        _uiState.value = _uiState.value.copy(birthdate = value, errorMessage = null)
    }

    fun onDongCodeChange(value: String) {
        _uiState.value = _uiState.value.copy(dongCode = value, errorMessage = null)
    }

    fun signup() {
        val current = _uiState.value
        val validationError = validate(current)
        if (validationError != null) {
            _uiState.value = current.copy(errorMessage = validationError)
            return
        }

        _uiState.value = current.copy(isLoading = true, errorMessage = null)
        viewModelScope.launch {
            val result = authRepository.signup(
                email = current.email.trim(),
                password = current.password,
                birthdate = current.birthdate.trim(),
                dongCode = current.dongCode.trim().ifBlank { null },
            )
            result.fold(
                onSuccess = {
                    _uiState.value = _uiState.value.copy(isLoading = false, signupSucceeded = true)
                },
                onFailure = { error ->
                    // 400(만39세 초과)/409(이메일 중복) 모두 백엔드가 사람이 읽을 detail
                    // 메시지를 내려주므로 그대로 보여준다(app/services/auth_service.py 참고).
                    val message = (error as? ApiException)?.message ?: "회원가입 중 오류가 발생했습니다."
                    _uiState.value = _uiState.value.copy(isLoading = false, errorMessage = message)
                },
            )
        }
    }

    private fun validate(state: SignupUiState): String? = when {
        state.email.isBlank() -> "이메일을 입력해주세요."
        state.password.length < MIN_PASSWORD_LENGTH -> "비밀번호는 ${MIN_PASSWORD_LENGTH}자 이상이어야 해요."
        !BIRTHDATE_REGEX.matches(state.birthdate.trim()) -> "생년월일을 YYYY-MM-DD 형식으로 입력해주세요."
        else -> null
    }

    companion object {
        fun factory(authRepository: AuthRepository): ViewModelProvider.Factory = viewModelFactory {
            initializer { SignupViewModel(authRepository) }
        }
    }
}
