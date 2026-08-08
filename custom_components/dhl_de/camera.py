"""Camera platform for Deutsche Post Briefankündigung."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from homeassistant.components.camera import Camera, CameraEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CAMERA_MAIL, DOMAIN, ICON_CAMERA
from .coordinator import BriefankundigungCoordinator, BriefankundigungData
from .device import get_briefankuendigung_device_info
from .email_parser import create_animated_gif

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up camera."""
    coordinator: BriefankundigungCoordinator = entry.runtime_data.mail_coordinator

    camera = DhlMailCamera(coordinator, entry)
    async_add_entities([camera])


class DhlMailCamera(CoordinatorEntity[BriefankundigungCoordinator], Camera):
    """Camera for Briefankündigung mail images."""

    _attr_has_entity_name = True
    _attr_name = "Briefankündigung Camera"

    def __init__(
        self,
        coordinator: BriefankundigungCoordinator,
        entry: ConfigEntry,
    ) -> None:
        """Initialize camera."""
        super().__init__(coordinator)
        Camera.__init__(self)
        self._entry = entry
        self._attr_unique_id = f"{entry.entry_id}_{CAMERA_MAIL}"
        self._attr_device_info = get_briefankuendigung_device_info(entry.entry_id, entry.data.get("email", ""))
        self._attr_icon = ICON_CAMERA
        self._last_image: bytes | None = None
        self._last_update: datetime | None = None

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return self.coordinator.last_update_success

    async def async_camera_image(
        self,
        width: int | None = None,
        height: int | None = None,
    ) -> bytes | None:
        """Return camera image."""
        # Generate animated GIF from today's mail images
        data: BriefankundigungData = self.coordinator.data

        all_images = []
        for mail in data.mails:
            all_images.extend(mail.images)

        if not all_images:
            # Return placeholder
            return await self._get_placeholder_image()

        # Create animated GIF
        gif_data = create_animated_gif(all_images, duration=3000)

        if gif_data:
            self._last_image = gif_data
            self._last_update = datetime.now()
            return gif_data

        return self._last_image

    async def _get_placeholder_image(self) -> bytes:
        """Get placeholder image."""
        # Check for custom image
        custom_path = self._entry.options.get("custom_image_file")
        if custom_path:
            try:
                import aiofiles
                async with aiofiles.open(custom_path, "rb") as f:
                    return await f.read()
            except Exception:
                pass

        # Default placeholder - simple gray image with text
        from PIL import Image, ImageDraw, ImageFont
        import io

        img = Image.new("RGB", (400, 300), (240, 240, 240))
        draw = ImageDraw.Draw(img)

        try:
            font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 24)
        except Exception:
            font = ImageFont.load_default()

        text = "Keine Briefankündigungen heute"
        bbox = draw.textbbox((0, 0), text, font=font)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]

        draw.text(
            ((400 - text_width) // 2, (300 - text_height) // 2),
            text,
            fill=(128, 128, 128),
            font=font,
        )

        output = io.BytesIO()
        img.save(output, format="PNG")
        return output.getvalue()

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra state attributes."""
        data: BriefankundigungData = self.coordinator.data
        return {
            "mail_count": data.today_count,
            "last_update": self._last_update.isoformat() if self._last_update else None,
            "mails": [
                {
                    "id": mail.id,
                    "sender": mail.sender,
                    "subject": mail.subject,
                    "date": mail.date.isoformat(),
                    "has_images": mail.has_large_image,
                }
                for mail in data.mails
            ],
        }