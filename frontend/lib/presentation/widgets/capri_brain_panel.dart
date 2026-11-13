// Cyberpunk Mainframe AI Brain Setup Panel ported from lachydotmcg/capri-desktop (app/Setup.cs & app/Brain.cs).
// Allows connecting Google Gemini (free AIza...), Groq (free gsk_...), NVIDIA NIM (nvapi-...),
// OpenRouter (sk-or-...), Anthropic Claude (sk-ant-...), OpenAI (sk-...), or Local Ollama / LM Studio,
// plus configuring User Nickname, Follow-ups (|||), and Screen Vision Glances.

import 'package:flutter/material.dart';
import '../../core/audio/capri_sfx.dart';

class BrainConfigState {
  final String provider;
  final String model;
  final String apiKeyMasked;
  final bool hasApiKey;
  final bool ollamaAvailable;
  final List<String> ollamaModels;
  final bool lmstudioAvailable;
  final String activeLabel;
  final String userName;
  final int notesCount;
  final bool followUpsEnabled;
  final bool proactiveGlances;

  const BrainConfigState({
    this.provider = 'auto',
    this.model = '',
    this.apiKeyMasked = '',
    this.hasApiKey = false,
    this.ollamaAvailable = false,
    this.ollamaModels = const [],
    this.lmstudioAvailable = false,
    this.activeLabel = 'Modo Local / Sin llave configurada',
    this.userName = 'choom',
    this.notesCount = 0,
    this.followUpsEnabled = true,
    this.proactiveGlances = false,
  });

  bool get isLiveBrainActive =>
      hasApiKey || ollamaAvailable || lmstudioAvailable || !activeLabel.contains('Sin ');

  factory BrainConfigState.fromMap(Map<String, dynamic> map) {
    final rawModels = map['ollama_models'];
    final modelsList = rawModels is List
        ? rawModels.map((e) => e.toString()).toList()
        : const <String>[];
    return BrainConfigState(
      provider: (map['provider'] ?? 'auto').toString(),
      model: (map['model'] ?? '').toString(),
      apiKeyMasked: (map['api_key_masked'] ?? '').toString(),
      hasApiKey: map['has_api_key'] == true,
      ollamaAvailable: map['ollama_available'] == true,
      ollamaModels: modelsList,
      lmstudioAvailable: map['lmstudio_available'] == true,
      activeLabel: (map['active_label'] ?? 'Modo Local').toString(),
      userName: (map['user_name'] ?? 'choom').toString(),
      notesCount: (map['notes_count'] as num?)?.toInt() ?? 0,
      followUpsEnabled: map['follow_ups_enabled'] != false,
      proactiveGlances: map['proactive_glances'] == true,
    );
  }
}

class CapriBrainPanel extends StatefulWidget {
  final BrainConfigState status;
  final void Function({
    required String provider,
    String? apiKey,
    required String model,
    required String userName,
    required bool followUpsEnabled,
    required bool proactiveGlances,
  }) onSave;
  final VoidCallback onGlanceScreen;
  final VoidCallback onClose;

  const CapriBrainPanel({
    super.key,
    required this.status,
    required this.onSave,
    required this.onGlanceScreen,
    required this.onClose,
  });

  @override
  State<CapriBrainPanel> createState() => _CapriBrainPanelState();
}

class _CapriBrainPanelState extends State<CapriBrainPanel> {
  static const Color _bg = Color(0xF50C0914);
  static const Color _pink = Color(0xFFFF1E6E);
  static const Color _cyan = Color(0xFF78FAFF);
  static const Color _mint = Color(0xFF34F5A0);
  static const Color _white = Color(0xFFF6F0FA);
  static const Color _dim = Color(0xFF968CA5);

  static const List<Map<String, String>> _providers = [
    {'id': 'auto', 'label': 'AUTO', 'hint': 'Detecta por prefijo o usa Ollama'},
    {'id': 'google', 'label': 'GEMINI', 'hint': 'Gratis en aistudio.google.com (AIza...)'},
    {'id': 'groq', 'label': 'GROQ', 'hint': 'Gratis y ultra rápido en console.groq.com (gsk_...)'},
    {'id': 'nvidia', 'label': 'NVIDIA', 'hint': 'Gratis en build.nvidia.com (nvapi-...)'},
    {'id': 'openrouter', 'label': 'OPENROUTER', 'hint': 'Modelos :free en openrouter.ai (sk-or-...)'},
    {'id': 'anthropic', 'label': 'CLAUDE', 'hint': 'Anthropic Claude (sk-ant-...)'},
    {'id': 'ollama', 'label': 'OLLAMA', 'hint': '100% Local en http://127.0.0.1:11434'},
  ];

