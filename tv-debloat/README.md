# tv-debloat

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

## 2. Use it

```bash
./tvdebloat.py connect 192.168.1.50   # accept the "Allow debugging?" prompt on the TV
./tvdebloat.py scan                   # see what bloatware is installed
./tvdebloat.py clean --dry-run        # preview
./tvdebloat.py clean                  # disable the "safe" tier
```

Go further:

```bash
./tvdebloat.py clean --level optional --skip com.netflix.ninja   # also preinstalled apps, keep Netflix
./tvdebloat.py clean --uninstall                                # uninstall for user 0 (frees storage)
./tvdebloat.py clean -p com.some.package                        # target a specific package
./tvdebloat.py list --third-party --filter tcl                  # browse what's installed
```

Undo:

```bash
./tvdebloat.py history     # what was changed
./tvdebloat.py restore     # undo everything
./tvdebloat.py restore -p com.google.android.videos
```

## Tiers

| Tier | Removed by | What it is |
|------|------------|------------|
| `safe` | `clean` (default) | Ads, recommendations, feedback, game hubs |
| `optional` | `--level optional` | Preinstalled apps some people use (Netflix, YouTube Music, Prime Video...) |
| `aggressive` | `--level aggressive` | Voice assistants and OTA updaters. **This breaks the voice remote and/or stops security updates.** |

Edit `bloatware.json` to add packages for your TV. Entries that aren't installed are ignored. Launchers, Settings, Play Store, Google Play Services, WebView and keyboards are on a protected list, and the tool won't touch them, even with `-p`.

## Is it safe?

- Nothing is deleted from the system. `disable-user` and `uninstall --user 0` only hide the app for the current user, and the APK stays on the system partition.
- Every change is logged in `~/.tv-debloat/<device>.json`, and `restore` puts the apps back.
- A factory reset always restores everything.

## Tests

```bash
python3 -m unittest discover -s tests -v
```

The tests use a fake `adb` (`tests/fake_adb.py`), so no TV is needed.
