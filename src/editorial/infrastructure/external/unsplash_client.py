"""
UnsplashImageClient — fetches images from Unsplash API.

Provides image search with fallback to solid color + text overlay.
Implements caching to minimize API requests.
"""
import hashlib
import json
import os
from pathlib import Path
from typing import Optional

import httpx

from src.editorial.core.exceptions import StoryGenerationError


class UnsplashImageClient:
    """Client for Unsplash image API with fallback strategy."""

    def __init__(
        self,
        access_key: Optional[str] = None,
        cache_dir: Optional[Path] = None,
        base_url: str = "https://api.unsplash.com",
        transport: Optional[httpx.BaseTransport] = None,
    ):
        """
        Initialize Unsplash client.

        Args:
            access_key: Unsplash API access key (optional, defaults to env var)
            cache_dir: Directory for caching search results
            base_url: Unsplash API base URL
        """
        self.access_key = access_key or os.getenv("UNSPLASH_ACCESS_KEY")
        self.base_url = base_url
        self.cache_dir = cache_dir or Path("data/unsplash_cache")
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        # A held client reuses connections and, in tests, lets a mock
        # transport drive the real request path rather than patching httpx.
        self._client = httpx.Client(timeout=15.0, transport=transport)

    def search_image(self, query: str) -> Optional[str]:
        """
        Search for an image on Unsplash.

        Args:
            query: Search query (e.g., "military radar", "declassified document")

        Returns:
            URL to the image, or None if no results found or API unavailable

        Raises:
            StoryGenerationError: If API request fails
        """
        # Check cache first
        cached_url = self._get_cached_url(query)
        if cached_url:
            return cached_url

        if not self.access_key:
            # No API key: return None to trigger fallback
            return None

        try:
            response = self._client.get(
                f"{self.base_url}/search/photos",
                params={"query": query, "per_page": 1, "orientation": "landscape"},
                headers={"Authorization": f"Client-ID {self.access_key}"},
            )
            response.raise_for_status()

            results = response.json().get("results", [])
            if not results:
                return None

            image_url = results[0]["urls"]["regular"]
            self._cache_url(query, image_url)
            return image_url

        except httpx.HTTPError as error:
            # API error: return None to trigger fallback
            return None

    def download_image(self, url: str, output_path: str) -> None:
        """
        Download an image to output_path.

        Args:
            url: Image URL returned by search_image
            output_path: Path to save the image

        Raises:
            StoryGenerationError: If the download fails
        """
        try:
            response = self._client.get(url, follow_redirects=True)
            response.raise_for_status()
            with open(output_path, "wb") as f:
                f.write(response.content)
        except (httpx.HTTPError, OSError) as error:
            raise StoryGenerationError(f"Failed to download image {url}: {error}") from error

    def create_fallback_image(
        self, text: str, output_path: str, bg_color: str = "#1a1a1a"
    ) -> None:
        """
        Create a fallback image with solid color and text overlay.

        Args:
            text: Text to overlay on image
            output_path: Path to save the image
            bg_color: Background color in hex (default: dark gray)

        Raises:
            StoryGenerationError: If image creation fails
        """
        try:
            from PIL import Image, ImageDraw, ImageFont
        except ImportError:
            raise StoryGenerationError(
                "Pillow required for fallback image creation. Install with: pip install Pillow"
            )

        try:
            # Create image: 1080x1080 (square for social media)
            width, height = 1080, 1080
            image = Image.new("RGB", (width, height), bg_color)
            draw = ImageDraw.Draw(image)

            # Try to use a nice font, fall back to default if not available
            try:
                font = ImageFont.truetype("/System/Library/Fonts/Arial.ttf", 48)
            except (OSError, IOError):
                font = ImageFont.load_default()

            # Wrap text and center it
            wrapped_text = self._wrap_text(text, 40)  # ~40 chars per line
            line_height = 60
            total_height = len(wrapped_text) * line_height
            y = (height - total_height) // 2

            for line in wrapped_text:
                bbox = draw.textbbox((0, 0), line, font=font)
                line_width = bbox[2] - bbox[0]
                x = (width - line_width) // 2
                draw.text((x, y), line, fill="white", font=font)
                y += line_height

            image.save(output_path, "JPEG")
        except Exception as error:
            raise StoryGenerationError(f"Failed to create fallback image: {error}") from error

    def _get_cached_url(self, query: str) -> Optional[str]:
        """Retrieve cached image URL if available."""
        cache_key = hashlib.md5(query.encode()).hexdigest()
        cache_file = self.cache_dir / f"{cache_key}.json"

        if not cache_file.exists():
            return None

        try:
            with open(cache_file) as f:
                data = json.load(f)
            return data.get("url")
        except Exception:
            return None

    def _cache_url(self, query: str, url: str) -> None:
        """Cache image URL for future queries."""
        cache_key = hashlib.md5(query.encode()).hexdigest()
        cache_file = self.cache_dir / f"{cache_key}.json"

        try:
            with open(cache_file, "w") as f:
                json.dump({"query": query, "url": url}, f)
        except Exception:
            pass  # Ignore cache write failures

    @staticmethod
    def _wrap_text(text: str, width: int) -> list[str]:
        """Wrap text to fit in a given character width."""
        words = text.split()
        lines = []
        current_line = []

        for word in words:
            if sum(len(w) for w in current_line) + len(current_line) + len(word) <= width:
                current_line.append(word)
            else:
                if current_line:
                    lines.append(" ".join(current_line))
                current_line = [word]

        if current_line:
            lines.append(" ".join(current_line))

        return lines
