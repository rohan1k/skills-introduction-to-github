#!/usr/bin/env python3
"""Fake adb simulating a Google TV. State lives in $FAKE_ADB_STATE."""
import json, os, sys
path = os.environ["FAKE_ADB_STATE"]
st = json.load(open(path)) if os.path.exists(path) else {
    "connected": False,
    "pkgs": {p: "enabled" for p in [
        "android", "com.android.vending", "com.google.android.gms",
        "com.google.android.apps.tv.launcherx", "com.google.android.play.games",
        "com.google.android.videos", "com.google.android.feedback",
        "com.netflix.ninja", "com.google.android.katniss", "com.example.userapp"]},
    "third": ["com.netflix.ninja", "com.example.userapp"],
}
a = sys.argv[1:]
if a[:1] == ["-s"]: a = a[2:]
def save(): json.dump(st, open(path, "w"))
if a[0] == "connect":
    st["connected"] = True; save(); print(f"connected to {a[1]}")
elif a[0] == "devices":
    print("List of devices attached")
    if st["connected"]: print("192.168.1.50:5555\tdevice")
elif a[0] == "shell":
    c = a[1].split()
    if c[0] == "getprop":
        print({"ro.product.manufacturer": "Sony", "ro.product.model": "BRAVIA",
               "ro.build.version.release": "12"}.get(c[1], ""))
    elif c[:3] == ["pm", "list", "packages"]:
        f = c[3] if len(c) > 3 else ""
        for p, s in st["pkgs"].items():
            if s == "uninstalled": continue
            if f == "-d" and s != "disabled": continue
            if f == "-3" and p not in st["third"]: continue
            if f == "-s" and p in st["third"]: continue
            print(f"package:{p}")
    elif c[:2] == ["pm", "disable-user"]:
        st["pkgs"][c[-1]] = "disabled"; save()
        print(f"Package {c[-1]} new state: disabled-user")
    elif c[:2] == ["pm", "uninstall"]:
        st["pkgs"][c[-1]] = "uninstalled"; save(); print("Success")
    elif c[:2] == ["pm", "enable"]:
        st["pkgs"][c[-1]] = "enabled"; save(); print(f"Package {c[-1]} new state: enabled")
    elif c[:3] == ["cmd", "package", "install-existing"]:
        if st["pkgs"].get(c[-1]) == "uninstalled":
            st["pkgs"][c[-1]] = "enabled"; save()
        print(f"Package {c[-1]} installed for user: 0")
elif a[0] == "reboot":
    pass
