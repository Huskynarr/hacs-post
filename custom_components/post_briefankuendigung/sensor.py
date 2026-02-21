"""Sensor platform for Briefankündigung."""
from __future__ import annotations

import logging
import imaplib
import email
from email.header import decode_header
import datetime
from typing import Any

from homeassistant.components.sensor import SensorEntity
from homeassistant.const import (
    CONF_HOST,
    CONF_PORT,
    CONF_USERNAME,
    CONF_PASSWORD,
)

from .const import (
    CONF_FOLDER,
    CONF_SENDER,
    CONF_SUBJECT,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = datetime.timedelta(minutes=15)


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the sensor platform."""
    config = hass.data[DOMAIN].get(config_entry.entry_id)
    if config is None:
        config = dict(config_entry.data)
        config.update(config_entry.options)
    async_add_entities([BriefankuendigungSensor(config, config_entry.entry_id)], True)


class BriefankuendigungSensor(SensorEntity):
    """Representation of a Briefankündigung Sensor."""

    def __init__(self, config: dict[str, Any], entry_id: str):
        """Initialize the sensor."""
        self._config = config
        self._state = 0
        self._attributes = {}
        self._attr_available = True
        self._attr_name = "Briefankündigung"
        self._attr_unique_id = f"{entry_id}_briefankuendigung"
        self._attr_icon = "mdi:email-outline"

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def extra_state_attributes(self):
        """Return the state attributes."""
        return self._attributes

    def update(self):
        """Fetch new state data for the sensor."""
        mail = None
        try:
            # Connect to IMAP
            mail = imaplib.IMAP4_SSL(self._config[CONF_HOST], self._config[CONF_PORT])
            mail.login(self._config[CONF_USERNAME], self._config[CONF_PASSWORD])
            mail.select(self._config[CONF_FOLDER], readonly=True)

            # Format date for IMAP (DD-Mon-YYYY)
            months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
            today = datetime.date.today()
            date_str = f"{today.day}-{months[today.month-1]}-{today.year}"

            sender_filters = _split_filter_values(self._config.get(CONF_SENDER))
            subject_filters = _split_filter_values(self._config.get(CONF_SUBJECT))

            # Search all messages since today and filter sender/subject in Python.
            # This supports multiple sender/subject keywords without IMAP charset issues.
            criteria = f'(SINCE "{date_str}")'

            typ, data = mail.search(None, criteria)

            if typ != "OK":
                raise RuntimeError("Error searching emails")

            email_ids = data[0].split()

            match_count = 0
            subjects = []

            for e_id in email_ids:
                typ, msg_data = mail.fetch(e_id, '(RFC822)')
                for response_part in msg_data:
                    if isinstance(response_part, tuple):
                        msg = email.message_from_bytes(response_part[1])
                        sender = _decode_mime_header(msg.get("From", ""))
                        subject = _decode_mime_header(msg.get("Subject", "No Subject"))

                        if sender_filters and not _contains_any(sender, sender_filters):
                            continue

                        if subject_filters and not _contains_any(subject, subject_filters):
                            continue

                        match_count += 1
                        subjects.append(subject)

            self._state = match_count
            self._attributes["subjects"] = subjects
            self._attributes["applied_sender_filters"] = sender_filters
            self._attributes["applied_subject_filters"] = subject_filters
            self._attributes["last_updated"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
            self._attr_available = True

        except Exception as err:
            _LOGGER.error("Error updating sensor: %s", err)
            self._attr_available = False
        finally:
            if mail is not None:
                try:
                    mail.close()
                except imaplib.IMAP4.error:
                    # Mailbox might not be selected on some failure paths.
                    pass
                except Exception as err:
                    _LOGGER.debug("Error closing IMAP mailbox: %s", err)

                try:
                    mail.logout()
                except Exception as err:
                    _LOGGER.debug("Error logging out from IMAP: %s", err)


def _split_filter_values(value: str | None) -> list[str]:
    """Split a user filter string into values (comma, semicolon or newline separated)."""
    if not value:
        return []

    normalized = value.replace(";", ",").replace("\n", ",")
    return [item.strip() for item in normalized.split(",") if item.strip()]


def _contains_any(text: str, filters: list[str]) -> bool:
    """Return True if text contains at least one filter value."""
    normalized = text.lower()
    return any(item.lower() in normalized for item in filters)


def _decode_mime_header(header_value: str) -> str:
    """Decode MIME encoded header values into a readable string."""
    decoded_list = decode_header(header_value)
    decoded = ""
    for text, encoding in decoded_list:
        if isinstance(text, bytes):
            decoded += text.decode(encoding if encoding else "utf-8", errors="replace")
        else:
            decoded += str(text)
    return decoded
