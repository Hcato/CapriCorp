// Capri rig: a single cut-out texture deformed in the fragment shader.
//
// Ported to Flutter (FragmentProgram) from the WebGL renderer of mochiiwuff/capri-desktop
// (src/renderer/js/sprite.js). Required Notice: Copyright (c) 2026 mochiiwuff
// (https://github.com/mochiiwuff/capri-desktop). Non-commercial use only, see THIRD_PARTY_NOTICES.md.
//
// Differences from the original:
//  - Flutter samples textures premultiplied, so cel() un-premultiplies before grading.
//  - No `discard` and no reversed smoothstep (undefined on some backends): see sstep().
//  - Every uniform is a float/vecN, set by index from capri_painter.dart (keep the order in sync).

#version 460 core
#include <flutter/runtime_effect.glsl>

precision highp float;

// ---- uniforms (order = setFloat index, see CapriPainter) ----
uniform vec2 uCanvas;      // 0-1   size of the drawn rect, logical px
uniform float uSeed;       // 2
uniform float uBoil;       // 3
uniform float uHair;       // 4
uniform float uHead;       // 5
uniform float uMane;       // 6
uniform float uArmL;       // 7
uniform float uArmR;       // 8
uniform float uLongL;      // 9
uniform float uLongR;      // 10
uniform float uSit;        // 11
uniform float uBend;       // 12
uniform float uKickL;      // 13
uniform float uKickR;      // 14
uniform vec2 uSmear;       // 15-16
uniform vec2 uEcho;        // 17-18
uniform float uGlitch;     // 19
uniform float uGlitchSeed; // 20
uniform float uSplit;      // 21
uniform float uCollapse;   // 22
uniform float uDissolve;   // 23
uniform float uSparkle;    // 24
uniform float uGrade;      // 25
uniform vec4 uSil;         // 26-29 rgb + amount
uniform vec2 uMisreg;      // 30-31
uniform vec3 uRim;         // 32-34
uniform float uAlpha;      // 35
uniform float uPx;         // 36  sprite pixels per device pixel

uniform sampler2D uTex;    // sampler 0: assets/capri/capri-full.png

out vec4 fragColor;

// sprite geometry (capri-full.png is 240x420, drawn with 56 px of room around it)
const vec2 SIZE = vec2(240.0, 420.0);
const float PAD = 56.0;
const vec2 VIEW = vec2(352.0, 532.0);

// landmarks, in sprite pixels
const vec2 NECK = vec2(118.0, 152.0);
const vec2 SHOULDER_L = vec2(98.0, 168.0);
const float MIRROR = 234.0;
const vec2 SHOULDER_R = vec2(136.0, 168.0);
const vec2 MANE = vec2(116.0, 92.0);
const vec2 FACE = vec2(124.0, 132.0);
const float AXIS = 118.0;
const float HIP = 232.0;
const float KNEE = 305.0;
const float KNEE_LX = 106.0;
const float KNEE_RX = 142.0;
const vec2 ARM_DIR = vec2(-0.85954, 0.51108);

// smoothstep that also works with edge0 > edge1 (reversed ramps are used a lot below)
float sstep(float a, float b, float x) {
  float t = clamp((x - a) / (b - a), 0.0, 1.0);
  return t * t * (3.0 - 2.0 * t);
}

float hash(vec2 p) {
  p = fract(p * vec2(123.34, 456.21));
  p += dot(p, p + 45.32);
  return fract(p.x * p.y);
}

float vnoise(vec2 p) {
  vec2 i = floor(p);
  vec2 f = fract(p);
  f = f * f * (3.0 - 2.0 * f);
  return mix(mix(hash(i), hash(i + vec2(1.0, 0.0)), f.x),
             mix(hash(i + vec2(0.0, 1.0)), hash(i + vec2(1.0, 1.0)), f.x), f.y);
}

