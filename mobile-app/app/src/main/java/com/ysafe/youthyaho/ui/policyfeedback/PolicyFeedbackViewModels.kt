package com.ysafe.youthyaho.ui.policyfeedback

import androidx.lifecycle.ViewModel
import androidx.lifecycle.ViewModelProvider
import androidx.lifecycle.viewModelScope
import androidx.lifecycle.viewmodel.initializer
import androidx.lifecycle.viewmodel.viewModelFactory
import com.ysafe.youthyaho.data.api.ApiException
import com.ysafe.youthyaho.data.api.dto.FeedbackAnswerRequestDto
import com.ysafe.youthyaho.data.api.dto.FeedbackFormDto
import com.ysafe.youthyaho.data.api.dto.FeedbackSubmissionDto
import com.ysafe.youthyaho.data.api.dto.PolicyUsageDto
import com.ysafe.youthyaho.data.api.dto.RewardGrantDto
import com.ysafe.youthyaho.data.repository.PolicyFeedbackRepository
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch

fun policyFeedbackErrorMessage(error: Throwable): String = when ((error as? ApiException)?.code) {
    0 -> "서버에 연결할 수 없습니다. 잠시 후 다시 시도해 주세요."
    401 -> "로그인 후 내 정책 기록과 피드백 기능을 이용할 수 있습니다."
    403 -> "이 정책 기록을 변경할 권한이 없습니다."
    404 -> "정책 또는 이용 기록을 찾을 수 없습니다."
    409 -> "이미 내 정책에 추가되었거나 작성한 의견입니다. 내 정책 기록을 확인해 주세요."
    422 -> "현재 이용 단계에서는 요청한 작업을 진행할 수 없습니다."
    429 -> "요청이 많습니다. 잠시 후 다시 시도해 주세요."
    else -> "정책 이용 정보를 처리하지 못했습니다. 잠시 후 다시 시도해 주세요."
}

data class PolicyDetailUiState(
    val loading: Boolean = true,
    val usage: PolicyUsageDto? = null,
    val errorMessage: String? = null,
    val message: String? = null,
)

class PolicyDetailViewModel(
    private val repository: PolicyFeedbackRepository,
    private val policyId: String,
) : ViewModel() {
    private val _uiState = MutableStateFlow(PolicyDetailUiState())
    val uiState: StateFlow<PolicyDetailUiState> = _uiState.asStateFlow()

    init { load() }

    fun load() {
        viewModelScope.launch {
            repository.getUsages().fold(
                onSuccess = { usages ->
                    _uiState.value = PolicyDetailUiState(
                        loading = false,
                        usage = usages.firstOrNull { it.policy_id == policyId || it.policy_name == policyId },
                    )
                },
                onFailure = { _uiState.value = PolicyDetailUiState(false, errorMessage = policyFeedbackErrorMessage(it)) },
            )
        }
    }

    fun addToMyPolicies() = ensureStatus(null)
    fun recordApplicationStarted() = ensureStatus("application_started")
    fun recordApplied() = ensureStatus("applied")

    private fun ensureStatus(target: String?) {
        viewModelScope.launch {
            _uiState.value = _uiState.value.copy(loading = true, errorMessage = null, message = null)
            var usage = _uiState.value.usage
            if (usage == null) {
                val created = repository.createUsage(policyId)
                if (created.isFailure) {
                    // 경쟁 요청 또는 이미 존재하는 기록이면 목록을 새로 불러와 중복
                    // 생성을 시도하지 않고 기존 기록을 사용한다.
                    if ((created.exceptionOrNull() as? ApiException)?.code == 409) {
                        val usages = repository.getUsages().getOrElse {
                            _uiState.value = PolicyDetailUiState(false, errorMessage = policyFeedbackErrorMessage(it))
                            return@launch
                        }
                        usage = usages.firstOrNull { it.policy_id == policyId || it.policy_name == policyId }
                    } else {
                        _uiState.value = PolicyDetailUiState(false, errorMessage = policyFeedbackErrorMessage(created.exceptionOrNull()!!))
                        return@launch
                    }
                } else {
                    usage = created.getOrNull()
                }
            }
            if (target == null) {
                _uiState.value = PolicyDetailUiState(false, usage, message = "내 정책 기록에 추가했습니다.")
                return@launch
            }
            val path = when (target) {
                "application_started" -> listOf("application_started")
                "applied" -> listOf("application_started", "applied")
                else -> emptyList()
            }
            for (next in path) {
                if (usage?.current_status == next) continue
                if (next !in (usage?.next_allowed_statuses ?: emptyList())) continue
                val updated = repository.updateStatus(usage!!.usage_id, next)
                if (updated.isFailure) {
                    _uiState.value = PolicyDetailUiState(false, usage, errorMessage = policyFeedbackErrorMessage(updated.exceptionOrNull()!!))
                    return@launch
                }
                usage = updated.getOrNull()
            }
            _uiState.value = PolicyDetailUiState(
                false,
                usage,
                message = if (target == "applied") "신청 완료로 기록했습니다." else "신청 시작을 기록했습니다.",
            )
        }
    }

    companion object {
        fun factory(repository: PolicyFeedbackRepository, policyId: String): ViewModelProvider.Factory =
            viewModelFactory { initializer { PolicyDetailViewModel(repository, policyId) } }
    }
}

data class PolicyRecordsUiState(
    val loading: Boolean = true,
    val usages: List<PolicyUsageDto> = emptyList(),
    val errorMessage: String? = null,
)

