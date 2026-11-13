// Pose-to-pose acting tables ported from mochiiwuff/capri-desktop (src/renderer/js/acting.js).
// Required Notice: Copyright (c) 2026 mochiiwuff (https://github.com/mochiiwuff/capri-desktop)
// Non-commercial use only, see THIRD_PARTY_NOTICES.md.

const double kSheetFps = 12.0;

class CapriPose {
  final double? head;
  final double? mane;
  final double? hair;
  final double? tilt;
  final double? bob;
  final double? sx;
  final double? sy;
  final double? arms;
  final double? armL;
  final double? armR;
  final double? reach;
  final double? long;
  final double? longL;
  final double? longR;
  final List<double>? smear;
  final List<double>? echo;
  final double? kickL;
  final double? kickR;
  final double? bend;

  const CapriPose({
    this.head,
    this.mane,
    this.hair,
    this.tilt,
    this.bob,
    this.sx,
    this.sy,
    this.arms,
    this.armL,
    this.armR,
    this.reach,
    this.long,
    this.longL,
    this.longR,
    this.smear,
    this.echo,
    this.kickL,
    this.kickR,
    this.bend,
  });
}

class CapriResolvedPose {
  double head;
  double mane;
  double hair;
  double tilt;
  double bob;
  double sx;
  double sy;
  double armL;
  double armR;
  double longL;
  double longR;
  double smearX;
  double smearY;
  double echoX;
  double echoY;
  double kickL;
  double kickR;
  double bend;

  CapriResolvedPose({
    this.head = 0.0,
    this.mane = 0.0,
    this.hair = 0.0,
    this.tilt = 0.0,
    this.bob = 0.0,
    this.sx = 1.0,
    this.sy = 1.0,
    this.armL = 0.0,
    this.armR = 0.0,
    this.longL = 1.0,
    this.longR = 1.0,
    this.smearX = 0.0,
    this.smearY = 0.0,
    this.echoX = 0.0,
    this.echoY = 0.0,
    this.kickL = 0.0,
    this.kickR = 0.0,
    this.bend = 0.0,
  });

  void applyResolved(
    CapriPose pose, {
    required bool directional,
    required int dir,
    required int facing,
    double reachScale = 1.0,
  }) {
    final int lean = (directional && dir != 0) ? dir * facing : 0;

    if (pose.head != null) {
      head = lean != 0 ? pose.head! * lean : pose.head!;
    }
    if (pose.mane != null) mane = pose.mane!;
    if (pose.hair != null) hair = pose.hair!;
    if (pose.tilt != null) {
      tilt = lean != 0 ? pose.tilt! * dir : pose.tilt!;
    }
    if (pose.bob != null) bob = pose.bob!;
    if (pose.sx != null) sx = pose.sx!;
    if (pose.sy != null) sy = pose.sy!;
    if (pose.armL != null) armL = pose.armL!;
    if (pose.armR != null) armR = pose.armR!;
    if (pose.longL != null) longL = pose.longL!;
    if (pose.longR != null) longR = pose.longR!;
    if (pose.kickL != null) kickL = pose.kickL!;
    if (pose.kickR != null) kickR = pose.kickR!;
    if (pose.bend != null) bend = pose.bend!;

    if (pose.arms != null) {
      armL = pose.arms!;
      armR = pose.arms!;
    }
    if (pose.reach != null) {
      if (lean < 0) {
        armL = pose.reach! * reachScale;
      } else {
        armR = pose.reach! * reachScale;
      }
    }
    if (pose.long != null) {
      if (lean < 0) {
        longL = pose.long!;
      } else {
        longR = pose.long!;
      }
    }
    if (pose.smear != null && pose.smear!.length >= 2) {
      smearX = lean != 0 ? pose.smear![0] * lean : pose.smear![0];
      smearY = pose.smear![1];
    }
    if (pose.echo != null && pose.echo!.length >= 2) {
      echoX = lean != 0 ? pose.echo![0] * lean : pose.echo![0];
      echoY = pose.echo![1];
    }
  }
}

class CapriKey {
  final int hold;
  final CapriPose pose;
  final String? cue;

