package com.sqlitebenchmark.reactnative

import android.os.Trace
import com.facebook.react.ReactPackage
import com.facebook.react.bridge.NativeModule
import com.facebook.react.bridge.ReactApplicationContext
import com.facebook.react.bridge.ReactContextBaseJavaModule
import com.facebook.react.bridge.ReactMethod
import com.facebook.react.uimanager.ViewManager

/**
 * Benchmark-only: synchronous android.os.Trace begin/end callable from JS, so each
 * benchmark case shows up as a `case:<name>` slice on the JS thread for
 * Macrobenchmark's TraceSectionMetric. Called once per timed sample, never per query.
 */
class BenchTraceModule(context: ReactApplicationContext) : ReactContextBaseJavaModule(context) {
  override fun getName() = "BenchTrace"

  @ReactMethod(isBlockingSynchronousMethod = true)
  fun beginSection(name: String): Boolean { Trace.beginSection(name); return true }

  @ReactMethod(isBlockingSynchronousMethod = true)
  fun endSection(): Boolean { Trace.endSection(); return true }
}

class BenchTracePackage : ReactPackage {
  override fun createNativeModules(context: ReactApplicationContext): List<NativeModule> = listOf(BenchTraceModule(context))
  override fun createViewManagers(context: ReactApplicationContext): List<ViewManager<*, *>> = emptyList()
}
