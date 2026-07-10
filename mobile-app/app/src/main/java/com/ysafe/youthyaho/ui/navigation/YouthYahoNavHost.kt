package com.ysafe.youthyaho.ui.navigation

import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.lifecycle.viewmodel.compose.viewModel
import androidx.navigation.NavHostController
import androidx.navigation.NavType
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import androidx.navigation.navArgument
import com.ysafe.youthyaho.data.local.TokenStore
import com.ysafe.youthyaho.data.repository.AuthRepository
import com.ysafe.youthyaho.data.repository.DiagnosisRepository
import com.ysafe.youthyaho.ui.auth.LoginScreen
import com.ysafe.youthyaho.ui.auth.LoginViewModel
import com.ysafe.youthyaho.ui.auth.SignupScreen
import com.ysafe.youthyaho.ui.auth.SignupViewModel
import com.ysafe.youthyaho.ui.diagnoseinput.DiagnoseInputScreen
import com.ysafe.youthyaho.ui.diagnoseinput.DiagnoseInputViewModel
import com.ysafe.youthyaho.ui.explanation.ExplanationScreen
import com.ysafe.youthyaho.ui.explanation.ExplanationViewModel
import com.ysafe.youthyaho.ui.history.HistoryScreen
import com.ysafe.youthyaho.ui.history.HistoryViewModel
import com.ysafe.youthyaho.ui.onboarding.OnboardingScreen
import com.ysafe.youthyaho.ui.recommendation.RecommendationScreen
import com.ysafe.youthyaho.ui.recommendation.RecommendationViewModel
import com.ysafe.youthyaho.ui.result.ResultScreen
import com.ysafe.youthyaho.ui.result.ResultViewModel
import com.ysafe.youthyaho.ui.settings.SettingsScreen
import com.ysafe.youthyaho.ui.settings.SettingsViewModel

private const val SESSION_ID_ARG = "sessionId"

sealed class Screen(val route: String) {
    data object Onboarding : Screen("onboarding")
    data object Login : Screen("login")
    data object Signup : Screen("signup")
    data object DiagnoseInput : Screen("diagnose_input")

    // 진단결과 이후 화면들은 session_id가 있어야 recommendations/explanation/history를
    // 호출할 수 있으므로(backend/app/routers/citizen.py), 네비게이션 인자로 들고 다닌다.
    data object Result : Screen("result/{$SESSION_ID_ARG}") {
        fun createRoute(sessionId: String) = "result/$sessionId"
    }
    data object Recommendation : Screen("recommendation/{$SESSION_ID_ARG}") {
        fun createRoute(sessionId: String) = "recommendation/$sessionId"
    }
    data object Explanation : Screen("explanation/{$SESSION_ID_ARG}") {
        fun createRoute(sessionId: String) = "explanation/$sessionId"
    }
    data object History : Screen("history/{$SESSION_ID_ARG}") {
        fun createRoute(sessionId: String) = "history/$sessionId"
    }
    data object Settings : Screen("settings")
}

/**
 * docs/09 화면 순서: 온보딩 -> 정보입력 -> 진단결과 -> 정책추천 -> 설명문구 -> 히스토리
 * -> 설정. 로그인/회원가입은 온보딩의 "게스트/로그인 선택"에서 진입하는 보조 화면이다
 * (로그인은 선택 기능 - 게스트로도 정보입력부터 그대로 진행 가능).
 */
