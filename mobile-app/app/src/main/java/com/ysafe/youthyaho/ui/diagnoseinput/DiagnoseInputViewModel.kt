package com.ysafe.youthyaho.ui.diagnoseinput

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

data class DiagnoseInputUiState(
    val ageGroup: String? = null,
    val dongCode: String = "",
    val incomeBand: String? = null,
    val housingType: String? = null,
    val hasDebt: Boolean = false,
    val isLoading: Boolean = false,
    val errorMessage: String? = null,
    // 성공 시에만 채워짐 - null이 아니게 되면 화면이 다음(진단결과)으로 이동한다.
    val sessionId: String? = null,
)

class DiagnoseInputViewModel(private val diagnosisRepository: DiagnosisRepository) : ViewModel() {

    private val _uiState = MutableStateFlow(DiagnoseInputUiState())
    val uiState: StateFlow<DiagnoseInputUiState> = _uiState.asStateFlow()

    fun onAgeGroupSelect(value: String) {
        _uiState.value = _uiState.value.copy(ageGroup = value, errorMessage = null)
    }

    fun onDongCodeChange(value: String) {
        _uiState.value = _uiState.value.copy(dongCode = value, errorMessage = null)
    }

    fun onIncomeBandSelect(value: String) {
        _uiState.value = _uiState.value.copy(incomeBand = value, errorMessage = null)
    }

    fun onHousingTypeSelect(value: String) {
        _uiState.value = _uiState.value.copy(housingType = value, errorMessage = null)
    }

    fun onHasDebtChange(value: Boolean) {
        _uiState.value = _uiState.value.copy(hasDebt = value)
    }

    fun submit() {
        val current = _uiState.value
        val ageGroup = current.ageGroup
        val incomeBand = current.incomeBand
        val housingType = current.housingType

        if (ageGroup == null || incomeBand == null || housingType == null || current.dongCode.isBlank()) {
            _uiState.value = current.copy(errorMessage = "모든 항목을 선택/입력해주세요.")
            return
        }

        _uiState.value = current.copy(isLoading = true, errorMessage = null)
        viewModelScope.launch {
            val result = diagnosisRepository.diagnose(
                ageGroup = ageGroup,
                dongCode = current.dongCode.trim(),
                incomeBand = incomeBand,
                housingType = housingType,
                hasDebt = current.hasDebt,
            )
            result.fold(
                onSuccess = { response ->
                    _uiState.value = _uiState.value.copy(isLoading = false, sessionId = response.session_id)
                },
                onFailure = { error ->
                    val message = (error as? ApiException)?.message ?: "진단 중 오류가 발생했습니다."
                    _uiState.value = _uiState.value.copy(isLoading = false, errorMessage = message)
                },
            )
        }
    }

    companion object {
        fun factory(diagnosisRepository: DiagnosisRepository): ViewModelProvider.Factory = viewModelFactory {
            initializer { DiagnoseInputViewModel(diagnosisRepository) }
        }
    }
}
