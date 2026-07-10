package com.ysafe.youthyaho.data.api.dto

import kotlinx.serialization.Serializable

@Serializable
data class ExplanationResponseDto(
    val session_id: String,
    val explanation: String,
    val is_llm_generated: Boolean,
)
