import math
import re
import subprocess
from dataclasses import dataclass, field
from typing import Optional

from app.config import settings
from app.utils.logger import log


@dataclass
class TrackLoudness:
    filepath: str
    integrated_loudness: float  # LUFS
    true_peak_db: float  # dBFS
    gain: str = ""   # formatted e.g. "+3.04 dB"
    peak: str = ""   # formatted e.g. "0.988553"


@dataclass
class AlbumReplayGain:
    album_gain: str = ""
    album_peak: str = ""
    tracks: dict[str, TrackLoudness] = field(default_factory=dict)


def format_gain(gain_db: float) -> str:
    """Format gain value as '+3.04 dB' or '-1.50 dB'."""
    return f"{gain_db:+.2f} dB"


def format_peak(peak_linear: float) -> str:
    """Format peak as linear value e.g. '0.988553'."""
    return f"{peak_linear:.6f}"


def analyze_track(filepath: str) -> Optional[TrackLoudness]:
    """Analyze a single audio file using ffmpeg ebur128 filter."""
    try:
        result = subprocess.run(
            [
                "ffmpeg", "-i", filepath,
                "-af", "ebur128=peak=true",
                "-f", "null", "-"
            ],
            capture_output=True,
            text=True,
            timeout=120,
        )
        stderr = result.stderr

        # Parse integrated loudness: "I:         -14.5 LUFS"
        i_match = re.search(r'I:\s+([-\d.]+)\s+LUFS', stderr)
        if not i_match:
            log.warning(f"Could not parse integrated loudness from ffmpeg output for {filepath}")
            return None
        integrated = float(i_match.group(1))

        # Parse true peak: "Peak:\s+(-?\d+\.?\d*)\s+dBFS" (from the Summary section)
        # The summary section has "True peak:" followed by the value
        peak_match = re.search(r'True peak:\s*\n\s*Peak:\s+([-\d.]+)\s+dBFS', stderr)
        if not peak_match:
            # Fallback: try simpler pattern
            peak_match = re.search(r'Peak:\s+([-\d.]+)\s+dBFS', stderr)
        if not peak_match:
            log.warning(f"Could not parse true peak from ffmpeg output for {filepath}")
            return None
        true_peak_db = float(peak_match.group(1))

        reference = settings.replaygain_reference_loudness
        gain_db = reference - integrated
        peak_linear = 10 ** (true_peak_db / 20)

        return TrackLoudness(
            filepath=filepath,
            integrated_loudness=integrated,
            true_peak_db=true_peak_db,
            gain=format_gain(gain_db),
            peak=format_peak(peak_linear),
        )

    except subprocess.TimeoutExpired:
        log.error(f"ffmpeg timed out analyzing {filepath}")
        return None
    except Exception as e:
        log.error(f"Error analyzing {filepath}: {e}")
        return None


def analyze_album(filepaths: list[str]) -> Optional[AlbumReplayGain]:
    """Analyze all tracks and compute album-level ReplayGain."""
    if not filepaths:
        return None

    tracks: dict[str, TrackLoudness] = {}
    for fp in filepaths:
        tl = analyze_track(fp)
        if tl:
            tracks[fp] = tl

    if not tracks:
        return None

    # Album gain = reference - weighted mean loudness
    # Using energy-based mean: 10 * log10(mean(10^(L/10)))
    reference = settings.replaygain_reference_loudness
    energies = [10 ** (t.integrated_loudness / 10) for t in tracks.values()]
    mean_energy = sum(energies) / len(energies)
    mean_loudness = 10 * math.log10(mean_energy) if mean_energy > 0 else -70.0
    album_gain_db = reference - mean_loudness

    # Album peak = max of all track peaks
    album_peak_linear = max(10 ** (t.true_peak_db / 20) for t in tracks.values())

    return AlbumReplayGain(
        album_gain=format_gain(album_gain_db),
        album_peak=format_peak(album_peak_linear),
        tracks=tracks,
    )
