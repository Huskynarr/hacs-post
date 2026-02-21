"""Sensor platform for Briefankündigung."""
import logging
import imaplib
import email
from email.header import decode_header
import datetime

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
)

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = datetime.timedelta(minutes=15)

async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the sensor platform."""
    config = config_entry.data
    async_add_entities([BriefankuendigungSensor(config)], True)

class BriefankuendigungSensor(SensorEntity):
    """Representation of a Briefankündigung Sensor."""

    def __init__(self, config):
        """Initialize the sensor."""
        self._config = config
        self._state = 0
        self._attributes = {}
        self._attr_available = True
        self._attr_name = "Briefankündigung"
        self._attr_unique_id = (
            f"{config[CONF_HOST]}:{config[CONF_USERNAME]}:{config[CONF_FOLDER]}:briefankuendigung"
        ).lower()
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
            
            sender = self._config.get(CONF_SENDER)
            target_subject = self._config.get(CONF_SUBJECT)

            # Search for emails from today and sender
            # Note: We filter by subject in Python to avoid IMAP charset issues
            criteria = f'(SINCE "{date_str}" FROM "{sender}")'
            
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
                        subject_header = msg["Subject"]
                        if subject_header:
                            decoded_list = decode_header(subject_header)
                            subject = ""
                            for text, encoding in decoded_list:
                                if isinstance(text, bytes):
                                    subject += text.decode(encoding if encoding else "utf-8", errors="replace")
                                else:
                                    subject += str(text)
                        else:
                            subject = "No Subject"

                        # Filter by subject if configured
                        if target_subject and target_subject.lower() not in subject.lower():
                            continue

                        match_count += 1
                        subjects.append(subject)

            self._state = match_count
            self._attributes["subjects"] = subjects
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
