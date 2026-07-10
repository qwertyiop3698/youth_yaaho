// root build.gradle.kts - 플러그인 버전만 선언(apply는 app/build.gradle.kts에서).
//
// org.jetbrains.kotlin.android는 일부러 안 넣는다 - AGP 9.0+부터 "built-in Kotlin"을
// 기본 제공해서 AGP가 이미 "kotlin" extension을 등록하는데, 여기에 kotlin-android
// 플러그인까지 적용하면 "Cannot add extension with name 'kotlin'" 충돌이 난다
// (developer.android.com/build/migrate-to-built-in-kotlin 확인, 2026-07-10).
plugins {
    alias(libs.plugins.android.application) apply false
    alias(libs.plugins.kotlin.compose) apply false
    alias(libs.plugins.kotlin.serialization) apply false
}
