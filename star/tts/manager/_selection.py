"""SelectionMixin — active-backend and default/language voice resolution.

Carved verbatim from the former ``star/tts/manager.py`` module.  All backend
selection and voice-resolution logic is unchanged; only the enclosing class was
split into cooperating mixins assembled by ``manager/__init__.py``.
"""
from ..._runtime import *  # noqa: F401,F403
from ..base import TTSBackend
from ..silent import SilentBackend

# Spelled-out language names → ISO-639-1, for engines (e.g. macOS ``say``,
# eSpeak) that put the language in the voice *name*/``id`` rather than a ``lang``
# tag.  Kept to the five UI languages star ships plus common near-synonyms; the
# lookup is a plain substring test so entries must be distinctive words.
_LANG_NAME_TO_CODE: Dict[str, str] = {
    "english": "en",
    "spanish": "es",
    "español": "es",
    "castilian": "es",
    "french": "fr",
    "français": "fr",
    "german": "de",
    "deutsch": "de",
    "portuguese": "pt",
    "português": "pt",
}


class SelectionMixin:
    """Active-backend selection and default/UI-language voice resolution."""

    def _select_backend(self, preference: str) -> None:
        """Pick the active backend from the plugin registry.

        Backend classes are discovered via the ``star.backends`` entry-points
        (built-ins and any installed third-party plugins) and walked in
        ``priority`` order.  An explicit *preference* tries only the engines
        registered under that name — ``"espeak"`` and ``"dectalk"`` each map to
        two implementations (in-process then CLI), tried in priority order.
        ``"auto"`` walks every auto-eligible engine and takes the first that
        reports itself available; everything falls back to :class:`SilentBackend`.
        """
        from ...plugins import PluginRegistry

        rate = int(self._settings["tts_rate"])
        vol = float(self._settings["tts_volume"])

        classes = sorted(PluginRegistry.get().backends, key=lambda c: c.priority)

        chosen: Optional[TTSBackend] = None
        if preference and preference != "auto":
            # Explicit engine: try only the implementations registered under
            # this name, lowest priority first (e.g. libespeak-ng before the
            # eSpeak CLI; DECtalk.dll before the say/dtalk CLI).
            for cls in classes:
                if cls.name != preference:
                    continue
                cand = self._construct_backend(cls)
                if cand.available():
                    chosen = cand
                    break
        else:
            # Auto: walk every auto-eligible engine in priority order.  The
            # bundled DECtalk.dll ("Perfect Paul") sorts first, then pyttsx3,
            # the macOS `say` voice (ranked above eSpeak so a Mac never falls to
            # the robotic eSpeak voice), eSpeak, Festival, and the DECtalk CLI.
            for cls in classes:
                if cls.name in self._AUTO_SKIP:
                    continue
                cand = self._construct_backend(cls)
                if cand.available():
                    chosen = cand
                    break

        self._backend = chosen or SilentBackend()
        self._backend.set_rate(rate)
        self._backend.set_volume(vol)
        self._resolve_default_voice()
        self._resolve_language_voice()

    def _construct_backend(self, cls: "type[TTSBackend]") -> TTSBackend:
        """Instantiate *cls* with the per-engine constructor arguments derived
        from settings.  Engines that share a ``name`` (eSpeak's and DECtalk's two
        implementations each) take identical arguments, so keying on ``name`` is
        safe.  Unknown / third-party backends are tried with the common
        ``(rate, volume, voice)`` signature, then with no arguments.
        """
        rate = int(self._settings["tts_rate"])
        vol = float(self._settings["tts_volume"])
        voice = str(self._settings["tts_voice"])
        name = cls.name
        if name == "espeak":
            return cls(rate=rate, voice=voice or "en-us")
        if name == "dectalk":
            return cls(rate=rate, voice=voice)
        if name == "piper":
            # A `tts_voice` ending in .onnx wins; otherwise the dedicated
            # `piper_model` setting supplies the model path.
            piper_voice = (
                voice
                if voice.lower().endswith(".onnx")
                else str(self._settings.get("piper_model", ""))
            )
            return cls(rate=rate, volume=vol, voice=piper_voice)
        try:
            return cls(rate=rate, volume=vol, voice=voice)
        except TypeError:
            return cls()

    def _resolve_default_voice(self) -> None:
        """Pick a sensible default voice when the user hasn't chosen one.

        When ``tts_voice`` is empty, prefer a voice whose name contains the
        ``tts_prefer_voice`` substring (default ``"eloquence"``), favoring a
        US-English variant.  This makes the bundled Eloquence voices the
        default on macOS while leaving the engine default untouched when no
        match is found.  The user's explicit voice choice always wins.
        """
        if str(self._settings.get("tts_voice", "")):
            return  # user has an explicit voice; never override it
        prefer = str(self._settings.get("tts_prefer_voice", "")).strip().lower()
        if not prefer:
            return
        try:
            voices = self._backend.list_voices()
        except Exception:
            voices = []
        if not voices:
            return
        matches = [
            v
            for v in voices
            if prefer in (v.get("name", "") + " " + v.get("id", "")).lower()
        ]
        if not matches:
            return
        # Favor a US-English variant of the preferred voice family.
        best = next(
            (m for m in matches if "us" in str(m.get("lang", "")).lower()),
            matches[0],
        )
        vid = best.get("id") or best.get("name")
        if vid:
            self._backend.set_voice(vid)

    @staticmethod
    def _voice_lang(voice: Dict[str, str]) -> str:
        """Return a voice's language as a lowercase ISO-639-1 prefix.

        Backends report ``lang`` inconsistently — ``"es"``, ``"es_ES"``,
        ``"es-ES"``, ``"Spanish (Spain)"``, or sometimes only baked into the
        voice *name*/``id`` (``"english-us"``, ``"spanish"``).  We normalise to
        the leading two-letter code so an equality test against the UI-language
        code (also ISO-639-1) is meaningful, falling back to a small
        English-name → code map for engines that spell the language out.
        """
        lang = str(voice.get("lang", "")).strip().lower()
        if lang:
            # "es_ES" / "es-ES" / "es" → "es"; ignore anything non-alphabetic.
            head = lang.replace("-", "_").split("_", 1)[0]
            if len(head) >= 2 and head[:2].isalpha():
                return head[:2]
        # No usable lang tag — sniff the human-readable name/id for a language
        # word (covers eSpeak's "english-us" ids and macOS's spelled-out names).
        blob = (str(voice.get("name", "")) + " " + str(voice.get("id", ""))).lower()
        for word, code in _LANG_NAME_TO_CODE.items():
            if word in blob:
                return code
        return ""

    def _resolve_language_voice(self) -> None:
        """Bias the default voice toward one that speaks the UI language.

        Preference order, applied only when the user has **not** pinned an
        explicit ``tts_voice`` and the active backend enumerates voices:

        1. a voice whose language matches :attr:`_pref_lang` (the UI language);
        2. otherwise leave whatever :meth:`_resolve_default_voice` chose (which
           already favours the bundled English default) — i.e. English, then
           the platform/engine default.

        This is deliberately conservative: with no UI-language preference, or
        no matching voice, nothing changes, so English/mono-lingual setups keep
        their existing behaviour.  The user's explicit voice choice always wins.
        """
        if not self._pref_lang or self._pref_lang == "en":
            return  # English or no preference → default resolution already fits
        if str(self._settings.get("tts_voice", "")):
            return  # explicit user voice; never override it
        try:
            voices = self._backend.list_voices()
        except Exception:
            voices = []
        if not voices:
            return
        matches = [v for v in voices if self._voice_lang(v) == self._pref_lang]
        if not matches:
            return  # no voice speaks the UI language → keep the English default
        best = matches[0]
        vid = best.get("id") or best.get("name")
        if vid:
            self._backend.set_voice(vid)

    def set_language(self, code: str) -> None:
        """Set the preferred spoken-language tag and re-resolve the voice.

        *code* is an ISO-639-1 UI-language code (``"es"``, ``"fr"`` …); ``"en"``
        or an empty string clears the preference (English / platform default).
        Safe to call at any time — it only changes the *default* voice and only
        when the user has not pinned one; a mid-speech call takes effect on the
        next utterance, not the current one.
        """
        raw = str(code or "").strip().lower()
        self._pref_lang = "" if raw in ("", "en") else raw
        self._resolve_language_voice()

    @property
    def preferred_language(self) -> str:
        """The active spoken-language preference (``""`` = English/default)."""
        return self._pref_lang
