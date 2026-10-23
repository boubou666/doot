plugins {
    id("com.android.application")
    id("com.chaquo.python")
}

// doot lui-meme vient de ce depot ; desktop-overlay doit connaitre Android
// (0.3 et plus). `-PdesktopOverlay=<chemin ou url pip>` en choisit un autre.
val dootPackage = rootProject.projectDir.resolve("../../doot")
val desktopOverlay = providers.gradleProperty("desktopOverlay").getOrElse(
    "desktop-overlay @ https://github.com/boubou666/desktop-overlay/releases/download/v0.3.0/desktop_overlay-0.3.0-py3-none-any.whl#sha256=d9cef4b14b7a7a6dd5cca83a5bb7de1357cea25d9296dc4523d478b3112ddca6"
)

android {
    namespace = "org.doot.android"
    compileSdk = 34

    defaultConfig {
        applicationId = "org.doot.android"
        minSdk = 24
        targetSdk = 34
        versionCode = 1
        versionName = "1.35.0"
        ndk {
            // Python 3.11 est le dernier que Chaquopy fournit aussi en 32 bits,
            // l'ABI de la plupart des televiseurs.
            abiFilters += listOf("armeabi-v7a", "arm64-v8a", "x86_64")
        }
    }

    sourceSets["main"].res.srcDir(layout.buildDirectory.dir("generated/doot-res"))

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }
}

chaquopy {
    defaultConfig {
        version = "3.11"
        pip {
            // cryptography ne sert qu'au partage chiffre et au coffre, importes
            // a la demande : sans roue 32 bits, on s'en passe.
            options("--no-deps")
            install(desktopOverlay)
        }
    }
    sourceSets {
        getByName("main") {
            srcDir(layout.buildDirectory.dir("generated/doot-python"))
        }
    }
}

val dootPython = tasks.register<Sync>("dootPython") {
    from(dootPackage) {
        exclude("**/__pycache__/**")
    }
    into(layout.buildDirectory.dir("generated/doot-python/doot"))
}

val logo = tasks.register<Copy>("dootLogo") {
    from(rootProject.projectDir.resolve("../../doot/assets/logo.png"))
    into(layout.buildDirectory.dir("generated/doot-res/drawable-nodpi"))
}
tasks.named("preBuild") { dependsOn(logo) }
tasks.matching { it.name.endsWith("PythonSources") }.configureEach { dependsOn(dootPython) }
