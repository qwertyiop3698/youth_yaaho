package com.ysafe.youthyaho.data.api

import com.ysafe.youthyaho.data.local.TokenStore
import kotlinx.coroutines.runBlocking
import okhttp3.Authenticator
import okhttp3.Interceptor
import okhttp3.Request
import okhttp3.Response
import okhttp3.Route

// 이 경로들은 애초에 access_token이 필요 없거나(로그인/회원가입), 여기서 401이 나면
// "토큰 만료"가 아니라 실제 인증 실패(비번 오류 등)이므로 자동 재시도 대상에서 뺀다.
private val NO_AUTH_PATHS = listOf(
    "api/v1/citizen/auth/login",
    "api/v1/citizen/auth/signup",
    "api/v1/citizen/auth/refresh",
)

private fun okhttp3.HttpUrl.isAuthEndpoint(): Boolean = NO_AUTH_PATHS.any { encodedPath.endsWith(it) }

/**
 * 저장된 access_token이 있으면 모든 요청에 Authorization 헤더로 붙인다. 없으면(게스트,
 * 익명 진단) 헤더 없이 그대로 나간다 - 기존 익명 플로우를 건드리지 않기 위함.
 */
class AuthHeaderInterceptor(private val tokenStore: TokenStore) : Interceptor {
    override fun intercept(chain: Interceptor.Chain): Response {
        val original = chain.request()
        if (original.url.isAuthEndpoint()) {
            return chain.proceed(original)
        }
        val token = runBlocking { tokenStore.currentAccessToken() }
        val request = if (token != null) {
            original.newBuilder().header("Authorization", "Bearer $token").build()
        } else {
            original
        }
        return chain.proceed(request)
    }
}

/**
 * access_token 만료로 401이 오면 refresh_token으로 새 토큰을 발급받아 자동
 * 재시도한다. [refreshCall]은 refresh_token을 받아 새 access_token을 반환하고(성공
 * 시 TokenStore에도 저장), 실패하면 null을 반환해야 한다 - 순환참조(refresh 호출이
 * 또 이 Authenticator를 거치는 것)를 피하려고 NetworkModule에서 별도의
 * "refresh 전용" Retrofit 클라이언트로 구현해서 넘겨준다.
 */
class TokenAuthenticator(
    private val tokenStore: TokenStore,
    private val refreshCall: suspend (refreshToken: String) -> String?,
) : Authenticator {

    override fun authenticate(route: Route?, response: Response): Request? {
        if (response.request.url.isAuthEndpoint()) return null
        if (responseChainLength(response) >= 2) return null // 무한 재시도 방지

        val refreshToken = runBlocking { tokenStore.currentRefreshToken() } ?: return null
        val newAccessToken = runBlocking { refreshCall(refreshToken) } ?: return null

        return response.request.newBuilder()
            .header("Authorization", "Bearer $newAccessToken")
            .build()
    }

    private fun responseChainLength(response: Response): Int {
        var count = 1
        var prior = response.priorResponse
        while (prior != null) {
            count++
            prior = prior.priorResponse
        }
        return count
    }
}
