import os
from typing import Optional

from mutagen.flac import FLAC
from mutagen.mp3 import MP3
from mutagen.mp4 import MP4, MP4FreeForm
from mutagen.oggvorbis import OggVorbis
from mutagen.oggopus import OggOpus
from mutagen.id3 import USLT, TXXX

from app.utils.logger import log


def write_lyrics(filepath: str, plain: Optional[str], synced: Optional[str]) -> bool:
    """Write lyrics to an audio file. Does NOT clear() — only adds/overwrites lyrics fields."""
    ext = os.path.splitext(filepath)[1].lower()
    try:
        if ext == ".flac":
            return _write_flac_lyrics(filepath, plain, synced)
        elif ext == ".mp3":
            return _write_mp3_lyrics(filepath, plain, synced)
        elif ext in (".m4a", ".mp4"):
            return _write_mp4_lyrics(filepath, plain, synced)
        elif ext in (".ogg", ".opus"):
            return _write_ogg_lyrics(filepath, plain, synced)
        else:
            log.warning(f"write_lyrics: unsupported format {filepath}")
            return False
    except Exception as e:
        log.error(f"Error writing lyrics to {filepath}: {e}")
        return False


def read_lyrics(filepath: str) -> tuple[Optional[str], Optional[str]]:
    """Read lyrics from an audio file. Returns (plain, synced)."""
    ext = os.path.splitext(filepath)[1].lower()
    try:
        if ext == ".flac":
            return _read_flac_lyrics(filepath)
        elif ext == ".mp3":
            return _read_mp3_lyrics(filepath)
        elif ext in (".m4a", ".mp4"):
            return _read_mp4_lyrics(filepath)
        elif ext in (".ogg", ".opus"):
            return _read_ogg_lyrics(filepath)
        else:
            return None, None
    except Exception as e:
        log.error(f"Error reading lyrics from {filepath}: {e}")
        return None, None


# ─── FLAC / OGG (Vorbis comments) ────────────────────────────────

def _write_flac_lyrics(filepath: str, plain: Optional[str], synced: Optional[str]) -> bool:
    audio = FLAC(filepath)
    if plain:
        audio["LYRICS"] = plain
    if synced:
        audio["SYNCEDLYRICS"] = synced
    audio.save()
    return True


def _read_flac_lyrics(filepath: str) -> tuple[Optional[str], Optional[str]]:
    audio = FLAC(filepath)
    plain = audio.get("LYRICS")
    synced = audio.get("SYNCEDLYRICS")
    return (plain[0] if plain else None, synced[0] if synced else None)


def _write_ogg_lyrics(filepath: str, plain: Optional[str], synced: Optional[str]) -> bool:
    ext = os.path.splitext(filepath)[1].lower()
    audio = OggOpus(filepath) if ext == ".opus" else OggVorbis(filepath)
    if plain:
        audio["LYRICS"] = plain
    if synced:
        audio["SYNCEDLYRICS"] = synced
    audio.save()
    return True


def _read_ogg_lyrics(filepath: str) -> tuple[Optional[str], Optional[str]]:
    ext = os.path.splitext(filepath)[1].lower()
    audio = OggOpus(filepath) if ext == ".opus" else OggVorbis(filepath)
    plain = audio.get("LYRICS")
    synced = audio.get("SYNCEDLYRICS")
    return (plain[0] if plain else None, synced[0] if synced else None)


# ─── MP3 (ID3) ──────────────────────────────────────────────────

def _write_mp3_lyrics(filepath: str, plain: Optional[str], synced: Optional[str]) -> bool:
    audio = MP3(filepath)
    if audio.tags is None:
        audio.add_tags()

    # Remove existing lyrics frames
    audio.tags.delall("USLT")
    for key in list(audio.tags.keys()):
        if key.startswith("TXXX:SYNCEDLYRICS"):
            del audio.tags[key]

    if plain:
        audio.tags.add(USLT(encoding=3, lang="eng", desc="", text=plain))
    if synced:
        audio.tags.add(TXXX(encoding=3, desc="SYNCEDLYRICS", text=synced))

    audio.save()
    return True


def _read_mp3_lyrics(filepath: str) -> tuple[Optional[str], Optional[str]]:
    audio = MP3(filepath)
    if not audio.tags:
        return None, None

    plain = None
    uslt_frames = audio.tags.getall("USLT")
    if uslt_frames:
        plain = str(uslt_frames[0])

    synced = None
    txxx = audio.tags.get("TXXX:SYNCEDLYRICS")
    if txxx:
        synced = str(txxx)

    return plain, synced


# ─── MP4 / M4A ──────────────────────────────────────────────────

def _write_mp4_lyrics(filepath: str, plain: Optional[str], synced: Optional[str]) -> bool:
    audio = MP4(filepath)
    # Prefer synced lyrics in the standard lyrics atom, fallback to plain
    text = synced or plain
    if text:
        audio["\xa9lyr"] = [text]
    audio.save()
    return True


def _read_mp4_lyrics(filepath: str) -> tuple[Optional[str], Optional[str]]:
    audio = MP4(filepath)
    lyr = audio.get("\xa9lyr")
    if not lyr:
        return None, None
    text = str(lyr[0])
    # If it looks like synced lyrics (has timestamps), return as synced
    if text and "[" in text and "]" in text and ":" in text:
        return None, text
    return text, None
