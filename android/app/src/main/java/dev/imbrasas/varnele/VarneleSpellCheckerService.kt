package dev.imbrasas.varnele

import android.os.Build
import android.service.textservice.SpellCheckerService
import android.view.textservice.SentenceSuggestionsInfo
import android.view.textservice.SuggestionsInfo
import android.view.textservice.TextInfo

/**
 * Android's system spell checker. Text fields send whole sentences here; misspellings
 * come back as typos (red underline) and grammar findings as grammar errors (blue
 * underline, Android 12+), each with the suggestions shown when the word is tapped.
 */
class VarneleSpellCheckerService : SpellCheckerService() {

    override fun createSession(): Session = VarneleSession()

    private class VarneleSession : Session() {
        override fun onCreate() {
            Native.warmUp()
        }

        /** Single word (older callers). */
        override fun onGetSuggestions(textInfo: TextInfo, suggestionsLimit: Int): SuggestionsInfo {
            val word = textInfo.text
            val f = Native.findings(word).firstOrNull { it.rule == "unknown" && it.start == 0 }
            return if (f == null) {
                SuggestionsInfo(
                    SuggestionsInfo.RESULT_ATTR_IN_THE_DICTIONARY, emptyArray(),
                    textInfo.cookie, textInfo.sequence,
                )
            } else {
                info(f, f.suggestions, suggestionsLimit, textInfo)
            }
        }

        /** Whole sentences: this is what lets the grammar rules see context. */
        override fun onGetSentenceSuggestionsMultiple(
            textInfos: Array<TextInfo>,
            suggestionsLimit: Int,
        ): Array<SentenceSuggestionsInfo> = textInfos.map { sentence(it, suggestionsLimit) }.toTypedArray()

        private fun sentence(ti: TextInfo, limit: Int): SentenceSuggestionsInfo {
            val text = ti.text
            val infos = ArrayList<SuggestionsInfo>()
            val offsets = ArrayList<Int>()
            val lengths = ArrayList<Int>()
            for (f in Native.findings(text)) {
                var start = f.start
                var suggestions = f.suggestions
                if (f.rule == "comma" && start > 0 && text[start - 1] == ' ') {
                    // replace " kad" with ", kad" so accepting the fix leaves no stray space
                    start -= 1
                    suggestions = listOf(", ${f.word}")
                }
                infos.add(info(f, suggestions, limit, ti))
                offsets.add(start)
                lengths.add(f.end - start)
            }
            return SentenceSuggestionsInfo(infos.toTypedArray(), offsets.toIntArray(), lengths.toIntArray())
        }

        private fun info(f: Finding, suggestions: List<String>, limit: Int, ti: TextInfo): SuggestionsInfo {
            var attrs = if (f.rule == "unknown" || Build.VERSION.SDK_INT < Build.VERSION_CODES.S) {
                SuggestionsInfo.RESULT_ATTR_LOOKS_LIKE_TYPO
            } else {
                SuggestionsInfo.RESULT_ATTR_LOOKS_LIKE_GRAMMAR_ERROR
            }
            if (suggestions.isNotEmpty()) attrs = attrs or SuggestionsInfo.RESULT_ATTR_HAS_RECOMMENDED_SUGGESTIONS
            val n = if (limit > 0) minOf(limit, suggestions.size) else suggestions.size
            return SuggestionsInfo(attrs, suggestions.take(n).toTypedArray(), ti.cookie, ti.sequence)
        }
    }
}
