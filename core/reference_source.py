from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path
from urllib.parse import urlparse


class ReferenceSourceResolver:
    def __init__(self, cache_dir: Path = Path("data/reference_cache")):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def resolve(self, source: str | Path) -> Path:
        source_str = str(source).strip()
        if self._looks_like_url(source_str):
            return self._download_url(source_str)

        path = Path(source_str).expanduser()
        if not path.exists():
            raise FileNotFoundError(f"Reference source not found: {path}")
        if path.suffix.lower() != ".wav":
            raise ValueError("Local reference files must currently be WAV.")
        return path

    def _looks_like_url(self, value: str) -> bool:
        parsed = urlparse(value)
        return parsed.scheme in {"http", "https"} and bool(parsed.netloc)

    def _download_url(self, url: str) -> Path:
        yt_dlp = shutil.which("yt-dlp")
        if yt_dlp is None:
            raise RuntimeError(
                "URL references require `yt-dlp` to be installed and available on PATH."
            )

        safe_name = re.sub(r"[^a-zA-Z0-9]+", "-", url)[:80].strip("-") or "reference"
        output_base = self.cache_dir / safe_name
        command = [
            yt_dlp,
            "-x",
            "--audio-format",
            "wav",
            "--no-playlist",
            "-o",
            str(output_base) + ".%(ext)s",
            url,
        ]
        try:
            subprocess.run(command, check=True, capture_output=True, text=True)
        except subprocess.CalledProcessError as exc:
            stderr = exc.stderr.strip()
            raise RuntimeError(f"Failed to fetch reference URL with yt-dlp: {stderr}") from exc

        candidates = sorted(self.cache_dir.glob(f"{safe_name}*.wav"))
        if not candidates:
            raise RuntimeError("yt-dlp completed but no WAV file was produced.")
        return candidates[-1]
