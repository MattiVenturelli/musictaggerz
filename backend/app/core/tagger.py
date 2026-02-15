import os
from dataclasses import dataclass
from typing import Optional

from mutagen.flac import FLAC, Picture
from mutagen.mp3 import MP3
from mutagen.mp4 import MP4, MP4Cover, MP4FreeForm
from mutagen.oggvorbis import OggVorbis
from mutagen.oggopus import OggOpus
from mutagen.id3 import (
    ID3, TIT2, TPE1, TPE2, TALB, TRCK, TPOS, TDRC, TCON, TPUB,
    TXXX, APIC, ID3NoHeaderError,
)

from app.utils.logger import log


@dataclass
class TagData:
    """Data to write to audio file tags."""
    title: Optional[str] = None
    artist: Optional[str] = None
    album_artist: Optional[str] = None
    album: Optional[str] = None
    track_number: Optional[int] = None
    track_total: Optional[int] = None
    disc_number: Optional[int] = None
    disc_total: Optional[int] = None
    year: Optional[int] = None
    genre: Optional[str] = None
    label: Optional[str] = None
    country: Optional[str] = None
    musicbrainz_release_id: Optional[str] = None
    musicbrainz_recording_id: Optional[str] = None
    cover_data: Optional[bytes] = None
    cover_mime: str = "image/jpeg"


def write_tags(filepath: str, tags: TagData) -> bool:
    """Write tags to an audio file. Returns True on success."""
    ext = os.path.splitext(filepath)[1].lower()
    try:
        if ext == ".flac":
            return _write_flac(filepath, tags)
        elif ext == ".mp3":
            return _write_mp3(filepath, tags)
        elif ext in (".m4a", ".mp4"):
            return _write_mp4(filepath, tags)
        elif ext in (".ogg", ".opus"):
            return _write_ogg(filepath, tags)
        else:
            log.warning(f"Unsupported format for writing: {filepath}")
            return False
    except Exception as e:
        log.error(f"Error writing tags to {filepath}: {e}")
        return False


def _write_flac(filepath: str, tags: TagData) -> bool:
    audio = FLAC(filepath)

    if tags.title is not None:
        audio["title"] = tags.title
    if tags.artist is not None:
        audio["artist"] = tags.artist
    if tags.album_artist is not None:
        audio["albumartist"] = tags.album_artist
    if tags.album is not None:
        audio["album"] = tags.album
    if tags.track_number is not None:
        tn = str(tags.track_number)
        if tags.track_total:
            tn += f"/{tags.track_total}"
        audio["tracknumber"] = tn
    if tags.disc_number is not None:
        dn = str(tags.disc_number)
        if tags.disc_total:
            dn += f"/{tags.disc_total}"
        audio["discnumber"] = dn
    if tags.year is not None:
        audio["date"] = str(tags.year)
    if tags.genre is not None:
        audio["genre"] = tags.genre
    if tags.label is not None:
        audio["label"] = tags.label
        audio["organization"] = tags.label
    if tags.country is not None:
        audio["releasecountry"] = tags.country
    if tags.musicbrainz_release_id is not None:
        audio["musicbrainz_albumid"] = tags.musicbrainz_release_id
    if tags.musicbrainz_recording_id is not None:
        audio["musicbrainz_trackid"] = tags.musicbrainz_recording_id

    if tags.cover_data:
        pic = Picture()
        pic.type = 3  # Front cover
        pic.mime = tags.cover_mime
        pic.desc = "Front"
        pic.data = tags.cover_data
        audio.clear_pictures()
        audio.add_picture(pic)

    audio.save()
    log.debug(f"FLAC tags written: {filepath}")
    return True


def _write_mp3(filepath: str, tags: TagData) -> bool:
    try:
        audio = MP3(filepath)
        if audio.tags is None:
            audio.add_tags()
    except ID3NoHeaderError:
        audio = MP3(filepath)
        audio.add_tags()

    id3 = audio.tags

    if tags.title is not None:
        id3.delall("TIT2")
        id3.add(TIT2(encoding=3, text=tags.title))
    if tags.artist is not None:
        id3.delall("TPE1")
        id3.add(TPE1(encoding=3, text=tags.artist))
    if tags.album_artist is not None:
        id3.delall("TPE2")
        id3.add(TPE2(encoding=3, text=tags.album_artist))
    if tags.album is not None:
        id3.delall("TALB")
        id3.add(TALB(encoding=3, text=tags.album))
    if tags.track_number is not None:
        id3.delall("TRCK")
        tn = str(tags.track_number)
        if tags.track_total:
            tn += f"/{tags.track_total}"
        id3.add(TRCK(encoding=3, text=tn))
    if tags.disc_number is not None:
        id3.delall("TPOS")
        dn = str(tags.disc_number)
        if tags.disc_total:
            dn += f"/{tags.disc_total}"
        id3.add(TPOS(encoding=3, text=dn))
    if tags.year is not None:
        id3.delall("TDRC")
        id3.add(TDRC(encoding=3, text=str(tags.year)))
    if tags.genre is not None:
        id3.delall("TCON")
        id3.add(TCON(encoding=3, text=tags.genre))
    if tags.label is not None:
        id3.delall("TPUB")
        id3.add(TPUB(encoding=3, text=tags.label))
    if tags.country is not None:
        id3.delall("TXXX:MusicBrainz Album Release Country")
        id3.add(TXXX(encoding=3, desc="MusicBrainz Album Release Country", text=tags.country))
    if tags.musicbrainz_release_id is not None:
        id3.delall("TXXX:MusicBrainz Album Id")
        id3.add(TXXX(encoding=3, desc="MusicBrainz Album Id", text=tags.musicbrainz_release_id))
    if tags.musicbrainz_recording_id is not None:
        id3.delall("TXXX:MusicBrainz Recording Id")
        id3.add(TXXX(encoding=3, desc="MusicBrainz Recording Id", text=tags.musicbrainz_recording_id))

    if tags.cover_data:
        id3.delall("APIC")
        id3.add(APIC(
            encoding=3,
            mime=tags.cover_mime,
            type=3,  # Front cover
            desc="Front",
            data=tags.cover_data,
        ))

    audio.save()
    log.debug(f"MP3 tags written: {filepath}")
    return True


