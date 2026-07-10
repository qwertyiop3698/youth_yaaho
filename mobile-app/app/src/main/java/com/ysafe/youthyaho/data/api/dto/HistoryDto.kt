package com.ysafe.youthyaho.data.api.dto

import kotlinx.serialization.Serializable
import kotlinx.serialization.json.JsonElement

@Serializable
data class HistoryEntryDto(
    val created_at: String,
    // 백엔드에서 dict[str, Any]로 오는 자유형식 필드라 동적 JSON 그대로 보관한다.
    val diagnosis_result: JsonElement,
)

@Serializable
data class HistoryResponseDto(
    val session_id: String,
    val history: List<HistoryEntryDto>,
    val note: String,
)
