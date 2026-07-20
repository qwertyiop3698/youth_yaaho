package com.ysafe.youthyaho.ui.splash

import androidx.activity.compose.BackHandler
import androidx.compose.foundation.Image
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.size
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.unit.dp
import com.ysafe.youthyaho.R
import kotlinx.coroutines.delay

private const val SPLASH_DURATION_MS = 1000L

/**
 * MainActivity의 시스템 스플래시(core-splashscreen) 다음에 뜨는 인앱 스플래시.
 * 로고를 정중앙에 SPLASH_DURATION_MS만큼 보여준 뒤 onTimeout으로 로그인 화면 전환을
 * 위임한다. NavHost 쪽에서 popUpTo로 백스택에서 제거하지만, 그 전환 애니메이션 중에도
 * 뒤로가기가 먹지 않도록 BackHandler로 한 번 더 막는다.
 */
@Composable
fun SplashScreen(onTimeout: () -> Unit) {
    BackHandler(enabled = true) {}

    LaunchedEffect(Unit) {
        delay(SPLASH_DURATION_MS)
        onTimeout()
    }

    Surface(modifier = Modifier.fillMaxSize(), color = MaterialTheme.colorScheme.background) {
        Box(modifier = Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
            Image(
                painter = painterResource(id = R.drawable.logo),
                contentDescription = null,
                modifier = Modifier.size(200.dp),
            )
        }
    }
}
