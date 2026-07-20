package com.ysafe.youthyaho.ui.settings

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Switch
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle

@Composable
fun SettingsScreen(
    viewModel: SettingsViewModel,
    onLoggedOut: () -> Unit,
    onPolicyRecords: () -> Unit,
    modifier: Modifier = Modifier,
) {
    val uiState by viewModel.uiState.collectAsStateWithLifecycle()

    LaunchedEffect(uiState.accountDeleted) {
        if (uiState.accountDeleted) onLoggedOut()
    }

    Column(modifier = modifier.fillMaxSize().padding(24.dp)) {
        Text(text = "설정", style = MaterialTheme.typography.headlineMedium)

        Row(
            modifier = Modifier.fillMaxWidth().padding(top = 24.dp),
            horizontalArrangement = Arrangement.SpaceBetween,
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Text(text = "알림 동의", style = MaterialTheme.typography.titleMedium)
            Switch(checked = uiState.notificationsEnabled, onCheckedChange = viewModel::setNotificationsEnabled)
        }
        Text(
            text = "기기에만 저장되며, 실제 알림 발송 기능은 아직 연동되지 않았어요.",
            style = MaterialTheme.typography.bodySmall,
            modifier = Modifier.padding(top = 4.dp, bottom = 24.dp),
        )

        if (uiState.isLoggedIn) {
            Button(
                onClick = onPolicyRecords,
                modifier = Modifier.fillMaxWidth().padding(bottom = 12.dp),
            ) {
                Text("내 정책 기록과 모의 리워드")
            }
            OutlinedButton(
                onClick = viewModel::requestDeleteAccount,
                enabled = !uiState.isDeleting,
                modifier = Modifier.fillMaxWidth(),
            ) {
                Text(if (uiState.isDeleting) "삭제 중..." else "계정 및 진단 기록 삭제")
            }
        } else {
            Text(
                text = "게스트 진단은 임의의 세션 ID로만 저장되며 계정과 연결되지 않아요.",
                style = MaterialTheme.typography.bodySmall,
                modifier = Modifier.padding(bottom = 24.dp),
            )
        }
        uiState.deleteErrorMessage?.let { message ->
            Text(text = message, color = MaterialTheme.colorScheme.error, modifier = Modifier.padding(top = 8.dp))
        }

        if (uiState.isLoggedIn) {
            Button(
                onClick = {
                    viewModel.logout()
                    onLoggedOut()
                },
                modifier = Modifier.fillMaxWidth().padding(top = 32.dp),
            ) {
                Text("로그아웃")
            }
        } else {
            Text(
                text = "게스트로 이용 중이에요.",
                style = MaterialTheme.typography.bodyMedium,
                modifier = Modifier.padding(top = 32.dp),
            )
        }
    }

    if (uiState.showDeleteConfirmDialog) {
        AlertDialog(
            onDismissRequest = viewModel::dismissDeleteDialog,
            title = { Text("데이터 삭제 요청") },
            text = { Text("계정과 계정에 연결된 모든 진단 기록을 즉시 삭제합니다. 이 작업은 되돌릴 수 없습니다.") },
            confirmButton = {
                TextButton(onClick = viewModel::confirmDeleteRequest) { Text("요청하기") }
            },
            dismissButton = {
                TextButton(onClick = viewModel::dismissDeleteDialog) { Text("취소") }
            },
        )
    }
}
