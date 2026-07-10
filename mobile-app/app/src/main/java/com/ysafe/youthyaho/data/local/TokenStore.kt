package com.ysafe.youthyaho.data.local

import android.content.Context
import androidx.datastore.preferences.core.booleanPreferencesKey
import androidx.datastore.preferences.core.edit
import androidx.datastore.preferences.core.stringPreferencesKey
import androidx.datastore.preferences.preferencesDataStore
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.flow.map

private val Context.authDataStore by preferencesDataStore(name = "auth_prefs")

/**
 * 로그인 토큰(access/refresh)을 로컬에 저장한다. 해커톤 데모 범위라 평문 DataStore
 * Preferences로 충분 - 실 서비스 전환 시 암호화 저장(EncryptedSharedPreferences 등)으로
 * 강화할 것. 게스트(비로그인) 사용자는 이 토큰들이 항상 null이고, 그래도 진단
 * 플로우는 그대로 동작한다(익명 세션 기반).
 */
class TokenStore(private val context: Context) {

    private object Keys {
        val ACCESS_TOKEN = stringPreferencesKey("access_token")
        val REFRESH_TOKEN = stringPreferencesKey("refresh_token")
        val NOTIFICATIONS_OPT_IN = booleanPreferencesKey("notifications_opt_in")
    }

    val accessTokenFlow: Flow<String?> = context.authDataStore.data.map { it[Keys.ACCESS_TOKEN] }
    val isLoggedInFlow: Flow<Boolean> = accessTokenFlow.map { it != null }

    // 알림 동의는 대응하는 FCM 연동이 없어 로컬에만 저장한다(PLAN.md "알려드릴 제약" 2번) -
    // 서버로 전송하지 않으므로 여러 기기 간 동기화는 되지 않는다.
    val notificationsOptInFlow: Flow<Boolean> =
        context.authDataStore.data.map { it[Keys.NOTIFICATIONS_OPT_IN] ?: false }

    suspend fun setNotificationsOptIn(enabled: Boolean) {
        context.authDataStore.edit { prefs -> prefs[Keys.NOTIFICATIONS_OPT_IN] = enabled }
    }

    suspend fun currentAccessToken(): String? = accessTokenFlow.first()

    suspend fun currentRefreshToken(): String? =
        context.authDataStore.data.map { it[Keys.REFRESH_TOKEN] }.first()

    suspend fun saveTokens(accessToken: String, refreshToken: String) {
        context.authDataStore.edit { prefs ->
            prefs[Keys.ACCESS_TOKEN] = accessToken
            prefs[Keys.REFRESH_TOKEN] = refreshToken
        }
    }

    suspend fun clear() {
        context.authDataStore.edit { it.clear() }
    }
}
