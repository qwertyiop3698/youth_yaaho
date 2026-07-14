package com.ysafe.youthyaho

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.compose.foundation.layout.fillMaxSize
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
                Surface(modifier = Modifier.fillMaxSize()) {
                    val navController = rememberNavController()
                    YouthYahoNavHost(
                        navController = navController,
                        authRepository = container.authRepository,
                        diagnosisRepository = container.diagnosisRepository,
                        tokenStore = container.tokenStore,
                    )
                }
            }
        }
    }
}
