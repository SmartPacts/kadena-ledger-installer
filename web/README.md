# Browser loader for the Kadena Ledger app

A transport-agnostic port of the parts of [ledgerblue](https://github.com/LedgerHQ/blue-loader-python)
(Apache-2.0) needed to install one known application onto a Nano S Plus. The same source
runs under Node for hardware testing and over WebHID in a browser.

**Not shipped yet.** The loader is proven on hardware; the browser transport and UI are not built.

## Layout

| File | Role |
|---|---|
| `src/crypto.ts` | secp256k1, the SCP key derivation, raw AES-CBC over Web Crypto |
| `src/secure-channel.ts` | encrypt + CBC-MAC channel, with chained IVs in both directions |
| `src/handshake.ts` | manager mutual authentication |
| `src/session.ts` | authenticated session; wraps every command |
| `src/hex.ts` | Intel HEX parser |
| `src/loader.ts` | delete, create, stream, commit |
| `src/preflight.ts` | device identity and the dashboard check |
| `harness/` | Node-only; never bundled |

## Rules this code follows, and why

Each of these came from something going wrong, not from taste.

**The expected hash must be on screen before the device asks for approval.**
The device displays the application hash and waits. If our expected value is printed
only after that, the user approves blind and compares afterwards — which is not a check.
Whatever drives this loader must show the value during `onFinalising`, never after
`installApp` resolves. This applies to the browser UI at least as strongly: a progress
bar that reveals the hash on completion is worse than useless, because it looks like
verification while preventing it.

**Install is one call.** `installApp` performs delete → create → stream → commit. It was
briefly possible to drive those by hand, and the missing `commit` produced an install
where every command returned `0x9000`, the CRC passed, and the device silently discarded
the app — leaving the device with nothing, because the delete had already run. No
host-side signal distinguishes that from success: current firmware will not report its
app inventory (`0x6511`). Do not re-expose a partial sequence.

**Addresses are arithmetic, never bit-shifts.** Load addresses sit above 2^31, where
JavaScript's bitwise operators wrap negative.

**libsecp256k1 ECDH is SHA-256 of the compressed shared point**, not the raw point. Using
the raw point yields a channel that fails much later as an opaque MAC error.

**Manager commands need the dashboard.** With an app open the device answers `0x6e00`.
Users hit this constantly, because opening the app to check it is the natural thing to do
right after installing.

## What this does not do

No genuine-device attestation. Our root is not Ledger's, so the handshake proves only
that the chain is internally consistent. The assurance that the correct application
reached the device comes from the hash on its screen — nothing here can substitute for it.

## Testing

```sh
node harness/test-hex.ts <app.hex> '<expected json>'   # offline, vs ledgerblue's values
node harness/test-channel.ts                           # read-only, needs a device
node harness/test-load.ts <app.hex>                    # WRITES to the device
```

The harness borrows a native HID transport from another workspace; set
`HID_TRANSPORT_FROM` to a `package.json` whose dependencies include
`@ledgerhq/hw-transport-node-hid`.
