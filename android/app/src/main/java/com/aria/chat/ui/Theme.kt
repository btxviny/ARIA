package com.aria.chat.ui

import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.darkColorScheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.ui.graphics.Color

private val Accent = Color(0xFFC96442)

private val Light = lightColorScheme(
    primary = Accent,
    onPrimary = Color.White,
    background = Color(0xFFFAF9F5),
    onBackground = Color(0xFF1F1E1D),
    surface = Color(0xFFFAF9F5),
    onSurface = Color(0xFF1F1E1D),
    surfaceVariant = Color(0xFFEFEDE6),
    onSurfaceVariant = Color(0xFF5E5D59),
    surfaceContainer = Color(0xFFF1EFE8),
    surfaceContainerHigh = Color(0xFFEAE7DE),
    outlineVariant = Color(0xFFDDD9CE),
    errorContainer = Color(0xFFFAE3DE),
    onErrorContainer = Color(0xFF5C1A0E),
)

private val Dark = darkColorScheme(
    primary = Color(0xFFD97757),
    onPrimary = Color(0xFF1F1E1D),
    background = Color(0xFF1F1E1D),
    onBackground = Color(0xFFEDEBE4),
    surface = Color(0xFF1F1E1D),
    onSurface = Color(0xFFEDEBE4),
    surfaceVariant = Color(0xFF30302E),
    onSurfaceVariant = Color(0xFFB8B5AB),
    surfaceContainer = Color(0xFF262624),
    surfaceContainerHigh = Color(0xFF30302E),
    outlineVariant = Color(0xFF454440),
    errorContainer = Color(0xFF5C2A22),
    onErrorContainer = Color(0xFFFAE3DE),
)

@Composable
fun AriaTheme(content: @Composable () -> Unit) {
    MaterialTheme(colorScheme = if (isSystemInDarkTheme()) Dark else Light, content = content)
}
