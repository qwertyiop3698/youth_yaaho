package com.ysafe.youthyaho.data.repository

import com.ysafe.youthyaho.data.api.CitizenApiService
import com.ysafe.youthyaho.data.api.apiResultOf
import com.ysafe.youthyaho.data.api.dto.DiagnoseRequestDto
import com.ysafe.youthyaho.data.api.dto.DiagnoseResponseDto
import com.ysafe.youthyaho.data.api.dto.ExplanationResponseDto
import com.ysafe.youthyaho.data.api.dto.HistoryResponseDto
import com.ysafe.youthyaho.data.api.dto.RecommendationItemDto

/**
 * 익명(게스트)/로그인 사용자 모두 동일하게 호출한다 - 로그인 여부에 따른 분기는
 * 이 레이어가 아니라 AuthHeaderInterceptor(네트워크 레이어)가 처리한다
 * (backend/app/routers/citizen.py의 diagnose가 선택적 Authorization 헤더를
 * 그대로 받는 것과 대응).
 */
class DiagnosisRepository(private val api: CitizenApiService) {

    // 이번 앱 실행 동안의 진단 결과를 session_id로 캐싱한다. 백엔드에 "세션ID로
    // 진단결과(domain_indices/cluster_membership/risk_probability)만 다시 조회"하는
    // 전용 엔드포인트가 없어서(/history는 다른 모양의 응답) 진단결과 화면이 별도
    // 네트워크 호출 없이 바로 쓸 수 있게 이 레이어에서 들고 있는다. 프로세스가
    // 죽었다 살아나는 경우처럼 캐시가 비어있으면 화면 쪽에서 "결과 없음"으로 처리한다.
    private val diagnoseResultCache = mutableMapOf<String, DiagnoseResponseDto>()

    suspend fun diagnose(
        ageGroup: String,
        dongCode: String,
        incomeBand: String,
        housingType: String,
        hasDebt: Boolean,
    ): Result<DiagnoseResponseDto> =
        apiResultOf {
            api.diagnose(
                DiagnoseRequestDto(
                    age_group = ageGroup,
                    dong_code = dongCode,
                    income_band = incomeBand,
                    housing_type = housingType,
                    has_debt = hasDebt,
                ),
            )
        }.onSuccess { response -> diagnoseResultCache[response.session_id] = response }

    fun getCachedResult(sessionId: String): DiagnoseResponseDto? = diagnoseResultCache[sessionId]

    // 정책 카탈로그 전체(우선순위순)를 반환한다 - "top3만" 자르는 건 이 레이어가
    // 아니라 화면(RecommendationViewModel)의 책임으로 둔다. API 자체는 범용으로
    // 두고, 몇 개를 보여줄지는 클라이언트 화면 요구사항(doc09: "top3")에 맡긴다.
    suspend fun getRecommendations(sessionId: String): Result<List<RecommendationItemDto>> =
        apiResultOf { api.recommendations(sessionId) }.map { it.recommendations }

    // 백엔드가 세션에 캐싱해두고 재요청 시 재호출하지 않는다(app/routers/citizen.py)
    // - 여기서는 그냥 매번 호출하면 된다, 이중 캐싱할 필요 없음.
    suspend fun getExplanation(sessionId: String): Result<ExplanationResponseDto> =
        apiResultOf { api.explanation(sessionId) }

    // 백엔드가 session_id당 진단 1건만 저장한다는 한계(citizen.py의 note 필드가
    // 그대로 알려줌)를 이 레이어에서 감추거나 가공하지 않고 원본 그대로 반환한다 -
    // "여러 항목을 순회하는 히스토리"처럼 보이게 만들면 실제로 없는 기능을 있는
    // 것처럼 오해시킬 수 있다.
    suspend fun getHistory(sessionId: String): Result<HistoryResponseDto> =
        apiResultOf { api.history(sessionId) }
}
