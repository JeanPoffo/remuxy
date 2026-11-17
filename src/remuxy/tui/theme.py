"""Look of the terminal UI: color palette, Textual theme, app stylesheet and how log lines are colored."""
import re

from textual.theme import Theme

# palette (also used by the logo and install.sh)
BG, PANEL, LINE, TEXT, DIM = "#1b1c2b", "#22233a", "#3b3d58", "#d4d5e3", "#6d7092"
LILAC, LILAC_DK, ORANGE, RED, GREEN, BLUE = "#c3a6ff", "#2c2a4a", "#e0884f", "#e86d6d", "#8fd19e", "#4c8dff"

THEME = Theme(name="remuxy", dark=True, primary=LILAC, secondary=ORANGE, accent=ORANGE, foreground=TEXT,
              background=BG, surface=PANEL, panel=LILAC_DK, boost=PANEL, error=RED, success=GREEN,
              warning=ORANGE, variables={"block-cursor-background": LILAC, "block-cursor-foreground": BG,
                                         "block-cursor-blurred-background": LILAC_DK,
                                         "footer-key-foreground": ORANGE, "footer-background": "#2a2c45",
                                         "scrollbar": LINE, "scrollbar-hover": LILAC, "scrollbar-active": ORANGE,
                                         "scrollbar-background": BG, "border": ORANGE, "border-blurred": LINE})

# lines printed by remux/ffmpeg -> style in the log (first match wins)
LOG_STYLES = [
    (re.compile(r"ALERT|ERROR|failed|Traceback|Interrupted|\bError\b|(?<!median )\berror\b(?! [+-]\d)"), f"bold {RED}"),
    (re.compile(r"WARNING|AMBIGUOUS|inconclusive"), ORANGE),
    (re.compile(r"^OK|OK \(|agree|-> OK"), GREEN),
    (re.compile(r"^== |^\[auto-sync\]"), f"bold {LILAC}"),
    (re.compile(r"^\$ "), DIM),
]
# ffmpeg status line ("size=... time=00:01:02.03 ... speed=12.3x")
FF_TIME = re.compile(r"time=\s*(-?\d+):(\d+):(\d+(?:\.\d+)?)")
FF_STAT = re.compile(r"^\s*(size|frame)=")
FF_SPEED = re.compile(r"speed=\s*([\d.]+)x")