  const CapriKey(this.hold, [this.pose = const CapriPose(), this.cue]);
}

class CapriAct {
  final bool loop;
  final double fps;
  final int priority;
  final bool directional;
  final bool flip;
  final List<CapriKey> keys;

  const CapriAct({
    this.loop = false,
    this.fps = kSheetFps,
    this.priority = 0,
    this.directional = false,
    this.flip = false,
    required this.keys,
  });

  int get totalFrames => keys.fold<int>(0, (sum, k) => sum + k.hold);
}

List<CapriKey> _rep(int n, List<CapriKey> pattern) {
  final out = <CapriKey>[];
  for (int i = 0; i < n; i++) {
    out.addAll(pattern);
  }
  return out;
}

class CapriActs {
  static final Map<String, CapriAct> all = {
    // ---- stances (looping) ----
    'stand': const CapriAct(
      loop: true,
      keys: [
        CapriKey(6, CapriPose(bob: 0, hair: -2.5, arms: 0.04)),
        CapriKey(4, CapriPose(bob: -2, hair: 0, arms: 0)),
        CapriKey(6, CapriPose(bob: -4, hair: 2.5, arms: -0.05)),
        CapriKey(4, CapriPose(bob: -2, hair: 0, arms: 0)),
      ],
    ),

    'sit': const CapriAct(
      loop: true,
      keys: [
        CapriKey(5, CapriPose(kickL: 0.24, kickR: -0.03, hair: -1.5, arms: -0.42)),
        CapriKey(2, CapriPose(kickL: 0.08, kickR: 0.08, arms: -0.42)),
        CapriKey(5, CapriPose(kickL: -0.03, kickR: 0.24, hair: 1.5, arms: -0.42)),
        CapriKey(2, CapriPose(kickL: 0.08, kickR: 0.08, arms: -0.42)),
        CapriKey(5, CapriPose(kickL: 0.24, kickR: -0.03, hair: -1.5, arms: -0.42)),
        CapriKey(2, CapriPose(kickL: 0.08, kickR: 0.08, arms: -0.42)),
        CapriKey(5, CapriPose(kickL: -0.03, kickR: 0.24, hair: 1.5, arms: -0.42)),
        CapriKey(10, CapriPose(kickL: 0.04, kickR: 0.04, head: 0.08, arms: -0.4)),
      ],
    ),

    'peek': const CapriAct(
      loop: true,
      directional: true,
      keys: [
        CapriKey(18, CapriPose(tilt: 7, head: 0.14, reach: 0.1)),
        CapriKey(1, CapriPose(tilt: 7, head: 0.2, smear: [-6, 0], reach: 0.16)),
        CapriKey(14, CapriPose(tilt: 7.5, head: 0.24, mane: 0.08, reach: 0.18)),
        CapriKey(1, CapriPose(tilt: 6, head: 0.14, reach: 0.12)),
        CapriKey(12, CapriPose(tilt: 6.5, head: 0.12, bob: -2, reach: 0.1)),
      ],
    ),

    'sleep': const CapriAct(
      loop: true,
      keys: [
        CapriKey(18, CapriPose(head: 0.1, mane: -0.12, bob: 2, arms: -0.3)),
        CapriKey(1, CapriPose(head: 0.16, mane: -0.13, bob: 4, arms: -0.34)),
        CapriKey(10, CapriPose(head: 0.21, mane: -0.15, bob: 5, arms: -0.36)),
        CapriKey(1, CapriPose(head: 0.06, mane: -0.08, bob: 0, smear: [0, 8], arms: -0.18)),
        CapriKey(4, CapriPose(head: 0.08, mane: -0.1, bob: 1, arms: -0.26)),
      ],
    ),

    'pointing': const CapriAct(
      loop: true,
      directional: true,
      keys: [
        CapriKey(12, CapriPose(reach: 1, long: 1.5, head: 0.17, mane: 0.16, tilt: 3)),
        CapriKey(1, CapriPose(reach: 1.05, long: 1.8, head: 0.2, mane: 0.24, tilt: 4), 'tap'),
        CapriKey(2, CapriPose(reach: 1, long: 1.52, head: 0.18, mane: 0.18, tilt: 3)),
        CapriKey(1, CapriPose(reach: 1.05, long: 1.8, head: 0.2, mane: 0.24, tilt: 4), 'tap'),
        CapriKey(10, CapriPose(reach: 1, long: 1.5, head: 0.17, mane: 0.16, tilt: 3, bob: -2)),
        CapriKey(1, CapriPose(reach: 1, long: 1.5, head: 0.02, mane: 0.12, tilt: 2, smear: [10, 0])),
        CapriKey(8, CapriPose(reach: 1, long: 1.5, head: -0.1, mane: 0.1, tilt: 2)),
        CapriKey(1, CapriPose(reach: 1, long: 1.5, head: 0.12, mane: 0.16, tilt: 3, smear: [-10, 0])),
        CapriKey(8, CapriPose(reach: 1, long: 1.5, head: 0.17, mane: 0.16, tilt: 3, bob: -1)),
      ],
    ),

    'held': const CapriAct(
      loop: true,
      keys: [
        CapriKey(3, CapriPose(armL: 0.62, armR: 0.36, mane: 0.22, head: 0.06, kickL: 0.24, kickR: -0.06, hair: -1.5)),
        CapriKey(3, CapriPose(armL: 0.4, armR: 0.6, mane: 0.17, head: -0.04, kickL: -0.06, kickR: 0.26, hair: 1.5)),
      ],
    ),

    // ---- one-shot acts ----
    'talk': CapriAct(
      priority: 0,
      keys: _rep(2, const [
        CapriKey(3, CapriPose(head: 0.04, mane: 0.08)),
        CapriKey(3, CapriPose(head: 0, mane: 0.03)),
      ]),
    ),

    'curious': const CapriAct(
      priority: 1,
      directional: true,
      keys: [
        CapriKey(1, CapriPose(head: -0.05, mane: 0.04)),
        CapriKey(1, CapriPose(head: 0.12, mane: 0.15, tilt: 1, smear: [-12, 4])),
        CapriKey(10, CapriPose(head: 0.19, mane: 0.14, tilt: 2)),
        CapriKey(6, CapriPose(head: 0.16, mane: 0.1, tilt: 1.6)),
        CapriKey(1, CapriPose(head: 0.07, tilt: 0.6)),
      ],
    ),

    'look': const CapriAct(
      priority: 1,
      keys: [
        CapriKey(1, CapriPose(head: 0.08, smear: [-8, 0])),
        CapriKey(8, CapriPose(head: 0.16)),
        CapriKey(1, CapriPose(head: 0)),
        CapriKey(1, CapriPose(head: -0.08, smear: [8, 0])),
        CapriKey(8, CapriPose(head: -0.16)),
        CapriKey(1, CapriPose(head: -0.05)),
        CapriKey(3, CapriPose(head: 0)),
      ],
    ),

    'gaze': const CapriAct(
      priority: 1,
      directional: true,
      keys: [
        CapriKey(3, CapriPose(), 'glint'),
        CapriKey(1, CapriPose(head: -0.05, bob: 1)),
        CapriKey(1, CapriPose(head: 0.14, mane: 0.12, smear: [-8, 6]), 'notice'),
        CapriKey(6, CapriPose(head: 0.2, mane: 0.1, hair: 0, bob: 0)),
        CapriKey(6, CapriPose(head: 0.23, mane: 0.14, hair: 0, bob: 0), 'starlight'),
        CapriKey(3, CapriPose(head: 0.23, mane: 0.15, hair: 0, bob: 0, reach: 0.25, long: 1.1)),
        CapriKey(3, CapriPose(head: 0.24, mane: 0.16, hair: 0, bob: 0, reach: 0.55, long: 1.2)),
        CapriKey(2, CapriPose(head: 0.24, mane: 0.16, hair: 0, bob: -1, reach: 0.8, long: 1.3)),
        CapriKey(2, CapriPose(head: 0.25, mane: 0.17, hair: 0, bob: -2, reach: 0.93, long: 1.35)),
        CapriKey(14, CapriPose(head: 0.25, mane: 0.17, hair: 0, bob: -3, reach: 1, long: 1.38)),
        CapriKey(1, CapriPose(head: 0.27, mane: 0.22, hair: 0, bob: -4, reach: 1.02, long: 1.42), 'glimmer'),
        CapriKey(8, CapriPose(head: 0.25, mane: 0.18, hair: 0, bob: -3, reach: 1, long: 1.38)),
        CapriKey(2, CapriPose(head: 0.14, mane: 0.1, bob: -2, reach: 0.45, long: 1.15)),
        CapriKey(2, CapriPose(head: 0.08, mane: 0.04, bob: -1, reach: 0.12, long: 1.03)),
        CapriKey(8, CapriPose(head: 0.06, mane: -0.04, reach: -0.06)),
        CapriKey(1),
      ],
    ),

    'uplink': const CapriAct(
      priority: 1,
      directional: true,
      keys: [
        CapriKey(2, CapriPose(hair: 0, bob: -2), 'glint'),
        CapriKey(3, CapriPose(hair: 0, bob: -2), 'stars'),
        CapriKey(3, CapriPose(hair: 0, bob: -2, mane: 0.05)),
        CapriKey(4, CapriPose(hair: 0, bob: -2, mane: 0.1, head: 0.03)),
        CapriKey(1, CapriPose(hair: 0, bob: -1, head: -0.06)),
        CapriKey(1, CapriPose(hair: 0, bob: -2, head: 0.16, mane: 0.16, smear: [-8, 6]), 'notice'),
        CapriKey(5, CapriPose(hair: 0, bob: -2, head: 0.22, mane: 0.14)),
        CapriKey(3, CapriPose(hair: 0, bob: -2, head: 0.23, mane: 0.15, reach: 0.3, long: 1.15)),
        CapriKey(3, CapriPose(hair: 0, bob: -2, head: 0.24, mane: 0.16, reach: 0.6, long: 1.3), 'align'),
        CapriKey(2, CapriPose(hair: 0, bob: -3, head: 0.25, mane: 0.17, reach: 0.85, long: 1.42)),
        CapriKey(2, CapriPose(hair: 0, bob: -4, head: 0.25, mane: 0.18, reach: 0.96, long: 1.5)),
        CapriKey(9, CapriPose(hair: 0, bob: -5, head: 0.25, mane: 0.18, reach: 1, long: 1.52)),
        CapriKey(1, CapriPose(hair: 0, bob: 1, head: 0.24, mane: 0.26, reach: 0.98, long: 1.45, sy: 0.95, sx: 1.03), 'charge'),
        CapriKey(2, CapriPose(hair: 0, bob: 3, head: 0.23, mane: 0.32, reach: 0.98, long: 1.42, sy: 0.93, sx: 1.04)),
        CapriKey(2, CapriPose(hair: 0, bob: 4, head: 0.23, mane: 0.38, reach: 0.99, long: 1.4, sy: 0.92, sx: 1.05)),
        CapriKey(2, CapriPose(hair: 0, bob: 5, head: 0.22, mane: 0.44, reach: 1, long: 1.4, sy: 0.91, sx: 1.06, echo: [2, 0])),
        CapriKey(1, CapriPose(hair: 0, bob: -10, head: 0.3, mane: 0.7, reach: 1.05, long: 1.78, sy: 1.14, sx: 0.9, echo: [10, -4], smear: [0, 14]), 'surge'),
        CapriKey(1, CapriPose(hair: 0, bob: -16, head: 0.31, mane: 0.86, reach: 1.06, long: 1.7, sy: 1.06, sx: 0.96, echo: [16, -6])),
        CapriKey(2, CapriPose(hair: 0, bob: -19, head: 0.3, mane: 0.8, reach: 1.06, long: 1.66, echo: [9, -3])),
        CapriKey(2, CapriPose(hair: 0, bob: -19, head: 0.28, mane: 0.74, reach: 1.06, long: 1.62, echo: [4, -1])),
        CapriKey(5, CapriPose(hair: 0, bob: -18, head: 0.28, mane: 0.62, reach: 1.05, long: 1.6)),
        CapriKey(1, CapriPose(hair: 0, bob: -15, head: 0.27, mane: 0.5, reach: 1.03, long: 1.55, smear: [0, -8]), 'break'),
        CapriKey(7, CapriPose(hair: 0, bob: -13, head: 0.26, mane: 0.36, reach: 1.02, long: 1.52)),
        CapriKey(1, CapriPose(hair: 0, bob: -13, head: 0.29, mane: 0.4, reach: 1.03, long: 1.54), 'twinkle'),
        CapriKey(4, CapriPose(hair: 0, bob: -12, head: 0.28, mane: 0.32, reach: 1.02, long: 1.52)),
        CapriKey(1, CapriPose(hair: 0, bob: -12, head: 0.29, mane: 0.34, reach: 1.02, long: 1.53), 'glimmer'),
        CapriKey(7, CapriPose(hair: 0, bob: -11, head: 0.27, mane: 0.28, reach: 1, long: 1.5)),
        CapriKey(2, CapriPose(bob: -7, head: 0.2, mane: 0.2, reach: 0.7, long: 1.3), 'home'),
        CapriKey(2, CapriPose(bob: -4, head: 0.14, mane: 0.12, reach: 0.4, long: 1.12)),
        CapriKey(2, CapriPose(bob: -1, head: 0.08, mane: 0.04, reach: 0.12, long: 1.03)),
        CapriKey(10, CapriPose(bob: 1, head: 0.06, mane: -0.06, reach: -0.06)),
        CapriKey(1),
      ],
    ),

    'victory': CapriAct(
      priority: 4,
      fps: 24,
      directional: true,
      keys: [
        const CapriKey(3, CapriPose(sy: 0.9, sx: 1.05, bob: 6, arms: -0.3, mane: -0.15)),
        const CapriKey(3, CapriPose(sy: 0.82, sx: 1.1, bob: 10, arms: -0.5, mane: -0.3, head: -0.04), 'gather'),
        const CapriKey(1, CapriPose(sy: 1.24, sx: 0.85, bob: -16, arms: 0.55, mane: 0.45, smear: [0, 22], echo: [12, 0]), 'launch'),
        const CapriKey(2, CapriPose(sy: 1.1, sx: 0.94, bob: -30, arms: 1.45, mane: 0.85, echo: [20, -4]), 'peak'),
        const CapriKey(10, CapriPose(bob: -36, arms: 1.32, mane: 0.78, head: 0.05)),
        const CapriKey(2, CapriPose(bob: -34, arms: 1.18, mane: 0.7, head: -0.08), 'laugh'),
        const CapriKey(2, CapriPose(bob: -38, arms: 1.36, mane: 0.8, head: 0.08)),
        ..._rep(4, const [
          CapriKey(2, CapriPose(bob: -34, arms: 1.18, mane: 0.7, head: -0.08)),
          CapriKey(2, CapriPose(bob: -38, arms: 1.36, mane: 0.8, head: 0.08)),
        ]),
        const CapriKey(2, CapriPose(bob: -24, arms: 0.7, mane: 0.45, sy: 1.04), 'speak'),
        const CapriKey(2, CapriPose(bob: -8, arms: 0.15, mane: 0.2, sy: 1.06, sx: 0.96, smear: [0, -12])),
        const CapriKey(2, CapriPose(bob: 3, arms: -0.15, mane: -0.06, sy: 0.88, sx: 1.08)),
        const CapriKey(3, CapriPose(bob: 1, arms: 0.05, sy: 0.97, sx: 1.02)),
        const CapriKey(2, CapriPose(arms: 0)),
      ],
    ),

    'zap': const CapriAct(
      priority: 2,
      fps: 24,
      directional: true,
      keys: [
        CapriKey(3, CapriPose(reach: 0.2, long: 0.9, head: -0.06, mane: 0.1, bob: 1)),
        CapriKey(1, CapriPose(reach: 1, long: 1.6, head: 0.12, mane: 0.32, smear: [-10, 0], echo: [6, 0]), 'zap'),
        CapriKey(6, CapriPose(reach: 1, long: 1.52, head: 0.14, mane: 0.26)),
        CapriKey(4, CapriPose(reach: 0.96, long: 1.42, head: 0.18, mane: 0.2), 'grin'),
        CapriKey(10, CapriPose(reach: 0.9, long: 1.36, head: 0.2, mane: 0.16)),
        CapriKey(3, CapriPose(reach: 0.5, long: 1.15, head: 0.14, mane: 0.08)),
        CapriKey(3, CapriPose(reach: 0.15, head: 0.06)),
        CapriKey(1),
      ],
    ),

    'point': const CapriAct(
      priority: 2,
      fps: 24,
      directional: true,
      keys: [
        CapriKey(2, CapriPose(head: 0.16, mane: 0.15, tilt: 1, smear: [-10, 2]), 'spot'),
        CapriKey(3, CapriPose(head: 0.2, mane: 0.12, tilt: 1.5)),
        CapriKey(3, CapriPose(reach: -0.45, long: 0.8, head: 0.12, tilt: -5, sy: 0.9, sx: 1.06, bob: 5, mane: -0.2)),
        CapriKey(2, CapriPose(reach: -0.55, long: 0.75, head: 0.1, tilt: -6, sy: 0.86, sx: 1.08, bob: 7, mane: -0.28), 'coil'),
        CapriKey(1, CapriPose(reach: 0.9, long: 2.3, head: 0.24, tilt: 8, sx: 0.94, sy: 1.1, mane: 0.6, smear: [-18, 0], echo: [14, 0]), 'lock'),
        CapriKey(1, CapriPose(reach: 1.08, long: 2, head: 0.22, tilt: 7, mane: 0.55, echo: [8, 0])),
        CapriKey(2, CapriPose(reach: 1.02, long: 1.42, head: 0.19, tilt: 4, mane: 0.4)),
        CapriKey(2, CapriPose(reach: 0.98, long: 1.58, head: 0.18, tilt: 3, mane: 0.3)),
        CapriKey(2, CapriPose(reach: 1, long: 1.5, head: 0.17, tilt: 3, mane: 0.22)),
      ],
    ),

    'unpoint': const CapriAct(
      priority: 2,
      fps: 24,
      directional: true,
      keys: [
        CapriKey(1, CapriPose(reach: 0.6, long: 0.9, head: 0.08, tilt: -2, smear: [12, 0], mane: 0.1)),
        CapriKey(2, CapriPose(reach: 0.1, long: 0.85, head: 0.04, tilt: -1)),
        CapriKey(2, CapriPose(reach: -0.06, long: 1, tilt: 0)),
        CapriKey(1),
      ],
    ),

    'split': const CapriAct(
      priority: 3,
      fps: 24,
      keys: [
        CapriKey(2, CapriPose(echo: [3, 0], mane: 0.1)),
        CapriKey(2, CapriPose(echo: [10, -2], mane: 0.18, head: 0.05)),
        CapriKey(2, CapriPose(echo: [22, -4], mane: 0.22, head: -0.06), 'minds'),
        CapriKey(6, CapriPose(echo: [34, -5], mane: 0.24, head: 0.06, bob: -3)),
        CapriKey(2, CapriPose(echo: [41, -6], mane: 0.26, head: -0.05, bob: -3)),
        CapriKey(6, CapriPose(echo: [36, -5], mane: 0.24, head: 0.07, bob: -3)),
        CapriKey(1, CapriPose(echo: [12, 0], sx: 1.08, sy: 0.94, bob: -1), 'snap'),
        CapriKey(1, CapriPose(sx: 0.96, sy: 1.04, mane: 0.3)),
        CapriKey(3, CapriPose(mane: 0.1)),
        CapriKey(1),
      ],
    ),

    'alarm': CapriAct(
      priority: 2,
      directional: true,
      keys: [
        const CapriKey(1, CapriPose(mane: 0.34, head: 0.1, tilt: 3, arms: 0.36), 'stare'),
        const CapriKey(1, CapriPose(mane: 0.12, head: 0.1, tilt: 3, arms: 0.24)),
        ..._rep(14, const [
          CapriKey(1, CapriPose(mane: 0.34, head: 0.1, tilt: 3, arms: 0.36)),
          CapriKey(1, CapriPose(mane: 0.12, head: 0.1, tilt: 3, arms: 0.24)),
        ]),
      ],
    ),

    'flinch': const CapriAct(
      priority: 2,
      keys: [
        CapriKey(2, CapriPose(head: 0.22, tilt: 4, sx: 0.92, sy: 1.06, mane: -0.12, bob: 5, smear: [-10, 0], arms: -0.32)),
        CapriKey(5, CapriPose(head: 0.18, tilt: 3.4, mane: -0.1, bob: 4, arms: -0.22)),
        CapriKey(1, CapriPose(head: 0.09, tilt: 1.5, bob: 2, arms: -0.08)),
      ],
    ),

    'spin': const CapriAct(
      priority: 3,
      fps: 24,
      keys: [
        CapriKey(2, CapriPose(sy: 0.92, sx: 1.05, bob: 3, arms: -0.2)),
        CapriKey(1, CapriPose(sx: 0.7, echo: [8, 0], mane: 0.25, arms: 0.15)),
        CapriKey(1, CapriPose(sx: 0.2, echo: [14, 0], mane: 0.35, bob: -4, arms: 0.28)),
        CapriKey(1, CapriPose(sx: -0.3, echo: [14, 0], mane: 0.35, bob: -6, arms: 0.3)),
        CapriKey(1, CapriPose(sx: -0.75, echo: [10, 0], mane: 0.3, bob: -6, arms: 0.3)),
        CapriKey(1, CapriPose(sx: -1, echo: [6, 0], bob: -6, arms: 0.28)),
        CapriKey(1, CapriPose(sx: -0.75, echo: [10, 0], mane: 0.3, bob: -5, arms: 0.3)),
        CapriKey(1, CapriPose(sx: -0.3, echo: [14, 0], mane: 0.35, bob: -4, arms: 0.3)),
        CapriKey(1, CapriPose(sx: 0.2, echo: [14, 0], mane: 0.35, bob: -2, arms: 0.25)),
        CapriKey(1, CapriPose(sx: 0.7, echo: [8, 0], mane: 0.25, arms: 0.15)),
        CapriKey(2, CapriPose(sx: 1.06, sy: 0.95, mane: 0.15, arms: -0.06)),
        CapriKey(1, CapriPose(sx: 1)),
      ],
    ),

    'hop': const CapriAct(
      priority: 3,
      fps: 24,
      keys: [
        CapriKey(3, CapriPose(sy: 0.86, sx: 1.08, bob: 6, mane: -0.08, arms: -0.3)),
        CapriKey(1, CapriPose(sy: 1.18, sx: 0.9, bob: -10, smear: [0, 16], arms: 0.4)),
        CapriKey(2, CapriPose(sy: 1.08, sx: 0.95, bob: -32, mane: 0.15, arms: 0.55)),
        CapriKey(4, CapriPose(bob: -42, mane: 0.3, arms: 0.6)),
        CapriKey(2, CapriPose(sy: 1.06, bob: -26, mane: 0.2, arms: 0.35)),
        CapriKey(1, CapriPose(sy: 1.12, sx: 0.92, bob: -8, smear: [0, -14], arms: 0.15)),
        CapriKey(2, CapriPose(sy: 0.82, sx: 1.12, bob: 5, mane: -0.1, arms: -0.28)),
        CapriKey(2, CapriPose(sy: 0.94, sx: 1.04, bob: 2, arms: 0.06)),
        CapriKey(1),
      ],
    ),

    'plop': const CapriAct(
      priority: 3,
      fps: 24,
      keys: [
        CapriKey(2, CapriPose(sy: 0.85, sx: 1.1, mane: -0.12, kickL: 0.3, kickR: 0.3, arms: -0.55)),
        CapriKey(2, CapriPose(sy: 1.05, sx: 0.97, kickL: 0.12, kickR: 0.12, arms: -0.38)),
        CapriKey(1),
      ],
    ),

    'stretch': const CapriAct(
      priority: 1,
      keys: [
        CapriKey(3, CapriPose(arms: -0.55, head: 0.08, mane: -0.1, sy: 0.95, sx: 1.04)),
        CapriKey(1, CapriPose(arms: 1.2, head: -0.04, mane: 0.18, sy: 1.06, sx: 0.96, smear: [0, -10])),
        CapriKey(2, CapriPose(arms: 1.8, head: -0.12, mane: 0.3, sy: 1.08, sx: 0.95, kickL: 0.22, kickR: 0.22)),
        CapriKey(12, CapriPose(arms: 1.92, head: -0.15, mane: 0.36, sy: 1.09, sx: 0.94, kickL: 0.26, kickR: 0.26)),
        CapriKey(2, CapriPose(arms: 1.86, head: -0.13, mane: 0.32, sy: 1.08, sx: 0.95, kickL: 0.2, kickR: 0.2)),
        CapriKey(1, CapriPose(arms: 0.7, mane: 0.1, smear: [0, 8])),
        CapriKey(3, CapriPose(arms: -0.5, head: 0.1, mane: -0.16, sy: 0.95, sx: 1.04)),
        CapriKey(4, CapriPose(arms: -0.42, head: 0.05, mane: -0.08)),
      ],
    ),

    'petted': const CapriAct(
      priority: 1,
      directional: true,
      keys: [
        CapriKey(2, CapriPose(head: 0.1, mane: 0.12, tilt: 1, sy: 0.98, sx: 1.01)),
        CapriKey(3, CapriPose(head: 0.22, mane: 0.22, tilt: 2.5, sy: 0.96, sx: 1.03, bob: 2)),
        CapriKey(3, CapriPose(head: 0.24, mane: 0.15, tilt: 3, sy: 0.96, sx: 1.03, bob: 3)),
        CapriKey(3, CapriPose(head: 0.23, mane: 0.24, tilt: 2.6, sy: 0.965, sx: 1.025, bob: 2)),
        CapriKey(3, CapriPose(head: 0.25, mane: 0.15, tilt: 3, sy: 0.96, sx: 1.03, bob: 3)),
        CapriKey(3, CapriPose(head: 0.23, mane: 0.23, tilt: 2.6, sy: 0.965, sx: 1.025, bob: 2)),
        CapriKey(3, CapriPose(head: 0.24, mane: 0.16, tilt: 3, sy: 0.96, sx: 1.03, bob: 3)),
        CapriKey(2, CapriPose(head: 0.12, mane: 0.08, tilt: 1.2)),
        CapriKey(1),
      ],
    ),
  };
}

