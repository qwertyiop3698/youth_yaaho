package com.ysafe.youthyaho.ui.policydemand

import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Button
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.RadioButton
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import androidx.lifecycle.ViewModel
import androidx.lifecycle.ViewModelProvider
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewmodel.initializer
import androidx.lifecycle.viewmodel.viewModelFactory
import androidx.lifecycle.viewModelScope
import com.ysafe.youthyaho.data.api.ApiException
import com.ysafe.youthyaho.data.api.dto.DemandFormDto
import com.ysafe.youthyaho.data.api.dto.DemandSubmissionDto
import com.ysafe.youthyaho.data.api.dto.SubmitDemandRequestDto
import com.ysafe.youthyaho.data.repository.PolicyDemandRepository
import com.ysafe.youthyaho.ui.common.ErrorContent
import com.ysafe.youthyaho.ui.common.LoadingIndicator
import com.ysafe.youthyaho.ui.common.YouthYahoScaffold
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch

data class DemandUiState(
    val loading: Boolean = true,
    val submitting: Boolean = false,
    val form: DemandFormDto? = null,
    val answers: Map<String, String> = emptyMap(),
    val otherText: String = "",
    val error: String? = null,
    val completed: DemandSubmissionDto? = null,
)

class PolicyDemandViewModel(
    private val repository: PolicyDemandRepository,
    private val sessionId: String,
    private val triggerReason: String,
) : ViewModel() {
    private val _state = MutableStateFlow(DemandUiState())
    val state: StateFlow<DemandUiState> = _state.asStateFlow()

    init {
        viewModelScope.launch {
            repository.form().fold(
                onSuccess = { _state.value = DemandUiState(loading = false, form = it) },
                onFailure = { _state.value = DemandUiState(loading = false, error = "수요 설문을 불러오지 못했습니다.") },
            )
        }
    }

    fun select(code: String, value: String) {
        _state.value = _state.value.copy(answers = _state.value.answers + (code to value), error = null)
    }

    fun updateOther(value: String) {
        val max = _state.value.form?.otherTextMaxLength ?: 200
        _state.value = _state.value.copy(otherText = value.take(max))
    }

    fun submit() {
        val current = _state.value
        val form = current.form ?: return
        if (form.questions.filter { it.required }.any { current.answers[it.code].isNullOrBlank() }) {
            _state.value = current.copy(error = "필수 4문항에 모두 응답해주세요.")
            return
        }
        val otherSelected = current.answers.values.any { it == "기타" }
        if (otherSelected && current.otherText.isBlank()) {
            _state.value = current.copy(error = "기타 선택 내용을 입력해주세요.")
            return
        }
        val request = SubmitDemandRequestDto(
            sessionId, triggerReason, current.answers.getValue("need_area"), current.answers.getValue("duration"),
            current.answers.getValue("amount"), current.answers.getValue("barrier"), current.answers["companion_support"],
            current.answers["employment_status"], current.otherText.trim().takeIf { otherSelected },
        )
        _state.value = current.copy(submitting = true, error = null)
        viewModelScope.launch {
            repository.submit(request).fold(
                onSuccess = { _state.value = _state.value.copy(submitting = false, completed = it) },
                onFailure = { error ->
                    _state.value = _state.value.copy(
                        submitting = false,
                        error = if ((error as? ApiException)?.code == 409) {
                            "동일한 수요는 90일 이후 다시 참여할 수 있습니다."
                        } else {
                            "제출하지 못했습니다. 잠시 후 다시 시도해주세요."
                        },
                    )
                },
            )
        }
    }

    companion object {
        fun factory(repository: PolicyDemandRepository, sessionId: String, triggerReason: String): ViewModelProvider.Factory =
            viewModelFactory { initializer { PolicyDemandViewModel(repository, sessionId, triggerReason) } }
    }
}

@Composable
fun PolicyDemandScreen(
    viewModel: PolicyDemandViewModel,
    onBack: () -> Unit,
    onDone: () -> Unit,
    modifier: Modifier = Modifier,
) {
    val state by viewModel.state.collectAsStateWithLifecycle()
    YouthYahoScaffold(title = "지금 필요한 지원", onBack = onBack, modifier = modifier) { paddingValues ->
    Column(Modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(paddingValues).padding(24.dp)) {
        when {
            state.loading -> LoadingIndicator()
            state.completed != null -> {
                Text(
                    "의견이 익명 정책 개선 자료에 반영되었습니다.",
                    style = MaterialTheme.typography.titleMedium,
                    modifier = Modifier.padding(top = 24.dp),
                )
                Text(
                    "동백전 Mock 리워드 ${state.completed?.reward?.amount}원 · ${state.completed?.reward?.status}",
                    modifier = Modifier.padding(top = 8.dp),
                )
                Button(onClick = onDone, modifier = Modifier.fillMaxWidth().padding(top = 24.dp)) {
                    Text("추천 화면으로 돌아가기")
                }
            }
            state.form != null -> {
                val form = state.form!!
                val requiredDone = form.questions.filter { it.required }.count { !state.answers[it.code].isNullOrBlank() }
                LinearProgressIndicator(progress = { requiredDone / 4f }, modifier = Modifier.fillMaxWidth().padding(top = 16.dp))
                Text(form.notice, style = MaterialTheme.typography.bodySmall, modifier = Modifier.padding(top = 12.dp))
                Text(
                    "완료 시 동백전 Mock 리워드 ${form.expectedRewardAmount}원 · 동일 수요 ${form.cooldownDays}일 재참여 제한",
                    modifier = Modifier.padding(top = 8.dp),
                )
                form.questions.forEachIndexed { index, question ->
                    Text(
                        "${index + 1}. ${question.prompt}${if (question.required) " *" else " (선택)"}",
                        style = MaterialTheme.typography.titleMedium,
                        modifier = Modifier.padding(top = 24.dp),
                    )
                    question.options.forEach { option ->
                        Row(verticalAlignment = Alignment.CenterVertically) {
                            RadioButton(selected = state.answers[question.code] == option, onClick = { viewModel.select(question.code, option) })
                            Text(option)
                        }
                    }
                }
                if (state.answers.values.any { it == "기타" }) {
                    OutlinedTextField(
                        value = state.otherText,
                        onValueChange = viewModel::updateOther,
                        label = { Text("기타 의견") },
                        supportingText = { Text("${state.otherText.length}/${form.otherTextMaxLength}") },
                        modifier = Modifier.fillMaxWidth().padding(top = 16.dp),
                    )
                }
                state.error?.let { ErrorContent(message = it, modifier = Modifier.padding(top = 12.dp)) }
                Button(onClick = viewModel::submit, enabled = !state.submitting, modifier = Modifier.fillMaxWidth().padding(top = 24.dp)) {
                    Text(if (state.submitting) "제출 중" else "익명 의견 제출")
                }
            }
            else -> ErrorContent(message = state.error ?: "설문을 표시할 수 없습니다.")
        }
    }
    }
}