class PolicyRecordsViewModel(private val repository: PolicyFeedbackRepository) : ViewModel() {
    private val _uiState = MutableStateFlow(PolicyRecordsUiState())
    val uiState: StateFlow<PolicyRecordsUiState> = _uiState.asStateFlow()

    init { load() }

    fun load() {
        viewModelScope.launch {
            repository.getUsages().fold(
                onSuccess = { _uiState.value = PolicyRecordsUiState(false, it) },
                onFailure = { _uiState.value = PolicyRecordsUiState(false, errorMessage = policyFeedbackErrorMessage(it)) },
            )
        }
    }

    fun updateStatus(usage: PolicyUsageDto, status: String) {
        if (status !in usage.next_allowed_statuses) return
        viewModelScope.launch {
            repository.updateStatus(usage.usage_id, status).fold(
                onSuccess = { updated ->
                    _uiState.value = _uiState.value.copy(
                        usages = _uiState.value.usages.map { if (it.usage_id == updated.usage_id) updated else it },
                    )
                },
                onFailure = { _uiState.value = _uiState.value.copy(errorMessage = policyFeedbackErrorMessage(it)) },
            )
        }
    }

    companion object {
        fun factory(repository: PolicyFeedbackRepository): ViewModelProvider.Factory =
            viewModelFactory { initializer { PolicyRecordsViewModel(repository) } }
    }
}

data class FeedbackFormUiState(
    val loading: Boolean = true,
    val form: FeedbackFormDto? = null,
    val selections: Map<String, String> = emptyMap(),
    val otherText: String = "",
    val submitting: Boolean = false,
    val submission: FeedbackSubmissionDto? = null,
    val errorMessage: String? = null,
) {
    val answeredCount: Int get() = form?.questions?.count { selections[it.question_code] != null } ?: 0
    val canSubmit: Boolean get() = form?.questions?.all { question ->
        selections[question.question_code] != null &&
            !(question.allows_other_text && selections[question.question_code] == "기타" && otherText.isBlank())
    } == true && !submitting
}

class FeedbackFormViewModel(
    private val repository: PolicyFeedbackRepository,
    private val usageId: String,
    private val policyId: String,
    private val stage: String,
) : ViewModel() {
    private val _uiState = MutableStateFlow(FeedbackFormUiState())
    val uiState: StateFlow<FeedbackFormUiState> = _uiState.asStateFlow()

    init {
        viewModelScope.launch {
            repository.getForm(policyId, stage).fold(
                onSuccess = { _uiState.value = FeedbackFormUiState(false, form = it) },
                onFailure = { _uiState.value = FeedbackFormUiState(false, errorMessage = policyFeedbackErrorMessage(it)) },
            )
        }
    }

    fun select(questionCode: String, choice: String) {
        val updated = _uiState.value.selections + (questionCode to choice)
        val clearsOther = _uiState.value.form?.questions
            ?.firstOrNull { it.question_code == questionCode }?.allows_other_text == true && choice != "기타"
        _uiState.value = _uiState.value.copy(
            selections = updated,
            otherText = if (clearsOther) "" else _uiState.value.otherText,
        )
    }

    fun changeOtherText(value: String) {
        val max = _uiState.value.form?.other_text_max_length ?: 200
        _uiState.value = _uiState.value.copy(otherText = value.take(max))
    }

    fun submit() {
        val state = _uiState.value
        if (!state.canSubmit || state.form == null) return
        val answers = state.form.questions.map { question ->
            val choice = state.selections.getValue(question.question_code)
            FeedbackAnswerRequestDto(
                question_code = question.question_code,
                choice = choice,
                other_text = if (question.allows_other_text && choice == "기타") state.otherText.trim() else null,
            )
        }
        viewModelScope.launch {
            _uiState.value = _uiState.value.copy(submitting = true, errorMessage = null)
            repository.submit(usageId, stage, answers).fold(
                onSuccess = { _uiState.value = _uiState.value.copy(submitting = false, submission = it) },
                onFailure = { _uiState.value = _uiState.value.copy(submitting = false, errorMessage = policyFeedbackErrorMessage(it)) },
            )
        }
    }

    companion object {
        fun factory(
            repository: PolicyFeedbackRepository,
            usageId: String,
            policyId: String,
            stage: String,
        ): ViewModelProvider.Factory = viewModelFactory {
            initializer { FeedbackFormViewModel(repository, usageId, policyId, stage) }
        }
    }
}

data class RewardsUiState(
    val loading: Boolean = true,
    val rewards: List<RewardGrantDto> = emptyList(),
    val errorMessage: String? = null,
) {
    val pendingAmount: Int get() = rewards.filter { it.status == "pending" }.sumOf { it.amount }
    val mockPaidAmount: Int get() = rewards.filter { it.status == "mock_paid" }.sumOf { it.amount }
}

class RewardsViewModel(private val repository: PolicyFeedbackRepository) : ViewModel() {
    private val _uiState = MutableStateFlow(RewardsUiState())
    val uiState: StateFlow<RewardsUiState> = _uiState.asStateFlow()

    init {
        viewModelScope.launch {
            repository.getRewards().fold(
                onSuccess = { _uiState.value = RewardsUiState(false, it) },
                onFailure = { _uiState.value = RewardsUiState(false, errorMessage = policyFeedbackErrorMessage(it)) },
            )
        }
    }

    companion object {
        fun factory(repository: PolicyFeedbackRepository): ViewModelProvider.Factory =
            viewModelFactory { initializer { RewardsViewModel(repository) } }
    }
}
