package com.ysafe.youthyaho.ui.settings

import com.ysafe.youthyaho.MainDispatcherRule
import com.ysafe.youthyaho.data.local.TokenStore
import com.ysafe.youthyaho.data.repository.AuthRepository
import io.mockk.coVerify
import io.mockk.coEvery
import io.mockk.every
import io.mockk.mockk
import kotlinx.coroutines.flow.flowOf
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.test.runTest
import kotlinx.coroutines.test.advanceUntilIdle
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Rule
import org.junit.Test

@OptIn(ExperimentalCoroutinesApi::class)
class SettingsViewModelTest {

    @get:Rule
    val mainDispatcherRule = MainDispatcherRule()

    private val tokenStore: TokenStore = mockk(relaxed = true)
    private val authRepository: AuthRepository = mockk(relaxed = true)

    private fun viewModel(notificationsEnabled: Boolean = false, isLoggedIn: Boolean = false): SettingsViewModel {
        every { tokenStore.notificationsOptInFlow } returns flowOf(notificationsEnabled)
        every { tokenStore.isLoggedInFlow } returns flowOf(isLoggedIn)
        return SettingsViewModel(tokenStore, authRepository)
    }

    @Test
    fun `initial state reflects stored notification preference and login state`() = runTest {
        val vm = viewModel(notificationsEnabled = true, isLoggedIn = true)

        val state = vm.uiState.value
        assertTrue(state.notificationsEnabled)
        assertTrue(state.isLoggedIn)
    }

    @Test
    fun `setNotificationsEnabled persists to token store`() = runTest {
        val vm = viewModel()

        vm.setNotificationsEnabled(true)

        coVerify { tokenStore.setNotificationsOptIn(true) }
    }

    @Test
    fun `delete request flow calls server and marks account deleted`() = runTest {
        coEvery { authRepository.deleteAccount() } returns Result.success(Unit)
        val vm = viewModel(isLoggedIn = true)

        vm.requestDeleteAccount()
        assertTrue(vm.uiState.value.showDeleteConfirmDialog)

        vm.confirmDeleteRequest()
        advanceUntilIdle()
        assertFalse(vm.uiState.value.showDeleteConfirmDialog)
        assertTrue(vm.uiState.value.accountDeleted)
        coVerify { authRepository.deleteAccount() }
    }

    @Test
    fun `dismissDeleteDialog hides dialog without marking submitted`() = runTest {
        val vm = viewModel()

        vm.requestDeleteAccount()
        vm.dismissDeleteDialog()

        assertFalse(vm.uiState.value.showDeleteConfirmDialog)
        assertFalse(vm.uiState.value.accountDeleted)
    }

    @Test
    fun `logout delegates to auth repository`() = runTest {
        val vm = viewModel()

        vm.logout()

        coVerify { authRepository.logout() }
    }
}
