package dev.imbrasas.varnele

import android.app.Activity
import android.content.ActivityNotFoundException
import android.content.Intent
import android.graphics.Typeface
import android.os.Build
import android.os.Bundle
import android.provider.Settings
import android.text.Editable
import android.text.InputType
import android.text.TextWatcher
import android.view.Gravity
import android.view.WindowInsets
import android.widget.Button
import android.widget.EditText
import android.widget.LinearLayout
import android.widget.ScrollView
import android.widget.TextView
import kotlin.system.measureNanoTime

/** A test screen: type Lithuanian, see findings and timing as you type. */
class MainActivity : Activity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)

        val pad = (16 * resources.displayMetrics.density).toInt()
        val root = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(pad, pad, pad, pad)
        }
        root.addView(TextView(this).apply {
            text = "Varnelė"
            textSize = 22f
            setTypeface(typeface, Typeface.BOLD)
        })
        root.addView(TextView(this).apply {
            text = "Rašykite lietuviškai – klaidos rodomos žemiau.\n" +
                "Kad tikrintų visose programose, pasirinkite „Varnelė“ rašybos tikrintuvu."
        })
        val input = EditText(this).apply {
            inputType = InputType.TYPE_CLASS_TEXT or InputType.TYPE_TEXT_FLAG_MULTI_LINE
            minLines = 4
            gravity = Gravity.TOP
            setText("Vakar maciau, kad pries pora dienu jis nuėjo į didele kavine. Aš buvo namie.")
        }
        root.addView(input)
        root.addView(Button(this).apply {
            text = "Rašybos tikrintuvo nustatymai"
            setOnClickListener { openSpellCheckerSettings() }
        })
        val output = TextView(this).apply {
            typeface = Typeface.MONOSPACE
            setTextIsSelectable(true)
        }
        root.addView(ScrollView(this).apply { addView(output) })
        setContentView(root)
        // Android 15+ draws apps edge to edge: keep the content clear of the status bar,
        // the navigation bar, the camera cutout and the on-screen keyboard.
        root.setOnApplyWindowInsetsListener { v, insets ->
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.R) {
                val i = insets.getInsets(
                    WindowInsets.Type.systemBars() or WindowInsets.Type.displayCutout() or WindowInsets.Type.ime(),
                )
                v.setPadding(pad + i.left, pad + i.top, pad + i.right, pad + i.bottom)
            } else {
                @Suppress("DEPRECATION")
                v.setPadding(
                    pad + insets.systemWindowInsetLeft, pad + insets.systemWindowInsetTop,
                    pad + insets.systemWindowInsetRight, pad + insets.systemWindowInsetBottom,
                )
            }
            insets
        }

        val warm = measureNanoTime { Native.warmUp() }

        fun run(note: String = "") {
            val text = input.text.toString()
            var found: List<Finding> = emptyList()
            val ns = measureNanoTime { found = Native.findings(text, formal = true) }
            output.text = buildString {
                append(note)
                append("Patikrinta per %.2f ms\n\n".format(ns / 1e6))
                for (f in found) {
                    append("${f.rule}: ${f.word}")
                    if (f.suggestions.isNotEmpty()) append(" → ${f.suggestions.joinToString(", ")}")
                    if (f.message.isNotEmpty()) append("\n   ${f.message}")
                    append("\n")
                }
                if (found.isEmpty()) append("Klaidų nerasta ✓")
            }
        }
        input.addTextChangedListener(object : TextWatcher {
            override fun beforeTextChanged(s: CharSequence?, a: Int, b: Int, c: Int) {}
            override fun onTextChanged(s: CharSequence?, a: Int, b: Int, c: Int) {}
            override fun afterTextChanged(s: Editable?) = run()
        })
        run("Paleidimas: %.0f ms\n".format(warm / 1e6))
    }

    private fun openSpellCheckerSettings() {
        for (action in listOf("android.settings.SPELL_CHECKER_SETTINGS", Settings.ACTION_INPUT_METHOD_SETTINGS)) {
            try {
                startActivity(Intent(action))
                return
            } catch (_: ActivityNotFoundException) {
            }
        }
    }
}
