package com.ysafe.youthyaho.data.api

import com.ysafe.youthyaho.BuildConfig
import com.ysafe.youthyaho.data.api.dto.RefreshRequestDto
import com.ysafe.youthyaho.data.local.TokenStore
import kotlinx.serialization.json.Json
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.logging.HttpLoggingInterceptor
import retrofit2.Retrofit
import retrofit2.converter.kotlinx.serialization.asConverterFactory

/**
 * Retrofit/OkHttp 조립. BuildConfig.API_BASE_URL 하나만 참조한다 - 에뮬레이터/실기기
 * 연결 모드 전환은 local.properties(API_BASE_URL)만 바꾸면 되고 여기는 안 건드림
 * (app/build.gradle.kts 주석 참고).
 */
object NetworkModule {

    private val json = Json { ignoreUnknownKeys = true }

    fun create(tokenStore: TokenStore): CitizenApiService {
        // refresh 전용 클라이언트: Authenticator를 안 붙여서 "refresh 호출이 401을 받으면
        // 또 refresh를 시도"하는 순환을 원천적으로 막는다.
        val refreshOnlyClient = baseClientBuilder().build()
        val refreshOnlyApi = buildRetrofit(refreshOnlyClient).create(CitizenApiService::class.java)

        val authenticator = TokenAuthenticator(tokenStore) { refreshToken ->
            val response = refreshOnlyApi.refresh(RefreshRequestDto(refresh_token = refreshToken))
            val tokens = if (response.isSuccessful) response.body() else null
            if (tokens != null) {
                tokenStore.saveTokens(tokens.access_token, tokens.refresh_token)
                tokens.access_token
            } else {
                // 회전 후 재사용되었거나 로그아웃으로 폐기된 refresh token이면 로컬
                // 로그인 상태도 즉시 정리한다. 일시적 5xx에는 토큰을 보존한다.
                if (response.code() == 401 || response.code() == 403) tokenStore.clear()
                null
            }
        }

        val mainClient = baseClientBuilder()
            .addInterceptor(AuthHeaderInterceptor(tokenStore))
            .authenticator(authenticator)
            .build()

        return buildRetrofit(mainClient).create(CitizenApiService::class.java)
    }

    private fun baseClientBuilder(): OkHttpClient.Builder {
        val logging = HttpLoggingInterceptor().apply {
            // BODY는 로그인 비밀번호와 토큰 응답까지 로그에 남길 수 있으므로 금지한다.
            level = if (BuildConfig.DEBUG) HttpLoggingInterceptor.Level.BASIC else HttpLoggingInterceptor.Level.NONE
        }
        return OkHttpClient.Builder().addInterceptor(logging)
    }

    private fun buildRetrofit(client: OkHttpClient): Retrofit =
        Retrofit.Builder()
            .baseUrl(BuildConfig.API_BASE_URL)
            .client(client)
            .addConverterFactory(json.asConverterFactory("application/json".toMediaType()))
            .build()
}
