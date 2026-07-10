package com.ysafe.youthyaho

import android.content.Context
import com.ysafe.youthyaho.data.api.NetworkModule
import com.ysafe.youthyaho.data.local.TokenStore
import com.ysafe.youthyaho.data.repository.AuthRepository
import com.ysafe.youthyaho.data.repository.DiagnosisRepository

/**
 * 수동 DI 컨테이너. Hilt는 도입하지 않았다 - 리포지토리/뷰모델 개수가 적어(해커톤
 * MVP 범위) KSP/kapt 애노테이션 프로세싱의 빌드시간 비용을 들일 이유가 없다고
 * 판단했다(PLAN.md 참고). 규모가 커지면 이 클래스를 Hilt Module로 교체하면 된다.
 */
class AppContainer(context: Context) {
    val tokenStore = TokenStore(context.applicationContext)
    private val apiService = NetworkModule.create(tokenStore)

    val authRepository = AuthRepository(apiService, tokenStore)
    val diagnosisRepository = DiagnosisRepository(apiService)
}