APP_CSS = f"""
Screen {{ background: {BG}; color: {TEXT}; }}
#topbar {{ height: 1; padding: 0 2; margin-top: 1; }}
#brand {{ width: auto; color: {ORANGE}; }}
#tab {{ width: auto; background: {LILAC}; color: {BG}; text-style: bold; padding: 0 1; margin-left: 2; }}
#tab2 {{ width: auto; color: {DIM}; padding: 0 1; }}
#instance {{ width: 1fr; content-align: right middle; color: {DIM}; }}

.box {{ border: round {LINE}; border-title-color: {DIM}; border-subtitle-color: {DIM};
        background: {BG}; padding: 0 1; }}
.box:focus-within {{ border: round {ORANGE}; border-title-color: {ORANGE}; border-subtitle-color: {ORANGE}; }}

#main {{ height: 14; margin: 1 1 0 1; }}
#left {{ width: 3fr; height: 100%; margin-right: 1; }}
#files {{ height: 1fr; padding: 1 1 0 1; }}
#opts {{ width: 2fr; height: 100%; }}

.row {{ height: 1; }}
.lbl {{ width: 9; color: {DIM}; }}
.path {{ width: 1fr; }}
.info {{ height: 1; padding-left: 9; margin-bottom: 1; }}

Input {{ height: 1; border: none; background: {PANEL}; color: {TEXT}; padding: 0 1; }}
Input:focus {{ border: none; background: {LILAC_DK}; }}
Input > .input--placeholder {{ color: {DIM}; }}
Input > .input--cursor {{ background: {LILAC}; color: {BG}; }}
Input > .input--selection {{ background: {LILAC} 40%; }}
Input.-invalid {{ border: none; background: #3a2230; }}

Select {{ width: 1fr; height: 1; }}
Select > SelectCurrent {{ height: 1; border: none; background: {PANEL}; color: {TEXT}; padding: 0 1; }}
Select:focus > SelectCurrent {{ border: none; background: {LILAC_DK}; color: {LILAC}; }}
Select > SelectCurrent Static#label {{ color: {TEXT}; }}
Select > SelectCurrent .arrow {{ color: {LILAC}; }}
Select > SelectOverlay {{ background: {PANEL}; border: round {LILAC}; color: {TEXT}; }}
Select > SelectOverlay > .option-list--option-highlighted {{ background: {LILAC_DK}; color: {LILAC}; }}

Checkbox {{ background: {BG}; border: none; padding: 0; height: 1; color: {TEXT}; }}
Checkbox:focus {{ border: none; background: {BG}; }}
Checkbox > .toggle--button {{ background: {PANEL}; color: {PANEL}; }}
Checkbox.-on > .toggle--button {{ background: {LILAC}; color: {BG}; }}
Checkbox:focus > .toggle--label {{ background: {LILAC_DK}; color: {LILAC}; }}

#opts-scroll {{ height: 1fr; scrollbar-size-vertical: 1; scrollbar-color: {LINE};
               scrollbar-color-hover: {LILAC}; scrollbar-background: {BG}; }}
.sec {{ color: {LILAC}; text-style: bold; margin-top: 1; width: 1fr; }}
.sec-first {{ margin-top: 0; }}
.opt {{ height: 1; margin-bottom: 0; }}
.opt-l {{ width: 13; color: {DIM}; }}
.opt Input {{ width: 1fr; }}
.checks {{ height: auto; }}
.checks > Vertical {{ width: 1fr; height: auto; }}

#actions {{ height: 1; margin-top: 1; }}
Button {{ min-width: 10; width: auto; height: 1; margin-right: 2; border: none; padding: 0 2;
          background: {PANEL}; color: {TEXT}; }}
Button:hover {{ background: {LINE}; }}
Button:focus {{ text-style: bold; background: {LILAC_DK}; color: {LILAC}; }}
#start {{ background: {LILAC}; color: {BG}; text-style: bold; }}
#start:hover, #start:focus {{ background: #d9c7ff; color: {BG}; }}
#cancel {{ color: {RED}; }}
Button:disabled {{ background: {PANEL} 50%; color: {LINE}; text-style: none; }}
#actions-hint {{ width: 1fr; content-align: right middle; color: {DIM}; }}
Button.pick {{ min-width: 3; width: 3; padding: 0; margin: 0 0 0 1; background: {PANEL}; color: {LILAC}; }}
Button.pick:focus {{ background: {LILAC}; color: {BG}; }}

#progress-box {{ height: 5; margin: 1 1 0 1; padding: 0 1; }}
#status {{ height: 1; }}
#phase {{ width: 1fr; }}
#eta {{ width: auto; }}
ProgressBar {{ width: 100%; height: 1; margin-top: 1; }}
ProgressBar > Horizontal {{ width: 100%; }}
Bar {{ width: 1fr; }}
Bar > .bar--bar {{ color: {ORANGE}; background: {PANEL}; }}
Bar > .bar--complete {{ color: {GREEN}; background: {PANEL}; }}
Bar > .bar--indeterminate {{ color: {LILAC}; background: {PANEL}; }}
PercentageStatus {{ width: 7; color: {LILAC}; text-style: bold; content-align: right middle; }}
ETAStatus {{ display: none; }}

#log-box {{ height: 1fr; margin: 1 1 0 1; padding: 0; }}
RichLog {{ background: {BG}; color: {TEXT}; padding: 0 1; scrollbar-size-vertical: 1;
          scrollbar-color: {LINE}; scrollbar-color-hover: {LILAC}; scrollbar-background: {BG}; }}

Footer {{ background: #2a2c45; color: {DIM}; }}
Footer > FooterKey {{ background: #2a2c45; }}
Footer > FooterKey .footer-key--key {{ background: #2a2c45; color: {ORANGE}; }}
Footer > FooterKey .footer-key--description {{ color: {TEXT}; }}
Footer > FooterKey:hover {{ background: {LINE}; }}

PickFile {{ align: center middle; background: {BG} 60%; }}
#picker {{ width: 90%; height: 85%; border: round {ORANGE}; background: {BG}; padding: 0 1; }}
#picker-title {{ color: {ORANGE}; text-style: bold; }}
#picker-dir {{ color: {LILAC}; margin-bottom: 1; }}
#picker-name {{ margin-top: 1; }}
#picker-help {{ color: {DIM}; margin-top: 1; }}
DirectoryTree {{ background: {BG}; height: 1fr; scrollbar-size-vertical: 1;
                scrollbar-color: {LINE}; scrollbar-background: {BG}; }}
DirectoryTree > .tree--cursor {{ background: {LILAC_DK}; color: {LILAC}; text-style: bold; }}
DirectoryTree:focus > .tree--cursor {{ background: {LILAC}; color: {BG}; }}
DirectoryTree > .directory-tree--folder {{ color: {LILAC}; }}
DirectoryTree > .directory-tree--extension {{ color: {ORANGE}; }}
DirectoryTree > .tree--guides, DirectoryTree > .tree--guides-hover {{ color: {LINE}; }}
DirectoryTree > .tree--guides-selected {{ color: {ORANGE}; }}
"""
