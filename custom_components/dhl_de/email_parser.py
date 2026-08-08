"""Email parser for Deutsche Post Briefankündigung."""

from __future__ import annotations

import base64
import logging
import re
from dataclasses import dataclass
from datetime import datetime, timedelta
from email import policy
from email.message import EmailMessage
from email.parser import BytesParser
from typing import Any
from urllib.parse import unquote

from PIL import Image

_LOGGER = logging.getLogger(__name__)


@dataclass(slots=True)
class MailItem:
    """Parsed mail announcement item."""

    id: str
    sender: str | None
    subject: str
    date: datetime
    images: list[bytes]  # Base64 decoded image data
    has_large_image: bool
    raw_email: EmailMessage


# Sender patterns for Deutsche Post Briefankündigung
BRIEF_SENDERS = [
    "ankuendigung@brief.deutschepost.de",
    "noreply@brief.deutschepost.de",
    "briefankuendigung@deutschepost.de",
]

# Subject patterns
BRIEF_SUBJECTS = [
    "briefankündigung",
    "briefankundigung",
    "ein brief ist unterwegs zu ihnen",
    "ihre briefankündigung",
]

# Image size thresholds (ignore small logos/icons)
MIN_IMAGE_WIDTH = 150
MIN_IMAGE_HEIGHT = 100


def is_briefankuendigung_email(email: EmailMessage) -> bool:
    """Check if email is a Briefankündigung."""
    from_addr = email.get("From", "").lower()
    subject = email.get("Subject", "").lower()

    # Check sender
    sender_match = any(sender in from_addr for sender in BRIEF_SENDERS)

    # Check subject
    subject_match = any(subj in subject for subj in BRIEF_SUBJECTS)

    return sender_match or subject_match


def extract_images_from_email(email: EmailMessage) -> list[bytes]:
    """Extract inline base64 images from email."""
    images = []

    def process_part(part: EmailMessage) -> None:
        content_type = part.get_content_type()
        content_disposition = part.get("Content-Disposition", "").lower()

        # Skip non-image parts
        if not content_type.startswith("image/"):
            return

        # Check if inline (not attachment)
        if "attachment" in content_disposition:
            return

        # Get payload
        payload = part.get_payload(decode=True)
        if not payload:
            return

        # Check if base64 encoded
        try:
            # Try to decode as base64 first
            decoded = base64.b64decode(payload)
        except Exception:
            # Not base64, use as-is
            decoded = payload

        # Validate image size
        if _is_valid_image(decoded):
            images.append(decoded)

    if email.is_multipart():
        for part in email.walk():
            process_part(part)
    else:
        process_part(email)

    return images


def _is_valid_image(image_data: bytes) -> bool:
    """Check if image meets minimum size requirements."""
    try:
        with Image.open(io.BytesIO(image_data)) as img:
            width, height = img.size
            return width >= MIN_IMAGE_WIDTH and height >= MIN_IMAGE_HEIGHT
    except Exception:
        return False


def parse_briefankuendigung_email(raw_email: bytes | EmailMessage) -> MailItem | None:
    """Parse a Briefankündigung email and extract images."""
    if isinstance(raw_email, bytes):
        email = BytesParser(policy=policy.default).parsebytes(raw_email)
    else:
        email = raw_email

    if not is_briefankuendigung_email(email):
        return None

    # Extract images
    images = extract_images_from_email(email)
    has_large_image = len(images) > 0

    # Generate unique ID
    message_id = email.get("Message-ID", "").strip("<>")
    date_str = email.get("Date", "")
    try:
        date = datetime.fromisoformat(date_str.replace(" ", "T"))
    except Exception:
        date = datetime.now()

    item_id = f"{message_id}_{int(date.timestamp())}" if message_id else f"brief_{int(date.timestamp())}"

    # Extract sender name
    from_header = email.get("From", "")
    sender = _extract_sender_name(from_header)

    return MailItem(
        id=item_id,
        sender=sender,
        subject=email.get("Subject", ""),
        date=date,
        images=images,
        has_large_image=has_large_image,
        raw_email=email,
    )


def _extract_sender_name(from_header: str) -> str | None:
    """Extract sender name from From header."""
    # Format: "Name <email@domain>"
    match = re.match(r'^"?([^"<]+)"?\s*<', from_header)
    if match:
        return match.group(1).strip()
    return None


def create_animated_gif(images: list[bytes], duration: int = 500, loop: int = 0) -> bytes | None:
    """Create animated GIF from image bytes."""
    if not images:
        return None

    try:
        pil_images = []
        for img_data in images:
            try:
                img = Image.open(io.BytesIO(img_data))
                # Convert to RGB if needed
                if img.mode in ("RGBA", "LA", "P"):
                    background = Image.new("RGB", img.size, (255, 255, 255))
                    if img.mode == "P":
                        img = img.convert("RGBA")
                    background.paste(img, mask=img.split()[-1] if img.mode in ("RGBA", "LA") else None)
                    img = background
                elif img.mode != "RGB":
                    img = img.convert("RGB")
                pil_images.append(img)
            except Exception as err:
                _LOGGER.warning("Failed to process image: %s", err)
                continue

        if not pil_images:
            return None

        # Save as GIF
        output = io.BytesIO()
        pil_images[0].save(
            output,
            format="GIF",
            save_all=True,
            append_images=pil_images[1:],
            duration=duration,
            loop=loop,
            optimize=True,
        )
        return output.getvalue()

    except Exception as err:
        _LOGGER.error("Failed to create GIF: %s", err)
        return None


def create_image_grid(images: list[bytes], cols: int = 2, padding: int = 10) -> bytes | None:
    """Create image grid from image bytes."""
    if not images:
        return None

    try:
        pil_images = []
        for img_data in images:
            try:
                img = Image.open(io.BytesIO(img_data))
                if img.mode != "RGB":
                    img = img.convert("RGB")
                pil_images.append(img)
            except Exception:
                continue

        if not pil_images:
            return None

        # Calculate grid dimensions
        max_width = max(img.width for img in pil_images)
        max_height = max(img.height for img in pil_images)

        rows = (len(pil_images) + cols - 1) // cols
        grid_width = cols * max_width + (cols + 1) * padding
        grid_height = rows * max_height + (rows + 1) * padding

        grid = Image.new("RGB", (grid_width, grid_height), (255, 255, 255))

        for idx, img in enumerate(pil_images):
            row = idx // cols
            col = idx % cols
            x = padding + col * (max_width + padding)
            y = padding + row * (max_height + padding)
            # Center image in cell
            img_x = x + (max_width - img.width) // 2
            img_y = y + (max_height - img.height) // 2
            grid.paste(img, (img_x, img_y))

        output = io.BytesIO()
        grid.save(output, format="PNG", optimize=True)
        return output.getvalue()

    except Exception as err:
        _LOGGER.error("Failed to create image grid: %s", err)
        return None


# Import io at module level
import io