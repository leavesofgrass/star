"""Voice picker, pronunciation/abbreviation rules, speed presets, profiles.

Methods of StarApp, split out of the former monolithic star/tui.py.
Mixed into StarApp in app.py; calls other groups via ``self``.
"""
from .._runtime import *  # noqa: F401,F403
from ..stats import _apply_profile_values, _delete_profile, _save_profile


class VoiceMixin:

    # ── Speed presets ───────────────────────────────────────────────────

    def _set_speed_preset(self, name: str) -> None:
        """Apply a named speed preset or a raw wpm integer."""
        name = (name or "").strip()
        if not name:
            presets = self.settings.get("speed_presets", {})
            lines = "  ".join(f"{k}={v}wpm" for k, v in presets.items())
            self.notify(
                f"Current: {self.settings['tts_rate']} wpm  |  {lines}", dur=6.0
            )
            return
        if name.isdigit():
            wpm = max(50, min(600, int(name)))
            self.tts.set_rate(wpm)
            self.notify(f"Speed: {wpm} wpm")
            return
        presets = self.settings.get("speed_presets", {})
        if name in presets:
            wpm = int(presets[name])
            self.tts.set_rate(wpm)
            self.notify(f"Speed preset “{name}”: {wpm} wpm")
        else:
            self.notify(
                f"Unknown preset “{name}”.  Known: {', '.join(presets)}",
                error=True,
            )

    def _preset_add(self, name: str) -> None:
        """Save the current TTS rate under *name* as a new speed preset."""
        name = (name or "").strip()
        if not name:
            self.notify("Usage: preset-add <name>", error=True)
            return
        wpm = int(self.settings["tts_rate"])
        presets = dict(self.settings.get("speed_presets", {}))
        presets[name] = wpm
        self.settings.set("speed_presets", presets)
        self.notify(f"Preset “{name}” saved: {wpm} wpm")

    def _preset_list(self) -> None:
        """Show all speed presets in the status bar."""
        presets = self.settings.get("speed_presets", {})
        if not presets:
            self.notify("No speed presets defined")
            return
        parts = [
            f"{k}: {v} wpm" for k, v in sorted(presets.items(), key=lambda x: x[1])
        ]
        self.notify("Presets — " + "  |  ".join(parts), dur=7.0)

    def _cycle_speed_preset(self) -> None:
        """Cycle through speed presets in ascending WPM order (F8)."""
        presets = self.settings.get("speed_presets", {})
        if not presets:
            self.notify("No speed presets defined")
            return
        ordered = sorted(presets.items(), key=lambda x: x[1])
        cur_rate = int(self.settings["tts_rate"])
        nxt = ordered[0]
        for name, wpm in ordered:
            if wpm > cur_rate:
                nxt = (name, wpm)
                break
        self.tts.set_rate(nxt[1])
        self.notify(f"Speed: “{nxt[0]}” — {nxt[1]} wpm")

    # ── Voice picker ───────────────────────────────────────────────────

    def _voice_picker(self) -> None:
        """Open an interactive voice-selection minibuffer.

        Voice *names* are used as the completion source so the user never
        has to type or copy a raw Windows registry path.  Substring search
        is used (type \"zira\" to find \"Microsoft Zira Desktop\").
        Pressing Enter applies the voice and speaks a brief test phrase.
        """
        voices = self.tts.list_voices()
        if not voices:
            self.notify(
                "No voices found. Is pyttsx3 installed and the backend set to pyttsx3?",
                error=True,
            )
            return

        # Build display strings and a lookup from display name → voice dict.
        # Append the language tag for clarity; deduplicate if names collide.
        name_map: Dict[str, Dict[str, str]] = {}
        ordered: List[str] = []
        for v in voices:
            name = v.get("name", v.get("id", "Unknown"))
            lang = v.get("lang", "")
            display = f"{name}  [{lang}]" if lang else name
            key, n = display, 1
            while key in name_map:
                n += 1
                key = f"{display} ({n})"
            ordered.append(key)
            name_map[key] = v

        # Pre-fill the current voice name so the user sees their selection.
        current_id = str(self.settings.get("tts_voice", ""))
        initial = ""
        for key, v in name_map.items():
            if v.get("id") == current_id:
                initial = key
                break

        def on_select(chosen: str) -> None:
            chosen = chosen.strip()
            match = name_map.get(chosen)
            if not match:
                # Fuzzy: first case-insensitive substring hit
                low = chosen.lower()
                for key, v in name_map.items():
                    if low in key.lower():
                        match = v
                        break
            if not match:
                self.notify(f"Voice not found: {chosen!r}", error=True)
                return
            self._apply_voice(match.get("id", ""), match.get("name", chosen))

        self._enter_minibuffer(
            "Voice (Tab to browse, type to filter): ",
            initial=initial,
            on_commit=on_select,
            completions=ordered,
        )

    def _apply_voice(self, voice_id: str, voice_name: str = "") -> None:
        """Apply *voice_id* to the active backend, persist it, and speak a
        brief confirmation phrase so the user can immediately hear the change."""
        self.tts._backend.set_voice(voice_id)
        self.settings.set("tts_voice", voice_id)
        label = voice_name or voice_id or "system default"
        self.notify(f"Voice: {label}")
        # Stop any current speech then speak a one-line test so the user
        # can hear the new voice without pressing Space.
        self.tts.stop()
        self.tts._backend.speak(f"Voice changed to {label}.")

    # ── Abbreviation helpers ───────────────────────────────────────────────

    def _abbrev_add(self, arg: str) -> None:
        """Add or update a custom abbreviation expansion.
        Usage:  abbrev-add <abbrev.> <expansion words>
        Example: abbrev-add RCT randomized controlled trial
        """
        parts = arg.strip().split(None, 1)
        if len(parts) < 2:
            self.notify(
                "Usage: abbrev-add <abbreviation> <expansion>   "
                "e.g.  abbrev-add RCT randomized controlled trial",
                error=True,
            )
            return
        abbr, expansion = parts[0], parts[1].strip()
        custom = dict(self.settings.get("abbrev_expansions") or {})
        custom[abbr] = expansion
        self.settings.set("abbrev_expansions", custom)
        self.notify(f"Abbreviation saved: {abbr!r} \u2192 {expansion!r}")

    def _abbrev_list(self) -> None:
        """Show all active custom abbreviation expansions."""
        custom = self.settings.get("abbrev_expansions") or {}
        if not custom:
            self.notify("No custom abbreviations defined.  Use abbrev-add to add one.")
            return
        pairs = "  |  ".join(f"{k} → {v}" for k, v in sorted(custom.items()))
        self.notify(f"Custom abbreviations: {pairs}", dur=8.0)

    # ── Pronunciation lexicon helpers ────────────────────────────────────

    def _pron_add(self, arg: str) -> None:
        """Add or update a pronunciation override.
        Usage:  pron-add <term> <spoken form>
        Example: pron-add Xa cept zah-sept
        """
        parts = arg.strip().split(None, 1)
        if len(parts) < 2:
            self.notify(
                "Usage: pron-add <term> <spoken form>   "
                "e.g.  pron-add CHF congestive heart failure",
                error=True,
            )
            return
        term, spoken = parts[0], parts[1].strip()
        lex = dict(self.settings.get("pronunciations") or {})
        lex[term] = spoken
        self.settings.set("pronunciations", lex)
        self.notify(f"Pronunciation saved: {term!r} → {spoken!r}")

    def _pron_remove(self, term: str) -> None:
        """Remove a pronunciation override by term."""
        term = term.strip()
        lex = dict(self.settings.get("pronunciations") or {})
        if term in lex:
            del lex[term]
            self.settings.set("pronunciations", lex)
            self.notify(f"Pronunciation removed: {term!r}")
        else:
            self.notify(f"No pronunciation for {term!r}.", error=True)

    def _pron_list(self) -> None:
        """Show all pronunciation overrides."""
        lex = self.settings.get("pronunciations") or {}
        if not lex:
            self.notify("No pronunciations defined.  Use pron-add to add one.")
            return
        pairs = "  |  ".join(f"{k} → {v}" for k, v in sorted(lex.items()))
        self.notify(f"Pronunciations: {pairs}", dur=8.0)

    # ── Voice & profile presets ──────────────────────────────────────────

    def _apply_loaded_settings(self) -> None:
        """Re-apply runtime state after a profile's values were written to
        settings (theme colors, TTS backend / voice / rate / volume)."""
        self.theme_name = self.settings.get("theme", self.theme_name)
        self._init_colors()
        try:
            self.tts.change_backend(str(self.settings.get("tts_backend", "auto")))
            voice = str(self.settings.get("tts_voice", ""))
            if voice:
                self.tts._backend.set_voice(voice)
            self.tts.set_rate(int(self.settings.get("tts_rate", 265)))
            self.tts.set_volume(float(self.settings.get("tts_volume", 1.0)))
        except Exception:
            pass

    def _profile_save(self, name: str) -> None:
        """Save the current settings as a named profile (M-x profile-save)."""
        if not _save_profile(self.settings, name):
            self.notify("Usage: profile-save <name>", error=True)
            return
        self.notify(f"Profile saved: {name.strip()!r}")

    def _profile_load(self, name: str) -> None:
        """Apply a saved profile (M-x profile-load <name>)."""
        name = name.strip()
        profiles = self.settings.get("profiles", {}) or {}
        if not name:
            if profiles:
                self.notify("Profiles: " + ", ".join(sorted(profiles)), dur=8.0)
            else:
                self.notify("No profiles saved.  Use profile-save <name>.")
            return
        if _apply_profile_values(self.settings, name) is None:
            self.notify(f"No profile named {name!r}.", error=True)
            return
        self._apply_loaded_settings()
        self.notify(f"Profile loaded: {name!r}")

    def _profile_list(self) -> None:
        """List saved profiles."""
        profiles = self.settings.get("profiles", {}) or {}
        if not profiles:
            self.notify("No profiles saved.  Use profile-save <name>.")
            return
        self.notify("Profiles: " + ", ".join(sorted(profiles)), dur=8.0)

    def _profile_delete(self, name: str) -> None:
        """Delete a saved profile."""
        name = name.strip()
        if _delete_profile(self.settings, name):
            self.notify(f"Profile deleted: {name!r}")
        else:
            self.notify(f"No profile named {name!r}.", error=True)
