package com.ysafe.youthyaho.ui.onboarding

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Button
import androidx.compose.material3.Checkbox
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.tooling.preview.Preview
import androidx.compose.ui.unit.dp
import com.ysafe.youthyaho.ui.theme.YouthYahoTheme

/**
 * docs/09: 슬로건 노출, 서비스 소개, 개인정보 동의, 게스트/로그인 선택.
 *
 * ViewModel 없이 순수 Compose 로컬 상태(동의 체크박스)만 쓴다 - API 호출이나
 * 비즈니스 로직이 없는 화면이라 ViewModel을 두는 게 과한 추상화라고 판단했다
 * (PLAN.md 테스트 전략: 로직이 있는 화면만 ViewModel 단위테스트 대상).
 */
@Composable
fun OnboardingScreen(
    onContinueAsGuest: () -> Unit,
    onNavigateToLogin: () -> Unit,
    onNavigateToSignup: () -> Unit,
    modifier: Modifier = Modifier,
) {
    var consentChecked by remember { mutableStateOf(false) }

    Column(
        modifier = modifier
            .fillMaxSize()
            .verticalScroll(rememberScrollState())
            .padding(24.dp),
        verticalArrangement = Arrangement.Center,
    ) {
        Text(text = "청년야호", style = MaterialTheme.typography.headlineMedium)
        Text(
            text = "위기가 오기 전에, 먼저 압니다",
            style = MaterialTheme.typography.titleLarge,
            modifier = Modifier.padding(top = 4.dp),
        )
        Text(
            text = "몇 가지 정보만 알려주시면, 부산 청년 1인가구를 위한 정책 중 " +
                "지금 신청하면 좋은 걸 먼저 찾아드려요.",
            style = MaterialTheme.typography.bodyLarge,
            modifier = Modifier.padding(top = 16.dp),
        )

        Spacer(modifier = Modifier.height(32.dp))

        Row(verticalAlignment = Alignment.CenterVertically) {
            Checkbox(checked = consentChecked, onCheckedChange = { consentChecked = it })
            Text(
                text = "개인정보 수집·이용에 동의합니다 (진단 목적에 한해 사용, 언제든 삭제 요청 가능)",
                style = MaterialTheme.typography.bodyMedium,
            )
        }

        Spacer(modifier = Modifier.height(24.dp))

        Button(
            onClick = onContinueAsGuest,
            enabled = consentChecked,
            modifier = Modifier.fillMaxWidth(),
        ) {
            Text("게스트로 계속하기")
        }

        Spacer(modifier = Modifier.height(12.dp))

        OutlinedButton(
            onClick = onNavigateToLogin,
            enabled = consentChecked,
            modifier = Modifier.fillMaxWidth(),
        ) {
            Text("로그인")
        }

        Spacer(modifier = Modifier.height(4.dp))

        TextButton(
            onClick = onNavigateToSignup,
            enabled = consentChecked,
            modifier = Modifier.fillMaxWidth(),
        ) {
            Text("아직 계정이 없으신가요? 회원가입")
        }

        Text(
            text = "로그인은 선택입니다 - 안 하셔도 진단은 그대로 이용할 수 있어요. " +
                "로그인하면 나중에 히스토리를 저장/조회할 수 있어요.",
            style = MaterialTheme.typography.bodyMedium,
            modifier = Modifier.padding(top = 16.dp),
        )
    }
}

@Preview(showBackground = true)
@Composable
private fun OnboardingScreenPreview() {
    YouthYahoTheme {
        OnboardingScreen(onContinueAsGuest = {}, onNavigateToLogin = {}, onNavigateToSignup = {})
    }
}
