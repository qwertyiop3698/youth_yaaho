package com.ysafe.youthyaho.data.local

import android.content.Context
import android.security.keystore.KeyGenParameterSpec
import android.security.keystore.KeyProperties
import android.util.Base64
import androidx.datastore.preferences.core.booleanPreferencesKey
import androidx.datastore.preferences.core.edit
import androidx.datastore.preferences.core.stringPreferencesKey
import androidx.datastore.preferences.preferencesDataStore
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.flow.map
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.launch
import java.nio.ByteBuffer
import java.security.KeyStore
import javax.crypto.Cipher
import javax.crypto.KeyGenerator
import javax.crypto.SecretKey
import javax.crypto.spec.GCMParameterSpec

private val Context.authDataStore by preferencesDataStore(name = "auth_prefs")

/**
 * 로그인 토큰(access/refresh)은 Android Keystore의 AES-GCM 키로 암호화한 뒤
 * DataStore에 저장한다. 암호화되지 않은 구버전 값은 사용하지 않고 자동 삭제해
 * 업데이트 뒤 한 번 재로그인하도록 한다. 게스트는 토큰 없이 익명 플로우를 쓴다.
 */
class TokenStore(private val context: Context) {

    private object Keys {
        val ACCESS_TOKEN = stringPreferencesKey("access_token")
        val REFRESH_TOKEN = stringPreferencesKey("refresh_token")
        val NOTIFICATIONS_OPT_IN = booleanPreferencesKey("notifications_opt_in")
    }

    private val cleanupScope = CoroutineScope(SupervisorJob() + Dispatchers.IO)

    init {
        cleanupScope.launch {
            context.authDataStore.edit { prefs ->
                val access = prefs[Keys.ACCESS_TOKEN]
                val refresh = prefs[Keys.REFRESH_TOKEN]
                if (access != null && !TokenCipher.isEncrypted(access)) prefs.remove(Keys.ACCESS_TOKEN)
                if (refresh != null && !TokenCipher.isEncrypted(refresh)) prefs.remove(Keys.REFRESH_TOKEN)
            }
        }
    }

    val accessTokenFlow: Flow<String?> = context.authDataStore.data.map {
        it[Keys.ACCESS_TOKEN]?.let(TokenCipher::decryptOrNull)
    }
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
        context.authDataStore.data.map { prefs ->
            prefs[Keys.REFRESH_TOKEN]?.let(TokenCipher::decryptOrNull)
        }.first()

    suspend fun saveTokens(accessToken: String, refreshToken: String) {
        context.authDataStore.edit { prefs ->
            prefs[Keys.ACCESS_TOKEN] = TokenCipher.encrypt(accessToken)
            prefs[Keys.REFRESH_TOKEN] = TokenCipher.encrypt(refreshToken)
        }
    }

    suspend fun clear() {
        context.authDataStore.edit { prefs ->
            prefs.remove(Keys.ACCESS_TOKEN)
            prefs.remove(Keys.REFRESH_TOKEN)
        }
    }
}

private object TokenCipher {
    private const val KEY_ALIAS = "youth_yaho_auth_tokens_v1"
    private const val ANDROID_KEYSTORE = "AndroidKeyStore"
    private const val TRANSFORMATION = "AES/GCM/NoPadding"
    private const val PREFIX = "v1:"

    fun isEncrypted(value: String): Boolean = value.startsWith(PREFIX)

    fun encrypt(plainText: String): String {
        val cipher = Cipher.getInstance(TRANSFORMATION)
        cipher.init(Cipher.ENCRYPT_MODE, getOrCreateKey())
        val encrypted = cipher.doFinal(plainText.toByteArray(Charsets.UTF_8))
        val iv = cipher.iv
        require(iv.size <= 255) { "AES-GCM IV가 너무 깁니다." }
        val payload = ByteBuffer.allocate(1 + iv.size + encrypted.size)
            .put(iv.size.toByte())
            .put(iv)
            .put(encrypted)
            .array()
        return PREFIX + Base64.encodeToString(payload, Base64.NO_WRAP)
    }

    fun decryptOrNull(encoded: String): String? {
        if (!isEncrypted(encoded)) return null
        return runCatching {
            val payload = Base64.decode(encoded.removePrefix(PREFIX), Base64.NO_WRAP)
            require(payload.isNotEmpty())
            val ivSize = payload[0].toInt() and 0xff
            require(ivSize in 12..16 && payload.size > 1 + ivSize)
            val iv = payload.copyOfRange(1, 1 + ivSize)
            val cipherText = payload.copyOfRange(1 + ivSize, payload.size)
            val cipher = Cipher.getInstance(TRANSFORMATION)
            cipher.init(Cipher.DECRYPT_MODE, getOrCreateKey(), GCMParameterSpec(128, iv))
            cipher.doFinal(cipherText).toString(Charsets.UTF_8)
        }.getOrNull()
    }

    private fun getOrCreateKey(): SecretKey {
        val keyStore = KeyStore.getInstance(ANDROID_KEYSTORE).apply { load(null) }
        (keyStore.getKey(KEY_ALIAS, null) as? SecretKey)?.let { return it }

        return KeyGenerator.getInstance(KeyProperties.KEY_ALGORITHM_AES, ANDROID_KEYSTORE).run {
            init(
                KeyGenParameterSpec.Builder(
                    KEY_ALIAS,
                    KeyProperties.PURPOSE_ENCRYPT or KeyProperties.PURPOSE_DECRYPT,
                )
                    .setBlockModes(KeyProperties.BLOCK_MODE_GCM)
                    .setEncryptionPaddings(KeyProperties.ENCRYPTION_PADDING_NONE)
                    .build(),
            )
            generateKey()
        }
    }
}
