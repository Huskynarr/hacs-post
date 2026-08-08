# DHL & Deutsche Post Integration for Home Assistant

[![HACS](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://github.com/hacs/integration)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Release](https://img.shields.io/github/v/release/huskynarr/hacs-post.svg)](https://github.com/huskynarr/hacs-post/releases)
[![GitHub Actions](https://github.com/huskynarr/hacs-post/workflows/CI/badge.svg)](https://github.com/huskynarr/hacs-post/actions)
[![Code Coverage](https://img.shields.io/codecov/c/github/huskynarr/hacs-post.svg)](https://codecov.io/gh/huskynarr/hacs-post)

A **Home Assistant Custom Integration** for tracking **DHL Paket Deutschland** shipments and **Deutsche Post Briefankündigungen** (mail announcements).

## ✨ Features

### 📦 Package Tracking (DHL Paket DE)
- **Official API** — Uses DHL Parcel DE Tracking API (Unified Tracking API)
- **Authentication** — API Key via DHL Developer Portal (Sandbox & Production)
- **Real-time tracking** — Status, history, estimated delivery, delivery window
- **Multiple parcels** — Track up to 15 tracking numbers per request
- **Rich sensors** — Per-parcel sensors with full details as attributes
- **Lifecycle management** — Automatic sensor creation/removal
- **Events** — `dhl_de_parcel_discovered`, `dhl_de_parcel_status_changed`, `dhl_de_parcel_delivered`

### 📬 Briefankündigung (Deutsche Post)
- **Email-based** — Parses emails from `ankuendigung@brief.deutschepost.de`
- **IMAP support** — Works with GMX, WEB.DE, or any IMAP provider
- **Mail images** — Extracts base64 inline images from emails
- **Camera entity** — Animated GIF of today's mail (like USPS Informed Delivery)
- **Daily summary** — Count of announced letters per day
- **Multi-account** — Support for multiple email accounts

### 🏪 Packstation
- **Automatic detection** — Recognizes Packstation deliveries from tracking data
- **Pickup notifications** — Alerts when parcel ready for pickup
- **Locker info** — Shows Packstation location and compartment when available

## 🚀 Installation

### Via HACS (Recommended)
1. Open HACS → **Integrations** → ⋮ → **Custom repositories**
2. Add repository URL: `https://github.com/huskynarr/hacs-post`
3. Category: **Integration**
4. Click **Add**, then search for **DHL & Deutsche Post** and **Download**
5. Restart Home Assistant
6. Go to **Settings → Devices & Services → Add Integration** → Search **DHL & Deutsche Post**

### Manual
1. Copy `custom_components/dhl_de` to your `config/custom_components/` directory
2. Restart Home Assistant
3. Add integration via UI

## ⚙️ Configuration

The integration is configured entirely via the UI (**Settings → Devices & Services → Add Integration**).

### Package Tracking Setup
1. Get API Key from [DHL Developer Portal](https://developer.dhl.com/)
   - Register → Create App → Select **Shipment Tracking - Unified** or **DHL Parcel DE Tracking**
   - Copy **Consumer Key** (this is your API Key)
2. In HA: Add Integration → **DHL & Deutsche Post** → **Package Tracking**
3. Enter your **API Key** and optional **Recipient Postal Code** (for detailed address info)
4. Choose **Environment**: Sandbox (free, no DHL account needed) or Production

### Briefankündigung Setup
1. Ensure you have **Briefankündigung activated** at [deutschepost.de/briefankuendigung](https://www.deutschepost.de/briefankuendigung) (via GMX or WEB.DE)
2. In HA: Add Integration → **DHL & Deutsche Post** → **Briefankündigung**
3. Enter **IMAP server**, **email**, **password** (or app password)
4. Configure **mail folder** (default: INBOX) and **scan interval**

## 📊 Entities

### Package Tracking Sensors
| Entity | Description |
|--------|-------------|
| `sensor.dhl_de_incoming_parcels` | Count of active incoming parcels |
| `sensor.dhl_de_parcel_<tracking>` | Per-parcel sensor with full details |
| `sensor.dhl_de_next_delivery` | Earliest expected delivery datetime |
| `sensor.dhl_de_awaiting_pickup` | Parcels ready at Packstation/Postfiliale |
| `sensor.dhl_de_delivered_parcels` | Recently delivered parcels (configurable window) |
| `sensor.dhl_de_outgoing_parcels` | Active outgoing/return parcels |
| `sensor.dhl_de_outgoing_delivered` | Delivered outgoing parcels |

### Briefankündigung Sensors
| Entity | Description |
|--------|-------------|
| `sensor.dhl_de_mail_count` | Number of letters announced today |
| `sensor.dhl_de_mail_<id>` | Per-letter sensor with sender/image |
| `camera.dhl_de_mail_camera` | Animated GIF of today's mail images |

### Parcel Attributes (Carrier-Agnostic Format)
```json
{
  "carrier": "DHL",
  "barcode": "00340434123456789012",
  "sender": "Amazon EU S.à r.l.",
  "receiver": "Max Mustermann",
  "status": "IN_DELIVERY",
  "raw_status": "Zustellung heute",
  "delivered": false,
  "delivered_at": null,
  "planned_from": "2024-01-15T08:00:00+01:00",
  "planned_to": "2024-01-15T18:00:00+01:00",
  "pickup": true,
  "pickup_point": "Packstation 123, 10115 Berlin",
  "url": "https://www.dhl.de/.../00340434123456789012",
  "weight": 1.2,
  "dimensions": {"length": 30, "width": 20, "height": 10},
  "history": [
    {"timestamp": "2024-01-14T14:30:00+01:00", "status": "IN_TRANSIT", "raw_status": "Im Verteilerzentrum angekommen"},
    {"timestamp": "2024-01-15T07:00:00+01:00", "status": "OUT_FOR_DELIVERY", "raw_status": "Zustellung heute"}
  ]
}
```

## 🔧 Advanced Configuration

### Options (via Integration Settings)
- **Poll Interval** — How often to check for updates (default: 30 min)
- **Delivered Filter** — Keep delivered parcels for N days or N most recent
- **Parcel History** — Enable/disable status timeline in attributes
- **Custom Image** — Custom "no mail" placeholder for Briefankündigung camera

### Services
| Service | Description |
|---------|-------------|
| `dhl_de.add_tracking` | Manually add a tracking number |
| `dhl_de.remove_tracking` | Remove a tracking number |
| `dhl_de.refresh` | Force immediate data refresh |

## 🏗️ Architecture

```
custom_components/dhl_de/
├── __init__.py              # Entry point, config entry setup
├── config_flow.py           # UI configuration flows
├── const.py                 # Constants, sensor definitions
├── manifest.json            # Integration metadata
├── hacs.json                # HACS manifest
├── device.py                # Device info helpers
├── api.py                   # DHL API client
├── coordinator.py           # Data update coordinators
├── sensor.py                # Sensor platforms
├── camera.py                # Briefankündigung camera
├── email_parser.py          # Briefankündigung email parsing
├── strings.json             # UI strings
├── translations/
│   ├── en.json              # English translations
│   └── de.json              # German translations
├── shippers/
│   └── post_de.py           # Deutsche Post Briefankündigung shipper
└── tests/
    ├── test_api.py
    ├── test_coordinator.py
    ├── test_email_parser.py
    └── test_sensors.py
```

## 🤝 Contributing

Contributions are welcome! Please read [CONTRIBUTING.md](CONTRIBUTING.md) first.

## 📄 License

MIT License — see [LICENSE](LICENSE) for details.

## 🙏 Acknowledgments

- [ha-parcel-integrations](https://github.com/ha-parcel-integrations) for the excellent parcel integration patterns
- [moralmunky/Home-Assistant-Mail-And-Packages](https://github.com/moralmunky/Home-Assistant-Mail-And-Packages) for Briefankündigung email parsing reference
- DHL Developer Portal for API documentation

## 💬 Support

- **Issues**: [GitHub Issues](https://github.com/huskynarr/hacs-post/issues)
- **Discussions**: [GitHub Discussions](https://github.com/huskynarr/hacs-post/discussions)
- **Wiki**: [Documentation Wiki](https://github.com/huskynarr/hacs-post/wiki)