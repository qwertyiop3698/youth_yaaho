package com.ysafe.youthyaho.ui.navigation

import android.net.Uri
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
import com.ysafe.youthyaho.data.repository.PolicyFeedbackRepository
import com.ysafe.youthyaho.data.repository.PolicyDemandRepository
import com.ysafe.youthyaho.ui.policydemand.PolicyDemandScreen
import com.ysafe.youthyaho.ui.policydemand.PolicyDemandViewModel
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
import com.ysafe.youthyaho.ui.policyfeedback.FeedbackFormRoute
import com.ysafe.youthyaho.ui.policyfeedback.FeedbackFormViewModel
import com.ysafe.youthyaho.ui.policyfeedback.PolicyDetailRoute
import com.ysafe.youthyaho.ui.policyfeedback.PolicyDetailViewModel
import com.ysafe.youthyaho.ui.policyfeedback.PolicyRecordsRoute
import com.ysafe.youthyaho.ui.policyfeedback.PolicyRecordsViewModel
import com.ysafe.youthyaho.ui.policyfeedback.RewardsRoute
import com.ysafe.youthyaho.ui.policyfeedback.RewardsViewModel
import com.ysafe.youthyaho.ui.result.ResultScreen
import com.ysafe.youthyaho.ui.result.ResultViewModel
import com.ysafe.youthyaho.ui.settings.SettingsScreen
import com.ysafe.youthyaho.ui.settings.SettingsViewModel
import com.ysafe.youthyaho.ui.splash.SplashScreen

private const val SESSION_ID_ARG = "sessionId"
private const val POLICY_ID_ARG = "policyId"
private const val POLICY_URL_ARG = "policyUrl"
private const val USAGE_ID_ARG = "usageId"
private const val FEEDBACK_STAGE_ARG = "feedbackStage"
private const val DEMAND_REASON_ARG = "demandReason"

sealed class Screen(val route: String) {
    data object Splash : Screen("splash")
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
    data object PolicyDetail : Screen("policy-detail/{$POLICY_ID_ARG}?url={$POLICY_URL_ARG}") {
        fun createRoute(policyId: String, url: String?) =
            "policy-detail/${Uri.encode(policyId)}?url=${Uri.encode(url.orEmpty())}"
    }
    data object PolicyRecords : Screen("policy-records")
    data object PolicyFeedback : Screen(
        "policy-feedback/{$USAGE_ID_ARG}/{$POLICY_ID_ARG}/{$FEEDBACK_STAGE_ARG}",
    ) {
        fun createRoute(usageId: String, policyId: String, stage: String) =
            "policy-feedback/${Uri.encode(usageId)}/${Uri.encode(policyId)}/${Uri.encode(stage)}"
    }
    data object Rewards : Screen("policy-rewards")
    data object PolicyDemand : Screen("policy-demand/{$SESSION_ID_ARG}/{$DEMAND_REASON_ARG}") {
        fun createRoute(sessionId: String, reason: String) = "policy-demand/${Uri.encode(sessionId)}/${Uri.encode(reason)}"
    }
    data object Settings : Screen("settings")
}

/**
 * docs/09 화면 순서: 스플래시 -> 로그인 -> 온보딩 -> 정보입력 -> 진단결과 -> 정책추천
 * -> 설명문구 -> 히스토리 -> 설정. 스플래시는 앱 실행 직후 로고만 잠깐 보여주고
 * 로그인 화면으로 바로 넘어간다(popUpTo로 백스택 제거, 뒤로가기로 재진입 불가).
 * 온보딩의 "게스트/로그인 선택"은 로그인 화면의 뒤로가기에서도 여전히 갈 수 있는
 * 보조 화면이다(로그인은 선택 기능 - 게스트로도 정보입력부터 그대로 진행 가능).
 */
