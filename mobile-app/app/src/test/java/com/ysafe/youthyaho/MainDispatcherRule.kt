package com.ysafe.youthyaho

import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.test.TestDispatcher
import kotlinx.coroutines.test.UnconfinedTestDispatcher
import kotlinx.coroutines.test.resetMain
import kotlinx.coroutines.test.setMain
import org.junit.rules.TestWatcher
import org.junit.runner.Description

/**
 * ViewModel의 viewModelScope(Dispatchers.Main 기반)를 JVM 단위테스트에서 실행하기
 * 위한 JUnit Rule - 순수 JVM 테스트에는 Dispatchers.Main이 없어서 이게 없으면
 * "Module with the Main dispatcher had failed to initialize" 예외가 난다.
 * UnconfinedTestDispatcher를 써서 launch된 코루틴이 (실제 정지 없이 mock으로 즉시
 * 반환되는 한) 동기적으로 완료되게 하여 테스트에서 advanceUntilIdle() 없이 바로
 * uiState를 검증할 수 있게 한다.
 */
@OptIn(ExperimentalCoroutinesApi::class)
class MainDispatcherRule(
    private val testDispatcher: TestDispatcher = UnconfinedTestDispatcher(),
) : TestWatcher() {
    override fun starting(description: Description) {
        Dispatchers.setMain(testDispatcher)
    }

    override fun finished(description: Description) {
        Dispatchers.resetMain()
    }
}
