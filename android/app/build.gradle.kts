import java.util.Properties

plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
}

val ndkVer = "27.2.12479018"

android {
    namespace = "dev.imbrasas.varnele"
    compileSdk = 35
    ndkVersion = ndkVer

    defaultConfig {
        applicationId = "dev.imbrasas.varnele"
        minSdk = 26
        targetSdk = 35
        versionCode = 1
        versionName = "0.1"
    }
    buildTypes {
        release {
            isMinifyEnabled = false
        }
    }
    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }
    kotlinOptions {
        jvmTarget = "17"
    }
}

// Build the Rust checker (rust/android) for the phone (arm64) and the emulator (x86_64).
val repo: File = rootDir.parentFile
val sdkDir: String = Properties()
    .apply { rootProject.file("local.properties").inputStream().use { load(it) } }
    .getProperty("sdk.dir")
val jniLibs = file("src/main/jniLibs")

val exportData by tasks.registering(Exec::class) {
    description = "Compile the grammar into data/varnele.bin (python3 -m varnele export)"
    workingDir = repo
    commandLine("python3", "-m", "varnele", "export")
    onlyIf { !File(repo, "data/varnele.bin").exists() }
}

val cargoBuild by tasks.registering(Exec::class) {
    description = "Build libvarnele_android.so with cargo-ndk"
    dependsOn(exportData)
    workingDir = File(repo, "rust")
    environment("ANDROID_NDK_HOME", "$sdkDir/ndk/$ndkVer")
    commandLine(
        "${System.getProperty("user.home")}/.cargo/bin/cargo", "ndk",
        "-t", "arm64-v8a", "-t", "x86_64",
        "-o", jniLibs.absolutePath,
        "build", "--release", "-p", "varnele-android",
    )
}

tasks.named("preBuild") { dependsOn(cargoBuild) }