@Composable
fun YouthYahoNavHost(
    navController: NavHostController,
    authRepository: AuthRepository,
    diagnosisRepository: DiagnosisRepository,
    policyFeedbackRepository: PolicyFeedbackRepository,
    policyDemandRepository: PolicyDemandRepository,
    tokenStore: TokenStore,
    modifier: Modifier = Modifier,
) {
    NavHost(navController = navController, startDestination = Screen.Splash.route, modifier = modifier) {
        composable(Screen.Splash.route) {
            SplashScreen(
                onTimeout = {
                    navController.navigate(Screen.Onboarding.route) {
                        popUpTo(Screen.Splash.route) { inclusive = true }
                    }
                },
            )
        }

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
                viewModel(factory = RecommendationViewModel.factory(diagnosisRepository, policyDemandRepository, sessionId))
            RecommendationScreen(
                viewModel = viewModel,
                onNextClick = {
                    navController.navigate(Screen.Explanation.createRoute(sessionId))
                },
                onPolicyDetail = { policy ->
                    navController.navigate(Screen.PolicyDetail.createRoute(policy.policy, policy.url))
                },
                onPolicyDemand = { reason -> navController.navigate(Screen.PolicyDemand.createRoute(sessionId, reason)) },
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

        composable(
            route = Screen.PolicyDetail.route,
            arguments = listOf(
                navArgument(POLICY_ID_ARG) { type = NavType.StringType },
                navArgument(POLICY_URL_ARG) { type = NavType.StringType; defaultValue = "" },
            ),
        ) { backStackEntry ->
            val policyId = backStackEntry.arguments?.getString(POLICY_ID_ARG).orEmpty()
            val policyUrl = backStackEntry.arguments?.getString(POLICY_URL_ARG).orEmpty().ifBlank { null }
            val viewModel: PolicyDetailViewModel = viewModel(
                factory = PolicyDetailViewModel.factory(policyFeedbackRepository, policyId),
            )
            PolicyDetailRoute(
                viewModel = viewModel,
                policyName = policyId,
                applicationUrl = policyUrl,
                onOpenRecords = { navController.navigate(Screen.PolicyRecords.route) },
            )
        }

        composable(Screen.PolicyRecords.route) {
            val viewModel: PolicyRecordsViewModel =
                viewModel(factory = PolicyRecordsViewModel.factory(policyFeedbackRepository))
            PolicyRecordsRoute(
                viewModel = viewModel,
                onOpenFeedback = { usageId, policyId, stage ->
                    navController.navigate(Screen.PolicyFeedback.createRoute(usageId, policyId, stage))
                },
                onOpenRewards = { navController.navigate(Screen.Rewards.route) },
            )
        }

        composable(
            route = Screen.PolicyFeedback.route,
            arguments = listOf(
                navArgument(USAGE_ID_ARG) { type = NavType.StringType },
                navArgument(POLICY_ID_ARG) { type = NavType.StringType },
                navArgument(FEEDBACK_STAGE_ARG) { type = NavType.StringType },
            ),
        ) { backStackEntry ->
            val usageId = backStackEntry.arguments?.getString(USAGE_ID_ARG).orEmpty()
            val policyId = backStackEntry.arguments?.getString(POLICY_ID_ARG).orEmpty()
            val stage = backStackEntry.arguments?.getString(FEEDBACK_STAGE_ARG).orEmpty()
            val viewModel: FeedbackFormViewModel = viewModel(
                factory = FeedbackFormViewModel.factory(
                    policyFeedbackRepository, usageId, policyId, stage,
                ),
            )
            FeedbackFormRoute(
                viewModel = viewModel,
                onDone = {
                    navController.navigate(Screen.PolicyRecords.route) {
                        popUpTo(Screen.PolicyRecords.route) { inclusive = true }
                    }
                },
            )
        }

        composable(
            route = Screen.PolicyDemand.route,
            arguments = listOf(navArgument(SESSION_ID_ARG) { type = NavType.StringType }, navArgument(DEMAND_REASON_ARG) { type = NavType.StringType }),
        ) { backStackEntry ->
            val sessionId = backStackEntry.arguments?.getString(SESSION_ID_ARG).orEmpty()
            val reason = backStackEntry.arguments?.getString(DEMAND_REASON_ARG).orEmpty()
            val demandViewModel: PolicyDemandViewModel = viewModel(factory = PolicyDemandViewModel.factory(policyDemandRepository, sessionId, reason))
            PolicyDemandScreen(demandViewModel, onDone = { navController.popBackStack() })
        }

        composable(Screen.Rewards.route) {
            val viewModel: RewardsViewModel =
                viewModel(factory = RewardsViewModel.factory(policyFeedbackRepository))
            RewardsRoute(viewModel)
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
                onPolicyRecords = { navController.navigate(Screen.PolicyRecords.route) },
            )
        }
    }
}
