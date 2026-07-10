package com.ysafe.youthyaho.ui.explanation

import androidx.lifecycle.ViewModel
import androidx.lifecycle.ViewModelProvider
import androidx.lifecycle.viewModelScope
import androidx.lifecycle.viewmodel.initializer
import androidx.lifecycle.viewmodel.viewModelFactory
import com.ysafe.youthyaho.data.api.ApiException
import com.ysafe.youthyaho.data.repository.DiagnosisRepository
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch

data class ExplanationUiState(
    val isLoading: Boolean = true,
    val errorMessage: String? = null,
    val explanation: String? = null,
    val isLlmGenerated: Boolean = false,
)

class ExplanationViewModel(
    private val diagnosisRepository: DiagnosisRepository,
    private val sessionId: String,
) : ViewModel() {

    private val _uiState = MutableStateFlow(ExplanationUiState())
    val uiState: StateFlow<ExplanationUiState> = _uiState.asStateFlow()

    init {
        load()
    }

    fun retry() {
        _uiState.value = ExplanationUiState(isLoading = true)
        load()
    }

    private fun load() {
        viewModelScope.launch {
            // 백엔드가 세션에 캐싱해서 재요청해도 재호출 안 하니(citizen.py), 여기서
            // 매번 그냥 호출한다 - 화면을 다시 봐도 저장된 설명을 그대로 받는다.
            val result = diagnosisRepository.getExplanation(sessionId)
            result.fold(
                onSuccess = { response ->
                    _uiState.value = ExplanationUiState(
                        isLoading = false,
                        explanation = response.explanation,
                        isLlmGenerated = response.is_llm_generated,
                    )
                },
                onFailure = { error ->
                    val message = (error as? ApiException)?.message ?: "설명을 불러오지 못했습니다."
                    _uiState.value = ExplanationUiState(isLoading = false, errorMessage = message)
                },
            )
        }
    }

    companion object {
        fun factory(diagnosisRepository: DiagnosisRepository, sessionId: String): ViewModelProvider.Factory =
            viewModelFactory {
                initializer { ExplanationViewModel(diagnosisRepository, sessionId) }
            }
    }
}
