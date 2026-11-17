#!/usr/bin/env python3
"""tvtrim: connect to an Android TV / Google TV / Fire TV over ADB and
remove preinstalled bloatware, reversibly.

Every change is made for user 0 only (`pm disable-user` or `pm uninstall -k
--user 0`). The APK stays on the system partition, so nothing is permanently
deleted and a factory reset always brings everything back. Each change is
recorded in ~/.tvtrim/<device>.json so `restore` can undo it.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
DEFAULT_LIST = HERE / "bloatware.json"
LEGACY_STATE_DIR = Path.home() / ".tv-debloat"


def _state_dir() -> Path:
    env = os.environ.get("TVTRIM_HOME") or os.environ.get("TV_DEBLOAT_HOME")
    if env:
        return Path(env)
    new = Path.home() / ".tvtrim"
    # Carry over change history from before the rename so `restore` keeps working.
    if not new.exists() and LEGACY_STATE_DIR.is_dir():
        try:
            LEGACY_STATE_DIR.rename(new)
        except OSError:
            return LEGACY_STATE_DIR
    return new


STATE_DIR = _state_dir()
TIERS = ("safe", "optional", "aggressive")
DEFAULT_PORT = 5555
LAST_DEVICE = STATE_DIR / "last_device"


# --------------------------------------------------------------------------- adb


class AdbError(RuntimeError):
    pass


class Adb:
    def __init__(self, serial: str | None = None, adb_path: str | None = None):
        self.adb = adb_path or os.environ.get("ADB") or shutil.which("adb")
        if not self.adb:
            raise AdbError(
                "adb not found. Install Android platform-tools:\n"
                "  macOS:   brew install android-platform-tools\n"
                "  Windows: winget install Google.PlatformTools\n"
                "  Linux:   sudo apt install adb"
            )
        self.serial = serial

    def run(self, *args: str, check: bool = True, timeout: int = 30) -> str:
        cmd = [self.adb]
        if self.serial:
            cmd += ["-s", self.serial]
        cmd += list(args)
        try:
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        except subprocess.TimeoutExpired:
            raise AdbError(f"adb timed out: {' '.join(args)}")
        out = (proc.stdout + proc.stderr).strip()
        if check and proc.returncode != 0:
            raise AdbError(out or f"adb exited with {proc.returncode}")
        return out

    def shell(self, command: str, check: bool = True) -> str:
        return self.run("shell", command, check=check)

    def devices(self) -> list[tuple[str, str]]:
        out = self.run("devices", check=False)
        rows = []
        for line in out.splitlines()[1:]:
            parts = line.split()
            if len(parts) >= 2:
                rows.append((parts[0], parts[1]))
        return rows

    def resolve_device(self) -> str:
        """Pick the target device, failing with a helpful message."""
        devs = self.devices()
        if self.serial:
            for s, state in devs:
                if s == self.serial:
                    if state != "device":
                        raise AdbError(_state_help(s, state))
                    return s
            raise AdbError(f"{self.serial} is not connected. Run: tvtrim connect <tv-ip>")
        ready = [s for s, st in devs if st == "device"]
        if not ready:
            bad = [(s, st) for s, st in devs if st != "device"]
            if bad:
                raise AdbError(_state_help(*bad[0]))
            raise AdbError("No TV connected. Run: tvtrim connect <tv-ip>")
        if len(ready) > 1:
            # Prefer the TV we last connected to (pairing can list it twice).
            last = LAST_DEVICE.read_text().strip() if LAST_DEVICE.exists() else ""
            if last in ready:
                self.serial = last
                return last
            # Same physical device under two names (mDNS + ip:port)?
            ids = set()
            for s in ready:
                ids.add(self.run("-s", s, "shell", "getprop ro.serialno", check=False).strip())
            if len(ids) == 1:
                self.serial = sorted(ready, key=lambda s: ":" not in s)[0]
                return self.serial
            raise AdbError(
                "Several devices connected; pick one with --device:\n  " + "\n  ".join(ready)
            )
        self.serial = ready[0]
        return self.serial

    def prop(self, name: str) -> str:
        return self.shell(f"getprop {name}", check=False).strip()

    def packages(self, flag: str = "") -> set[str]:
        out = self.shell(f"pm list packages {flag}".strip(), check=False)
        return {l[len("package:"):].strip() for l in out.splitlines() if l.startswith("package:")}


def _state_help(serial: str, state: str) -> str:
    if state == "unauthorized":
        return (f"{serial} is unauthorized. Look at the TV and accept the "
                "'Allow USB debugging?' prompt (tick 'Always allow'), then retry.")
    if state == "offline":
        return f"{serial} is offline. Run: tvtrim disconnect && tvtrim connect <tv-ip>"
    return f"{serial} is in state '{state}'."


# ---------------------------------------------------------------------- catalog


def load_catalog(path: Path) -> dict:
    with open(path) as f:
        data = json.load(f)
    entries = {}
    for gid, group in data["groups"].items():
        for pkg, meta in group["packages"].items():
            entries[pkg] = {"group": gid, "label": group["label"], **meta}
    return {"entries": entries, "protected": set(data.get("protected", []))}


def tiers_up_to(level: str) -> set[str]:
    return set(TIERS[: TIERS.index(level) + 1])


# ------------------------------------------------------------------------ state


def state_path(serial: str) -> Path:
    safe = "".join(c if c.isalnum() or c in "-._" else "_" for c in serial)
    return STATE_DIR / f"{safe}.json"


def load_state(serial: str) -> dict:
    p = state_path(serial)
    if p.exists():
        return json.loads(p.read_text())
    return {"device": serial, "changes": {}}


def save_state(serial: str, state: dict) -> None:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    state_path(serial).write_text(json.dumps(state, indent=2, sort_keys=True))


# --------------------------------------------------------------------- helpers


def color(s: str, code: str) -> str:
    if not sys.stdout.isatty() or os.environ.get("NO_COLOR"):
        return s
    return f"\033[{code}m{s}\033[0m"


TIER_COLOR = {"safe": "32", "optional": "33", "aggressive": "31"}


def confirm(prompt: str) -> bool:
    try:
        return input(f"{prompt} [y/N] ").strip().lower() in ("y", "yes")
    except EOFError:
        return False


def connected(args) -> Adb:
    adb = Adb(args.device)
    adb.resolve_device()
    return adb


def scan(adb: Adb, catalog: dict) -> list[dict]:
    installed = adb.packages()
    disabled = adb.packages("-d")
    found = []
    for pkg, meta in sorted(catalog["entries"].items(), key=lambda kv: (TIERS.index(kv[1]["tier"]), kv[0])):
        if pkg in catalog["protected"]:
            continue
        if pkg in installed:
            found.append({"package": pkg, "status": "disabled" if pkg in disabled else "active", **meta})
    return found


# --------------------------------------------------------------------- commands


def cmd_connect(args) -> int:
    adb = Adb()
    target = args.host if ":" in args.host else f"{args.host}:{args.port}"
    print(f"Connecting to {target} ...")
    out = adb.run("connect", target, check=False)
    print(out)
    if "connected" not in out or "cannot" in out or "failed" in out:
        print("\nCouldn't connect. On the TV:\n"
              "  1. Settings > System > About > tap 'Android TV OS build' 7 times\n"
              "  2. Settings > System > Developer options > turn on 'USB debugging'\n"
              "     (Fire TV: Settings > My Fire TV > Developer options > ADB debugging)\n"
              "  3. Make sure the TV and this computer are on the same network\n"
              "  Newer Google TV builds may need: tvtrim pair <ip>:<pair-port> <code>")
        return 1
    adb.serial = target
    for _ in range(10):
        state = dict(adb.devices()).get(target)
        if state == "device":
            break
        if state == "unauthorized":
            print("Accept the 'Allow USB debugging?' prompt on your TV ...")
        time.sleep(1.5)
    try:
        adb.resolve_device()
    except AdbError as e:
        print(e)
        return 1
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    LAST_DEVICE.write_text(target)
    print(color("Connected.", "32"))
    return _print_info(adb)


def cmd_pair(args) -> int:
    print(Adb().run("pair", args.target, args.code, check=False))
    print("Paired. Now run: tvtrim connect <tv-ip>:<port>\n"
          "(use the IP address & Port shown on the TV's Wireless debugging screen, not the pairing port)")
    return 0


def cmd_disconnect(args) -> int:
    print(Adb().run("disconnect", *( [args.host] if args.host else [] ), check=False))
    return 0


def cmd_info(args) -> int:
    return _print_info(connected(args))


def _print_info(adb: Adb) -> int:
    brand = adb.prop("ro.product.manufacturer")
    model = adb.prop("ro.product.model")
    android = adb.prop("ro.build.version.release")
    user_pkgs = len(adb.packages("-3"))
    all_pkgs = len(adb.packages())
    print(f"Device:   {adb.serial}\nModel:    {brand} {model}\nAndroid:  {android}\n"
          f"Packages: {all_pkgs} total, {user_pkgs} third-party")
    return 0


def cmd_scan(args) -> int:
    adb = connected(args)
    catalog = load_catalog(args.list)
    found = scan(adb, catalog)
    if not found:
        print("No known bloatware found on this TV. Use `tvtrim list` to browse all packages.")
        return 0
    print(f"{'TIER':<11}{'STATUS':<10}{'PACKAGE':<46}DESCRIPTION")
    for f in found:
        tier = color(f"{f['tier']:<11}", TIER_COLOR[f["tier"]])
        print(f"{tier}{f['status']:<10}{f['package']:<46}{f['desc']}")
        if f.get("note"):
            print(f"{'':<21}! {f['note']}")
    counts = {t: sum(1 for f in found if f["tier"] == t and f["status"] == "active") for t in TIERS}
    print(f"\nActive: {counts['safe']} safe, {counts['optional']} optional, {counts['aggressive']} aggressive")
    if counts["safe"]:
        print("Next: tvtrim clean            (safe tier only)")
    elif counts["optional"]:
        print("Safe tier done. Optional apps can be removed with: tvtrim clean --level optional --skip <app>")
    return 0


def cmd_list(args) -> int:
    adb = connected(args)
    pkgs = adb.packages("-3" if args.third_party else ("-s" if args.system else ""))
    disabled = adb.packages("-d")
    for p in sorted(pkgs):
        if args.filter and args.filter.lower() not in p.lower():
            continue
        print(f"{p}{'  (disabled)' if p in disabled else ''}")
    return 0


def cmd_clean(args) -> int:
    adb = connected(args)
    catalog = load_catalog(args.list)
    mode = "uninstall" if args.uninstall else "disable"

    if args.package:
        installed = adb.packages()
        targets = []
        for p in args.package:
            if p in catalog["protected"]:
                print(color(f"Refusing to touch protected system package {p}", "31"))
                continue
            if p not in installed:
                print(f"Skipping {p}: not installed")
                continue
            meta = catalog["entries"].get(p, {"tier": "custom", "desc": "(manually specified)"})
            targets.append({"package": p, **meta})
    else:
        allowed = tiers_up_to(args.level)
        targets = [f for f in scan(adb, catalog) if f["tier"] in allowed and f["status"] == "active"]
        if args.group:
            targets = [t for t in targets if t["group"] in args.group]
        if args.skip:
            targets = [t for t in targets if t["package"] not in args.skip]

    if not targets:
        print("Nothing to do.")
        return 0

    verb = "Uninstall (for user 0)" if mode == "uninstall" else "Disable"
    print(f"{verb} {len(targets)} package(s):")
    for t in targets:
        print(f"  - {t['package']:<46}{t.get('desc', '')}")
    notes = [t for t in targets if t.get("note")]
    if notes:
        print(color("\nBefore you go ahead:", "33"))
        for t in notes:
            print(f"  ! {t['package']}: {t['note']}")
    if any(t.get("tier") == "aggressive" for t in targets):
        print(color("\nWarning: aggressive packages can break voice search or system updates.", "31"))

    if args.dry_run:
        print("\nDry run, nothing changed.")
        return 0
    if not args.yes and not confirm("\nProceed?"):
        print("Aborted.")
        return 1

    state = load_state(adb.serial)
    failures = 0
    for t in targets:
        p = t["package"]
        cmd = f"pm uninstall -k --user 0 {p}" if mode == "uninstall" else f"pm disable-user --user 0 {p}"
        out = adb.shell(cmd, check=False)
        ok = ("Success" in out) or (mode == "disable" and "disabled" in out.lower())
        if ok:
            state["changes"][p] = {"action": mode, "at": time.strftime("%Y-%m-%dT%H:%M:%S")}
            print(color(f"  ok    {p}", "32"))
        else:
            failures += 1
            print(color(f"  fail  {p}: {out}", "31"))
    save_state(adb.serial, state)
    print(f"\nDone. {len(targets) - failures} changed, {failures} failed. "
          f"Undo any time with: tvtrim restore")
    if failures < len(targets) and not args.reboot:
        print("Apps still on the home screen? Restart the TV (or re-run with --reboot).")
    if args.reboot and failures < len(targets):
        adb.run("reboot", check=False)
        print("Rebooting TV ...")
    return 1 if failures else 0


def cmd_restore(args) -> int:
    adb = connected(args)
    state = load_state(adb.serial)
    changes = state["changes"]
    targets = args.package or sorted(changes)
    if not targets:
        print("Nothing recorded to restore for this TV.")
        return 0
    if not args.yes and not confirm(f"Restore {len(targets)} package(s)?"):
        print("Aborted.")
        return 1
    failures = 0
    for p in targets:
        action = changes.get(p, {}).get("action")
        # Try both: an untracked package may have been disabled or uninstalled.
        cmds = {
            "disable": [f"pm enable {p}"],
            "uninstall": [f"cmd package install-existing {p}"],
        }.get(action, [f"cmd package install-existing {p}", f"pm enable {p}"])
        ok = False
        for c in cmds:
            out = adb.shell(c, check=False)
            if "installed for user" in out or "new state: enabled" in out or "Success" in out:
                ok = True
        if ok:
            changes.pop(p, None)
            print(color(f"  restored  {p}", "32"))
        else:
            failures += 1
            print(color(f"  fail      {p}: {out}", "31"))
    save_state(adb.serial, state)
    return 1 if failures else 0


def cmd_history(args) -> int:
    """Reads the local log, so it works without the TV connected."""
    if args.device:
        files = [state_path(args.device)]
    else:
        files = sorted(STATE_DIR.glob("*.json")) if STATE_DIR.is_dir() else []
    shown = 0
    for f in files:
        if not f.exists():
            continue
        data = json.loads(f.read_text())
        changes = data.get("changes", {})
        if not changes:
            continue
        shown += 1
        print(f"{data.get('device', f.stem)}  ({len(changes)} changes)")
        for p, c in sorted(changes.items(), key=lambda kv: (kv[1]["at"], kv[0])):
            print(f"  {c['at']}  {c['action']:<10}{p}")
    if not shown:
        print("No changes recorded.")
    return 0


# ------------------------------------------------------------------------ main


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(
        prog="tvtrim",
        description="Connect to an Android TV / Google TV / Fire TV over ADB and remove bloatware (reversibly).",
    )
    ap.add_argument("-d", "--device", help="adb serial or ip:port (when several are connected)")
    ap.add_argument("--list", type=Path, default=DEFAULT_LIST, help="bloatware catalog JSON")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("connect", help="connect to a TV over Wi-Fi")
    p.add_argument("host", help="TV IP address (Settings > Network > status)")
    p.add_argument("--port", type=int, default=DEFAULT_PORT)
    p.set_defaults(func=cmd_connect)

    p = sub.add_parser("pair", help="pair with Android 11+ wireless debugging")
    p.add_argument("target", help="ip:port shown in the TV's pairing dialog")
    p.add_argument("code", help="6-digit pairing code")
    p.set_defaults(func=cmd_pair)

    p = sub.add_parser("disconnect", help="disconnect from a TV")
    p.add_argument("host", nargs="?")
    p.set_defaults(func=cmd_disconnect)

    sub.add_parser("info", help="show device info").set_defaults(func=cmd_info)
    sub.add_parser("scan", help="find known bloatware on the TV").set_defaults(func=cmd_scan)

    p = sub.add_parser("list", help="list installed packages")
    g = p.add_mutually_exclusive_group()
    g.add_argument("--third-party", action="store_true")
    g.add_argument("--system", action="store_true")
    p.add_argument("--filter", help="substring filter")
    p.set_defaults(func=cmd_list)

    p = sub.add_parser("clean", help="disable or uninstall bloatware")
    p.add_argument("--level", choices=TIERS, default="safe", help="how far to go (default: safe)")
    p.add_argument("--package", "-p", action="append", help="target a specific package (repeatable)")
    p.add_argument("--skip", action="append", help="keep this package (repeatable)")
    p.add_argument("--group", "-g", action="append",
                   help="only these catalog groups, e.g. tcl, google, streaming (repeatable)")
    p.add_argument("--uninstall", action="store_true",
                   help="uninstall for user 0 instead of disabling (frees more; still restorable)")
    p.add_argument("--dry-run", "-n", action="store_true", help="show what would change")
    p.add_argument("--yes", "-y", action="store_true", help="don't ask for confirmation")
    p.add_argument("--reboot", action="store_true", help="reboot the TV afterwards")
    p.set_defaults(func=cmd_clean)

    p = sub.add_parser("restore", help="undo changes made by clean")
    p.add_argument("--package", "-p", action="append", help="restore only this package")
    p.add_argument("--yes", "-y", action="store_true")
    p.set_defaults(func=cmd_restore)

    sub.add_parser("history", help="show changes made to this TV").set_defaults(func=cmd_history)
    return ap


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return args.func(args)
    except AdbError as e:
        print(color(f"Error: {e}", "31"), file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    sys.exit(main())
