# tvtrim

A command-line tool that connects to your smart TV over Wi-Fi (ADB) and removes preinstalled bloatware, reversibly.

**Works with:** Android TV / Google TV sets (Sony, TCL, Hisense, Philips, Sharp, ...), Chromecast with Google TV, Nvidia Shield, Amazon Fire TV.
**Doesn't work with:** Samsung (Tizen), LG (webOS), Roku, Vizio. Those platforms don't allow removing built-in apps.

## 1. One-time setup

1. Install `adb` on your computer:
   - macOS: `brew install android-platform-tools`
   - Windows: `winget install Google.PlatformTools`
   - Linux: `sudo apt install adb`
2. Turn on debugging on the TV:
   - **Android/Google TV:** Settings → System → About → tap **Android TV OS build** 7 times. Then Settings → System → Developer options → **USB debugging** on.
   - **Fire TV:** Settings → My Fire TV → Developer options → **ADB debugging** on.
3. Find the TV's IP address: Settings → Network & Internet → (your Wi-Fi) → IP address.

Python 3.8+ is needed. There are no other dependencies.

Make `tvtrim` a command you can run from anywhere (run this once, inside this folder):

```bash
chmod +x tvtrim.py
sudo mkdir -p /usr/local/bin
sudo ln -sf "$PWD/tvtrim.py" /usr/local/bin/tvtrim
```

Without that step, use `python3 tvtrim.py` wherever this guide says `tvtrim`.

### Newer Google TV (Android 12+, e.g. TCL): Wireless debugging

If Developer options has **Wireless debugging** instead of a plain on/off switch:

1. Set Wireless debugging to **Enabled**, then open **Pair device with pairing code**.
2. `tvtrim pair <ip>:<pairing-port> <6-digit-code>`
3. Back on the Wireless debugging screen, note the **IP address & Port** (a different port from the pairing one).
4. `tvtrim connect <ip>:<port>`

## 2. Use it

| Command | What it does |
|---|---|
| `tvtrim connect 192.168.1.50` | Accept the "Allow debugging?" prompt on the TV |
| `tvtrim scan` | See what bloatware is installed |
| `tvtrim clean --dry-run` | Preview |
| `tvtrim clean` | Disable the "safe" tier |

Go further:

| Command | What it does |
|---|---|
| `tvtrim clean --level optional --skip com.netflix.ninja` | Also preinstalled apps, keep Netflix |
| `tvtrim clean --uninstall` | Uninstall for user 0 (frees storage) |
| `tvtrim clean -p com.some.package` | Target a specific package |
| `tvtrim list --third-party --filter tcl` | Browse what's installed |

Undo:

| Command | What it does |
|---|---|
| `tvtrim history` | What was changed |
| `tvtrim restore` | Undo everything |
| `tvtrim restore -p com.google.android.videos` | Undo one app |

## Tiers

| Tier | Removed by | What it is |
|------|------------|------------|
| `safe` | `clean` (default) | Ads, recommendations, feedback, game hubs |
| `optional` | `--level optional` | Preinstalled apps some people use (Netflix, YouTube Music, Prime Video...) |
| `aggressive` | `--level aggressive` | Voice assistants and OTA updaters. **This breaks the voice remote and/or stops security updates.** |

Edit `bloatware.json` to add packages for your TV. Entries that aren't installed are ignored. Launchers, Settings, Play Store, Google Play Services, WebView and keyboards are on a protected list, and the tool won't touch them, even with `-p`.

## TCL Google TV

The catalog has 32 TCL packages, based on [tcl-tv-despy](https://github.com/aviv0404/tcl-tv-despy), which was tested on a TCL Smart TV Pro running Android TV 14. Package names can differ between models. The tool only acts on packages your TV actually has.

- **safe:** TCL ad rows on the home screen, TCL Channel, the content/ads feed, store-demo pop-ups, log upload, remote diagnostics, Safety Guard, Play Auto Installs.
- **optional:** TCL Alexa, the voice assistant, the TCL account and app store, Magiconnect, the smart-home dashboard, AirPlay, Miracast, the game bar, the screensaver.
- **aggressive:** `com.tcl.ttvs` (TCL's tracking/push hub; restore it before a firmware update) and `com.tcl.initsetup` (restore it before a factory reset).
- **never touched:** `com.tcl.tv` (Live TV/HDMI), `com.tcl.tvinput`, `com.tcl.autopair` (remote pairing), `com.tcl.suspension`.

Suggested run on a TCL:

| Command | What it does |
|---|---|
| `tvtrim clean` | Ads and telemetry |
| `tvtrim clean --level optional --skip com.tcl.airplay2 --skip com.mediatek.AirplayAPK --skip com.mediatek.airplaydaemon` |  |

### Tested: TCL Smart TV Pro, Android 14 (Google TV)

| Step | Command | Result |
|------|---------|--------|
| Ads and telemetry | `clean` | 14 disabled, 0 failed |
| TCL extras (kept AirPlay) | `clean --level optional -g tcl --skip com.tcl.airplay2 --skip com.mediatek.AirplayAPK --skip com.mediatek.airplaydaemon` | 13 disabled, 0 failed |
| Unwanted streaming apps | `clean -p <app> -p <app> ...` | 7 disabled, 0 failed |
| Privacy Sandbox ad services | `clean -p com.android.adservices.api -p com.android.ondevicepersonalization.services -p com.android.federatedcompute.services` | 3 disabled, 0 failed |

Live TV, HDMI inputs, the remote, voice search and the remaining apps all kept working.

## Getting rid of the home screen ads

Disabling apps doesn't remove the rows Google TV draws on its own home screen:

- **"Top picks for you" and other recommendation rows:** Settings → Accounts & Sign In → your account → **Apps only mode**. This also turns off Watchlist, the Live tab and "Continue watching".
- **The "Sponsored" banner at the top** stays even in Apps only mode. To get rid of it, install **Projectivy Launcher** from the Play Store and turn on *Override current launcher* in its settings. The Home button then opens Projectivy instead of Google TV.
- **Disabled apps still visible?** The home screen caches its app list. Restart the TV.

## When you're done

Turn debugging off so nothing else on your network can control the TV: run `tvtrim disconnect`, then on the TV go to Developer options and switch off USB and Wireless debugging. Your changes stay in place. Turn debugging back on any time you need `restore`.

## Is it safe?

- Nothing is deleted from the system. `disable-user` and `uninstall --user 0` only hide the app for the current user, and the APK stays on the system partition.
- Every change is logged in `~/.tvtrim/<device>.json`, and `restore` puts the apps back.
- A factory reset always restores everything.

## Tests

```bash
python3 -m unittest discover -s tests -v
```

The tests use a fake `adb` (`tests/fake_adb.py`), so no TV is needed.
