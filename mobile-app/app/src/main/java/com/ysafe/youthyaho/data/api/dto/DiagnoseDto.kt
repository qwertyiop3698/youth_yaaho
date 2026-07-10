package com.ysafe.youthyaho.data.api.dto

import kotlinx.serialization.Serializable

@Serializable
data class DiagnoseRequestDto(
    val age_group: String,
    val dong_code: String,
    val income_band: String,
    val housing_type: String,
    val has_debt: Boolean = false,
)

@Serializable
data class DiagnoseResponseDto(
    val session_id: String,
    val domain_indices: Map<String, Float>,
    val cluster_membership: Map<String, Float>,
    val risk_probability: Float? = null,
    val diagnosis_mode: String,
    val approximation_notice: String,
)
