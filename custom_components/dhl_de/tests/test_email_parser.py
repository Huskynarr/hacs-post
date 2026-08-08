"""Tests for email parser."""

from __future__ import annotations

import base64
from email.message import EmailMessage
from email.mime.image import MIMEImage
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import pytest

from custom_components.dhl_de.email_parser import (
    MailItem,
    create_animated_gif,
    create_image_grid,
    extract_images_from_email,
    is_briefankuendigung_email,
    parse_briefankuendigung_email,
)


def create_test_email(with_images: bool = True) -> EmailMessage:
    """Create a test email."""
    email = MIMEMultipart()
    email["From"] = "Deutsche Post Briefankündigung <ankuendigung@brief.deutschepost.de>"
    email["To"] = "user@example.com"
    email["Subject"] = "Briefankündigung: Ein Brief ist unterwegs zu Ihnen"
    email["Date"] = "Mon, 15 Jan 2024 07:00:00 +0100"
    email["Message-ID"] = "<test123@example.com>"

    # Text part
    text = MIMEText("Ihr Brief kommt morgen an.", "plain")
    email.attach(text)

    if with_images:
        # Create a test image
        from PIL import Image
        import io

        img = Image.new("RGB", (200, 150), color="red")
        img_bytes = io.BytesIO()
        img.save(img_bytes, format="PNG")
        img_bytes = img_bytes.getvalue()

        # Base64 encode
        b64_img = base64.b64encode(img_bytes).decode()

        # Image part
        img_part = MIMEImage(base64.b64decode(b64_img), name="brief.png")
        img_part.add_header("Content-Disposition", "inline")
        img_part.add_header("Content-ID", "<brief1>")
        email.attach(img_part)

    return email


def test_is_briefankuendigung_email_sender():
    """Test detection by sender."""
    email = create_test_email()
    assert is_briefankuendigung_email(email) is True


def test_is_briefankuendigung_email_subject():
    """Test detection by subject."""
    email = create_test_email()
    email["From"] = "other@example.com"
    email["Subject"] = "Briefankündigung für Sie"
    assert is_briefankuendigung_email(email) is True


def test_is_briefankuendigung_email_negative():
    """Test negative detection."""
    email = create_test_email()
    email["From"] = "other@example.com"
    email["Subject"] = "Newsletter"
    assert is_briefankuendigung_email(email) is False


def test_extract_images_from_email():
    """Test image extraction."""
    email = create_test_email()
    images = extract_images_from_email(email)

    assert len(images) == 1
    assert len(images[0]) > 0


def test_extract_images_no_images():
    """Test extraction with no images."""
    email = create_test_email(with_images=False)
    images = extract_images_from_email(email)

    assert len(images) == 0


def test_parse_briefankuendigung_email():
    """Test full email parsing."""
    email = create_test_email()
    item = parse_briefankuendigung_email(email)

    assert item is not None
    assert isinstance(item, MailItem)
    assert item.id is not None
    assert item.sender == "Deutsche Post Briefankündigung"
    assert item.has_large_image is True
    assert len(item.images) == 1


def test_parse_non_brief_email():
    """Test parsing non-Brief email."""
    email = create_test_email()
    email["From"] = "other@example.com"
    email["Subject"] = "Newsletter"

    item = parse_briefankuendigung_email(email)
    assert item is None


def test_create_animated_gif():
    """Test GIF creation."""
    from PIL import Image
    import io

    # Create test images
    images = []
    for color in ["red", "green", "blue"]:
        img = Image.new("RGB", (100, 100), color=color)
        img_bytes = io.BytesIO()
        img.save(img_bytes, format="PNG")
        images.append(img_bytes.getvalue())

    gif = create_animated_gif(images, duration=100)

    assert gif is not None
    assert len(gif) > 0
    assert gif[:6] == b"GIF89a"  # GIF header


def test_create_animated_gif_empty():
    """Test GIF creation with empty list."""
    gif = create_animated_gif([])
    assert gif is None


def test_create_image_grid():
    """Test image grid creation."""
    from PIL import Image
    import io

    images = []
    for color in ["red", "green", "blue", "yellow"]:
        img = Image.new("RGB", (100, 100), color=color)
        img_bytes = io.BytesIO()
        img.save(img_bytes, format="PNG")
        images.append(img_bytes.getvalue())

    grid = create_image_grid(images, cols=2)

    assert grid is not None
    assert len(grid) > 0
    assert grid[:8] == b"\x89PNG\r\n\x1a\n"  # PNG header