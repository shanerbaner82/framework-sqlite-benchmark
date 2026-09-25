package com.nativephp.plugins.mobile_trace

import android.content.Context
import android.os.Trace
import com.nativephp.mobile.bridge.BridgeFunction

/**
 * android.os.Trace sections from PHP. nativephp_call() runs synchronously on the
 * PHP thread, so begin/end land on that thread and nest like any other section.
 */
object TraceFunctions {
    class Begin(private val context: Context) : BridgeFunction {
        override fun execute(parameters: Map<String, Any>): Map<String, Any> {
            Trace.beginSection((parameters["n"] as? String ?: "php").take(127))
            return mapOf("ok" to 1)
        }
    }

    class End(private val context: Context) : BridgeFunction {
        override fun execute(parameters: Map<String, Any>): Map<String, Any> {
            Trace.endSection()
            return mapOf("ok" to 1)
        }
    }
}
