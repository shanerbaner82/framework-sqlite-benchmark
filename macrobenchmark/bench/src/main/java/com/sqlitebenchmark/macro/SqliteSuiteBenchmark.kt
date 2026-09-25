package com.sqlitebenchmark.macro

import android.util.Log
import androidx.benchmark.macro.CompilationMode
import androidx.benchmark.macro.ExperimentalMetricApi
import androidx.benchmark.macro.MacrobenchmarkScope
import androidx.benchmark.macro.Metric
import androidx.benchmark.macro.StartupMode
import androidx.benchmark.macro.StartupTimingMetric
import androidx.benchmark.macro.TraceSectionMetric
import androidx.benchmark.macro.junit4.MacrobenchmarkRule
import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import androidx.test.uiautomator.By
import androidx.test.uiautomator.Until
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith
import java.io.File
import java.util.regex.Pattern

/**
 * One @Test per app/mode. Each Macrobenchmark iteration = one COMPLETE run of the 17-case
 * suite in a freshly (cold) started app process:
 *   cold start -> tap the app's Run button -> wait for the SQLITE_BENCHMARK_DONE logcat marker.
 * Metrics:
 *   - StartupTimingMetric (timeToInitialDisplay of the cold start)
 *   - TraceSectionMetric("case:<name>", Mode.Average): each app wraps every TIMED sample
 *     (5 per case, warmup excluded) in android.os.Trace begin/end on the thread that runs the
 *     benchmark (NS: main/JS thread, RN: JS thread, NativePHP: PHP thread). One pair per sample,
 *     outside the per-query loop. Mode.Average = mean of the 5 samples in that iteration.
 *   - TraceSectionMetric(Mode.Count) to prove all 5 samples per case were captured.
 * The in-app report (its own timers, median of 5) is saved per iteration as a cross-check.
 *
 * Instrumentation args: iterations (default 5), compilation (full|none|partial, default full).
 */
@OptIn(ExperimentalMetricApi::class)
@RunWith(AndroidJUnit4::class)
class SqliteSuiteBenchmark {
    @get:Rule
    val rule = MacrobenchmarkRule()

    private val args = InstrumentationRegistry.getArguments()
    private val iterations = args.getString("iterations")?.toInt() ?: 5
    private val compilation: CompilationMode = when (args.getString("compilation") ?: "full") {
        "none" -> CompilationMode.None()
        "partial" -> CompilationMode.Partial()
        else -> CompilationMode.Full()
    }
    private val outDir: File by lazy {
        (InstrumentationRegistry.getInstrumentation().context.externalMediaDirs.first()).also { it.mkdirs() }
    }

    private val cases = listOf(
        "schema_create_drop", "insert_autocommit", "insert_transaction", "point_select", "indexed_filter",
        "range_scan", "full_scan_aggregate", "order_limit", "join_aggregate", "like_search", "json_extract",
        "update_by_pk", "delete_by_pk", "upsert", "transaction_rollback", "blob_insert_length", "index_create",
    )

    private fun metrics(): List<Metric> = listOf<Metric>(StartupTimingMetric()) +
        cases.map { TraceSectionMetric("case:$it", TraceSectionMetric.Mode.Average, label = "case_${it}_avg") } +
        cases.map { TraceSectionMetric("case:$it", TraceSectionMetric.Mode.Count, label = "case_${it}_count") }

    @Test fun nativescript() = suite("ns", "com.sqlitebenchmark.nativescript", "run benchmark")
    @Test fun reactnative() = suite("rn", "com.sqlitebenchmark.reactnative", "run benchmark")
    @Test fun nativephpPdo() = suite("nativephp-pdo", "com.sqlitebenchmark.nativephp", "Run PHP loop")
    @Test fun nativephpLaravel() = suite("nativephp-laravel", "com.sqlitebenchmark.nativephp", "PHP loop Laravel DB")

    private fun suite(tag: String, pkg: String, button: String) {
        var iteration = 0
        rule.measureRepeated(
            packageName = pkg,
            metrics = metrics(),
            iterations = iterations,
            startupMode = StartupMode.COLD,
            compilationMode = compilation,
            setupBlock = { pressHome() },
        ) {
            iteration++
            device.executeShellCommand("logcat -c")
            startActivityAndWait()
            val target = device.wait(Until.findObject(By.text(Pattern.compile(button, Pattern.CASE_INSENSITIVE))), 60_000)
                ?: error("[$tag] button '$button' not found")
            // Buttons may be present before they're enabled/laid out; give the UI a moment to settle.
            Thread.sleep(1_500)
            target.click()
            val json = waitForReport(tag, 20 * 60_000L)
            File(outDir, "inapp-$tag-iter$iteration.json").writeText(json)
            Log.i("SqliteMacro", "[$tag] iteration $iteration done (${json.length} bytes)")
        }
    }

    /** Polls logcat (every 2 s, to keep device-side overhead low) for the app's DONE marker and reassembles its JSON chunks. */
    private fun MacrobenchmarkScope.waitForReport(tag: String, timeoutMs: Long): String {
        val deadline = System.currentTimeMillis() + timeoutMs
        val done = Regex("SQLITE_BENCHMARK_DONE (\\d+)")
        while (System.currentTimeMillis() < deadline) {
            Thread.sleep(2_000)
            val log = device.executeShellCommand("logcat -d -v raw -e SQLITE_BENCHMARK_DONE")
            val runId = done.findAll(log).lastOrNull()?.groupValues?.get(1) ?: continue
            val parts = device.executeShellCommand("logcat -d -v raw -e SQLITE_BENCHMARK_PART")
            val rx = Regex("SQLITE_BENCHMARK_PART $runId (\\d+)/(\\d+) (.*?)(?: -- From line \\d+)?$", RegexOption.MULTILINE)
            val chunks = rx.findAll(parts).associate { it.groupValues[1].toInt() to (it.groupValues[2].toInt() to it.groupValues[3]) }
            val total = chunks.values.firstOrNull()?.first ?: error("[$tag] no chunks for run $runId")
            check(chunks.size == total) { "[$tag] expected $total chunks, got ${chunks.size}" }
            val json = (1..total).joinToString("") { chunks.getValue(it).second }
            check(json.contains("\"integrity_check\":\"ok\"")) { "[$tag] integrity_check not ok" }
            check(!json.contains("\"status\":\"error\"")) { "[$tag] a case failed: $json" }
            return json
        }
        error("[$tag] timed out waiting for SQLITE_BENCHMARK_DONE")
    }
}