@Composable
fun YouthYahoNavHost(
    navController: NavHostController,
    authRepository: AuthRepository,
    diagnosisRepository: DiagnosisRepository,
    tokenStore: TokenStore,
    modifier: Modifier = Modifier,
) {
    NavHost(navController = navController, startDestination = Screen.Onboarding.route, modifier = modifier) {
        composable(Screen.Onboarding.route) {
            OnboardingScreen(
                onContinueAsGuest = {
                    navController.navigate(Screen.DiagnoseInput.route) {
                        popUpTo(Screen.Onboarding.route) { inclusive = true }
                    }
                },
                onNavigateToLogin = { navController.navigate(Screen.Login.route) },
                onNavigateToSignup = { navController.navigate(Screen.Signup.route) },
            )
        }

        composable(Screen.Login.route) {
            val viewModel: LoginViewModel = viewModel(factory = LoginViewModel.factory(authRepository))
            LoginScreen(
                viewModel = viewModel,
                onLoginSuccess = {
                    navController.navigate(Screen.DiagnoseInput.route) {
                        popUpTo(Screen.Onboarding.route) { inclusive = true }
                    }
                },
                onNavigateBack = { navController.popBackStack() },
                onNavigateToSignup = {
                    navController.navigate(Screen.Signup.route) {
                        popUpTo(Screen.Login.route) { inclusive = true }
                    }
                },
            )
        }

        composable(Screen.Signup.route) {
            val viewModel: SignupViewModel = viewModel(factory = SignupViewModel.factory(authRepository))
            SignupScreen(
                viewModel = viewModel,
                onSignupSuccess = {
                    navController.navigate(Screen.Login.route) {
                        popUpTo(Screen.Signup.route) { inclusive = true }
                    }
                },
                onNavigateBack = { navController.popBackStack() },
            )
        }

        composable(Screen.DiagnoseInput.route) {
            val viewModel: DiagnoseInputViewModel =
                viewModel(factory = DiagnoseInputViewModel.factory(diagnosisRepository))
            DiagnoseInputScreen(
                viewModel = viewModel,
                onDiagnoseSuccess = { sessionId ->
                    navController.navigate(Screen.Result.createRoute(sessionId)) {
                        popUpTo(Screen.DiagnoseInput.route) { inclusive = true }
                    }
                },
            )
        }

        composable(
            route = Screen.Result.route,
            arguments = listOf(navArgument(SESSION_ID_ARG) { type = NavType.StringType }),
        ) { backStackEntry ->
            val sessionId = backStackEntry.arguments?.getString(SESSION_ID_ARG).orEmpty()
            val viewModel: ResultViewModel =
                viewModel(factory = ResultViewModel.factory(diagnosisRepository, sessionId))
            ResultScreen(
                viewModel = viewModel,
                onNextClick = {
                    navController.navigate(Screen.Recommendation.createRoute(sessionId))
                },
            )
        }

        composable(
            route = Screen.Recommendation.route,
            arguments = listOf(navArgument(SESSION_ID_ARG) { type = NavType.StringType }),
        ) { backStackEntry ->
            val sessionId = backStackEntry.arguments?.getString(SESSION_ID_ARG).orEmpty()
            val viewModel: RecommendationViewModel =
                viewModel(factory = RecommendationViewModel.factory(diagnosisRepository, sessionId))
            RecommendationScreen(
                viewModel = viewModel,
                onNextClick = {
                    navController.navigate(Screen.Explanation.createRoute(sessionId))
                },
            )
        }

        composable(
            route = Screen.Explanation.route,
            arguments = listOf(navArgument(SESSION_ID_ARG) { type = NavType.StringType }),
        ) { backStackEntry ->
            val sessionId = backStackEntry.arguments?.getString(SESSION_ID_ARG).orEmpty()
            val viewModel: ExplanationViewModel =
                viewModel(factory = ExplanationViewModel.factory(diagnosisRepository, sessionId))
            ExplanationScreen(
                viewModel = viewModel,
                onNextClick = {
                    navController.navigate(Screen.History.createRoute(sessionId))
                },
            )
        }

        composable(
            route = Screen.History.route,
            arguments = listOf(navArgument(SESSION_ID_ARG) { type = NavType.StringType }),
        ) { backStackEntry ->
            val sessionId = backStackEntry.arguments?.getString(SESSION_ID_ARG).orEmpty()
            val viewModel: HistoryViewModel =
                viewModel(factory = HistoryViewModel.factory(diagnosisRepository, sessionId))
            HistoryScreen(
                viewModel = viewModel,
                onNextClick = { navController.navigate(Screen.Settings.route) },
            )
        }

        composable(Screen.Settings.route) {
            val viewModel: SettingsViewModel =
                viewModel(factory = SettingsViewModel.factory(tokenStore, authRepository))
            SettingsScreen(
                viewModel = viewModel,
                onLoggedOut = {
                    navController.navigate(Screen.Onboarding.route) {
                        popUpTo(0) { inclusive = true }
                    }
                },
            )
        }
    }
}
