import os
from dataclasses import dataclass, field
from typing import Optional, List

from mutagen import File as MutagenFile
from mutagen.flac import FLAC
from mutagen.mp3 import MP3
from mutagen.mp4 import MP4
from mutagen.oggvorbis import OggVorbis
from mutagen.oggopus import OggOpus
from mutagen.id3 import ID3

from app.utils.logger import log

AUDIO_EXTENSIONS = {".flac", ".mp3", ".m4a", ".mp4", ".ogg", ".opus", ".wma"}


@dataclass
class TrackInfo:
    path: str
    title: Optional[str] = None
    artist: Optional[str] = None
    album: Optional[str] = None
    album_artist: Optional[str] = None
    track_number: Optional[int] = None
    disc_number: Optional[int] = None
    year: Optional[int] = None
    genre: Optional[str] = None
    duration: Optional[float] = None
    format: Optional[str] = None
    has_cover: bool = False
    musicbrainz_recording_id: Optional[str] = None
    musicbrainz_release_id: Optional[str] = None


@dataclass
class AlbumInfo:
    path: str
    artist: Optional[str] = None
    album: Optional[str] = None
    year: Optional[int] = None
    tracks: List[TrackInfo] = field(default_factory=list)

    @property
    def track_count(self) -> int:
        return len(self.tracks)


def _safe_int(value) -> Optional[int]:
    if value is None:
        return None
    try:
        s = str(value).split("/")[0].strip()
        return int(s) if s else None
    except (ValueError, TypeError):
        return None


def _safe_str(value) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, list):
        return str(value[0]) if value else None
    return str(value).strip() or None


def _read_flac(filepath: str) -> TrackInfo:
    audio = FLAC(filepath)
    return TrackInfo(
        path=filepath,
        title=_safe_str(audio.get("title")),
        artist=_safe_str(audio.get("artist")),
        album=_safe_str(audio.get("album")),
        album_artist=_safe_str(audio.get("albumartist")),
        track_number=_safe_int(audio.get("tracknumber", [None])[0] if audio.get("tracknumber") else None),
        disc_number=_safe_int(audio.get("discnumber", [None])[0] if audio.get("discnumber") else None),
        year=_safe_int(audio.get("date", [None])[0] if audio.get("date") else None),
        genre=_safe_str(audio.get("genre")),
        duration=audio.info.length if audio.info else None,
        format="FLAC",
        has_cover=len(audio.pictures) > 0,
        musicbrainz_recording_id=_safe_str(audio.get("musicbrainz_trackid")),
        musicbrainz_release_id=_safe_str(audio.get("musicbrainz_albumid")),
    )


def _read_mp3(filepath: str) -> TrackInfo:
    audio = MP3(filepath)
    tags = audio.tags

    title = artist = album = album_artist = genre = None
    track_number = disc_number = year = None
    has_cover = False
    mb_recording_id = mb_release_id = None

    if tags:
        title = _safe_str(tags.get("TIT2"))
        artist = _safe_str(tags.get("TPE1"))
        album = _safe_str(tags.get("TALB"))
        album_artist = _safe_str(tags.get("TPE2"))
        genre = _safe_str(tags.get("TCON"))
        track_number = _safe_int(tags.get("TRCK"))
        disc_number = _safe_int(tags.get("TPOS"))
        year = _safe_int(tags.get("TDRC"))
        has_cover = len(tags.getall("APIC")) > 0
        # MusicBrainz IDs stored as TXXX frames
        txxx_album = tags.get("TXXX:MusicBrainz Album Id")
        if txxx_album:
            mb_release_id = _safe_str(txxx_album)
        txxx_rec = tags.get("TXXX:MusicBrainz Recording Id")
        if txxx_rec:
            mb_recording_id = _safe_str(txxx_rec)

    return TrackInfo(
        path=filepath,
        title=title,
        artist=artist,
        album=album,
        album_artist=album_artist,
        track_number=track_number,
        disc_number=disc_number,
        year=year,
        genre=genre,
        duration=audio.info.length if audio.info else None,
        format="MP3",
        has_cover=has_cover,
        musicbrainz_recording_id=mb_recording_id,
        musicbrainz_release_id=mb_release_id,
    )


