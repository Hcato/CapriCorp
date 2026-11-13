import 'package:flutter_test/flutter_test.dart';
import 'package:frontend/core/constants/sprite_registry.dart';
import 'package:frontend/data/models/assistant_event.dart';
import 'package:frontend/domain/entities/assistant_state.dart';
import 'package:frontend/presentation/animation/capri_acts.dart';
import 'package:frontend/presentation/animation/capri_desk_sprites.dart';
import 'package:frontend/presentation/animation/capri_rig.dart';

void main() {
  group('AssistantState parsing tests', () {
    test('Parsea estados desde strings en mayúsculas y minúsculas', () {
      expect(AssistantState.fromString('Thinking'), AssistantState.thinking);
      expect(AssistantState.fromString('idle'), AssistantState.idle);
      expect(AssistantState.fromString('TELEPORTING'), AssistantState.teleporting);
      expect(AssistantState.fromString('Listening'), AssistantState.listening);
      expect(AssistantState.fromString('speaking'), AssistantState.speaking);
      expect(AssistantState.fromString('desconocido'), AssistantState.idle);
    });
  });

  group('AssistantEvent JSON tests', () {
    test('Decodifica payload JSON de cambio de estado', () {
      const jsonPayload = '{"event": "change_state", "state": "Thinking"}';
      final event = AssistantEvent.fromJsonString(jsonPayload);

      expect(event.event, 'change_state');
      expect(event.state, AssistantState.thinking);
    });

    test('Decodifica payload JSON de diálogo y habla', () {
      const jsonPayload = '{"event": "say", "text": "Hola mundo"}';
      final event = AssistantEvent.fromJsonString(jsonPayload);

      expect(event.event, 'say');
      expect(event.text, 'Hola mundo');
    });
  });

  group('SpriteRegistry tests', () {
    test('Todos los estados apuntan al rig base y tienen retrato facial', () {
      for (final state in AssistantState.values) {
        final config = SpriteRegistry.getConfig(state);
        expect(config.frameCount, greaterThan(0));
        expect(config.fps, greaterThan(0));
        expect(config.assetPath, SpriteRegistry.baseSpriteAsset);
        expect(SpriteRegistry.getFacePortraitAsset(state).isNotEmpty, true);
      }
    });
  });

  group('CapriActs, CapriFxLayer & CapriRig tests', () {
    test('ActPlayer muestrea hojas de exposición y dispara cues una sola vez por keyframe', () {
      final player = ActPlayer('victory', dir: 1, startMs: 0.0);
      final sample0 = player.sample(0.0);
      expect(sample0, isNotNull);

      // En el keyframe 1 (frame 3 a 24fps -> 125ms) debe dispararse el cue 'gather' una sola vez
      final sampleGatherFirst = player.sample(130.0);
      expect(sampleGatherFirst?.cue, 'gather');
      final sampleGatherHold = player.sample(145.0);
      expect(sampleGatherHold?.cue, isNull);

      // Después de completar todas las exposiciones no cíclicas, retorna null
      final sampleAfterEnd = player.sample(5000.0);
      expect(sampleAfterEnd, isNull);
    });

    test('CapriRig ejecuta la secuencia de teletransporte en 7 fases y genera efectos en CapriFxLayer', () {
      final rig = CapriRig();
      rig.setAssistantState(AssistantState.teleporting, 0.0);

      // Fase 2 (colapso en línea vertical de luz + burst + slices)
      expect(rig.tick(180.0), false);
      expect(rig.u.collapse, greaterThan(0.0));
      expect(rig.fx.hasActiveItems, true);

      // Fase 3 (desaparecida en el vacío + slit + beam)
      expect(rig.tick(300.0), false);
      expect(rig.u.alpha, 0.0);

      // Fase 5 (impact frame verde neón)
      expect(rig.tick(560.0), false);
      expect(rig.u.silAmount, 1.0);
      expect(rig.u.silG, 1.0);

      // Completado (>= 844ms)
      expect(rig.tick(900.0), true);
      expect(rig.u.collapse, 0.0);
      expect(rig.u.glitch, 0.0);
      expect(rig.u.silAmount, 0.0);
      expect(rig.u.alpha, 1.0);
    });

    test('CapriRig disuelve el cuerpo hacia la máscara flotante (doze -> Mask) al dormir', () {
      final rig = CapriRig();
      rig.setAssistantState(AssistantState.sleeping, 0.0);
      expect(rig.fx.maskVisible, false);

      // Durante la disolución (3500ms..4200ms)
      rig.tick(3800.0);
      expect(rig.u.dissolve, greaterThan(0.0));

      // Al completar doze (>= 4200ms), el cuerpo desaparece y queda la máscara verde flotando
      rig.tick(4300.0);
      expect(rig.u.alpha, 0.0);
      expect(rig.fx.maskVisible, true);
      expect(rig.fx.maskPeekEye, isNull);
    });

    test('CapriDeskSprites selecciona clips dangle, perch y detecta 3 pokes en modo mini', () {
      final desk = CapriDeskSprites();
      expect(
        desk.selectClipName(
          state: AssistantState.idle,
          posture: CapriPosture.standing,
          isDragging: true,
          nowSec: 0.0,
        ),
        'dangle',
      );
      expect(
        desk.selectClipName(
          state: AssistantState.idle,
          posture: CapriPosture.perched,
          isDragging: false,
          nowSec: 0.5,
        ),
        'perch',
      );

      expect(desk.registerMiniPoke(1.0), false);
      expect(desk.registerMiniPoke(1.3), false);
      expect(desk.registerMiniPoke(1.6), true);
      expect(CapriVisualSkin.fromId('watcher'), CapriVisualSkin.watcherSprites);
    });
  });
}
