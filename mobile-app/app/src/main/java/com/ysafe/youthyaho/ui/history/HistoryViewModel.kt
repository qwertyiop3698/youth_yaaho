package com.ysafe.youthyaho.ui.history

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
import kotlinx.serialization.json.JsonElement
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.JsonPrimitive
import kotlinx.serialization.json.floatOrNull

data class HistoryUiState(
    val isLoading: Boolean = true,
    val errorMessage: String? = null,
    val createdAt: String? = null,
    val note: String? = null,
    val domainIndices: Map<String, Float> = emptyMap(),
    val clusterMembership: Map<String, Float> = emptyMap(),
    val riskProbability: Float? = null,
)

class HistoryViewModel(
    private val diagnosisRepository: DiagnosisRepository,
    private val sessionId: String,
) : ViewModel() {

    private val _uiState = MutableStateFlow(HistoryUiState())
    val uiState: StateFlow<HistoryUiState> = _uiState.asStateFlow()

    init {
        load()
    }

    fun retry() {
        _uiState.value = HistoryUiState(isLoading = true)
        load()
    }

    private fun load() {
        viewModelScope.launch {
            val result = diagnosisRepository.getHistory(sessionId)
            result.fold(
                onSuccess = { response ->
                    // 백엔드가 session_id당 진단 1건만 저장하므로(note 필드가 이미
                    // 밝히는 한계) history 리스트의 첫 항목만 쓴다.
                    val entry = response.history.firstOrNull()
                    val diagnosisResult = entry?.diagnosis_result
                    _uiState.value = HistoryUiState(
                        isLoading = false,
                        createdAt = entry?.created_at,
                        note = response.note,
                        domainIndices = diagnosisResult.extractFloatMap("domain_indices"),
                        clusterMembership = diagnosisResult.extractFloatMap("cluster_membership"),
                        riskProbability = diagnosisResult.extractFloat("risk_probability"),
                    )
                },
                onFailure = { error ->
                    val message = (error as? ApiException)?.message ?: "히스토리를 불러오지 못했습니다."
                    _uiState.value = HistoryUiState(isLoading = false, errorMessage = message)
                },
            )
        }
    }

    companion object {
        fun factory(diagnosisRepository: DiagnosisRepository, sessionId: String): ViewModelProvider.Factory =
            viewModelFactory {
                initializer { HistoryViewModel(diagnosisRepository, sessionId) }
            }
    }
}

// kotlinx.serialization의 .jsonObject/.jsonPrimitive 확장은 타입이 안 맞으면
// 예외를 던진다(as? 캐스트가 아니라 강제 캐스트라서). 백엔드가 표본부족 등으로
// risk_probability를 null로 채워 보낼 수 있고(diagnose_service.py), 과거에 저장된
// 히스토리는 스키마가 지금과 다를 수도 있으므로 - 키 누락/명시적 null/타입 불일치
// 전부 크래시 없이 "데이터 없음"으로 떨어지도록 as? 캐스트만 쓴다.
private fun JsonElement?.extractFloatMap(key: String): Map<String, Float> =
    (this as? JsonObject)?.get(key)?.let { it as? JsonObject }
        ?.mapValues { (_, value) -> (value as? JsonPrimitive)?.floatOrNull ?: 0f }
        ?: emptyMap()

private fun JsonElement?.extractFloat(key: String): Float? =
    (this as? JsonObject)?.get(key)?.let { it as? JsonPrimitive }?.floatOrNull
