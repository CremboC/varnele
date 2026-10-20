package dev.imbrasas.varnele

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

/** The Rust checker (rust/android), with the compiled Lithuanian data built in. */
object Native {
    init {
        System.loadLibrary("varnele_android")
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
