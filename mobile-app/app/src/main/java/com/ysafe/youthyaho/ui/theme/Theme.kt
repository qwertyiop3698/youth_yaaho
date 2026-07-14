package com.ysafe.youthyaho.ui.theme

import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.darkColorScheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable

private val LightColors = lightColorScheme(
    primary = BrandBlue,
    onPrimary = BrandOnPrimary,
    secondary = BrandTeal,
    onSecondary = BrandOnPrimary,
    background = BrandBackground,
    onBackground = BrandInk,
    surface = BrandSurface,
    onSurface = BrandInk,
    surfaceVariant = BrandSurfaceMuted,
    onSurfaceVariant = BrandTextSecondary,
    outline = BrandBlue,
    outlineVariant = BrandBorder,
    error = BrandError,
)

private val DarkColors = darkColorScheme(
    primary = BrandBlueOnDark,
    onPrimary = BrandBackgroundDark,
    secondary = BrandTeal,
    onSecondary = BrandBackgroundDark,
    background = BrandBackgroundDark,
    onBackground = BrandInkDark,
    surface = BrandSurfaceDark,
    onSurface = BrandInkDark,
    surfaceVariant = BrandSurfaceMutedDark,
    onSurfaceVariant = BrandTextSecondaryDark,
    outline = BrandBlueOnDark,
    outlineVariant = BrandBorderDark,
    error = BrandError,
)

@Composable
fun YouthYahoTheme(
    darkTheme: Boolean = isSystemInDarkTheme(),
    content: @Composable () -> Unit,
) {
    val colorScheme = if (darkTheme) DarkColors else LightColors
    MaterialTheme(
        colorScheme = colorScheme,
        typography = YouthYahoTypography,
        content = content,
    )
}
