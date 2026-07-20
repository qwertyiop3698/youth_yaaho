package com.ysafe.youthyaho.data.repository

import com.ysafe.youthyaho.data.api.CitizenApiService
import com.ysafe.youthyaho.data.api.apiResultOf
import com.ysafe.youthyaho.data.api.dto.DemandEligibilityDto
import com.ysafe.youthyaho.data.api.dto.DemandFormDto
import com.ysafe.youthyaho.data.api.dto.DemandSubmissionDto
import com.ysafe.youthyaho.data.api.dto.SubmitDemandRequestDto

class PolicyDemandRepository(private val api: CitizenApiService) {
    suspend fun eligibility(sessionId: String, reason: String): Result<DemandEligibilityDto> =
        apiResultOf { api.demandEligibility(sessionId, reason) }
    suspend fun form(): Result<DemandFormDto> = apiResultOf { api.demandForm() }
    suspend fun submit(request: SubmitDemandRequestDto): Result<DemandSubmissionDto> =
        apiResultOf { api.submitDemand(request) }
}