vec2 rot(vec2 p, vec2 c, float a) {
  float s = sin(a);
  float k = cos(a);
  p -= c;
  return c + vec2(k * p.x - s * p.y, s * p.x + k * p.y);
}

vec4 tex(vec2 p) {
  if (p.x < 0.0 || p.y < 0.0 || p.x > SIZE.x || p.y > SIZE.y) return vec4(0.0);
  return texture(uTex, p / SIZE);
}

vec3 rgb2hsv(vec3 c) {
  vec4 K = vec4(0.0, -1.0 / 3.0, 2.0 / 3.0, -1.0);
  vec4 p = mix(vec4(c.bg, K.wz), vec4(c.gb, K.xy), step(c.b, c.g));
  vec4 q = mix(vec4(p.xyw, c.r), vec4(c.r, p.yzx), step(p.x, c.r));
  float d = q.x - min(q.w, q.y);
  return vec3(abs(q.z + (q.w - q.y) / (6.0 * d + 1e-10)), d / (q.x + 1e-10), q.x);
}

vec3 hsv2rgb(vec3 c) {
  vec4 K = vec4(1.0, 2.0 / 3.0, 1.0 / 3.0, 3.0);
  vec3 p = abs(fract(c.xxx + K.xyz) * 6.0 - K.www);
  return c.z * mix(K.xxx, clamp(p - K.xxx, 0.0, 1.0), c.y);
}

// Pull pinks/crimsons toward the show's hot red and the mask toward neon green.
// Returns the graded colour in rgb and "how much of the mane it is" in a.
vec4 grade(vec3 c) {
  vec3 h = rgb2hsv(c);
  float hx = h.x < 0.5 ? h.x + 1.0 : h.x;
  float lit = sstep(0.1, 0.3, h.z);
  float red = sstep(0.78, 0.85, hx) * (1.0 - sstep(1.06, 1.1, hx)) * lit * sstep(0.06, 0.2, h.y);
  float green = sstep(0.22, 0.27, h.x) * (1.0 - sstep(0.47, 0.52, h.x)) * lit * sstep(0.15, 0.3, h.y);
  hx = mix(hx, 0.968, red * 0.6 * uGrade);
  h.x = fract(hx);
  h.y = mix(h.y, max(h.y, 0.86), red * uGrade);
  h.y = mix(h.y, min(1.0, h.y * 1.1 + 0.06), green * uGrade);
  h.z = mix(h.z, min(1.0, h.z * 1.5 + 0.1), (red + green) * uGrade);
  return vec4(hsv2rgb(h), red);
}

// Graded, speckled, premultiplied sample of the figure.
vec4 cel(vec2 s) {
  vec4 c = tex(s);
  if (c.a <= 0.001) return vec4(0.0);
  vec4 g = grade(c.rgb / c.a);
  vec3 rgb = g.rgb;
  float red = g.a;
  if (red > 0.0 && uSparkle > 0.0) {
    vec2 cell = floor(s / max(0.8, uPx * 1.2));
    float star = step(0.976, hash(cell + 3.1)) * 0.85;
    float tw = step(0.993, hash(cell + uSeed * 1.37));
    rgb = mix(rgb, vec3(1.0, 0.95, 0.97), clamp((star + tw) * red * uSparkle, 0.0, 1.0));
  }
  return vec4(rgb * c.a, c.a);
}

float legSep(float y) { return 117.0 + max(0.0, y - 300.0) * 0.15; }
float legL(vec2 s) { return step(KNEE - 6.0, s.y) * (1.0 - step(legSep(s.y), s.x)); }
float legR(vec2 s) { return step(KNEE - 6.0, s.y) * step(legSep(s.y), s.x); }

float thighScale() { return mix(1.0, 0.3, uSit); }

