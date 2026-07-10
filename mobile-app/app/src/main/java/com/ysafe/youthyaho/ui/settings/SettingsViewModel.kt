package com.ysafe.youthyaho.ui.settings

import androidx.lifecycle.ViewModel
import androidx.lifecycle.ViewModelProvider
import androidx.lifecycle.viewModelScope
import androidx.lifecycle.viewmodel.initializer
import androidx.lifecycle.viewmodel.viewModelFactory
import com.ysafe.youthyaho.data.local.TokenStore
import com.ysafe.youthyaho.data.repository.AuthRepository
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.combine
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch

data class SettingsUiState(
    val notificationsEnabled: Boolean = false,
    val isLoggedIn: Boolean = false,
    val showDeleteConfirmDialog: Boolean = false,
    val deleteRequestSubmitted: Boolean = false,
)

class SettingsViewModel(
    private val tokenStore: TokenStore,
    private val authRepository: AuthRepository,
) : ViewModel() {

    private val _uiState = MutableStateFlow(SettingsUiState())
    val uiState: StateFlow<SettingsUiState> = _uiState.asStateFlow()

    init {
        viewModelScope.launch {
            combine(tokenStore.notificationsOptInFlow, tokenStore.isLoggedInFlow) { notificationsEnabled, isLoggedIn ->
                notificationsEnabled to isLoggedIn
            }.collect { (notificationsEnabled, isLoggedIn) ->
                _uiState.update { it.copy(notificationsEnabled = notificationsEnabled, isLoggedIn = isLoggedIn) }
            }
        }
    }

    fun setNotificationsEnabled(enabled: Boolean) {
        viewModelScope.launch { tokenStore.setNotificationsOptIn(enabled) }
    }

    fun requestDeleteAccount() {
        _uiState.update { it.copy(showDeleteConfirmDialog = true) }
    }

    fun dismissDeleteDialog() {
        _uiState.update { it.copy(showDeleteConfirmDialog = false) }
    }

    // 백엔드에 실제 삭제 API가 없어(doc11 Must/Should 목록에도 없음) 서버 호출 없이
    // 로컬 확인 다이얼로그 + "접수됨" 상태만 보여주는 스텁이다.
    fun confirmDeleteRequest() {
        _uiState.update { it.copy(showDeleteConfirmDialog = false, deleteRequestSubmitted = true) }
    }

    fun logout() {
        viewModelScope.launch { authRepository.logout() }
    }

    companion object {
        fun factory(tokenStore: TokenStore, authRepository: AuthRepository): ViewModelProvider.Factory =
            viewModelFactory {
                initializer { SettingsViewModel(tokenStore, authRepository) }
            }
    }
}
