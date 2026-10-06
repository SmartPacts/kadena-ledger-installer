# Security

## Reporting a problem

Open an issue at
[SmartPacts/kadena-ledger-installer/issues](https://github.com/SmartPacts/kadena-ledger-installer/issues).

If you believe you have found something that puts users at risk, and you would rather not
post it publicly first, say so in an issue without the details and we will arrange a
private channel.

**We will never ask for your recovery phrase, private keys, or a screenshot showing them.
Anyone who does is attacking you, including if they claim to be us.**

## What this tool is

It installs an already-published, already-built application onto a Ledger Nano S Plus.
It does not compile anything, does not modify the app, and does not handle keys, seeds
or transactions at any point.

## Trust model

The security of the result does **not** depend on trusting this program.

It depends on one thing: the SHA-256 hash the Ledger computes from the bytes it received
and displays on its own screen must match the hash published with the app release. That
comparison is performed by the user, on hardware the host computer does not control.

A fully compromised host can send a different application. It cannot make the device
display the correct hash for it. This is why every document here treats the hash
comparison as mandatory rather than optional, and why the installer asks the user to
confirm it explicitly after installing.

## What the installer verifies

| Artefact | Control |
|---|---|
| Connected device | probed (read-only) and required to be a Nano S Plus; known-unsupported models are refused with an explanation |
| Device OS version | selects the release: one pinned release per supported OS series (1.6.x, 1.7.x); any other or unreadable version aborts, never guessed |
| `installer_nanos_plus.sh` from the chosen release | SHA-256 pinned in source for that release; mismatch aborts before anything is sent to the device |
| Firmware image extracted from it | SHA-256 pinned in source for that release; equals the release's published `app.hex` byte for byte |
| App version string inside the release file | must equal the chosen release's version |
| `LOAD_PARAMS` | parsed out of the verified file rather than restated, so they cannot drift from the parameters tested on hardware |
| Target device in those parameters | must be `0x33100004` (Nano S Plus) |
| API level in those parameters | must be the one the device's OS series accepts (26 for 1.6.x, 27 for 1.7.x) |

Every supported OS series has its own pinned release. A new app release, or support for
a new OS series, requires a new release of this installer, with new pins.

## Known limits

Stated because pretending otherwise would be the actual vulnerability.

- **PyPI is trusted.** `ledgerblue` is pinned to `0.1.58` by version but installed from
  PyPI without hash pinning. A compromised `ledgerblue` could load a different app — and
  the device would then display a different hash, which the user is instructed to catch.
- **The installers are not code-signed.** No Apple Developer certificate, no Windows
  code-signing certificate. Both operating systems will warn the user, and the
  documentation tells them so rather than teaching them to dismiss warnings casually.
- **GitHub is trusted for distribution.** A repository compromise could publish a bad
  installer with matching pins. The independent defence remains the device hash, also
  published in the app repository's release notes and in `SHA256SUMS.txt`, and
  reproducible by building the app from source.
- **No `curl | bash`.** Deliberately. Teaching non-technical users to pipe a remote
  script into a shell to set up a hardware wallet trains exactly the behaviour that
  phishing campaigns exploit. Users download a file and run it.

## For anyone who forks or mirrors this

Please change the branding and the issue URL. A copy of this tool that still points at
our issue tracker while shipping different pins is indistinguishable from an attack, and
we will treat it as one.
