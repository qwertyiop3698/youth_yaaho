pluginManagement {
    repositories {
        google()
        mavenCentral()
        gradlePluginPortal()
    }
}

dependencyResolutionManagement {
    repositoriesMode.set(RepositoriesMode.FAIL_ON_PROJECT_REPOS)
    repositories {
        google()
        mavenCentral()
        // MPAndroidChart(레이더차트)는 JitPack에만 배포돼 있음 - docs/09 차트 라이브러리 조사 결론.
        maven { url = uri("https://jitpack.io") }
    }
}

rootProject.name = "youthyaho"
include(":app")