class SampledDrawing {
  final CapriPose pose;
  final int index;
  final String? cue;

  const SampledDrawing({
    required this.pose,
    required this.index,
    this.cue,
  });
}

class ActPlayer {
  final String name;
  final CapriAct act;
  final int dir;
  final double reach;
  final double startMs;
  final int totalFrames;
  int _lastKeyIndex = -1;

  ActPlayer(
    this.name, {
    this.dir = 1,
    this.reach = 1.0,
    required this.startMs,
  })  : act = CapriActs.all[name] ?? CapriActs.all['stand']!,
        totalFrames = (CapriActs.all[name] ?? CapriActs.all['stand']!).totalFrames;

  int get priority => act.priority;

  SampledDrawing? sample(double nowMs) {
    final double frameDurationMs = 1000.0 / act.fps;
    int f = ((nowMs - startMs) / frameDurationMs).floor();
    if (f < 0) f = 0;

    if (f >= totalFrames) {
      if (!act.loop) return null;
      f = f % totalFrames;
    }

    for (int i = 0; i < act.keys.length; i++) {
      final key = act.keys[i];
      if (f < key.hold) {
        final bool isNewKey = i != _lastKeyIndex;
        _lastKeyIndex = i;
        return SampledDrawing(
          pose: key.pose,
          index: i,
          cue: isNewKey ? key.cue : null,
        );
      }
      f -= key.hold;
    }
    return null;
  }
}

