package com.ysafe.youthyaho.data.api.dto

import kotlinx.serialization.Serializable

@Serializable
data class RecommendationItemDto(
    val policy: String,
    val priority: Int,
    val expected_effect: Float,
    val eligible: Boolean,
    val eligibility_confidence: String,
    val url: String? = null,
)

@Serializable
data class OtherPolicyItemDto(
    val policy: String,
    val category: String? = null,
    val agency: String? = null,
    val description: String? = null,
    val url: String? = null,
    val apply_period: String? = null,
)

@Serializable
data class RecommendationsResponseDto(
    val recommendations: List<RecommendationItemDto>,
    val other_policies: List<OtherPolicyItemDto> = emptyList(),
)