  late String _selectedProvider;
  late bool _followUps;
  late bool _glances;
  late final TextEditingController _keyCtrl;
  late final TextEditingController _modelCtrl;
  late final TextEditingController _nameCtrl;

  @override
  void initState() {
    super.initState();
    _selectedProvider = widget.status.provider;
    _followUps = widget.status.followUpsEnabled;
    _glances = widget.status.proactiveGlances;
    _keyCtrl = TextEditingController();
    _modelCtrl = TextEditingController(text: widget.status.model);
    _nameCtrl = TextEditingController(text: widget.status.userName);
  }

  @override
  void didUpdateWidget(covariant CapriBrainPanel oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.status.activeLabel != widget.status.activeLabel) {
      _selectedProvider = widget.status.provider;
      _followUps = widget.status.followUpsEnabled;
      _glances = widget.status.proactiveGlances;
    }
  }

  @override
  void dispose() {
    _keyCtrl.dispose();
    _modelCtrl.dispose();
    _nameCtrl.dispose();
    super.dispose();
  }

  String _currentProviderHint() {
    for (final p in _providers) {
      if (p['id'] == _selectedProvider) return p['hint']!;
    }
    return 'Pega cualquier API Key (AIza..., gsk_..., nvapi-..., sk-or-..., sk-ant-...)';
  }

  void _submit() {
    CapriSfx.instance.play('charge');
    final typedKey = _keyCtrl.text.trim();
    widget.onSave(
      provider: _selectedProvider,
      apiKey: typedKey.isNotEmpty ? typedKey : null,
      model: _modelCtrl.text.trim(),
      userName: _nameCtrl.text.trim().isEmpty ? 'choom' : _nameCtrl.text.trim(),
      followUpsEnabled: _followUps,
      proactiveGlances: _glances,
    );
  }

  @override
  Widget build(BuildContext context) {
    final st = widget.status;
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 4, vertical: 4),
      child: Container(
        padding: const EdgeInsets.fromLTRB(10, 8, 10, 9),
        decoration: BoxDecoration(
          color: _bg,
          border: Border.all(color: _cyan, width: 1.5),
          boxShadow: [
            BoxShadow(
              color: _pink.withValues(alpha: 0.35),
              blurRadius: 14,
            ),
          ],
        ),
        child: SingleChildScrollView(
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              // 1. Cabecera + Estado del Enlace Neuronal
              Row(
                children: [
                  Container(
                    width: 8,
                    height: 8,
                    decoration: BoxDecoration(
                      shape: BoxShape.circle,
                      color: st.isLiveBrainActive ? _mint : _pink,
                    ),
                  ),
                  const SizedBox(width: 6),
                  const Expanded(
                    child: Text(
                      'CAPRI MAINFRAME // CEREBRO IA',
                      style: TextStyle(
                        fontFamily: 'ShareTechMono',
                        color: _cyan,
                        fontSize: 11,
                        fontWeight: FontWeight.bold,
                        letterSpacing: 0.5,
                      ),
                    ),
                  ),
                  GestureDetector(
                    onTap: widget.onClose,
                    child: const Icon(Icons.close_rounded, color: _dim, size: 16),
                  ),
                ],
              ),
              const SizedBox(height: 4),

              // Etiqueta de proveedor activo y notas en me.md
              Container(
                width: double.infinity,
                padding: const EdgeInsets.symmetric(horizontal: 7, vertical: 4),
                decoration: BoxDecoration(
                  color: const Color(0xFF171124),
                  border: Border.all(
                    color: st.isLiveBrainActive ? _mint.withValues(alpha: 0.6) : _pink.withValues(alpha: 0.6),
                  ),
                ),
                child: Text(
                  'ACTIVO: ${st.activeLabel}  •  NOTAS: ${st.notesCount}',
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                  style: TextStyle(
                    fontFamily: 'ShareTechMono',
                    color: st.isLiveBrainActive ? _mint : _pink,
                    fontSize: 9.5,
                    fontWeight: FontWeight.bold,
                  ),
                ),
              ),
              const SizedBox(height: 6),

              // 2. Píldoras de proveedor (`Cloud.KindOf`)
              Wrap(
                spacing: 4,
                runSpacing: 4,
                children: _providers.map((p) {
                  final id = p['id']!;
                  final active = _selectedProvider == id;
                  return GestureDetector(
                    onTap: () {
                      CapriSfx.instance.play('key');
                      setState(() {
                        _selectedProvider = id;
                        _modelCtrl.clear();
                      });
                    },
                    child: Container(
                      padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2.5),
                      decoration: BoxDecoration(
                        color: active ? _pink : const Color(0xFF191326),
                        border: Border.all(
                          color: active ? _cyan : const Color(0x44FFFFFF),
                        ),
                      ),
                      child: Text(
                        p['label']!,
                        style: TextStyle(
                          fontFamily: 'ShareTechMono',
                          color: active ? Colors.white : _dim,
                          fontSize: 9.5,
                          fontWeight: FontWeight.bold,
                        ),
                      ),
                    ),
                  );
                }).toList(),
              ),
              const SizedBox(height: 4),
              Text(
                _currentProviderHint(),
                maxLines: 1,
                overflow: TextOverflow.ellipsis,
                style: const TextStyle(
                  fontFamily: 'ShareTechMono',
                  color: _dim,
                  fontSize: 9,
                ),
              ),
              const SizedBox(height: 5),

              // 3. Campo de API Key (autodetección por prefijo)
              if (_selectedProvider != 'ollama')
                SizedBox(
                  height: 28,
                  child: TextField(
                    controller: _keyCtrl,
                    obscureText: true,
                    onChanged: (_) {
                      if (_modelCtrl.text.isNotEmpty) {
                        _modelCtrl.clear();
                      }
                    },
                    style: const TextStyle(
                      fontFamily: 'ShareTechMono',
                      color: _white,
                      fontSize: 11,
                    ),
                    decoration: InputDecoration(
                      isDense: true,
                      contentPadding: const EdgeInsets.symmetric(horizontal: 7, vertical: 6),
                      hintText: st.hasApiKey
                          ? 'Llave guardada (${st.apiKeyMasked}) — pega otra para cambiar'
                          : 'Pega tu API Key (AIza..., gsk_..., nvapi-..., sk-...)',
                      hintStyle: const TextStyle(color: _dim, fontSize: 9.5),
                      filled: true,
                      fillColor: const Color(0xFF161022),
                      enabledBorder: const OutlineInputBorder(
                        borderRadius: BorderRadius.zero,
                        borderSide: BorderSide(color: Color(0x5578FAFF)),
                      ),
                      focusedBorder: const OutlineInputBorder(
                        borderRadius: BorderRadius.zero,
                        borderSide: BorderSide(color: _pink, width: 1.3),
                      ),
                    ),
                  ),
                ),
              if (_selectedProvider != 'ollama') const SizedBox(height: 5),

              // 4. Fila: Tu apodo (`userName`) + Modelo opcional
              Row(
                children: [
                  Expanded(
                    flex: 5,
                    child: SizedBox(
                      height: 26,
                      child: TextField(
                        controller: _nameCtrl,
                        style: const TextStyle(
                          fontFamily: 'ShareTechMono',
                          color: _cyan,
                          fontSize: 10.5,
                        ),
                        decoration: const InputDecoration(
                          isDense: true,
                          contentPadding: EdgeInsets.symmetric(horizontal: 6, vertical: 5),
                          hintText: 'Tu apodo (choom)',
                          hintStyle: TextStyle(color: _dim, fontSize: 9.5),
                          filled: true,
                          fillColor: Color(0xFF161022),
                          enabledBorder: OutlineInputBorder(
                            borderRadius: BorderRadius.zero,
                            borderSide: BorderSide(color: Color(0x44FFFFFF)),
                          ),
                          focusedBorder: OutlineInputBorder(
                            borderRadius: BorderRadius.zero,
                            borderSide: BorderSide(color: _cyan),
                          ),
                        ),
                      ),
                    ),
                  ),
                  const SizedBox(width: 5),
                  Expanded(
                    flex: 6,
                    child: SizedBox(
                      height: 26,
                      child: TextField(
                        controller: _modelCtrl,
                        style: const TextStyle(
                          fontFamily: 'ShareTechMono',
                          color: _white,
                          fontSize: 10.5,
                        ),
                        decoration: const InputDecoration(
                          isDense: true,
                          contentPadding: EdgeInsets.symmetric(horizontal: 6, vertical: 5),
                          hintText: 'Modelo (vacío = auto)',
                          hintStyle: TextStyle(color: _dim, fontSize: 9.5),
                          filled: true,
                          fillColor: Color(0xFF161022),
                          enabledBorder: OutlineInputBorder(
                            borderRadius: BorderRadius.zero,
                            borderSide: BorderSide(color: Color(0x44FFFFFF)),
                          ),
                          focusedBorder: OutlineInputBorder(
                            borderRadius: BorderRadius.zero,
                            borderSide: BorderSide(color: _cyan),
                          ),
                        ),
                      ),
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 6),

              // 5. Toggles: Follow-ups (`|||`) y Miradas a Pantalla (`Glances`)
              Row(
                children: [
                  Expanded(
                    child: _MiniToggleChip(
                      label: 'Follow-ups (|||)',
                      checked: _followUps,
                      onTap: () => setState(() => _followUps = !_followUps),
                    ),
                  ),
                  const SizedBox(width: 5),
                  Expanded(
                    child: _MiniToggleChip(
                      label: 'Mirar Pantalla',
                      checked: _glances,
                      onTap: () => setState(() => _glances = !_glances),
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 7),

              // 6. Botones de Acción: Conectar y Mirar Pantalla Ahora
              Row(
                children: [
                  Expanded(
                    child: GestureDetector(
                      onTap: _submit,
                      child: Container(
                        height: 26,
                        alignment: Alignment.center,
                        decoration: BoxDecoration(
                          color: _pink,
                          border: Border.all(color: _cyan, width: 1.1),
                        ),
                        child: const Text(
                          'GUARDAR Y ACTIVAR IA',
                          style: TextStyle(
                            fontFamily: 'ShareTechMono',
                            color: Colors.white,
                            fontSize: 10.5,
                            fontWeight: FontWeight.bold,
                          ),
                        ),
                      ),
                    ),
                  ),
                  const SizedBox(width: 5),
                  GestureDetector(
                    onTap: () {
                      CapriSfx.instance.play('key');
                      widget.onGlanceScreen();
                    },
                    child: Container(
                      height: 26,
                      padding: const EdgeInsets.symmetric(horizontal: 8),
                      alignment: Alignment.center,
                      decoration: BoxDecoration(
                        color: const Color(0xFF1A1428),
                        border: Border.all(color: _mint, width: 1.1),
                      ),
                      child: const Row(
                        mainAxisSize: MainAxisSize.min,
                        children: [
                          Icon(Icons.visibility_rounded, color: _mint, size: 13),
                          SizedBox(width: 4),
                          Text(
                            'VER PC',
                            style: TextStyle(
                              fontFamily: 'ShareTechMono',
                              color: _mint,
                              fontSize: 10,
                              fontWeight: FontWeight.bold,
                            ),
                          ),
                        ],
                      ),
                    ),
                  ),
                ],
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _MiniToggleChip extends StatelessWidget {
  final String label;
  final bool checked;
  final VoidCallback onTap;

  const _MiniToggleChip({
    required this.label,
    required this.checked,
    required this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    const mint = Color(0xFF34F5A0);
    const dim = Color(0xFF968CA5);
    return GestureDetector(
      onTap: onTap,
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 4),
        decoration: BoxDecoration(
          color: const Color(0xFF161022),
          border: Border.all(
            color: checked ? mint : const Color(0x38FFFFFF),
          ),
        ),
        child: Row(
          children: [
            Container(
              width: 9,
              height: 9,
              decoration: BoxDecoration(
                color: checked ? mint : Colors.transparent,
                border: Border.all(color: checked ? mint : dim),
              ),
            ),
            const SizedBox(width: 5),
            Expanded(
              child: Text(
                label,
                maxLines: 1,
                overflow: TextOverflow.ellipsis,
                style: TextStyle(
                  fontFamily: 'ShareTechMono',
                  color: checked ? Colors.white : dim,
                  fontSize: 9.5,
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

