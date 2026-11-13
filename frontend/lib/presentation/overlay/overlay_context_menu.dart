import 'package:flutter/material.dart';
import 'package:window_manager/window_manager.dart';
import '../../core/constants/app_constants.dart';
import '../../domain/entities/assistant_state.dart';
import '../../domain/state/assistant_controller.dart';

/// Despliega el menú contextual estilo Cyberpunk al hacer clic derecho sobre el personaje.
void showOverlayContextMenu(
  BuildContext context,
  Offset position,
  AssistantController controller,
) {
  final overlay = Overlay.of(context).context.findRenderObject() as RenderBox?;
  if (overlay == null) return;

  final relativePosition = RelativeRect.fromRect(
    Rect.fromLTWH(position.dx, position.dy, 0, 0),
    Offset.zero & overlay.size,
  );

  showMenu<String>(
    context: context,
    position: relativePosition,
    color: const Color(0xF00D0E15),
    elevation: 12,
    shape: RoundedRectangleBorder(
      borderRadius: BorderRadius.circular(12),
      side: BorderSide(color: AppConstants.neonCyan.withValues(alpha: 0.5), width: 1.2),
    ),
    items: [
      // Encabezado
      const PopupMenuItem<String>(
        enabled: false,
        height: 32,
        child: Text(
          'CAPRI OVERLAY // v1.0',
          style: TextStyle(
            color: AppConstants.neonCyan,
            fontSize: 10,
            fontWeight: FontWeight.bold,
            letterSpacing: 1.2,
          ),
        ),
      ),
      const PopupMenuDivider(height: 8),

      // Silenciar / Activar sonido
      PopupMenuItem<String>(
        value: 'mute',
        child: Row(
          children: [
            Icon(
              controller.isMuted ? Icons.volume_off_rounded : Icons.volume_up_rounded,
              color: controller.isMuted ? Colors.redAccent : AppConstants.neonCyan,
              size: 18,
            ),
            const SizedBox(width: 10),
            Text(
              controller.isMuted ? 'Activar Sonido' : 'Silenciar',
              style: const TextStyle(color: Colors.white, fontSize: 13),
            ),
          ],
        ),
      ),

      // Submenú / Opciones rápidas de animación para testing
      PopupMenuItem<String>(
        value: 'test_state',
        child: const Row(
          children: [
            Icon(Icons.theater_comedy_rounded, color: AppConstants.neonPink, size: 18),
            SizedBox(width: 10),
            Text('Probar Estado...', style: TextStyle(color: Colors.white, fontSize: 13)),
          ],
        ),
      ),

      // Opciones
      const PopupMenuItem<String>(
        value: 'options',
        child: Row(
          children: [
            Icon(Icons.settings_rounded, color: Color(0xFFFFB703), size: 18),
            SizedBox(width: 10),
            Text('Opciones', style: TextStyle(color: Colors.white, fontSize: 13)),
          ],
        ),
      ),

      const PopupMenuDivider(height: 8),

      // Cerrar Asistente
      const PopupMenuItem<String>(
        value: 'close',
        child: Row(
          children: [
            Icon(Icons.power_settings_new_rounded, color: Colors.redAccent, size: 18),
            SizedBox(width: 10),
            Text('Cerrar Asistente', style: TextStyle(color: Colors.redAccent, fontSize: 13)),
          ],
        ),
      ),
    ],
  ).then((selected) {
    if (selected == null || !context.mounted) return;

    switch (selected) {
      case 'mute':
        controller.toggleMute();
        break;

      case 'test_state':
        _showStateSelectorDialog(context, controller);
        break;

      case 'options':
        _showOptionsDialog(context, controller);
        break;

      case 'close':
        windowManager.close();
        break;
    }
  });
}

/// Diálogo para seleccionar manualmente un estado del asistente (para pruebas de desarrollo).
void _showStateSelectorDialog(BuildContext context, AssistantController controller) {
  showDialog(
    context: context,
    builder: (ctx) {
      return AlertDialog(
        backgroundColor: const Color(0xF20D0E15),
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(16),
          side: const BorderSide(color: AppConstants.neonPink, width: 1.2),
        ),
        title: const Text(
          'Simular Estado del Asistente',
          style: TextStyle(color: AppConstants.neonPink, fontSize: 16, fontWeight: FontWeight.bold),
        ),
        content: SizedBox(
          width: 240,
          child: SingleChildScrollView(
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: AssistantState.values.map((state) {
                final isCurrent = controller.currentState == state;
                return ListTile(
                  dense: true,
                   visualDensity: VisualDensity.compact,
                  selected: isCurrent,
                  selectedColor: AppConstants.neonCyan,
                  title: Text(
                    state.displayName,
                    style: TextStyle(
                      color: isCurrent ? AppConstants.neonCyan : Colors.white70,
                      fontWeight: isCurrent ? FontWeight.bold : FontWeight.normal,
                    ),
                  ),
                  trailing: isCurrent ? const Icon(Icons.check, color: AppConstants.neonCyan, size: 16) : null,
                  onTap: () {
                    controller.changeState(state, notifyBackend: true, force: true);
                    Navigator.of(ctx).pop();
                  },
                );
              }).toList(),
            ),
          ),
        ),
      );
    },
  );
}

/// Diálogo de información y configuración de Capri
void _showOptionsDialog(BuildContext context, AssistantController controller) {
  showDialog(
    context: context,
    builder: (ctx) {
      return AlertDialog(
        backgroundColor: const Color(0xF20D0E15),
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(16),
          side: const BorderSide(color: AppConstants.neonCyan, width: 1.2),
        ),
        title: const Row(
          children: [
            Icon(Icons.tune_rounded, color: AppConstants.neonCyan),
            SizedBox(width: 8),
            Text(
              'Opciones de Capri',
              style: TextStyle(color: Colors.white, fontSize: 16, fontWeight: FontWeight.bold),
            ),
          ],
        ),
        content: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            _buildOptionRow('WebSocket Endpoint', AppConstants.defaultWsUrl),
            const SizedBox(height: 10),
            _buildOptionRow(
              'Estado WebSocket',
              controller.wsStatus.name.toUpperCase(),
              color: controller.wsStatus.name == 'connected' ? Colors.greenAccent : Colors.orangeAccent,
            ),
            const SizedBox(height: 10),
            _buildOptionRow('Estado Actual', controller.currentState.displayName),
            const SizedBox(height: 14),
            Container(
              padding: const EdgeInsets.all(10),
              decoration: BoxDecoration(
                color: Colors.white.withValues(alpha: 0.05),
                borderRadius: BorderRadius.circular(8),
              ),
              child: const Text(
                'Nota: Coloca las hojas de sprites (.png) en frontend/assets/sprites/ para cargar las animaciones de mochiiwuff/capri-desktop.',
                style: TextStyle(color: Colors.white60, fontSize: 11),
              ),
            ),
          ],
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(ctx).pop(),
            child: const Text('Cerrar', style: TextStyle(color: AppConstants.neonCyan)),
          ),
        ],
      );
    },
  );
}

Widget _buildOptionRow(String label, String value, {Color color = Colors.white}) {
  return Column(
    crossAxisAlignment: CrossAxisAlignment.start,
    children: [
      Text(label, style: const TextStyle(color: Colors.white38, fontSize: 11)),
      const SizedBox(height: 2),
      Text(value, style: TextStyle(color: color, fontSize: 13, fontWeight: FontWeight.w600)),
    ],
  );
}
