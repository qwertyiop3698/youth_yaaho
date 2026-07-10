import java.io.FileInputStream
import java.util.Properties
import org.jetbrains.kotlin.gradle.dsl.JvmTarget

// org.jetbrains.kotlin.android는 적용하지 않는다 - AGP 9.0+의 built-in Kotlin 지원과
// 충돌해서 "Cannot add extension with name 'kotlin'" 에러가 난다(root build.gradle.kts
// 주석 참고). compose/serialization 서브플러그인은 built-in Kotlin과 호환되므로 그대로 둔다.
plugins {
    alias(libs.plugins.android.application)
    alias(libs.plugins.kotlin.compose)
    alias(libs.plugins.kotlin.serialization)
}

// local.properties에서 API_BASE_URL을 읽는다(실기기/LAN IP 연결용, git에 커밋되지
// 않는 파일이라 하드코딩이 아님). 없으면 에뮬레이터 기본값(10.0.2.2)으로 폴백한다.
// 전환 방법:
//   1) 에뮬레이터(기본값): local.properties에 아무것도 안 적으면 됨.
//   2) 실기기 + adb reverse: `adb reverse tcp:8000 tcp:8000` 실행 후
//      local.properties에 `API_BASE_URL=http://localhost:8000/` 추가.
//   3) 실기기 + LAN IP: 개발 PC의 실제 IP로 local.properties에
//      `API_BASE_URL=http://192.168.x.x:8000/` 추가(PC와 폰이 같은 네트워크에 있어야 함).
val localProperties = Properties().apply {
    val file = rootProject.file("local.properties")
    if (file.exists()) {
        load(FileInputStream(file))
    }
}
val apiBaseUrl: String = (localProperties.getProperty("API_BASE_URL") ?: "http://10.0.2.2:8000/")

android {
    namespace = "com.ysafe.youthyaho"
    compileSdk = 36

    defaultConfig {
        applicationId = "com.ysafe.youthyaho"
        minSdk = 26
        targetSdk = 36
        versionCode = 1
        versionName = "0.1.0"

        buildConfigField("String", "API_BASE_URL", "\"$apiBaseUrl\"")
        testInstrumentationRunner = "androidx.test.runner.AndroidJUnitRunner"
    }

    buildTypes {
        debug {
            // 명시적으로 false를 적어서 "기본값에 의존하다 뭔가 잘못 적용된 것 아닌가"
            // 하는 의심 여지를 없앤다. 참고: R8은 shrink 여부와 무관하게 D8을 대체하는
            // dex 변환기라서, isMinifyEnabled=false여도 빌드 로그에 R8 단계 자체는
            // 정상적으로 나타난다(축소 없이 pass-through로 dex만 만듦) - R8이 "보인다"는
            // 것 자체가 비정상 신호는 아니다.
            isMinifyEnabled = false
        }
        release {
            isMinifyEnabled = false
            proguardFiles(getDefaultProguardFile("proguard-android-optimize.txt"), "proguard-rules.pro")
        }
    }

    buildFeatures {
        compose = true
        buildConfig = true
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }

    packaging {
        resources {
            excludes += "/META-INF/{AL2.0,LGPL2.1}"
        }
    }
}

// kotlinOptions{} 블록은 Kotlin 2.2에서 제거됐다 - compilerOptions{}로 대체.
// 이 "kotlin" extension은 이제 kotlin-android 플러그인이 아니라 AGP 9.0+의
// built-in Kotlin 지원이 등록해준다(위 plugins{} 블록 주석 참고). 사실
// compileOptions의 targetCompatibility(17)로 jvmTarget이 자동 결정되지만, 의도를
// 명시적으로 남겨두려고 그대로 둔다.
kotlin {
    compilerOptions {
        jvmTarget.set(JvmTarget.JVM_17)
    }
}

dependencies {
    implementation(libs.androidx.core.ktx)
    implementation(libs.androidx.lifecycle.viewmodel.compose)
    implementation(libs.androidx.lifecycle.runtime.compose)
    implementation(libs.androidx.activity.compose)
    implementation(libs.androidx.navigation.compose)
    implementation(libs.androidx.datastore.preferences)

    implementation(platform(libs.compose.bom))
    implementation(libs.compose.ui)
    implementation(libs.compose.ui.graphics)
    implementation(libs.compose.ui.tooling.preview)
    implementation(libs.compose.material3)
    debugImplementation(libs.compose.ui.tooling)
    debugImplementation(libs.compose.ui.test.manifest)

    implementation(libs.retrofit.core)
    implementation(libs.retrofit.kotlinx.serialization.converter)
    implementation(libs.okhttp.core)
    implementation(libs.okhttp.logging.interceptor)
    implementation(libs.kotlinx.serialization.json)
    implementation(libs.kotlinx.coroutines.android)

    // 레이더차트(진단결과 화면) - Vico는 radar 미지원이라 원본 MPAndroidChart를
    // AndroidView로 래핑해서 사용(docs/09 조사 결론, PLAN.md 참고).
    implementation(libs.mp.android.chart)

    testImplementation(libs.junit)
    testImplementation(libs.mockk)
    testImplementation(libs.turbine)
    testImplementation(libs.kotlinx.coroutines.test)
    testImplementation(libs.androidx.core.testing)

    androidTestImplementation(libs.androidx.junit)
    androidTestImplementation(libs.androidx.espresso.core)
    androidTestImplementation(platform(libs.compose.bom))
    androidTestImplementation(libs.compose.ui.test.junit4)
}
