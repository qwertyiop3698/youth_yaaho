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
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle

@Composable
fun SettingsScreen(
    viewModel: SettingsViewModel,
    onLoggedOut: () -> Unit,
    modifier: Modifier = Modifier,
) {
    val uiState by viewModel.uiState.collectAsStateWithLifecycle()

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

        OutlinedButton(onClick = viewModel::requestDeleteAccount, modifier = Modifier.fillMaxWidth()) {
            Text("데이터 삭제 요청")
        }
        if (uiState.deleteRequestSubmitted) {
            Text(
                text = "삭제 요청이 접수되었어요. (데모용 표시 - 실제 서버 처리는 아직 연동되지 않았어요)",
                style = MaterialTheme.typography.bodySmall,
                modifier = Modifier.padding(top = 8.dp),
            )
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
            text = { Text("진단 기록 삭제를 요청하시겠어요? 실제 삭제 처리는 아직 서버에 연동되지 않아 확인만 남습니다.") },
            confirmButton = {
                TextButton(onClick = viewModel::confirmDeleteRequest) { Text("요청하기") }
            },
            dismissButton = {
                TextButton(onClick = viewModel::dismissDeleteDialog) { Text("취소") }
            },
        )
    }
}
