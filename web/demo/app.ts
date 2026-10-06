/**
 * Browser install flow.
 *
 * The layout is driven by one rule (see web/README.md): the expected hash must be on
 * screen BEFORE the device asks for approval, and stay there while it waits. A tidy
 * progress bar that reveals the hash on completion would look more polished and be
 * strictly less safe, because it would make the comparison impossible at the only
 * moment it counts.
 */

import { IntelHex } from "../src/hex.ts";
import { AppLoader, deriveLoadParameters } from "../src/loader.ts";
import { ManagerSession } from "../src/session.ts";
import { getDeviceInfo, NotOnDashboardError, quitApp } from "../src/preflight.ts";
import { requestWebHidTransport } from "../src/webhid-transport.ts";
import { hex as toHex } from "../src/crypto.ts";
import type { Transport } from "../src/transport.ts";

const APP_VERSION = "1.3.2";
const APP_NAME = "Kadena";
const APP_HEX_URL = "./app.hex";
const APP_HEX_SHA256 = "d8e19ec77a0de71dd11e35cdbd8bce56c02a5a40740b9dbafd80117fec11f455";
const EXPECTED_DEVICE_HASH =
  "0f6f62ceb5f9b841fbd1b2253a9d14c221000d8da2aeb733c4d70ee30888ccc6";
const TARGET_ID = 0x33100004;
const LOAD_OPTIONS = { apiLevel: 26, dataSize: 16896, installParamsSize: 62, flags: 0 };

const $ = (id: string) => document.getElementById(id)!;
const show = (id: string, visible = true) => $(id).classList.toggle("hidden", !visible);

function log(message: string, kind: "info" | "ok" | "warn" | "err" = "info") {
  const line = document.createElement("div");
  line.className = `line ${kind}`;
  line.textContent = message;
  $("log").append(line);
  $("log").scrollTop = $("log").scrollHeight;
}

function setProgress(fraction: number) {
  ($("bar") as HTMLElement).style.width = `${Math.round(fraction * 100)}%`;
}

/** Render the hash as wrapping 8-character blocks — never one long scrolling line. */
function renderHash(target: HTMLElement, digest: string) {
  target.replaceChildren(
    ...digest.match(/.{1,8}/g)!.map((block) => {
      const span = document.createElement("span");
      span.textContent = block;
      return span;
    }),
  );
}

async function sha256Hex(bytes: Uint8Array): Promise<string> {
  const digest = await crypto.subtle.digest("SHA-256", bytes as BufferSource);
  return toHex(new Uint8Array(digest));
}

/** Fetch the firmware image and refuse it unless it is byte-for-byte the pinned one. */
async function loadImage(): Promise<IntelHex> {
  const response = await fetch(APP_HEX_URL);
  if (!response.ok) throw new Error(`could not download the app image (${response.status})`);
  const bytes = new Uint8Array(await response.arrayBuffer());

  const actual = await sha256Hex(bytes);
  if (actual !== APP_HEX_SHA256) {
    throw new Error(
      `The app image does not match its published checksum.\n` +
        `expected ${APP_HEX_SHA256}\nactually ${actual}\n` +
        `Nothing has been sent to your device. Do not continue.`,
    );
  }
  log(`app image checksum verified (${actual.slice(0, 16)}…)`, "ok");
  return new IntelHex(new TextDecoder().decode(bytes));
}

async function connectAndInstall() {
  ($("connect") as HTMLButtonElement).disabled = true;
  show("intro", false);
  show("progress");
  $("log").textContent = "";
  setProgress(0);

  let transport: Transport | null = null;
  try {
    transport = await requestWebHidTransport();
    log("device connected", "ok");

    // --- preflight ---
    let info;
    try {
      info = await getDeviceInfo(transport);
    } catch (error) {
      if (!(error instanceof NotOnDashboardError)) throw error;
      log("an app is open — asking it to close", "warn");
      await quitApp(transport);
      await transport.close?.();
      throw new Error(
        "The device closed its app and reconnected. Click Install again to continue.",
      );
    }

    log(`Ledger Nano S Plus, firmware ${info.osVersion}`, "ok");
    if (info.targetId !== TARGET_ID) {
      throw new Error(
        "This device is not a Nano S Plus. The Kadena app can only be installed this way " +
          "on a Nano S Plus — every other Ledger needs it to come from Ledger Live.",
      );
    }

    const image = await loadImage();
    const params = deriveLoadParameters(image, LOAD_OPTIONS);

    // The expected value goes up NOW, before anything is written and before the device
    // asks for anything. It stays visible for the rest of the flow.
    renderHash($("expected"), EXPECTED_DEVICE_HASH);
    show("verify");

    log("approve the unknown manager on your device…", "warn");
    const session = await ManagerSession.open(transport, TARGET_ID);
    log(`manager key: ${toHex(session.managerPublicKey).slice(0, 24)}… (differs every run)`);

    const loader = new AppLoader(session);
    await loader.installApp(APP_NAME, image, params, {
      onDeleted: (existed) => log(existed ? "removed the previous version" : "no previous version"),
      onProgress: ({ loaded, total }) => setProgress(loaded / total),
      onFinalising: () => {
        setProgress(1);
        $("verify").classList.add("attention");
        $("verifyLead").textContent =
          "Your device is showing its own hash now and waiting for you. Compare it, then approve.";
        log("compare the hash on your device, then approve", "warn");
      },
    });

    log(`Kadena ${APP_VERSION} installed`, "ok");
    show("confirm");
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    log(message, "err");
    show("retry");
  } finally {
    await transport?.close?.();
    ($("connect") as HTMLButtonElement).disabled = false;
  }
}

$("connect").addEventListener("click", () => void connectAndInstall());
$("matched").addEventListener("click", () => {
  show("confirm", false);
  $("outcome").textContent =
    "Verified. Open the Kadena app on your device to use it. Some wallets also need " +
    "“Blind signing” switched on inside the app’s own settings.";
  $("outcome").className = "outcome ok";
});
$("mismatched").addEventListener("click", () => {
  show("confirm", false);
  $("outcome").textContent =
    "Do not use this installation. Open Ledger Live → My Ledger and uninstall Kadena, " +
    "do not open the app, and report it. Your recovery phrase was never exposed — an app " +
    "cannot read it — but an app that displays one payment and signs another is exactly " +
    "the risk this check exists to catch.";
  $("outcome").className = "outcome err";
});
$("retry").addEventListener("click", () => {
  show("retry", false);
  show("progress", false);
  show("verify", false);
  show("intro");
});

if (!("hid" in navigator)) {
  show("intro", false);
  show("unsupported");
}