vec2 unsit(vec2 q) {
  if (uSit <= 0.0 || q.y <= HIP) return q;
  float c = thighScale();
  if (q.y <= HIP + (KNEE - HIP) * c) {
    q.y = HIP + (q.y - HIP) / c;
  } else {
    q.y += (KNEE - HIP) * (1.0 - c);
  }
  return q;
}

float armL(vec2 s) {
  if (s.x > 101.0 || s.y > 234.0) return 0.0;
  float top = 159.0 + (98.0 - s.x) * 0.5;
  float bot = s.x < 50.0 ? 234.0 : 178.0 + (98.0 - s.x) * 0.62;
  return step(top, s.y) * step(s.y, bot);
}

vec2 mirrorArm(vec2 s) { return vec2(MIRROR - s.x, s.y); }

vec2 stretchArm(vec2 s, float k) {
  if (k == 1.0) return s;
  vec2 v = s - SHOULDER_L;
  float along = dot(v, ARM_DIR);
  return SHOULDER_L + ARM_DIR * (along / k) + (v - ARM_DIR * along);
}

vec2 armLeft(vec2 q) { return stretchArm(rot(q, SHOULDER_L, -uArmL), uLongL); }
vec2 armRight(vec2 q) { return stretchArm(mirrorArm(rot(q, SHOULDER_R, uArmR)), uLongR); }

bool legsRigged() { return uSit > 0.0 || uKickL != 0.0 || uKickR != 0.0; }

vec2 hips(vec2 q) {
  if (uBend == 0.0) return q;
  return rot(q, vec2(AXIS, HIP), -uBend * sstep(HIP - 16.0, HIP + 8.0, q.y));
}

vec4 torso(vec2 q) {
  q = hips(q);
  if (!legsRigged()) return armL(q) > 0.0 ? vec4(0.0) : cel(q);
  float kneeY = HIP + (KNEE - HIP) * thighScale();
  vec2 qB = unsit(q);
  vec2 qL = unsit(rot(q, vec2(KNEE_LX, kneeY), -uKickL));
  vec2 qR = unsit(rot(q, vec2(KNEE_RX, kneeY), uKickR));
  vec4 b = legL(qB) + legR(qB) + armL(qB) > 0.0 ? vec4(0.0) : cel(qB);
  vec4 l = legL(qL) > 0.0 ? cel(qL) : vec4(0.0);
  vec4 r = legR(qR) > 0.0 ? cel(qR) : vec4(0.0);
  vec4 c = l + b * (1.0 - l.a);
  return r + c * (1.0 - r.a);
}

float armAlpha(vec2 q) {
  vec2 qL = armLeft(q);
  vec2 qR = armRight(q);
  return max(armL(qL) * tex(qL).a, armL(qR) * tex(qR).a);
}

vec2 bend(vec2 q) {
  float tips = sstep(26.0, 40.0, abs(q.x - AXIS)) * sstep(195.0, 175.0, q.y);
  q = rot(q, NECK, -uHead * max(sstep(162.0, 138.0, q.y), tips));

  if (uMane != 0.0) {
    vec2 d = q - MANE;
    float spikes = 0.55 + 0.9 * vnoise(vec2(atan(d.y, d.x) * 2.6, 4.0));
    float w = sstep(182.0, 60.0, q.y) * sstep(16.0, 30.0, distance(q, FACE));
    q = MANE + d / (1.0 + uMane * w * 0.32 * spikes);
  }

  float hw = sstep(175.0, 5.0, q.y);
  q.x -= uHair * hw * (0.65 + 0.35 * sin(q.y * 0.055));
  q.y -= uHair * 0.22 * hw * sin(q.x * 0.045);
  return q;
}

