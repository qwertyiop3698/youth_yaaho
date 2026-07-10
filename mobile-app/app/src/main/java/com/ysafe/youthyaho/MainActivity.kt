package com.ysafe.youthyaho

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.material3.Surface
import androidx.compose.ui.Modifier
import androidx.navigation.compose.rememberNavController
import com.ysafe.youthyaho.ui.navigation.YouthYahoNavHost
import com.ysafe.youthyaho.ui.theme.YouthYahoTheme

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
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
