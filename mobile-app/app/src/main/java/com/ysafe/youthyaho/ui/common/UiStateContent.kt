package com.ysafe.youthyaho.ui.common

import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.Button
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp

/** 화면마다 손으로 그리던 로딩/에러/빈상태 블록을 공통화한 것 - 각 화면은 이
 * 세 조각을 자신의 when{} 분기에 맞게 조합해서 쓴다(하나의 거대한 상태머신으로
 * 강제로 묶지 않음 - 화면마다 로딩/에러가 블로킹인지 인라인인지 다르기 때문). */

@Composable
fun LoadingIndicator(modifier: Modifier = Modifier) {
    CircularProgressIndicator(modifier = modifier.padding(top = 24.dp))
}

@Composable
fun ErrorContent(
    message: String,
    onRetry: (() -> Unit)? = null,
    modifier: Modifier = Modifier,
) {
    Column(modifier = modifier) {
        Text(
            text = message,
            color = MaterialTheme.colorScheme.error,
            style = MaterialTheme.typography.bodyMedium,
        )
        if (onRetry != null) {
            Button(onClick = onRetry, modifier = Modifier.padding(top = 16.dp)) {
                Text("다시 시도")
            }
        }
    }
}

@Composable
fun EmptyContent(message: String, modifier: Modifier = Modifier) {
    Text(
        text = message,
        style = MaterialTheme.typography.bodyMedium,
        color = MaterialTheme.colorScheme.onSurfaceVariant,
        modifier = modifier.fillMaxWidth().padding(top = 16.dp),
    )
}
