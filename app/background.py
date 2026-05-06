"""Random background image for the main panel.

Drop any number of ``.jpg`` / ``.jpeg`` / ``.png`` / ``.webp`` / ``.gif``
files into the ``backgrounds/`` directory. On each browser session the
dashboard picks one at random and paints it behind the main content
area. The sidebar keeps its own opaque background so the image only
appears in the main panel.

The selection is cached in ``st.session_state`` so it stays stable
across script reruns (button clicks, cell edits, etc.) — refresh the
browser to roll a new background.
"""

from __future__ import annotations

import base64
import random
from pathlib import Path
from typing import List

import streamlit as st

DEFAULT_DIR = Path("backgrounds")
SUPPORTED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".gif"}
SESSION_KEY = "_background_image_path"

# Toggle key shared with the dashboard's "Hide Background" widget. When
# this flag is True in ``st.session_state``, ``BackgroundImage.apply``
# skips CSS injection so the page falls back to the default theme bg.
HIDE_KEY = "hide_background"

# Black veil sat on top of the background image to *darken* it (rather
# than wash it out). ``0`` shows the raw image; ``1`` hides it completely.
DEFAULT_OVERLAY_OPACITY = 0.55
DEFAULT_OVERLAY_RGB = "0, 0, 0"

# When the image is darkened, page-bg-overlapping text needs a light
# colour to stay readable. Cards (metric containers' children, plotly
# charts, AgGrid) keep their own backgrounds and are unaffected.
DEFAULT_FOREGROUND_COLOR = "#fafafa"

_MIME_BY_EXT = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".webp": "image/webp",
    ".gif": "image/gif",
}


class BackgroundImage:
    """Picks a random image from a directory and injects it as CSS."""

    def __init__(
        self,
        directory: Path | str = DEFAULT_DIR,
        overlay_opacity: float = DEFAULT_OVERLAY_OPACITY,
        overlay_rgb: str = DEFAULT_OVERLAY_RGB,
        foreground_color: str = DEFAULT_FOREGROUND_COLOR,
    ) -> None:
        self.directory = Path(directory)
        # Clamp to [0, 1] in case a caller passes something out of range.
        self.overlay_opacity = max(0.0, min(1.0, float(overlay_opacity)))
        self.overlay_rgb = overlay_rgb
        self.foreground_color = foreground_color

    # ----- Discovery & selection -----------------------------------------

    def list_images(self) -> List[Path]:
        if not self.directory.exists():
            return []
        return sorted(
            p
            for p in self.directory.iterdir()
            if p.is_file() and p.suffix.lower() in SUPPORTED_EXTENSIONS
        )

    def pick(self) -> Path | None:
        """Return a random image path, cached for the browser session."""
        cached = st.session_state.get(SESSION_KEY)
        if cached:
            cached_path = Path(cached)
            if cached_path.exists():
                return cached_path

        images = self.list_images()
        if not images:
            return None

        chosen = random.choice(images)
        st.session_state[SESSION_KEY] = str(chosen)
        return chosen

    # ----- CSS injection --------------------------------------------------

    def apply(self) -> None:
        """Inject CSS to set the chosen image as the main-panel background.

        Targets ``[data-testid="stMain"]`` (Streamlit's main content
        container) with a defensive fallback to ``section.main`` for
        older versions. The sidebar is unaffected because Streamlit
        renders it as a sibling element with its own opaque background.

        A dark overlay (``self.overlay_opacity``) is layered on top of
        the image so the photo reads as a darkened version of itself
        rather than a washed-out one. Page-bg-overlapping text is
        recoloured to ``self.foreground_color`` so headings, metric
        labels, captions and dividers stay readable.

        Honours the ``hide_background`` session-state flag: if the user
        has toggled the dashboard's "Hide Background" switch on, this
        is a no-op and Streamlit's default theme bg shows through.
        """
        if st.session_state.get(HIDE_KEY, False):
            return

        image_path = self.pick()
        if image_path is None:
            return

        encoded = base64.b64encode(image_path.read_bytes()).decode("ascii")
        mime = _MIME_BY_EXT.get(image_path.suffix.lower(), "image/jpeg")
        data_url = f"data:{mime};base64,{encoded}"
        overlay = f"rgba({self.overlay_rgb}, {self.overlay_opacity})"
        fg = self.foreground_color

        css = f"""
        <style>
        [data-testid="stMain"],
        section.main {{
            background-image:
                linear-gradient({overlay}, {overlay}),
                url("{data_url}");
            background-size: cover;
            background-position: center center;
            background-attachment: fixed;
            background-repeat: no-repeat;
        }}

        /* Recolour text drawn directly on the (now-darker) page bg.
           Cards, charts and tables ship with their own opaque
           backgrounds and stay untouched by these selectors. */
        [data-testid="stMain"] :is(h1, h2, h3, h4, h5, h6),
        [data-testid="stMain"] [data-testid="stMetricLabel"],
        [data-testid="stMain"] [data-testid="stMetricLabel"] *,
        [data-testid="stMain"] [data-testid="stMetricValue"],
        [data-testid="stMain"] [data-testid="stMetricValue"] *,
        [data-testid="stMain"] [data-testid="stMetricDelta"],
        [data-testid="stMain"] [data-testid="stMetricDelta"] * {{
            color: {fg} !important;
        }}
        [data-testid="stMain"] hr {{
            border-color: {fg} !important;
            opacity: 0.3;
        }}
        </style>
        """
        st.markdown(css, unsafe_allow_html=True)
