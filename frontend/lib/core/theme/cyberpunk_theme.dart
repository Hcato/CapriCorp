import 'package:flutter/material.dart';
import '../constants/app_constants.dart';

/// Tema visual Cyberpunk para el overlay de escritorio Capri.
class CyberpunkTheme {
  static ThemeData get darkTheme {
    return ThemeData(
      useMaterial3: true,
      brightness: Brightness.dark,
      scaffoldBackgroundColor: Colors.transparent,
      canvasColor: Colors.transparent,
      colorScheme: const ColorScheme.dark(
        primary: AppConstants.neonCyan,
        secondary: AppConstants.neonPink,
        surface: AppConstants.darkGlass,
      ),
      dialogTheme: DialogThemeData(
        backgroundColor: AppConstants.darkGlass,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(16),
        ),
      ),
    );
  }
}
