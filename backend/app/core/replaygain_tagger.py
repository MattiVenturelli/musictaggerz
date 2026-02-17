import os
from typing import Optional

from mutagen.flac import FLAC
from mutagen.mp3 import MP3
from mutagen.mp4 import MP4, MP4FreeForm
from mutagen.oggvorbis import OggVorbis
from mutagen.oggopus import OggOpus
from mutagen.id3 import TXXX

from app.utils.logger import log


def write_replaygain(
    filepath: str,
    track_gain: str,
    track_peak: str,
    album_gain: str,
    album_peak: str,
) -> bool:
    """Write ReplayGain tags to an audio file. Does NOT clear() existing tags."""
    ext = os.path.splitext(filepath)[1].lower()
    try:
        if ext == ".flac":
            return _write_flac_rg(filepath, track_gain, track_peak, album_gain, album_peak)
        elif ext == ".mp3":
            return _write_mp3_rg(filepath, track_gain, track_peak, album_gain, album_peak)
        elif ext in (".m4a", ".mp4"):
            return _write_mp4_rg(filepath, track_gain, track_peak, album_gain, album_peak)
        elif ext == ".ogg":
            return _write_ogg_rg(filepath, track_gain, track_peak, album_gain, album_peak)
        elif ext == ".opus":
            return _write_opus_rg(filepath, track_gain, track_peak, album_gain, album_peak)
        else:
            log.warning(f"write_replaygain: unsupported format {filepath}")
            return False
    except Exception as e:
        log.error(f"Error writing ReplayGain to {filepath}: {e}")
        return False


# ─── FLAC (Vorbis comments) ──────────────────────────────────────

def _write_flac_rg(filepath: str, tg: str, tp: str, ag: str, ap: str) -> bool:
    audio = FLAC(filepath)
    audio["REPLAYGAIN_TRACK_GAIN"] = tg
    audio["REPLAYGAIN_TRACK_PEAK"] = tp
    audio["REPLAYGAIN_ALBUM_GAIN"] = ag
    audio["REPLAYGAIN_ALBUM_PEAK"] = ap
    audio.save()
    return True


# ─── OGG Vorbis (Vorbis comments) ────────────────────────────────

def _write_ogg_rg(filepath: str, tg: str, tp: str, ag: str, ap: str) -> bool:
    audio = OggVorbis(filepath)
    audio["REPLAYGAIN_TRACK_GAIN"] = tg
    audio["REPLAYGAIN_TRACK_PEAK"] = tp
    audio["REPLAYGAIN_ALBUM_GAIN"] = ag
    audio["REPLAYGAIN_ALBUM_PEAK"] = ap
    audio.save()
    return True


# ─── Opus (R128 tags with -23 LUFS reference, Q7.8 format) ───────

def _write_opus_rg(filepath: str, tg: str, tp: str, ag: str, ap: str) -> bool:
    """Opus uses R128_TRACK_GAIN and R128_ALBUM_GAIN in Q7.8 fixed point (1/256 dB).
    Reference is -23 LUFS for Opus (vs -18 LUFS for standard ReplayGain).
    """
    audio = OggOpus(filepath)

    # Convert from standard ReplayGain dB string to R128 Q7.8 int
    # R128 reference is -23 LUFS, standard RG reference is configurable (default -18)
    # Adjustment: r128_gain = (rg_gain + (rg_ref - (-23))) * 256
    from app.config import settings
    ref_offset = settings.replaygain_reference_loudness - (-23.0)

    tg_db = _parse_gain_db(tg)
    ag_db = _parse_gain_db(ag)

    if tg_db is not None:
        r128_track = int(round((tg_db + ref_offset) * 256))
        audio["R128_TRACK_GAIN"] = str(r128_track)

    if ag_db is not None:
        r128_album = int(round((ag_db + ref_offset) * 256))
        audio["R128_ALBUM_GAIN"] = str(r128_album)

    audio.save()
    return True


def _parse_gain_db(gain_str: str) -> Optional[float]:
    """Parse '+3.04 dB' or '-1.50 dB' to float."""
    if not gain_str:
        return None
    try:
        return float(gain_str.replace("dB", "").strip())
    except (ValueError, TypeError):
        return None


# ─── MP3 (TXXX frames) ──────────────────────────────────────────

def _write_mp3_rg(filepath: str, tg: str, tp: str, ag: str, ap: str) -> bool:
    audio = MP3(filepath)
    if audio.tags is None:
        audio.add_tags()

    # Remove existing RG TXXX frames
    for desc in ("replaygain_track_gain", "replaygain_track_peak",
                 "replaygain_album_gain", "replaygain_album_peak"):
        key = f"TXXX:{desc}"
        if key in audio.tags:
            del audio.tags[key]

    audio.tags.add(TXXX(encoding=3, desc="replaygain_track_gain", text=tg))
    audio.tags.add(TXXX(encoding=3, desc="replaygain_track_peak", text=tp))
    audio.tags.add(TXXX(encoding=3, desc="replaygain_album_gain", text=ag))
    audio.tags.add(TXXX(encoding=3, desc="replaygain_album_peak", text=ap))

    audio.save()
    return True


# ─── MP4 / M4A (freeform atoms) ─────────────────────────────────

def _write_mp4_rg(filepath: str, tg: str, tp: str, ag: str, ap: str) -> bool:
    audio = MP4(filepath)
    prefix = "----:com.apple.iTunes:"
    audio[f"{prefix}replaygain_track_gain"] = [MP4FreeForm(tg.encode("utf-8"))]
    audio[f"{prefix}replaygain_track_peak"] = [MP4FreeForm(tp.encode("utf-8"))]
    audio[f"{prefix}replaygain_album_gain"] = [MP4FreeForm(ag.encode("utf-8"))]
    audio[f"{prefix}replaygain_album_peak"] = [MP4FreeForm(ap.encode("utf-8"))]
    audio.save()
    return True
