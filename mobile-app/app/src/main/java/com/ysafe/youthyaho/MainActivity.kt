package com.ysafe.youthyaho

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.compose.foundation.layout.WindowInsets
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.safeDrawing
import androidx.compose.foundation.layout.windowInsetsPadding
import androidx.compose.material3.Surface
import androidx.compose.ui.Modifier
import androidx.core.splashscreen.SplashScreen.Companion.installSplashScreen
import androidx.navigation.compose.rememberNavController
import com.ysafe.youthyaho.ui.navigation.YouthYahoNavHost
import com.ysafe.youthyaho.ui.theme.YouthYahoTheme

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        // installSplashScreen()은 super.onCreate() 전에 호출해야 한다(AndroidManifest의
        // Theme.YouthYaho.Splash와 짝을 이루는 core-splashscreen 규약).
        installSplashScreen()
        super.onCreate(savedInstanceState)
        val container = (application as YouthYahoApp).container

        setContent {
            YouthYahoTheme {
                // targetSdk 36(Android 15+)에서는 OS가 edge-to-edge를 강제한다(앱이
                // enableEdgeToEdge()를 호출하지 않아도 콘텐츠가 상태바/내비게이션바
                // 밑까지 그려짐). Surface 배경은 그대로 화면 전체를 채우되, 실제
                // 콘텐츠(NavHost)만 safeDrawing 인셋만큼 안쪽으로 들여써서 스크롤 시
                // 상단 항목이 상태바에 가려지는 문제를 막는다.
                Surface(modifier = Modifier.fillMaxSize()) {
                    val navController = rememberNavController()
                    YouthYahoNavHost(
                        navController = navController,
                        authRepository = container.authRepository,
                        diagnosisRepository = container.diagnosisRepository,
                        policyFeedbackRepository = container.policyFeedbackRepository,
                        policyDemandRepository = container.policyDemandRepository,
                        tokenStore = container.tokenStore,
                        modifier = Modifier.windowInsetsPadding(WindowInsets.safeDrawing),
                    )
                }
            }
        }
    }
}
