plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
    id("com.chaquo.python")
}

android {
    namespace = "com.alvsia.pro"
    compileSdk = 34
    ndkVersion = "27.0.12077973"

    defaultConfig {
        applicationId = "com.alvsia.pro"
        minSdk = 26
        targetSdk = 34
        versionCode = 100
        versionName = "6.0.0-smart-premium"
        buildConfigField("int", "PROTO", "2")
        buildConfigField("String", "CERT_SHA256", "\"99b33815c88a17abbcfe22be15250363f6dfc79c11ffc980e71b62b74b1f295c\"")
        // Sprint 1: DEX hash placeholder — CodeMagic seal script patches this at build time
        buildConfigField("String", "DEX_SHA256", "\"0000000000000000000000000000000000000000000000000000000000000000\"")
        buildConfigField("int", "EXPECTED_DEX_COUNT", "1")
        ndk {
            abiFilters += listOf("arm64-v8a")
        }
    }

    // Sprint 1: R8 full mode for deeper obfuscation (control flow + class merging)
    buildFeatures {
        compose = true
        buildConfig = true
    }

    externalNativeBuild {
        cmake {
            path = file("src/main/cpp/CMakeLists.txt")
            version = "3.22.1"
        }
    }

    // ABI is restricted to arm64-v8a by defaultConfig.ndk. Do not enable splits here,
    // because Android Gradle Plugin rejects using splits.abi and ndk.abiFilters together.

    buildTypes {
        release {
            isMinifyEnabled = true
            isShrinkResources = true
            isCrunchPngs = true  // Sprint 1: smaller PNGs in release
            // Sprint 1: R8 full mode + aggressive optimization
            isDebuggable = false
            isJniDebuggable = false
            proguardFiles(
                getDefaultProguardFile("proguard-android-optimize.txt"),
                "proguard-rules.pro"
            )
            // Sprint 1: V2 signing enforced (anti-repack)
            signingConfigs {
                create("release") {
                    // Placeholders — CodeMagic injects real values from CM_KEYSTORE secrets
                    // storeFile = file("alvsia-release.keystore")
                    // storePassword = System.getenv("CM_KEYSTORE_PASSWORD")
                    // keyAlias = System.getenv("CM_KEY_ALIAS")
                    // keyPassword = System.getenv("CM_KEY_PASSWORD")
                    enableV1Signing = false  // minSdk 26; retain v2/v3 only for release hardening
                    enableV2Signing = true   // V2 covers whole APK — enforce
                    enableV3Signing = true   // V3 adds key rotation support
                }
            }
        }
        debug {
            isMinifyEnabled = false
            isDebuggable = true
        }
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }
    kotlinOptions {
        jvmTarget = "17"
        freeCompilerArgs += listOf(
            "-Xno-call-assertions",
            "-Xno-receiver-assertions",
            "-Xno-param-assertions"
        )
    }
    composeOptions {
        kotlinCompilerExtensionVersion = "1.5.14"
    }
    packaging {
        jniLibs {
            // Extract executable native CLI engines so ProcessBuilder can invoke them
            // from ApplicationInfo.nativeLibraryDir on Android 10+.
            useLegacyPackaging = true
        }
        resources {
            excludes += setOf(
                "META-INF/version-control-info.textproto",
                "**/version-control-info.textproto",
                "META-INF/*.version",
                "**/META-INF/*.version",
                "META-INF/*.kotlin_module",
                "META-INF/DEPENDENCIES",
                "META-INF/LICENSE.md",
                "META-INF/NOTICE.md",
                "**/kotlin-tooling-metadata.json",
                "**/DebugProbesKt.bin",
                "**/META-INF/com.android.tools/**",
                "**/*.kotlin_builtins",
            )
        }
    }
}

chaquopy {
    defaultConfig {
        version = "3.8"
        pip {
            // Retry slow Chaquopy index downloads; source fallback cannot compile native packages here.
            options("--timeout", "120", "--retries", "10")
            install("pycryptodome")
            install("requests")
            install("rich")
            install("zstandard")
        }
    }
}

dependencies {
    implementation(files("libs/unluac_pro.jar"))

    val composeBom = platform("androidx.compose:compose-bom:2024.06.00")
    implementation(composeBom)
    implementation("androidx.compose.ui:ui")
    implementation("androidx.compose.ui:ui-graphics")
    implementation("androidx.compose.foundation:foundation")
    implementation("androidx.compose.material3:material3")
    implementation("androidx.activity:activity-compose:1.9.0")
    implementation("androidx.lifecycle:lifecycle-runtime-ktx:2.8.3")
    implementation("androidx.lifecycle:lifecycle-runtime-compose:2.8.3")
    implementation("com.squareup.okhttp3:okhttp:4.12.0")
    implementation("org.jetbrains.kotlinx:kotlinx-coroutines-android:1.8.1")
}
