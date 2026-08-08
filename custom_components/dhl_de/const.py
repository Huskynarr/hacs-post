"""Constants for DHL & Deutsche Post integration."""

from __future__ import annotations

from datetime import timedelta
from homeassistant.const import Platform

DOMAIN = "dhl_de"
NAME = "DHL & Deutsche Post"
VERSION = "1.0.0"

# Platforms
PLATFORMS: list[Platform] = [Platform.SENSOR, Platform.CAMERA]

# Defaults
DEFAULT_POLL_INTERVAL = timedelta(minutes=30)
DEFAULT_MAIL_FOLDER = "INBOX"
DEFAULT_MAIL_SENDERS = "ankuendigung@brief.deutschepost.de"
DEFAULT_MAIL_SUBJECTS = "Briefankündigung"

# API
API_BASE_SANDBOX = "https://api-sandbox.dhl.com"
API_BASE_PRODUCTION = "https://api-eu.dhl.com"
API_TRACK_ENDPOINT = "/track/shipments"
API_PARCEL_DE_ENDPOINT = "/parcel/de/tracking/v0/shipments"

# Tracking
MAX_TRACKING_NUMBERS = 15
TRACKING_HISTORY_DAYS = 90

# Sensors - Package Tracking
SENSOR_INCOMING_PARCELS = "incoming_parcels"
SENSOR_PARCEL = "parcel"
SENSOR_NEXT_DELIVERY = "next_delivery"
SENSOR_AWAITING_PICKUP = "awaiting_pickup"
SENSOR_DELIVERED_PARCELS = "delivered_parcels"
SENSOR_OUTGOING_PARCELS = "outgoing_parcels"
SENSOR_OUTGOING_DELIVERED = "outgoing_delivered"

# Sensors - Briefankündigung
SENSOR_MAIL_COUNT = "mail_count"
SENSOR_MAIL = "mail"
CAMERA_MAIL = "mail_camera"

# Parcel Status Categories (canonical format matching ha-parcel-integrations)
PARCEL_STATUS_CATEGORIES = {
    "PRE_TRANSIT": "pre_transit",
    "IN_TRANSIT": "in_transit",
    "OUT_FOR_DELIVERY": "out_for_delivery",
    "DELIVERED": "delivered",
    "AVAILABLE_FOR_PICKUP": "available_for_pickup",
    "RETURNED_TO_SENDER": "returned_to_sender",
    "EXCEPTION": "exception",
    "UNKNOWN": "unknown",
}

# Active categories (not delivered)
ACTIVE_CATEGORIES = {
    "PRE_TRANSIT",
    "IN_TRANSIT",
    "OUT_FOR_DELIVERY",
    "AVAILABLE_FOR_PICKUP",
    "EXCEPTION",
    "UNKNOWN",
}

# DHL Status Mapping to Canonical
DHL_STATUS_MAP = {
    # Pre-transit
    "data_received": "PRE_TRANSIT",
    "electronic_shipping_info_received": "PRE_TRANSIT",
    "shipment_information_received": "PRE_TRANSIT",
    # In transit
    "in_transit": "IN_TRANSIT",
    "arrived_at_facility": "IN_TRANSIT",
    "departed_facility": "IN_TRANSIT",
    "processed_at_facility": "IN_TRANSIT",
    "customs_clearance": "IN_TRANSIT",
    # Out for delivery
    "out_for_delivery": "OUT_FOR_DELIVERY",
    "delivery_scheduled_today": "OUT_FOR_DELIVERY",
    "with_courier": "OUT_FOR_DELIVERY",
    # Delivered
    "delivered": "DELIVERED",
    "delivered_to_recipient": "DELIVERED",
    "delivered_to_parcel_locker": "DELIVERED",
    "delivered_to_post_office": "DELIVERED",
    # Pickup
    "ready_for_pickup": "AVAILABLE_FOR_PICKUP",
    "arrived_at_pickup_point": "AVAILABLE_FOR_PICKUP",
    "at_packstation": "AVAILABLE_FOR_PICKUP",
    "at_postfiliale": "AVAILABLE_FOR_PICKUP",
    # Returned
    "returned_to_sender": "RETURNED_TO_SENDER",
    "return_initiated": "RETURNED_TO_SENDER",
    # Exception
    "delivery_exception": "EXCEPTION",
    "delivery_attempted": "EXCEPTION",
    "address_issue": "EXCEPTION",
    "customs_hold": "EXCEPTION",
}

# Configuration Keys
CONF_API_KEY = "api_key"
CONF_ENVIRONMENT = "environment"
CONF_POSTAL_CODE = "postal_code"
CONF_IMAP_SERVER = "imap_server"
CONF_IMAP_PORT = "imap_port"
CONF_EMAIL = "email"
CONF_PASSWORD = "password"
CONF_MAIL_FOLDER = "mail_folder"
CONF_MAIL_SENDERS = "mail_senders"
CONF_MAIL_SUBJECTS = "mail_subjects"
CONF_POLL_INTERVAL = "poll_interval"
CONF_DELIVERED_FILTER_DAYS = "delivered_filter_days"
CONF_DELIVERED_FILTER_COUNT = "delivered_filter_count"
CONF_PARCEL_HISTORY = "parcel_history"
CONF_CUSTOM_IMAGE = "custom_image"
CONF_CUSTOM_IMAGE_FILE = "custom_image_file"

# Environment Options
ENV_SANDBOX = "sandbox"
ENV_PRODUCTION = "production"
ENVIRONMENTS = [ENV_SANDBOX, ENV_PRODUCTION]

# Delivered Filter Options
FILTER_DAYS = "days"
FILTER_COUNT = "count"

# Services
SERVICE_ADD_TRACKING = "add_tracking"
SERVICE_REMOVE_TRACKING = "remove_tracking"
SERVICE_REFRESH = "refresh"

# Events
EVENT_PARCEL_DISCOVERED = "dhl_de_parcel_discovered"
EVENT_PARCEL_STATUS_CHANGED = "dhl_de_parcel_status_changed"
EVENT_PARCEL_DELIVERED = "dhl_de_parcel_delivered"
EVENT_MAIL_DISCOVERED = "dhl_de_mail_discovered"

# Icons
ICON_PACKAGE = "mdi:package-variant"
ICON_PACKAGE_UP = "mdi:package-variant-closed"
ICON_PACKAGE_DOWN = "mdi:package-variant-closed"
ICON_TRUCK = "mdi:truck-delivery"
ICON_CLOCK = "mdi:clock-outline"
ICON_MAILBOX = "mdi:mailbox"
ICON_EMAIL = "mdi:email"
ICON_CAMERA = "mdi:camera"
ICON_PACKSTATION = "mdi:locker"

# Device Classes
from homeassistant.components.sensor import SensorDeviceClass

# Manufacturer
MANUFACTURER = "Deutsche Post DHL Group"

# Attribution
ATTRIBUTION = "Data provided by DHL/Deutsche Post APIs"