def _read_mp4(filepath: str) -> TrackInfo:
    audio = MP4(filepath)

    track_num = None
    disc_num = None
    if audio.get("trkn"):
        track_num = audio["trkn"][0][0]
    if audio.get("disk"):
        disc_num = audio["disk"][0][0]

    # MusicBrainz IDs in freeform atoms (MusicBrainz Picard convention)
    mb_recording_id = None
    mb_release_id = None
    mb_rec_raw = audio.get("----:com.apple.iTunes:MusicBrainz Track Id")
    if mb_rec_raw:
        mb_recording_id = mb_rec_raw[0].decode("utf-8", errors="ignore") if isinstance(mb_rec_raw[0], bytes) else str(mb_rec_raw[0])
    mb_rel_raw = audio.get("----:com.apple.iTunes:MusicBrainz Album Id")
    if mb_rel_raw:
        mb_release_id = mb_rel_raw[0].decode("utf-8", errors="ignore") if isinstance(mb_rel_raw[0], bytes) else str(mb_rel_raw[0])

    return TrackInfo(
        path=filepath,
        title=_safe_str(audio.get("\xa9nam")),
        artist=_safe_str(audio.get("\xa9ART")),
        album=_safe_str(audio.get("\xa9alb")),
        album_artist=_safe_str(audio.get("aART")),
        track_number=track_num,
        disc_number=disc_num,
        year=_safe_int(audio.get("\xa9day", [None])[0] if audio.get("\xa9day") else None),
        genre=_safe_str(audio.get("\xa9gen")),
        duration=audio.info.length if audio.info else None,
        format="M4A",
        has_cover="covr" in audio,
        musicbrainz_recording_id=mb_recording_id,
        musicbrainz_release_id=mb_release_id,
    )


def _read_ogg(filepath: str) -> TrackInfo:
    ext = os.path.splitext(filepath)[1].lower()
    if ext == ".opus":
        audio = OggOpus(filepath)
    else:
        audio = OggVorbis(filepath)

    return TrackInfo(
        path=filepath,
        title=_safe_str(audio.get("title")),
        artist=_safe_str(audio.get("artist")),
        album=_safe_str(audio.get("album")),
        album_artist=_safe_str(audio.get("albumartist")),
        track_number=_safe_int(audio.get("tracknumber", [None])[0] if audio.get("tracknumber") else None),
        disc_number=_safe_int(audio.get("discnumber", [None])[0] if audio.get("discnumber") else None),
        year=_safe_int(audio.get("date", [None])[0] if audio.get("date") else None),
        genre=_safe_str(audio.get("genre")),
        duration=audio.info.length if audio.info else None,
        format="OGG",
        has_cover=False,
        musicbrainz_recording_id=_safe_str(audio.get("musicbrainz_trackid")),
        musicbrainz_release_id=_safe_str(audio.get("musicbrainz_albumid")),
    )


def read_track(filepath: str) -> Optional[TrackInfo]:
    ext = os.path.splitext(filepath)[1].lower()
    try:
        if ext == ".flac":
            return _read_flac(filepath)
        elif ext == ".mp3":
            return _read_mp3(filepath)
        elif ext in (".m4a", ".mp4"):
            return _read_mp4(filepath)
        elif ext in (".ogg", ".opus"):
            return _read_ogg(filepath)
        else:
            log.warning(f"Unsupported format: {filepath}")
            return None
    except Exception as e:
        log.error(f"Error reading {filepath}: {e}")
        return None


def scan_album_folder(folder_path: str) -> Optional[AlbumInfo]:
    if not os.path.isdir(folder_path):
        return None

    tracks: List[TrackInfo] = []
    for filename in sorted(os.listdir(folder_path)):
        ext = os.path.splitext(filename)[1].lower()
        if ext not in AUDIO_EXTENSIONS:
            continue
        filepath = os.path.join(folder_path, filename)
        if not os.path.isfile(filepath):
            continue
        track = read_track(filepath)
        if track:
            tracks.append(track)

    if not tracks:
        return None

    artist = _most_common([t.album_artist or t.artist for t in tracks if t.album_artist or t.artist])
    album = _most_common([t.album for t in tracks if t.album])
    year = _most_common([t.year for t in tracks if t.year])

    return AlbumInfo(
        path=folder_path,
        artist=artist,
        album=album,
        year=year,
        tracks=sorted(tracks, key=lambda t: (t.disc_number or 1, t.track_number or 0)),
    )


def _most_common(values: list):
    if not values:
        return None
    counts = {}
    for v in values:
        counts[v] = counts.get(v, 0) + 1
    return max(counts, key=counts.get)