def _write_mp4(filepath: str, tags: TagData) -> bool:
    audio = MP4(filepath)

    if tags.title is not None:
        audio["\xa9nam"] = [tags.title]
    if tags.artist is not None:
        audio["\xa9ART"] = [tags.artist]
    if tags.album_artist is not None:
        audio["aART"] = [tags.album_artist]
    if tags.album is not None:
        audio["\xa9alb"] = [tags.album]
    if tags.track_number is not None:
        audio["trkn"] = [(tags.track_number, tags.track_total or 0)]
    if tags.disc_number is not None:
        audio["disk"] = [(tags.disc_number, tags.disc_total or 0)]
    if tags.year is not None:
        audio["\xa9day"] = [str(tags.year)]
    if tags.genre is not None:
        audio["\xa9gen"] = [tags.genre]
    if tags.label is not None:
        audio["----:com.apple.iTunes:LABEL"] = [
            MP4FreeForm(tags.label.encode("utf-8"))
        ]
    if tags.country is not None:
        audio["----:com.apple.iTunes:MusicBrainz Album Release Country"] = [
            MP4FreeForm(tags.country.encode("utf-8"))
        ]
    if tags.musicbrainz_release_id is not None:
        audio["----:com.apple.iTunes:MusicBrainz Album Id"] = [
            MP4FreeForm(tags.musicbrainz_release_id.encode("utf-8"))
        ]
    if tags.musicbrainz_recording_id is not None:
        audio["----:com.apple.iTunes:MusicBrainz Track Id"] = [
            MP4FreeForm(tags.musicbrainz_recording_id.encode("utf-8"))
        ]

    if tags.cover_data:
        fmt = MP4Cover.FORMAT_JPEG
        if tags.cover_mime == "image/png":
            fmt = MP4Cover.FORMAT_PNG
        audio["covr"] = [MP4Cover(tags.cover_data, imageformat=fmt)]

    audio.save()
    log.debug(f"MP4 tags written: {filepath}")
    return True


def _write_ogg(filepath: str, tags: TagData) -> bool:
    ext = os.path.splitext(filepath)[1].lower()
    if ext == ".opus":
        audio = OggOpus(filepath)
    else:
        audio = OggVorbis(filepath)

    if tags.title is not None:
        audio["title"] = tags.title
    if tags.artist is not None:
        audio["artist"] = tags.artist
    if tags.album_artist is not None:
        audio["albumartist"] = tags.album_artist
    if tags.album is not None:
        audio["album"] = tags.album
    if tags.track_number is not None:
        tn = str(tags.track_number)
        if tags.track_total:
            tn += f"/{tags.track_total}"
        audio["tracknumber"] = tn
    if tags.disc_number is not None:
        dn = str(tags.disc_number)
        if tags.disc_total:
            dn += f"/{tags.disc_total}"
        audio["discnumber"] = dn
    if tags.year is not None:
        audio["date"] = str(tags.year)
    if tags.genre is not None:
        audio["genre"] = tags.genre
    if tags.label is not None:
        audio["label"] = tags.label
        audio["organization"] = tags.label
    if tags.country is not None:
        audio["releasecountry"] = tags.country
    if tags.musicbrainz_release_id is not None:
        audio["musicbrainz_albumid"] = tags.musicbrainz_release_id
    if tags.musicbrainz_recording_id is not None:
        audio["musicbrainz_trackid"] = tags.musicbrainz_recording_id

    # OGG cover embedding via METADATA_BLOCK_PICTURE
    if tags.cover_data:
        import base64
        pic = Picture()
        pic.type = 3
        pic.mime = tags.cover_mime
        pic.desc = "Front"
        pic.data = tags.cover_data
        audio["metadata_block_picture"] = base64.b64encode(pic.write()).decode("ascii")

    audio.save()
    log.debug(f"OGG tags written: {filepath}")
    return True
