package com.ysafe.youthyaho.data.repository

import com.ysafe.youthyaho.data.api.CitizenApiService
import com.ysafe.youthyaho.data.api.apiResultOf
import com.ysafe.youthyaho.data.api.dto.LoginRequestDto
import com.ysafe.youthyaho.data.api.dto.SignupRequestDto
import com.ysafe.youthyaho.data.api.dto.SignupResponseDto
import com.ysafe.youthyaho.data.local.TokenStore
import kotlinx.coroutines.flow.Flow

/**
 * 회원가입/로그인/로그아웃. 익명(게스트) 진단 플로우는 이 리포지토리를 거치지 않고
 * DiagnosisRepository가 곧바로 CitizenApiService.diagnose()를 호출한다 - 로그인은
 * "히스토리 저장/조회를 위한 선택 기능"이라 진단 자체와 결합하지 않는다(docs/09).
 */
class AuthRepository(
    private val api: CitizenApiService,
    private val tokenStore: TokenStore,
) {
    val isLoggedIn: Flow<Boolean> = tokenStore.isLoggedInFlow

    suspend fun signup(
        email: String,
        password: String,
        birthdate: String, // "YYYY-MM-DD"
        dongCode: String?,
    ): Result<SignupResponseDto> =
        apiResultOf {
            api.signup(
                SignupRequestDto(email = email, password = password, birthdate = birthdate, dong_code = dongCode),
            )
        }

    suspend fun login(email: String, password: String): Result<Unit> =
        apiResultOf { api.login(LoginRequestDto(email = email, password = password)) }
            .map { tokens -> tokenStore.saveTokens(tokens.access_token, tokens.refresh_token) }

    suspend fun logout() {
        tokenStore.clear()
    }
}
