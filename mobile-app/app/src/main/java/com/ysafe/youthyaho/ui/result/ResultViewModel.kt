package com.ysafe.youthyaho.ui.result

import androidx.lifecycle.ViewModel
import androidx.lifecycle.ViewModelProvider
import androidx.lifecycle.viewmodel.initializer
import androidx.lifecycle.viewmodel.viewModelFactory
import com.ysafe.youthyaho.data.api.dto.DiagnoseResponseDto
import com.ysafe.youthyaho.data.repository.DiagnosisRepository
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow

data class ResultUiState(
    val result: DiagnoseResponseDto? = null,
    // 이번 앱 실행에서 diagnose()를 거치지 않고 이 화면에 온 경우(캐시 미스) true.
    val notFound: Boolean = false,
)

class ResultViewModel(
    diagnosisRepository: DiagnosisRepository,
    sessionId: String,
) : ViewModel() {

    private val _uiState = MutableStateFlow(ResultUiState())
    val uiState: StateFlow<ResultUiState> = _uiState.asStateFlow()

    init {
        val cached = diagnosisRepository.getCachedResult(sessionId)
        _uiState.value = if (cached != null) ResultUiState(result = cached) else ResultUiState(notFound = true)
    }

    companion object {
        fun factory(diagnosisRepository: DiagnosisRepository, sessionId: String): ViewModelProvider.Factory =
            viewModelFactory {
                initializer { ResultViewModel(diagnosisRepository, sessionId) }
            }
    }
}
