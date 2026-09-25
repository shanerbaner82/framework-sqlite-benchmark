// Placeholder app: com.android.test needs a targetProjectPath. The benchmarks never launch it;
// they target the three benchmark apps by package name (self-instrumenting test APK).
plugins { id("com.android.application") }
android {
    namespace = "com.sqlitebenchmark.macrotarget"
    compileSdk = 36
    defaultConfig { applicationId = "com.sqlitebenchmark.macrotarget"; minSdk = 28; targetSdk = 36 }
}