vec4 rig(vec2 q) {
  vec2 qL = armLeft(q);
  vec2 qR = armRight(q);
  vec4 l = armL(qL) > 0.0 ? cel(qL) : vec4(0.0);
  vec4 r = armL(qR) > 0.0 ? cel(qR) : vec4(0.0);
  vec4 arms = l + r * (1.0 - l.a);
  vec4 b = torso(bend(q));
  bool joint = distance(q, SHOULDER_L) < 18.0 || distance(q, SHOULDER_R) < 18.0;
  if (joint) return b + arms * (1.0 - b.a);
  if (arms.a < 0.5 && b.a > 0.5 && (uArmL != 0.0 || uArmR != 0.0)) {
    float edge = max(max(armAlpha(q + vec2(1.8, 0.0)), armAlpha(q - vec2(1.8, 0.0))),
                     max(armAlpha(q + vec2(0.0, 1.8)), armAlpha(q - vec2(0.0, 1.8))));
    if (edge > 0.5) return vec4(uRim, 1.0);
  }
  return arms + b * (1.0 - arms.a);
}

float rigAlpha(vec2 q) { return rig(q).a; }

vec2 settle(vec2 p) {
  vec2 q = p;
  // teleport: squeeze into a vertical line of light
  q.x = AXIS + (q.x - AXIS) / max(1.0 - uCollapse, 0.025);
  q.y = 240.0 + (q.y - 240.0) / (1.0 + uCollapse * 0.4);

  if (uGlitch > 0.0) {
    float bh = mix(5.0, 26.0, hash(vec2(uGlitchSeed, 7.0)));
    float band = floor(q.y / bh);
    float on = step(1.0 - uGlitch * 0.6, hash(vec2(band, uGlitchSeed)));
    q.x += on * (hash(vec2(band + 3.0, uGlitchSeed)) - 0.5) * 72.0 * uGlitch;
  }

  q += (vec2(vnoise(q * 0.075 + uSeed * 13.7), vnoise(q * 0.075 + uSeed * 7.3 + 31.0)) - 0.5) * 2.0 * uBoil;
  return q;
}

void main() {
  vec2 p = FlutterFragCoord().xy / uCanvas * VIEW - PAD;

  if (uDissolve > 0.0) {
    vec2 g = rot(p, vec2(110.0, 210.0), 0.55);
    vec2 cell = floor(g / vec2(16.0, 9.0));
    if (hash(cell + floor(uGlitchSeed)) < uDissolve) {
      fragColor = vec4(0.0);
      return;
    }
  }

  vec2 q = settle(p);
  vec4 c = rig(q);
  vec3 col = c.rgb;
  float a = c.a;

  // chromatic split
  if (uSplit > 0.0) {
    vec4 cr = rig(q + vec2(uSplit, 0.0));
    vec4 cb = rig(q - vec2(uSplit, uSplit * 0.3));
    col = vec3(cr.r, col.g, cb.b);
    a = max(a, max(cr.a, cb.a));
  }

  // smear frame: two multiples of the head trailing where it came from
  if (dot(uSmear, uSmear) > 0.0) {
    float hw = sstep(178.0, 140.0, q.y);
    vec4 m1 = rig(q - uSmear * hw * 0.5);
    col += m1.rgb * (1.0 - a);
    a += m1.a * (1.0 - a);
    vec4 m2 = rig(q - uSmear * hw);
    col += m2.rgb * (1.0 - a);
    a += m2.a * (1.0 - a);
  }

  // impact frame: flat silhouette
  col = mix(col, uSil.rgb * a, uSil.a);

  // afterimages: a green and a red copy pulled apart
  if (dot(uEcho, uEcho) > 0.0) {
    float e1 = rigAlpha(q - uEcho) * (1.0 - a);
    col += vec3(0.21, 1.0, 0.48) * e1;
    a += e1;
    float e2 = rigAlpha(q + uEcho) * (1.0 - a);
    col += vec3(1.0, 0.13, 0.32) * e2;
    a += e2;
  }

  // violet misregistration behind the figure
  float rim = rigAlpha(q - uMisreg) * (1.0 - a);
  col += uRim * rim;
  a += rim;

  fragColor = vec4(col, a) * uAlpha;
}

