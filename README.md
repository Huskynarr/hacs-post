# Briefankündigung für Home Assistant

[![HACS](https://img.shields.io/badge/HACS-Custom-41BDF5.svg?logo=homeassistant&logoColor=fff)](https://hacs.xyz)
[![GitHub Release](https://img.shields.io/github/v/release/Huskynarr/hacs-post?display_name=tag&sort=semver)](https://github.com/Huskynarr/hacs-post/releases)
[![Validate](https://github.com/Huskynarr/hacs-post/actions/workflows/validate.yml/badge.svg)](https://github.com/Huskynarr/hacs-post/actions/workflows/validate.yml)
[![License](https://img.shields.io/github/license/Huskynarr/hacs-post)](https://github.com/Huskynarr/hacs-post/blob/main/LICENSE)

Ein benutzerdefiniertes Home Assistant-Integration (Custom Component), das Ihr E-Mail-Postfach per IMAP auf neue "Briefankündigung"-E-Mails der Deutschen Post überprüft.

## Funktionen

-   **Sensor:** Zeigt die Anzahl der heutigen Briefankündigungen an.
-   **Attribute:** Listet die Betreffzeilen der gefundenen E-Mails auf.
-   **Konfiguration:** Einfache Einrichtung über die Home Assistant Benutzeroberfläche (Config Flow).

## Installation

### Über HACS (Empfohlen)

[![In HACS öffnen](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=Huskynarr&repository=hacs-post&category=integration)

1.  Klicken Sie auf den Button und bestätigen Sie das Repository in HACS.
2.  Installieren Sie die Integration.
3.  Starten Sie Home Assistant neu.

### Manuell

1.  Kopieren Sie den Ordner `custom_components/post_briefankuendigung` in Ihren `custom_components`-Ordner in Home Assistant.
2.  Starten Sie Home Assistant neu.

## Konfiguration

1.  Gehen Sie zu **Einstellungen** > **Geräte & Dienste**.
2.  Klicken Sie auf **Integration hinzufügen**.
3.  Suchen Sie nach **Briefankündigung**.
4.  Geben Sie Ihre IMAP-Zugangsdaten ein:
    -   **IMAP Server**: z.B. `imap.gmx.net` oder `imap.web.de`
    -   **Port**: 993 (Standard für SSL)
    -   **Benutzername**: Ihre E-Mail-Adresse
    -   **Passwort**: Ihr E-Mail-Passwort (bei Gmail/GMX/Web.de ggf. App-Passwort verwenden!)
    -   **Ordner**: `INBOX` (oder wo die Briefankündigungen landen)
    -   **Absender**: Die E-Mail-Adresse, von der die Ankündigungen kommen (Standard: `noreply@deutschepost.de`)
    -   **Betreff**: Ein Schlüsselwort, nach dem im Betreff gesucht werden soll (Standard: `Briefankündigung`)

## Hinweise

-   Stellen Sie sicher, dass IMAP in Ihrem E-Mail-Konto aktiviert ist.
-   Bei vielen Anbietern (Gmail, GMX, Web.de) müssen Sie möglicherweise ein "App-spezifisches Passwort" erstellen, wenn Sie die Zwei-Faktor-Authentifizierung (2FA) nutzen.
-   Der Sensor aktualisiert sich standardmäßig alle 15 Minuten.

## Lizenz

MIT
