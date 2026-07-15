package com.ysafe.youthyaho.ui.recommendation

import androidx.lifecycle.ViewModel
import androidx.lifecycle.ViewModelProvider
import androidx.lifecycle.viewModelScope
import androidx.lifecycle.viewmodel.initializer
import androidx.lifecycle.viewmodel.viewModelFactory
import com.ysafe.youthyaho.data.api.ApiException
import com.ysafe.youthyaho.data.api.dto.OtherPolicyItemDto
import com.ysafe.youthyaho.data.api.dto.RecommendationItemDto
import com.ysafe.youthyaho.data.repository.DiagnosisRepository
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch

// doc09: "정책 추천: 우선순위 top3 정책 카드". 백엔드는 정책 카탈로그 전체를
// 우선순위순으로 반환하므로(관리자 화면 등 다른 소비자도 있을 수 있어 API 자체를
// 3개로 제한하지 않음), 화면에서 상위 3개만 잘라 보여준다.
private const val TOP_N = 3

data class RecommendationUiState(
    val isLoading: Boolean = true,
    val errorMessage: String? = null,
    val topRecommendations: List<RecommendationItemDto> = emptyList(),
    val otherPolicies: List<OtherPolicyItemDto> = emptyList(),
)

class RecommendationViewModel(
    private val diagnosisRepository: DiagnosisRepository,
    private val sessionId: String,
) : ViewModel() {

    private val _uiState = MutableStateFlow(RecommendationUiState())
    val uiState: StateFlow<RecommendationUiState> = _uiState.asStateFlow()

    init {
        load()
    }

    fun retry() {
        _uiState.value = RecommendationUiState(isLoading = true)
        load()
    }

    private fun load() {
        viewModelScope.launch {
            val result = diagnosisRepository.getRecommendations(sessionId)
            result.fold(
                onSuccess = { response ->
                    _uiState.value = RecommendationUiState(
                        isLoading = false,
                        topRecommendations = response.recommendations.sortedBy { it.priority }.take(TOP_N),
                        otherPolicies = response.other_policies,
                    )
                },
                onFailure = { error ->
                    val message = (error as? ApiException)?.message ?: "정책 추천을 불러오지 못했습니다."
                    _uiState.value = RecommendationUiState(isLoading = false, errorMessage = message)
                },
            )
        }
    }

    companion object {
        fun factory(diagnosisRepository: DiagnosisRepository, sessionId: String): ViewModelProvider.Factory =
            viewModelFactory {
                initializer { RecommendationViewModel(diagnosisRepository, sessionId) }
            }
    }
}
