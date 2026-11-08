package com.aria.chat.ui

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.selection.SelectionContainer
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.text.AnnotatedString
import androidx.compose.ui.text.LinkAnnotation
import androidx.compose.ui.text.SpanStyle
import androidx.compose.ui.text.TextLinkStyles
import androidx.compose.ui.text.buildAnnotatedString
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextDecoration
import androidx.compose.ui.text.withLink
import androidx.compose.ui.text.withStyle
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp

private val INLINE = Regex(
    """\*\*(.+?)\*\*|`([^`]+)`|\[([^\]]+)]\((https?://[^)\s]+)\)|(https?://[^\s)<>]+)"""
)

/** Small markdown subset: headings, bullets, code fences, **bold**, `code`, links. */
@Composable
fun MarkdownText(text: String, modifier: Modifier = Modifier) {
    val linkColor = MaterialTheme.colorScheme.primary
    val codeBg = MaterialTheme.colorScheme.surfaceContainerHigh
    SelectionContainer {
        Column(modifier) {
            var inFence = false
            val fence = StringBuilder()
            for (line in text.lines()) {
                if (line.trimStart().startsWith("```")) {
                    if (inFence) {
                        Text(
                            fence.toString().trimEnd(),
                            fontFamily = FontFamily.Monospace,
                            fontSize = 13.sp,
                            modifier = Modifier.padding(vertical = 4.dp).fillMaxWidth()
                                .clip(RoundedCornerShape(8.dp)).background(codeBg).padding(10.dp),
                        )
                        fence.clear()
                    }
                    inFence = !inFence
                    continue
                }
                if (inFence) { fence.appendLine(line); continue }
                val t = line.trim()
                when {
                    t.isEmpty() -> Text("", fontSize = 6.sp)
                    t.startsWith("#") -> {
                        val body = t.trimStart('#').trim()
                        Text(inline(body, linkColor, codeBg), fontWeight = FontWeight.Bold, fontSize = 18.sp,
                            modifier = Modifier.padding(top = 6.dp))
                    }
                    t.startsWith("- ") || t.startsWith("* ") ->
                        Text(inline("•  " + t.drop(2), linkColor, codeBg), modifier = Modifier.padding(start = 8.dp))
                    else -> Text(inline(line, linkColor, codeBg), lineHeight = 22.sp)
                }
            }
            if (inFence && fence.isNotEmpty()) Text(fence.toString().trimEnd(), fontFamily = FontFamily.Monospace)
        }
    }
}

private fun inline(s: String, linkColor: androidx.compose.ui.graphics.Color, codeBg: androidx.compose.ui.graphics.Color): AnnotatedString =
    buildAnnotatedString {
        val styles = TextLinkStyles(SpanStyle(color = linkColor, textDecoration = TextDecoration.Underline))
        var last = 0
        for (m in INLINE.findAll(s)) {
            append(s.substring(last, m.range.first))
            val g = m.groupValues
            when {
                g[1].isNotEmpty() -> withStyle(SpanStyle(fontWeight = FontWeight.Bold)) { append(g[1]) }
                g[2].isNotEmpty() -> withStyle(SpanStyle(fontFamily = FontFamily.Monospace, background = codeBg)) { append(g[2]) }
                g[3].isNotEmpty() -> withLink(LinkAnnotation.Url(g[4], styles)) { append(g[3]) }
                else -> withLink(LinkAnnotation.Url(g[5], styles)) { append(g[5]) }
            }
            last = m.range.last + 1
        }
        append(s.substring(last))
    }
