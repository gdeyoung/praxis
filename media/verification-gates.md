# Verification-gated media generation

The pattern: **generated media ships only through a quality gate, never directly.** Everyone publishes generation workflows; the gate is what makes them production-grade. Every rule below caught real failures.

## The gate stack

```
script/pre-production ──▶ generation ──▶ verification gate ──▶ human review ──▶ publish
     (human-approved          (TTS, images,        (automated:              (one
      inputs before           video, music)         WER, duration,             glance)
      any spend)                                    silence, format)
```

## Pre-production gates (spend control)

Nothing expensive runs until the cheap human-approved artifacts exist:

- **Hook/title/thumbnail approved before generation.** A 3-option hook brief, a search-optimized title set, a thumbnail concept — reviewed in seconds, before minutes of GPU time and hours of assembly.
- **Narration scripts fact-checked and TTS-normalized before synthesis.** Numbers, names, and claims verified against sources; abbreviations and symbols expanded to their spoken forms (`~200` → "around two hundred"). Most "TTS stumbled" bugs are script bugs.

## The narration loop (zero-stumble audio)

The highest-value gate we run, for any voice-driven video:

1. **Synthesize** narration with a self-hosted TTS engine.
2. **Transcribe it back** with a strong ASR model ([WhisperX](https://github.com/m-bain/whisperX) class).
3. **Compute word error rate** against the script.
4. **Auto-retry** failed segments with slightly perturbed synthesis parameters (different seed/temperature), up to N attempts.
5. Segments that still fail get flagged for a human with the audio inline — not silently shipped.

A generated voice reading wrong numbers with confidence is worse than no video. The round-trip transcription gate costs seconds and catches substitutions, dropped words, and hallucinated digits that human proofreading of a script never would.

## Subtitle constraints (hard-won)

- **4–7 words per caption, ~2.5 seconds on screen.** Longer captions are unreadable at phone size and playback speed 1.5×.
- Captions generated from the *verified* transcript timestamps, not re-timed by hand.
- Burn-in vs. sidecar is a per-platform decision, but the constraint is identical either way.

## Hardware encode across a mixed fleet

Different GPUs, different encoders, one rule: **use the hardware block, verify the output plays.**

| Hardware class | Encoder | Notes |
|---|---|---|
| NVIDIA | NVENC (`h264_nvenc`/`hevc_nvenc`) | Watch for session limits on consumer drivers |
| AMD / APU | VA-API (`h264_vaapi`) | Verify `vaapi` device exists per host — not all drivers expose it |
| CPU fallback | `libx264 -preset medium` | The correctness baseline everything gets diffed against |

Encode verification is more than exit code 0: probe the output (`ffprobe`) for expected duration, resolution, and a nonzero audio stream. A truncated or silent encode with a zero exit code is a real failure class.

## Final-mile review

Finished media lands in a review inbox with two things: an **inline player** (watch without downloading) and the **bare absolute path** (fetch without copying). Small friction reduction, measurably faster review turnaround. Anything that needs a decision ships with a pre-drafted action (`APPROVE`/`REJECT`/`DECIDE`) — review should cost one reply, not a conversation.

## The general principle

Every generation step gets a verifier that measures the failure you actually fear — transcription accuracy for narration, playability for encodes, caption density for subtitles, spec proportions for art. Generation is cheap now; **knowing it's wrong before your audience does** is the moat.
