package com.ysafe.youthyaho.ui.auth

import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Button
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.ysafe.youthyaho.ui.common.BUSAN_DISTRICT_OPTIONS
import com.ysafe.youthyaho.ui.common.ChipSingleSelect
import com.ysafe.youthyaho.ui.common.YouthYahoScaffold
import kotlinx.coroutines.delay

private const val SUCCESS_MESSAGE_DELAY_MS = 1200L

@Composable
fun SignupScreen(
    viewModel: SignupViewModel,
    onSignupSuccess: () -> Unit,
    onNavigateBack: () -> Unit,
    modifier: Modifier = Modifier,
) {
    val uiState by viewModel.uiState.collectAsStateWithLifecycle()

    // 성공 메시지를 잠깐 보여준 뒤 로그인 화면으로 이동한다(가입만으로는 자동
    // 로그인되지 않음 - 백엔드가 signup에서 토큰을 발급하지 않는 설계).
    LaunchedEffect(uiState.signupSucceeded) {
        if (uiState.signupSucceeded) {
            delay(SUCCESS_MESSAGE_DELAY_MS)
            onSignupSuccess()
        }
    }

    YouthYahoScaffold(title = "회원가입", onBack = onNavigateBack, modifier = modifier) { paddingValues ->
    Column(
        modifier = Modifier
            .fillMaxSize()
            .verticalScroll(rememberScrollState())
            .padding(paddingValues)
            .padding(24.dp),
    ) {
        Text(
            text = "청년 상한(만 39세 이하)만 가입할 수 있어요. 생년월일은 본인이 직접 입력한 " +
                "값이라 별도 본인인증은 아니에요.",
            style = MaterialTheme.typography.bodyMedium,
            modifier = Modifier.padding(top = 8.dp),
        )

        if (uiState.signupSucceeded) {
            Text(
                text = "가입이 완료됐어요! 로그인 화면으로 이동할게요.",
                color = MaterialTheme.colorScheme.primary,
                style = MaterialTheme.typography.bodyLarge,
                modifier = Modifier.padding(top = 24.dp),
            )
            return@Column
        }

        OutlinedTextField(
            value = uiState.email,
            onValueChange = viewModel::onEmailChange,
            label = { Text("이메일") },
            singleLine = true,
            keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Email),
            modifier = Modifier.fillMaxWidth().padding(top = 24.dp),
        )

        OutlinedTextField(
            value = uiState.password,
            onValueChange = viewModel::onPasswordChange,
            label = { Text("비밀번호 (8자 이상)") },
            singleLine = true,
            visualTransformation = PasswordVisualTransformation(),
            keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Password),
            modifier = Modifier.fillMaxWidth().padding(top = 12.dp),
        )

        OutlinedTextField(
            value = uiState.birthdate,
            onValueChange = viewModel::onBirthdateChange,
            label = { Text("생년월일 (YYYY-MM-DD)") },
            placeholder = { Text("2000-01-01") },
            singleLine = true,
            keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Number),
            modifier = Modifier.fillMaxWidth().padding(top = 12.dp),
        )

        ChipSingleSelect(
            label = "거주 지역 (구/군, 선택)",
            options = BUSAN_DISTRICT_OPTIONS,
            selected = uiState.dongCode.ifBlank { null },
            onSelect = viewModel::onDongCodeChange,
            modifier = Modifier.padding(top = 12.dp),
            wrap = true,
        )

        uiState.errorMessage?.let { message ->
            Text(
                text = message,
                color = MaterialTheme.colorScheme.error,
                style = MaterialTheme.typography.bodyMedium,
                modifier = Modifier.padding(top = 8.dp),
            )
        }

        Button(
            onClick = viewModel::signup,
            enabled = !uiState.isLoading,
            modifier = Modifier.fillMaxWidth().padding(top = 24.dp),
        ) {
            if (uiState.isLoading) {
                CircularProgressIndicator(
                    modifier = Modifier.size(20.dp),
                    color = MaterialTheme.colorScheme.onPrimary,
                    strokeWidth = 2.dp,
                )
            } else {
                Text("가입하기")
            }
        }

    }
    }
}
