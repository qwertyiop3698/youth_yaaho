package com.ysafe.youthyaho.data.api

import java.io.IOException
import kotlinx.serialization.Serializable
import kotlinx.serialization.json.Json
import retrofit2.Response

/** HTTP 상태코드를 들고 다니는 예외 - ViewModel이 401/403/409 등을 구분해 다른
 * 메시지를 보여줄 때 사용한다(예: 나이초과 403 vs 비번오류 401). */
class ApiException(val code: Int, message: String) : Exception(message)

@Serializable
private data class ErrorBodyDto(val detail: String? = null)

private val errorJson = Json { ignoreUnknownKeys = true }

/**
 * Retrofit `Response<T>`를 [Result]로 변환한다. 성공(2xx)이면 body를, 실패면
 * FastAPI의 `{"detail": "..."}` 에러 응답을 파싱해 사람이 읽을 메시지로 감싼
 * [ApiException]을 담는다. 네트워크 자체가 끊긴 경우([IOException])도 여기서
 * 잡아서 동일한 [Result] 형태로 통일한다.
 */
suspend fun <T> apiResultOf(call: suspend () -> Response<T>): Result<T> {
    return try {
        val response = call()
        if (response.isSuccessful) {
            val body = response.body()
            if (body != null) {
                Result.success(body)
            } else {
                Result.failure(ApiException(response.code(), "서버 응답이 비어 있습니다."))
            }
        } else {
            val detail = parseDetail(response.errorBody()?.string())
                ?: "요청이 실패했습니다 (HTTP ${response.code()})."
            Result.failure(ApiException(response.code(), detail))
        }
    } catch (e: IOException) {
        Result.failure(ApiException(0, "서버에 연결할 수 없습니다. 네트워크 상태를 확인해주세요."))
    }
}

private fun parseDetail(rawBody: String?): String? {
    if (rawBody.isNullOrBlank()) return null
    return try {
        errorJson.decodeFromString(ErrorBodyDto.serializer(), rawBody).detail
    } catch (e: Exception) {
        null
    }
}
