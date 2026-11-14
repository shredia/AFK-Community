import org.jetbrains.kotlin.gradle.ExperimentalWasmDsl
import org.jetbrains.kotlin.gradle.dsl.JvmTarget

plugins {
    alias(libs.plugins.kotlinMultiplatform)
    alias(libs.plugins.androidMultiplatformLibrary)
    alias(libs.plugins.composeMultiplatform)
    alias(libs.plugins.composeCompiler)
    alias(libs.plugins.kotlinSerialization)
}

kotlin {
    jvm()
    js {
        browser()
        binaries.executable()
    }
    @OptIn(ExperimentalWasmDsl::class)
    wasmJs {
        browser()
        binaries.executable()
    }
    android {
        namespace = "io.github.shredia.afkcommunity.shared"
        compileSdk = libs.versions.android.compileSdk.get().toInt()
        minSdk = libs.versions.android.minSdk.get().toInt()
        compilerOptions {
            jvmTarget = JvmTarget.JVM_11
        }
        androidResources {
            enable = true
        }
        withHostTest {
            isIncludeAndroidResources = true
        }
        withDeviceTestBuilder {
            sourceSetTreeName = "test"
        }.configure {
            instrumentationRunner = "androidx.test.runner.AndroidJUnitRunner"
        }
    }
    sourceSets {
        androidMain.dependencies {
            implementation(libs.compose.uiToolingPreview)
            implementation(libs.compose.uiTooling)
        }
        commonMain.dependencies {
            implementation(libs.compose.runtime)
            implementation(libs.compose.foundation)
            implementation(libs.compose.material3)
            implementation(libs.compose.ui)
            implementation(libs.compose.components.resources)
            implementation(libs.compose.uiToolingPreview)
            implementation(libs.androidx.lifecycle.viewmodelCompose)
            implementation(libs.androidx.lifecycle.runtimeCompose)
            implementation(libs.kotlinx.coroutinesCore)
            implementation(libs.kotlinx.serializationJson)
            implementation(libs.kotlinx.datetime)
        }
        commonTest.dependencies {
            implementation(libs.kotlin.test)
            implementation(libs.kotlinx.coroutinesTest)
        }
        jsMain.dependencies {
            implementation(libs.wrappers.browser)
        }
        getByName("androidDeviceTest").dependencies {
            implementation(libs.androidx.testRunner)
        }
    }
}

dependencies {
    androidRuntimeClasspath(libs.compose.uiTooling)
}
// ---------------- Recursos ----------------
// Los idiomas son los MISMOS archivos que usa la app Python (NC/idiomas/*.json): una sola fuente de traducciones.
// Se juntan con src/commonMain/composeResources en build/recursos, y Compose los empaqueta desde ahí
// (quedan en files/idiomas/<código>.json).
val juntarRecursos by tasks.registering(Sync::class) {
    from(layout.projectDirectory.dir("src/commonMain/composeResources"))
    from(rootProject.layout.projectDirectory.dir("../idiomas")) {
        include("*.json")
        into("files/idiomas")
    }
    // Imágenes del juego y tablas del sitio que vienen con la app Python (recursos/assets): las mismas rutas que
    // usan los datos ("/game-ui/...", "/api/catalogue/media/...") quedan en files/assets/...
    from(rootProject.layout.projectDirectory.dir("../recursos/assets")) {
        into("files/assets")
    }
    from(rootProject.layout.projectDirectory.dir("../recursos")) {
        include("fractura_temporal_base.json")
        into("files")
    }
    // Recortes de capturas del juego (íconos de la Fractura que no se pueden descargar): /capturas/<nombre>.png
    from(rootProject.layout.projectDirectory.dir("../recursos/capturas")) {
        into("files/assets/capturas")
    }
    into(layout.buildDirectory.dir("recursos"))
    // Los recursos no se pueden listar: files/idiomas/indice.txt dice qué idiomas hay (un código por línea)
    doLast {
        val carpeta = destinationDir.resolve("files/idiomas")
        val codigos = carpeta.listFiles().orEmpty().filter { it.extension == "json" }.map { it.nameWithoutExtension }
        carpeta.resolve("indice.txt").writeText(codigos.sorted().joinToString("\n"))
    }
}

compose.resources {
    packageOfResClass = "io.github.shredia.afkcommunity.recursos"
    customDirectory(
        sourceSetName = "commonMain",
        directoryProvider = layout.dir(juntarRecursos.map { it.destinationDir }),
    )
}
