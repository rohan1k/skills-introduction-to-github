import io, json, os, sys, tempfile, unittest
from contextlib import redirect_stdout
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))


class TvDebloatTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        os.environ["ADB"] = str(HERE / "fake_adb.py")
        os.environ["FAKE_ADB_STATE"] = os.path.join(self.tmp, "tv.json")
        os.environ["TVTRIM_HOME"] = os.path.join(self.tmp, "home")
        import importlib, tvtrim
        self.t = importlib.reload(tvtrim)

    def run_cli(self, *argv):
        buf = io.StringIO()
        with redirect_stdout(buf):
            code = self.t.main(list(argv))
        return code, buf.getvalue()

    def tv(self):
        return json.loads(Path(os.environ["FAKE_ADB_STATE"]).read_text())["pkgs"]

    def test_requires_connection(self):
        self.assertEqual(self.run_cli("scan")[0], 2)

    def test_connect_scan_clean_restore(self):
        code, out = self.run_cli("connect", "192.168.1.50")
        self.assertEqual(code, 0, out)
        self.assertIn("Sony BRAVIA", out)

        code, out = self.run_cli("scan")
        self.assertIn("com.google.android.play.games", out)
        self.assertNotIn("com.google.android.apps.tv.launcherx", out)  # protected

        code, out = self.run_cli("clean", "--dry-run")
        self.assertIn("Dry run", out)
        self.assertEqual(self.tv()["com.google.android.play.games"], "enabled")

        code, out = self.run_cli("clean", "-y")
        self.assertEqual(code, 0, out)
        pk = self.tv()
        self.assertEqual(pk["com.google.android.play.games"], "disabled")
        self.assertEqual(pk["com.google.android.feedback"], "disabled")
        self.assertEqual(pk["com.netflix.ninja"], "enabled")      # optional tier kept
        self.assertEqual(pk["com.google.android.katniss"], "enabled")  # aggressive kept

        code, out = self.run_cli("clean", "-y", "--level", "optional", "--uninstall",
                                 "--skip", "com.netflix.ninja")
        self.assertEqual(self.tv()["com.netflix.ninja"], "enabled")

        self.run_cli("clean", "-y", "--uninstall", "-p", "com.netflix.ninja")
        self.assertEqual(self.tv()["com.netflix.ninja"], "uninstalled")

        code, out = self.run_cli("restore", "-y")
        self.assertEqual(code, 0, out)
        self.assertTrue(all(s == "enabled" for s in self.tv().values()), self.tv())
        self.assertIn("No changes", self.run_cli("history")[1])

    def test_history_offline(self):
        self.run_cli("connect", "192.168.1.50")
        self.run_cli("clean", "-y")
        os.remove(os.environ["FAKE_ADB_STATE"])  # TV gone
        code, out = self.run_cli("history")
        self.assertEqual(code, 0)
        self.assertIn("192.168.1.50:5555", out)
        self.assertIn("com.tcl.partnercustomizer", out)

    def test_tcl(self):
        self.run_cli("connect", "192.168.1.50")
        self.run_cli("clean", "-y")
        pk = self.tv()
        self.assertEqual(pk["com.tcl.partnercustomizer"], "disabled")
        self.assertEqual(pk["com.tcl.smartalexa"], "enabled")   # optional
        self.assertEqual(pk["com.tcl.ttvs"], "enabled")         # aggressive
        self.assertEqual(pk["com.tcl.tv"], "enabled")           # protected
        code, out = self.run_cli("clean", "-n", "--level", "optional", "-g", "tcl")
        self.assertIn("com.tcl.smartalexa", out)
        self.assertNotIn("com.netflix.ninja", out)
        code, out = self.run_cli("clean", "-n", "--level", "aggressive")
        self.assertIn("before a firmware update", out)
        self.assertNotIn("com.tcl.tv ", out)
        self.assertIn("Refusing", self.run_cli("clean", "-y", "-p", "com.tcl.tv")[1])

    def test_same_tv_listed_twice(self):
        os.environ["FAKE_ADB_DUP"] = "1"
        try:
            self.run_cli("connect", "192.168.1.50")
            self.assertEqual(self.run_cli("scan")[0], 0)
            os.remove(os.path.join(self.tmp, "home", "last_device"))
            self.assertEqual(self.run_cli("scan")[0], 0)  # falls back to serialno match
        finally:
            del os.environ["FAKE_ADB_DUP"]

    def test_migrates_legacy_history(self):
        import importlib
        fake_home = Path(self.tmp) / "user"
        (fake_home / ".tv-debloat").mkdir(parents=True)
        (fake_home / ".tv-debloat" / "tv.json").write_text("{}")
        saved = {k: os.environ.pop(k, None) for k in ("TVTRIM_HOME", "TV_DEBLOAT_HOME")}
        os.environ["HOME"], old_home = str(fake_home), os.environ.get("HOME")
        try:
            t = importlib.reload(self.t)
            self.assertEqual(t.STATE_DIR, fake_home / ".tvtrim")
            self.assertTrue((fake_home / ".tvtrim" / "tv.json").exists())
            self.assertFalse((fake_home / ".tv-debloat").exists())
        finally:
            os.environ["HOME"] = old_home
            for k, v in saved.items():
                if v is not None:
                    os.environ[k] = v

    def test_refuses_protected(self):
        self.run_cli("connect", "192.168.1.50")
        code, out = self.run_cli("clean", "-y", "-p", "com.android.vending")
        self.assertIn("Refusing", out)
        self.assertEqual(self.tv()["com.android.vending"], "enabled")


if __name__ == "__main__":
    unittest.main()
