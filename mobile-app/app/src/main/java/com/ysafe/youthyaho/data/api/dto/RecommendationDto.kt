package com.ysafe.youthyaho.data.api.dto

import kotlinx.serialization.Serializable

@Serializable
data class RecommendationItemDto(
    val policy: String,
    val priority: Int,
    val expected_effect: Float,
    val eligible: Boolean,
    val eligibility_confidence: String,
)

@Serializable
data class RecommendationsResponseDto(
    val recommendations: List<RecommendationItemDto>,
)
