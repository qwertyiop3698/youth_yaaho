package com.ysafe.youthyaho.ui.explanation

import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.ysafe.youthyaho.ui.common.ErrorContent
import com.ysafe.youthyaho.ui.common.LoadingIndicator
import com.ysafe.youthyaho.ui.common.YouthYahoScaffold

@Composable
fun ExplanationScreen(
    viewModel: ExplanationViewModel,
    onBack: () -> Unit,
    onNextClick: () -> Unit,
    modifier: Modifier = Modifier,
) {
    val uiState by viewModel.uiState.collectAsStateWithLifecycle()

    YouthYahoScaffold(title = "왜 추천했는지", onBack = onBack, modifier = modifier) { paddingValues ->
    Column(
        modifier = Modifier
            .fillMaxSize()
            .verticalScroll(rememberScrollState())
            .padding(paddingValues)
            .padding(24.dp),
    ) {
        Text(
            text = "진단 결과를 바탕으로 이유를 설명해드려요.",
            style = MaterialTheme.typography.bodyMedium,
            modifier = Modifier.padding(bottom = 24.dp),
        )

        when {
            uiState.isLoading -> {
                LoadingIndicator()
            }
            uiState.errorMessage != null -> {
                ErrorContent(message = uiState.errorMessage ?: "", onRetry = viewModel::retry)
            }
            else -> {
                Card(modifier = Modifier.fillMaxWidth()) {
                    Column(modifier = Modifier.padding(20.dp)) {
                        Text(text = uiState.explanation ?: "", style = MaterialTheme.typography.bodyLarge)
                        if (uiState.isLlmGenerated) {
                            Text(
                                text = "Claude AI가 이번 진단에 맞춰 직접 분석한 설명이에요.",
                                style = MaterialTheme.typography.bodyMedium,
                                color = MaterialTheme.colorScheme.primary,
                                modifier = Modifier.padding(top = 12.dp),
                            )
                        }
                    }
                }
            }
        }

        Button(onClick = onNextClick, modifier = Modifier.fillMaxWidth().padding(top = 24.dp)) {
            Text("히스토리 보기")
        }
    }
    }
}
