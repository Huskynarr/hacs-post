"""Deutsche Post Briefankündigung shipper for Mail and Packages compatible parsing."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.core import HomeAssistant

from ...email_parser import MailItem, is_briefankuendigung_email, parse_briefankuendigung_email

_LOGGER = logging.getLogger(__name__)


class PostDEShipper:
    """Shipper for Deutsche Post Briefankündigung emails."""

    SENSOR_TYPE = "post_de_mail"
    EMAIL_ADDRESSES = ["ankuendigung@brief.deutschepost.de", "noreply@brief.deutschepost.de"]
    SUBJECT_KEYWORDS = ["briefankündigung", "briefankundigung", "ein brief ist unterwegs"]

    def __init__(self, hass: HomeAssistant, config: dict[str, Any]) -> None:
        """Initialize shipper."""
        self.hass = hass
        self.config = config

    async def async_process_emails(self, emails: list[Any]) -> list[MailItem]:
        """Process emails and extract Briefankündigung items."""
        items = []

        for email in emails:
            if not is_briefankuendigung_email(email):
                continue

            item = parse_briefankuendigung_email(email)
            if item and item.has_large_image:
                items.append(item)

        return items

    def get_sensor_data(self, items: list[MailItem]) -> dict[str, Any]:
        """Convert items to sensor data format."""
        return {
            "count": len(items),
            "items": [
                {
                    "id": item.id,
                    "sender": item.sender,
                    "subject": item.subject,
                    "date": item.date.isoformat(),
                    "has_images": item.has_large_image,
                    "image_count": len(item.images),
                }
                for item in items
            ],
        }