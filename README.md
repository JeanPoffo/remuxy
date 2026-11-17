<p align="center"><img src="assets/logo.svg" alt="remuxY" width="420"></p>

<div align="center">

[![Version](https://img.shields.io/badge/version-1.0.0-blue.svg)](#)
[![Status](https://img.shields.io/badge/status-active-success.svg)](#)
[![GitHub Issues](https://img.shields.io/github/issues/JeanPoffo/remuxy.svg)](https://github.com/JeanPoffo/remuxy/issues)
[![GitHub Pull Requests](https://img.shields.io/github/issues-pr/JeanPoffo/remuxy.svg)](https://github.com/JeanPoffo/remuxy/pulls)

</div>

<p align="center">Copies the audio track of one movie into another and keeps it in sync: start offsets, fps, duration and drift are checked and corrected.</p>

## 📝 Contents

- [About](#about)
- [Getting started](#getting-started)
- [Usage](#usage): [TUI](#tui) · [CLI](#cli) · [Examples](#examples)
- [How it works](#how-it-works)
- [Troubleshooting](#troubleshooting)
- [Project structure](#structure) · [Built with](#built-using)

## 🧐 About <a name="about"></a>

You have two files of the same movie: the **source** has an audio track you want (e.g. a dub) and the **target** has the picture you want to keep. `remux` adds the source audio to the target as an **extra track**; the target's video, subtitles and original audio are untouched. The source can be a movie (MKV, MP4, VOB...) or an **audio-only file** (mp3, aac, m4a, ac3, eac3, dts, flac, wav, mka...).

Doing it by hand usually ends out of sync, because versions differ in **fps** (23.976 / 24 / 25), **cuts** (studio logos, extra scenes) and container **start offsets**. remuxy measures all of that and corrects it, and lays out the file for **Plex/TV Direct Play** (new track first and default, 48 kHz, proper interleaving; see [Plex/TV compatibility](#plex)).

## 🏁 Getting started <a name="getting-started"></a>

```bash
curl -fsSL https://raw.githubusercontent.com/JeanPoffo/remuxy/main/install.sh | bash
```

Then, in a new terminal:

```bash
remuxy                                            # terminal UI
remux dub.ac3 movie.mkv --auto-sync --verify      # command line
```

The installer:
1. Detects **apt** (Debian, Ubuntu, Mint, Pop!_OS...) or **pacman** (Arch, Manjaro, EndeavourOS...).
2. Installs only what is missing among **ffmpeg** and **pipx** (plus `python3-venv` on Debian/Ubuntu), asking for `sudo` only for this step. If the distro has no pipx package, pipx is installed with pip for your user.
3. Installs remuxy from GitHub with **pipx** in an isolated environment with `textual` and `numpy`, without touching the system Python.
4. Puts `remux` and `remuxy` on PATH (`~/.local/bin`).

Run it as your user, **not with sudo**: that would install the commands into root's account, so the script refuses it.

| Command | What it does |
| --- | --- |
| `curl -fsSL …/install.sh \| bash` | Installs, or updates to the latest version |
| `curl -fsSL …/install.sh \| bash -s -- --uninstall` | Removes remuxy (keeps ffmpeg and pipx) |
| `./install.sh --dev` (in a `git clone`) | Editable install for development: changes in `src/` apply without reinstalling |

**Requirements:** Linux with apt or pacman, Python 3.9+. On other distros, install ffmpeg and pipx yourself and run `pipx install https://github.com/JeanPoffo/remuxy/archive/refs/heads/main.zip`.

## 🎈 Usage <a name="usage"></a>

### Terminal UI (`remuxy`) <a name="tui"></a>

A [Textual](https://github.com/Textualize/textual) front end for `remux`, with a [Bagels](https://github.com/EnhancedJax/Bagels)-inspired palette.

```bash
remuxy                       # empty form
remuxy dub.ac3 movie.mkv     # source and target already filled in
```

- **Files:** source, target and output. `…` (or `^f` / `^g` / `^o`) opens a folder browser that only lists media files. Each file gets a one-line summary (duration, video, audio tracks with language, subtitles); on the source, the audio track that will be copied is highlighted and the others are dimmed.
- **Options:** every `remux` option in three groups (Sync, New track, Measurement). Empty field = `remux` default. `auto-sync`, `verify` and `overwrite` start checked.
- **Start / Dry-run / Cancel:** cancelling stops ffmpeg and deletes the partial file.
- **Progress:** current phase (analysis, auto-sync, remux, verification) and, while muxing, percentage, processed time, ffmpeg speed and time left.
- **Log:** full remux and ffmpeg output; warnings orange, errors red, success green, ffmpeg metadata dimmed. If `--verify` reports more than 40 ms the result shows in orange.

| Key | Action |
| --- | --- |
| `^r` / `^t` / `^k` | Start / Dry-run / Cancel |
| `^f` / `^g` / `^o` | Pick source / target / output |
| `^l` | Clear the log |
| `^q` | Quit (cancels a running remux first) |
| `Tab` / `Shift+Tab` | Move between fields |

### Command line (`remux`) <a name="cli"></a>

```
remux SOURCE TARGET [options]
```

`SOURCE` is where the audio comes from (movie or audio-only file); `TARGET` receives it (video, subtitles, attachments and original audio are kept).

**Output and tracks**

| Option | Default | Description |
| --- | --- | --- |
| `-o`, `--output` | `<target>.synced.mkv` | Output file. Always **Matroska**, so use `.mkv` (another extension triggers a warning). Cannot be an input file. |
| `--audio N` | `0` | Audio track of the **source** (0 = first). |
| `--ref-audio N` | `0` | Audio track of the **target** used as reference by `--auto-sync`/`--verify`. |
| `--append` | off | Puts the new track **after** the originals instead of first and default. |
| `--replace` | off | Removes the target's original audio tracks. |
| `--overwrite` | off | Overwrites the output if it exists. |
| `--dry-run` | off | Only analyzes and prints the ffmpeg command. |

**Timing**

| Option | Default | Description |
| --- | --- | --- |
| `--offset S` | `0.0` | Manual fine adjustment in seconds: positive delays the new audio, negative advances it. Added **on top** of `--auto-sync`. |
| `--speed X` | auto | Forces the speed factor, e.g. `1.04271` for 23.976 → 25 fps, `1.04167` for 24 → 25. |
| `--no-tempo` | off | Disables the automatic speed correction. |
| `--stretch M` | `atempo` | `atempo` keeps the pitch (each instant wobbles ~±15 ms). `resample` changes speed and pitch together (+0.72 semitone for 23.976 → 25, like a real PAL speedup); exact, no artifacts. |

**Measurement**

| Option | Default | Description |
| --- | --- | --- |
| `--auto-sync` | off | Measures the real alignment by audio correlation (delay, speed, drift, cuts). Needs `numpy`; decodes both tracks once (a 1-hour movie took 75 s with `--auto-sync --verify`). |
| `--verify` | off | Measures the residual error of the new audio in the output. Needs `numpy`; not available with `--replace`. Exit code 2 above 40 ms. |
| `--points N` | `12` | Number of measured windows (min. 3). |
| `--window S` | `120` | Maximum window length (s); shrinks by itself on short movies. |
| `--search S` | `30` | Window search ± (s) when the whole-movie correlation finds no clear peak. When it does, the delay has no limit and this barely matters. |
| `--min-score X` | `0.03` | Minimum correlation (0–1) for a window to vote. A correct match on a dub is low (0.1 is normal); the vote decides, not this threshold. |

**New track**

| Option | Default | Description |
| --- | --- | --- |
| `--codec C` | `auto` | `auto`, `aac`, `ac3`, `eac3`, `libopus`, `flac` or `copy`. **auto** copies the track untouched when it already is AAC/AC3/E-AC3 at 48 kHz and there is no speed change, otherwise re-encodes to `aac` (the log says why). **copy** keeps any audio intact (AC3, DTS, TrueHD...) with **any delay** (applied to the timestamps; a trimmed start is cut in whole packets, up to ~32 ms); with a speed change it re-encodes in the source's family (`ac3`, `eac3`, `aac`, `flac`) or else `ac3` (multichannel) / `aac`, and warns. Prefer `aac`/`ac3`/`eac3` for TVs (`libopus`/`flac` may not Direct Play). Channels are kept; only `ac3`/`eac3` cap at 5.1 (7.1 is downmixed **keeping the LFE**). DVD/Blu-ray PCM cannot be copied into MKV and becomes `flac` (lossless). |
| `--sample-rate N` | `48000` | Sample rate when re-encoding; `0` keeps the source's (Opus is always 48 kHz; AC3/E-AC3 only accept 32/44.1/48 kHz). `copy` keeps the source's and warns if it differs. |
| `--bitrate B` | 96k/channel, max 640k | E.g. `192k`, `640k`. Ignored for `flac`. |
| `--lang L` | source's, or `und` | Language code (`por`, `eng`...). |
| `--title T` | source's | Track title. |
| `--default` | auto | Marks the new track as default and clears it on the originals; only matters with `--append`. |
| `--keep-sub-default` | off | Keeps the "default" flag on image subtitles (VOBSUB/PGS). |

Invalid values (negative `--audio`, `--points` < 3, `--min-score` outside 0–1, `--speed` outside 0.5–2, malformed `--bitrate`) are rejected before any work.

### Examples <a name="examples"></a>

```bash
remux dubbed.mkv original.mkv --lang por --title "Português"         # same version, just bring the audio
remux movie_23976.mkv movie_25.mkv --dry-run                          # 23.976 -> 25 fps: check the analysis,
remux movie_23976.mkv movie_25.mkv                                    #   then run (speed fix is automatic)
remux source.mkv target.mkv --auto-sync --verify                      # different cuts/intros (any length)
remux source.mkv target.mkv --offset -1.5                             # audio 1.5 s late in the result -> advance
remux source.mkv target.mkv --audio 2 --codec ac3 --bitrate 640k --replace   # 3rd track, AC3 5.1, replace
remux dub_pt.ac3 movie.mkv --lang por --title "Português 5.1" --codec copy --auto-sync --verify  # audio-only
remux dub_pt.mp3 movie.mkv --auto-sync --verify                       # audio-only, any format
remux dvd_ntsc.mkv dvd_pal.mkv --dry-run                              # NTSC (29.97 pulldown) -> PAL: detection
remux dvd_ntsc.mkv dvd_pal.mkv --auto-sync --verify                   #   is automatic; check it, then run
remux dvd_ntsc.mkv dvd_pal.mkv --stretch resample --auto-sync --verify   # real PAL speedup (pitch changes)
remux source.mkv target.mkv --append                                  # originals first, new one last
remux source.mkv target.mkv --keep-sub-default                        # leave PGS flags as they are

# batch: the loop goes on, and exit code 2 flags the files to check
for f in *.ac3; do remux "$f" "${f%.ac3}.mkv" --auto-sync --verify || echo "CHECK: $f"; done
```

## 💭 How it works <a name="how-it-works"></a>

The audio position in the target is modeled as a line, `t_target = a + b · t_source` (`a` = shift in seconds, `b` = stretch factor). An ffmpeg filter (`atempo` + `adelay`/`atrim` + `apad`/`atrim`) applies it and makes the audio end with the target's video. With `--codec copy` there is no filter: the shift goes straight into the packet timestamps.

**1. Metadata (always).** Reads each file's video/audio `start_time` with `ffprobe`, finds the **real speed** of each side and their ratio `b` (changed with `atempo`, pitch preserved), and computes the initial delay `a + b · audio_start`, then delays (`adelay`) or trims (`atrim`). Same speed but durations more than 0.5 s apart → warns about different cuts.

**Speed detection.** The reported fps lies: an NTSC film DVD reports **29.97** (pulldown) but runs at **23.976**; trusting it would stretch by the wrong factor (0.834x instead of 1.043x in a test). So remuxy lists the possible real speeds of each side, builds the ratios between 0.9x and 1.1x and picks the one matching the **duration** ratio (near ties within 0.15% go by priority, film at 23.976 first).

| Case | Result |
| --- | --- |
| NTSC DVD (29.97 pulldown) → PAL DVD (25) | PAL speedup: 23.976 → 25, audio at 1.04271x |
| Native 29.97 → 25 with the same duration (standards conversion) | No speed change |
| Same fps on both sides | Offset only |
| Audio-only source | Assumes a 23.976/24/25 film and picks by duration ratio |
| Interlaced video reporting the field rate (50 / 59.94 / 60) | Also considers 25 / 23.976–29.97 / 24–30 |
| Unknown or non-standard fps (VFR, mixed telecine) | Deduces the speed from the duration |
| Durations match no known combination | No stretch, warns (probably different cuts) |

Candidates the durations cannot separate (e.g. 23.976 vs 24 fps, 0.1% apart) print `AMBIGUOUS`; confirm with `--auto-sync --verify`.

**Audio-only source.** The reference is the start of the audio itself. Raw formats without a time index (`.mp3`, `.mp2`, `.aac`, `.ac3`, `.eac3`, `.dts`, `.thd`...) may only have a bitrate **estimate** of their duration (a VBR MP3 without a Xing header showed 282.9 s for 303 s of audio), so they are decoded once to measure it exactly; `--auto-sync` reuses that decode.

**2. Measurement (`--auto-sync`).** Both tracks are decoded once and reduced to two curves at 200 points/s: the **energy envelope** and the **attacks** (sudden volume rises). No words are compared, so it works with dubs, where only music and effects match. On 5.1/7.1 only the **side channels** are used (the center holds the dialogue), unless they are near silence (old movies with everything in the center).
1. **Whole movie, per candidate speed** (predicted, none, every 23.976/24/25 combination): the correlation peak gives the delay with **no search limit** and confirms or corrects the speed; the predicted one only loses to a clearly better one.
2. **Windows:** `--points` windows spread over the overlap, around that delay.
3. **Vote:** only what a group of windows agrees on counts (same delay within 60 ms, or the same line if there is drift): at least 3 windows and 40% of them, spanning windows that share no audio. False peaks land at random and do not agree.
4. **Result:** constant delay → shift only; **drift** → speed factor too, windows redone with it compensated; **different cuts** → if the left-out windows agree on *another* delay, it reports which stretch will be off and by how much (one adjustment cannot fix both); **inconclusive** (unrelated audio) → keeps the metadata model and warns.

**3. Verification (`--verify`).** Measures the new audio against the target's original audio in the output, with the same windows and vote, and prints median and max error. Up to ~40 ms (1 frame at 25 fps) is imperceptible; above it prints `ALERT` and **exits with code 2** (useful for batches). With `--offset` the deviation is treated as intentional.

**4. Plex/TV compatibility (always)** <a name="plex"></a>

| Behavior | Why | Change with |
| --- | --- | --- |
| New track is the **1st audio track** and **default** | Plex only Direct Plays the 1st; otherwise it remuxes and may stall on Samsung TVs | `--append` |
| New audio re-encoded at **48 kHz** | Some TVs handle 44.1 kHz and others badly | `--sample-rate` |
| Image subtitles (VOBSUB/PGS) lose "default" ("forced" stays) | Default-on image subs force a full transcode in Plex | `--keep-sub-default` |
| Only the main video is copied; embedded cover art is dropped | ffmpeg would turn MKV cover images into real MJPEG video tracks | auto |
| `mov_text` (MP4) subtitles become SRT; unsupported ones are left out with a warning | Matroska cannot take them by copy and the whole mux would fail | auto |
| DVD/Blu-ray PCM original audio becomes FLAC (lossless) | Matroska cannot take `pcm_dvd`/`pcm_bluray` by copy | auto |
| Chapters and global metadata always come **from the target** | Otherwise ffmpeg would use the source's, with wrong times | auto |
| Removing "default" keeps the other flags (forced, comment...) | Commentary tracks and forced subs stay intact | auto |
| Timestamp gaps in the source audio become silence (`aresample=async=1`) | Otherwise the audio "glues" over the gap and drifts from there on | auto |
| DVD VOB/MPG read with deeper analysis (`-probesize/-analyzeduration 200M`) and `+genpts` | DVD subtitles appear late and timestamps may be missing | auto |
| Audio **interleaved** with the video (`-max_interleave_delta 0`), checked at the end (max distance over the first 300 s, OK up to 2 s) | Otherwise the new audio may sit far behind in the file (37 s of audio only at 24 MB) and small-buffer TVs stall at the start | auto |
| Written to `.<output>.part`, **renamed only when done** | Plex ignores dotfiles, so it never scans a half-written file; a failure or Ctrl-C leaves nothing under the final name | auto |

## 🔧 Troubleshooting <a name="troubleshooting"></a>

- **Run `--dry-run` first:** durations, fps, offsets, warnings and the ffmpeg command (shell-quoted, ready to paste), without writing anything.
- **Only an fps difference?** Metadata is enough and more precise than measuring; `--auto-sync` is for different cuts or unexplained drift.
- **`ALERT: above 40 ms`** (exit code 2): probably out of sync. Run again with `--auto-sync`, or force the speed with `--speed`.
- **Constant ~15–20 ms in `--verify`:** codec delay (a raw `.aac` does not report its ~21 ms encoder delay) or `atempo` wobble. Imperceptible; `--stretch resample` removes the `atempo` part.
- **`AMBIGUOUS: ... 23.976 vs 24 fps`:** run `--auto-sync --verify` (it tests both); if still wrong, use `--speed`.
- **`WARNING: ... different cuts`** (same fps, different durations), or an audio-only source much shorter/longer than the movie (e.g. no credits; it is not stretched): use `--auto-sync` or `--offset`.
- **`WARNING: N windows ... agree on ANOTHER delay`:** the movies have different cuts (an extra scene, say). One adjustment cannot fix it: find another version, or use `--offset` to sync the part that matters most.
- **`inconclusive measurement`:** the tracks may share nothing (another score/mix) or the reference is wrong: check `--ref-audio` (a commentary track will not do) and try `--points 24`.
- **`N windows without a reliable peak were ignored`** on a dub is normal: dialogue-only scenes have nothing in common.
- **`PROBLEM: TVs may stall at the start`** (interleave check): the new audio is more than 2 s away from the video in the file. Remux again; if it persists, open an issue.
- **Memory:** to interleave, ffmpeg buffers packets until every track has one. A very sparse subtitle track (forced-only) grows that buffer (90 MB file: ~156 MB peak vs ~62 MB); very large remuxes may reach a few GB.
- **Run time:** only the new audio is re-encoded (video is copied); `--auto-sync` and `--verify` decode the audio tracks once each.

## 📁 Project structure <a name="structure"></a>

```
remuxy/
├── install.sh              installer (apt/pacman + pipx)
├── pyproject.toml          package metadata and commands
├── assets/                 logo
└── src/remuxy/
    ├── remux.py            `remux` command: orchestrates the steps below
    ├── remuxy.py           `remuxy` command: starts the TUI
    ├── core/               one module per step of `remux`
    │   ├── arguments.py      CLI options and validation
    │   ├── media.py          probed input file (streams, starts, durations, fps)
    │   ├── speed.py          real speeds behind the fps and the speed ratio
    │   ├── prior_model.py    metadata timing model t_target = a + b · t_source
    │   ├── track.py          decoded audio envelopes for correlation
    │   ├── coarse.py         whole-movie correlation per candidate speed
    │   ├── correlation.py    single-window correlation
    │   ├── windows.py        window planning and measurement
    │   ├── consensus.py      window voting
    │   ├── auto_sync.py      --auto-sync
    │   ├── codec.py          output codec / sample rate choice
    │   ├── audio_filter.py   ffmpeg audio filter for the model
    │   ├── mux_command.py    final ffmpeg command
    │   ├── interleave.py     interleave check
    │   ├── verify.py         output check and --verify
    │   └── constants.py, probe.py, process.py
    └── tui/                theme, file summary, file picker and the app screen
```

## ⛏️ Built with <a name="built-using"></a>

- [Python](https://www.python.org/)
- [FFmpeg](https://ffmpeg.org/): probing (`ffprobe`), audio filters (`atempo`, `adelay`, `atrim`, `apad`) and muxing
- [NumPy](https://numpy.org/): FFT cross-correlation and window voting for `--auto-sync`
- [Textual](https://github.com/Textualize/textual): terminal UI
- [pipx](https://pipx.pypa.io/): isolated install of the commands
- [Hatch](https://hatch.pypa.io/): packaging (`hatchling` backend)
