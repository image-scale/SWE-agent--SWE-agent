from __future__ import annotations

import base64
import logging
import re
from typing import Any
from urllib.parse import urlparse

import requests
from pydantic import BaseModel, PrivateAttr

logger = logging.getLogger(__name__)

MAX_IMAGE_SIZE = 10 * 1024 * 1024  # 10MB limit


class ProblemStatement:
    """Base class for problem statements."""

    id: str = ""
    type: str = "base"

    def get_problem_statement(self) -> str:
        raise NotImplementedError


class EmptyProblemStatement(ProblemStatement):
    """Empty problem statement."""

    type: str = "empty"

    def get_problem_statement(self) -> str:
        return ""


class TextProblemStatement(BaseModel):
    """Problem statement from plain text."""

    text: str
    id: str = ""
    type: str = "text"

    def get_problem_statement(self) -> str:
        return self.text


class GithubIssue(BaseModel):
    """Problem statement from a GitHub issue."""

    github_url: str
    id: str = ""
    type: str = "github"

    def get_problem_statement(self) -> str:
        raise NotImplementedError


class SWEBenchMultimodalProblemStatement(BaseModel):
    """Multimodal problem statement for SWE-bench."""

    text: str
    issue_images: list[str] = []
    id: str = ""
    type: str = "swe_bench_multimodal"
    _cached_statement: str | None = PrivateAttr(default=None)

    def get_problem_statement(self) -> str:
        """Get the problem statement, including any images as base64 data URLs."""
        # Return cached result if available
        if self._cached_statement is not None:
            return self._cached_statement

        # Start with the text
        result = self.text

        # Process each image
        for image_url in self.issue_images:
            image_data = self._download_image(image_url)
            if image_data:
                mime_type, b64_data = image_data
                result += f"\n\n![{image_url}](data:{mime_type};base64,{b64_data})"

        # Cache the result
        self._cached_statement = result
        return result

    def _download_image(self, url: str) -> tuple[str, str] | None:
        """Download an image and return (mime_type, base64_data) or None on failure."""
        # Validate URL
        try:
            parsed = urlparse(url)
            if not parsed.scheme or parsed.scheme not in ("http", "https"):
                logger.warning(f"Invalid URL scheme: {url}")
                return None
            if not parsed.netloc:
                logger.warning(f"Invalid URL: {url}")
                return None
        except Exception:
            logger.warning(f"Invalid URL: {url}")
            return None

        try:
            response = requests.get(url, timeout=30)
            response.raise_for_status()

            # Check content type
            content_type = response.headers.get("content-type", "")
            mime_type = content_type.split(";")[0].strip()

            if not mime_type.startswith("image/"):
                logger.warning(f"Invalid MIME type {mime_type} for {url}")
                return None

            # Check content length if available
            content_length = response.headers.get("content-length")
            if content_length and int(content_length) > MAX_IMAGE_SIZE:
                logger.warning(f"Image too large: {content_length} bytes for {url}")
                return None

            # Read the image data
            image_data = b"".join(response.iter_content(chunk_size=8192))

            # Check actual size
            if len(image_data) > MAX_IMAGE_SIZE:
                logger.warning(f"Image too large: {len(image_data)} bytes for {url}")
                return None

            # Base64 encode
            b64_data = base64.b64encode(image_data).decode("utf-8")

            return (mime_type, b64_data)

        except requests.exceptions.RequestException as e:
            logger.warning(f"Failed to download image {url}: {e}")
            return None
