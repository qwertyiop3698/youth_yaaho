package com.ysafe.youthyaho.ui.common

import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics

/**
 * 화면마다 제각각이던 뒤로가기(Login/Signup는 하단 TextButton "뒤로", 나머지는
 * 아예 없음)를 상단 앱바 하나로 통일한다.
 *
 * 화살표는 벡터 아이콘 대신 문자 글리프("←")로 그린다 - 이 프로젝트는 아직
 * material-icons-core 의존성을 추가하지 않았고(build.gradle.kts 확인), 아이콘
 * 하나 때문에 새 의존성을 늘리는 대신 이미 쓰고 있는 Text만으로 해결한다.
 *
 * onBack이 null이면(예: 뒤로 갈 곳이 없는 화면) 뒤로가기 버튼 없이 제목만 보여준다.
 */
@Composable
fun YouthYahoScaffold(
    title: String,
    onBack: (() -> Unit)? = null,
    modifier: Modifier = Modifier,
    content: @Composable (PaddingValues) -> Unit,
) {
    Scaffold(
        modifier = modifier,
        topBar = {
            TopAppBar(
                title = { Text(text = title) },
                navigationIcon = {
                    if (onBack != null) {
                        IconButton(
                            onClick = onBack,
                            modifier = Modifier.semantics { contentDescription = "뒤로가기" },
                        ) {
                            Text(text = "←", style = MaterialTheme.typography.headlineSmall)
                        }
                    }
                },
            )
        },
    ) { paddingValues ->
        content(paddingValues)
    }
}
