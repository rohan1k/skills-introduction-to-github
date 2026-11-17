# 📺 tvtrim

*Trim the bloat off your smart TV.*

A command-line tool that connects to your smart TV over Wi-Fi and removes preinstalled bloatware: ads, tracking, promo rows and apps you never asked for. Every change can be undone.

**Works with:** Android TV and Google TV sets (TCL, Sony, Hisense, Philips and others), Chromecast with Google TV, Nvidia Shield and Amazon Fire TV.
**Doesn't work with:** Samsung (Tizen), LG (webOS), Roku or Vizio. Those don't allow removing built-in apps.

## Quick start

```bash
git clone https://github.com/rohan1k/tvtrim.git
cd tvtrim/tv-debloat
brew install android-platform-tools        # or: winget install Google.PlatformTools / sudo apt install adb

python3 tvdebloat.py connect <tv-ip>       # accept the prompt on the TV
python3 tvdebloat.py scan                  # see what's installed
python3 tvdebloat.py clean --dry-run       # preview
python3 tvdebloat.py clean                 # remove ads and telemetry
python3 tvdebloat.py restore               # undo everything
```

Before connecting, turn on debugging on the TV. Go to Settings → System → About and tap **Android TV OS build** 7 times, then Developer options → **USB debugging** or **Wireless debugging**.

See [`tv-debloat/README.md`](tv-debloat/README.md) for the full guide: the three tiers, keeping specific apps, pairing with Wireless debugging, TCL-specific notes, and getting rid of home-screen ads.

## Tested on

| TV | Android | Result |
|----|---------|--------|
| TCL Smart TV Pro (Google TV) | 14 | 37 packages disabled, 0 failures. Live TV, HDMI, the remote, voice search and the kept apps all still work. |

## Safety

- Apps are disabled for the TV's user account, not deleted. `restore` brings them back, and so does a factory reset.
- Core system parts (the home screen, Settings, Play Store, keyboards, Live TV and inputs, remote pairing) are protected. The tool refuses to touch them.
- Turn debugging off on the TV when you're done.

---

This repository started as the GitHub Skills [Introduction to GitHub](https://github.com/rohan1k/tvtrim/issues/1) exercise.

&copy; 2025 GitHub &bull; [Code of Conduct](https://www.contributor-covenant.org/version/2/1/code_of_conduct/code_of_conduct.md) &bull; [MIT License](https://gh.io/mit)
