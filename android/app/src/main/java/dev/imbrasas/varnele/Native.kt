package dev.imbrasas.varnele

import android.content.Context
import java.io.FileInputStream
import java.nio.ByteBuffer
import java.nio.channels.FileChannel
import org.json.JSONArray

/** One problem found in a text. Offsets are UTF-16 indices, like Kotlin strings. */
data class Finding(
    val start: Int,
    val end: Int,
    val word: String,
    /** unknown | colloquial | case | agreement | quantity | negation | subject | object | comma */
    val rule: String,
    val message: String,
    val suggestions: List<String>,
)

/** The Rust checker (rust/android); the compiled Lithuanian data is the asset varnele.bin. */
object Native {
    init {
        System.loadLibrary("varnele_android")
    }

    /** The data file, memory-mapped: the library reads it in place, so it is kept. */
    private var data: ByteBuffer? = null

    private external fun dataNative(data: ByteBuffer)

    /** Hands the library its data; call before anything else (later calls do nothing). */
    @Synchronized
    fun init(context: Context) {
        if (data != null) return
        // stored uncompressed (noCompress in build.gradle.kts), so it can be mapped from the APK
        val buf = context.assets.openFd("varnele.bin").use { fd ->
            FileInputStream(fd.fileDescriptor).use {
                it.channel.map(FileChannel.MapMode.READ_ONLY, fd.startOffset, fd.declaredLength)
            }
        }
        dataNative(buf)
        data = buf
    }

    /** Loads the data; call once early so the first check is quick. */
    external fun warmUp()

    /** JSON array of findings. */
    external fun check(text: String, formal: Boolean): String

    fun findings(text: String, formal: Boolean = false): List<Finding> {
        val arr = JSONArray(check(text, formal))
        return (0 until arr.length()).map { i ->
            val o = arr.getJSONObject(i)
            val s = o.getJSONArray("suggestions")
            Finding(
                o.getInt("start"), o.getInt("end"), o.getString("word"), o.getString("rule"),
                o.getString("message"), (0 until s.length()).map { s.getString(it) },
            )
        }
    }
}
