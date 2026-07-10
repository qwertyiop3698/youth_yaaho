package com.ysafe.youthyaho.data.api.dto

import kotlinx.serialization.Serializable

/**
 * backend/app/schemas.py의 필드명을 그대로 따른다(snake_case) - DTO는 와이어 포맷과
 * 1:1로 맞추고, UI가 쓰는 카멜케이스 도메인 모델은 domain/model에서 별도로 둔다.
 */
@Serializable
data class SignupRequestDto(
    val email: String,
    val password: String,
    val birthdate: String, // "YYYY-MM-DD"
    val dong_code: String? = null,
)

@Serializable
data class SignupResponseDto(
    val user_id: String,
    val email: String,
    val is_age_verified: Boolean,
)

@Serializable
data class LoginRequestDto(
    val email: String,
    val password: String,
)

@Serializable
data class RefreshRequestDto(
    val refresh_token: String,
)

@Serializable
data class TokenResponseDto(
    val access_token: String,
    val refresh_token: String,
    val token_type: String = "bearer",
)
