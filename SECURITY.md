# Security Policy

## Supported Versions

We provide security updates for the following versions:

| Version | Supported          |
| ------- | ------------------ |
| 1.x.x   | :white_check_mark: |
| < 1.0   | :x:                |

## Reporting a Vulnerability

**Please do NOT report security vulnerabilities via public GitHub issues.**

Instead, please report them via email to **huskynarr@proton.me** with the subject line "[SECURITY] DHL/Deutsche Post Integration".

### What to Include

Please include as much information as possible:

- Description of the vulnerability
- Steps to reproduce
- Potential impact
- Suggested fix (if any)
- Your contact information

### Response Timeline

- **Initial response**: Within 48 hours
- **Assessment**: Within 7 days
- **Fix timeline**: Depends on severity, typically within 30 days for critical issues

### Disclosure Policy

- We will coordinate disclosure with the reporter
- Fixed versions will be released as soon as possible
- Security advisories will be published on GitHub Security Advisories
- CVE will be requested for significant vulnerabilities

## Security Considerations

### Credential Handling

- API Keys and passwords are stored in Home Assistant's encrypted config entry storage
- No credentials are logged (except at DEBUG level with explicit user consent)
- Dedicated aiohttp sessions per config entry to prevent cookie leakage

### Network Security

- All API communication uses HTTPS/TLS
- Certificate validation enabled by default
- No insecure fallback options

### Data Privacy

- No telemetry or usage data collected
- No external services contacted except DHL APIs and configured IMAP servers
- Mail images stored locally in HA's `www` directory (user-controlled access)

### Dependency Security

- Dependencies pinned in `pyproject.toml`
- Regular `uv audit` checks in CI
- Automated Dependabot alerts for vulnerable dependencies

## Safe Usage Guidelines

1. **Use App Passwords** — For IMAP with 2FA providers (GMX, WEB.DE, Gmail)
2. **Restrict API Key** — Use Sandbox for testing, Production only when needed
3. **Network Isolation** — Run HA on isolated network segment when possible
4. **Regular Updates** — Keep integration and HA core updated

## Acknowledgments

We appreciate responsible disclosure and will credit reporters (unless they prefer anonymity) in security advisories.