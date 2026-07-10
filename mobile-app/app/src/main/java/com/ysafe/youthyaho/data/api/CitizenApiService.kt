package com.ysafe.youthyaho.data.api

import com.ysafe.youthyaho.data.api.dto.DiagnoseRequestDto
import com.ysafe.youthyaho.data.api.dto.DiagnoseResponseDto
import com.ysafe.youthyaho.data.api.dto.ExplanationResponseDto
import com.ysafe.youthyaho.data.api.dto.HistoryResponseDto
import com.ysafe.youthyaho.data.api.dto.LoginRequestDto
import com.ysafe.youthyaho.data.api.dto.RecommendationsResponseDto
import com.ysafe.youthyaho.data.api.dto.RefreshRequestDto
import com.ysafe.youthyaho.data.api.dto.SignupRequestDto
import com.ysafe.youthyaho.data.api.dto.SignupResponseDto
import com.ysafe.youthyaho.data.api.dto.TokenResponseDto
import retrofit2.Response
import retrofit2.http.Body
import retrofit2.http.GET
import retrofit2.http.POST
import retrofit2.http.Path

/**
 * backend/app/routers/citizen.py 그대로 매핑. diagnose는 Authorization 헤더를
 * TokenAuthenticator/OkHttp 인터셉터가 자동으로 붙여준다(로그인 상태일 때만) -
 * 여기 인터페이스에는 명시적 헤더 파라미터를 두지 않는다(익명 플로우와 로그인
 * 플로우를 이 레이어에서 분기하지 않기 위함).
 */
interface CitizenApiService {

    @POST("api/v1/citizen/auth/signup")
    suspend fun signup(@Body request: SignupRequestDto): Response<SignupResponseDto>

    @POST("api/v1/citizen/auth/login")
    suspend fun login(@Body request: LoginRequestDto): Response<TokenResponseDto>

    @POST("api/v1/citizen/auth/refresh")
    suspend fun refresh(@Body request: RefreshRequestDto): Response<TokenResponseDto>

    @POST("api/v1/citizen/diagnose")
    suspend fun diagnose(@Body request: DiagnoseRequestDto): Response<DiagnoseResponseDto>

    @GET("api/v1/citizen/{sessionId}/recommendations")
    suspend fun recommendations(@Path("sessionId") sessionId: String): Response<RecommendationsResponseDto>

    @GET("api/v1/citizen/{sessionId}/explanation")
    suspend fun explanation(@Path("sessionId") sessionId: String): Response<ExplanationResponseDto>

    @GET("api/v1/citizen/{sessionId}/history")
    suspend fun history(@Path("sessionId") sessionId: String): Response<HistoryResponseDto>
}
