"""Shared constants: standard frame rates, container/codec rules and the auto-sync envelope resolution."""
from fractions import Fraction

# Standard frame rates; a reported fps is snapped to the nearest one (or treated as unknown).
STD_FPS = [Fraction(24000, 1001), Fraction(24), Fraction(25), Fraction(30000, 1001),
           Fraction(30), Fraction(50), Fraction(60000, 1001), Fraction(60)]
# Film speeds assumed for a side whose real speed is unknown (audio-only source, VFR...).
FILM = [Fraction(24000, 1001), Fraction(24), Fraction(25)]

# Formats without a reliable time index: estimated duration and inaccurate seeking -> decode the whole track.
SLOW_SEEK = {".mp3", ".mp2", ".mpa", ".aac", ".adts", ".ac3", ".eac3", ".ec3", ".dts", ".thd", ".mlp"}
# MPEG-PS (DVD VOB): subtitle streams show up late and timestamps may be missing.
MPEG_PS = {".vob", ".mpg", ".mpeg", ".m2p"}

# Codecs Matroska does not accept by stream copy, and what they become (lossless).
NO_COPY = {"pcm_dvd": "flac", "pcm_bluray": "flac"}
IMAGE_SUBS = {"dvd_subtitle", "hdmv_pgs_subtitle", "dvb_subtitle"}
# Subtitles Matroska accepts by copy / that can be converted to SRT; anything else is left out.
SUB_COPY = IMAGE_SUBS | {"subrip", "srt", "ass", "ssa", "webvtt", "hdmv_text_subtitle"}
SUB_TEXT = {"mov_text", "text"}
# Track flags preserved when only "default" is removed.
KEEP_FLAGS = ("dub", "original", "comment", "lyrics", "karaoke", "forced", "hearing_impaired",
              "visual_impaired", "clean_effects", "captions", "descriptions")

# --codec auto copies the track without re-encoding when it already is one of these (Direct Play on Samsung/LG TVs).
AUTO_COPY = {"aac", "ac3", "eac3"}
# When --codec copy has to fall back to re-encoding, keep the source's codec family.
SAME_CODEC = {"ac3": "ac3", "eac3": "eac3", "aac": "aac", "flac": "flac"}
LAYOUT = {1: "mono", 2: "stereo", 6: "5.1", 8: "7.1"}

# Auto-sync: audio is decoded at ENV_SR Hz and reduced to ENV_HZ envelope points per second.
ENV_SR, ENV_HZ = 4000, 200
# Layouts with a center channel (where dialogue lives). To compare a dub with the original audio, what both
# share is music/effects in the side channels, so the center channel is left out.
CENTER = {"3.0", "3.1", "4.0", "4.1", "5.0", "5.0(side)", "5.1", "5.1(side)", "6.0", "6.1", "6.1(back)",
          "7.0", "7.0(front)", "7.1", "7.1(wide)", "7.1(wide-side)", "hexagonal", "octagonal"}

# Post-mux verification: residual error (seconds) still considered imperceptible (~1 frame at 25 fps).
VERIFY_TOLERANCE = 0.040
