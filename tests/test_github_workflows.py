"""Guardrails so GitHub auto-scan/refresh keep firing on every Arena session."""
from pathlib import Path
import unittest

from scripts import update_playlists as u

WORKFLOWS = u.ROOT / ".github" / "workflows"
STALE_SESSION = "arena/01a0de28-m3u-channel-scrape"


class WorkflowTriggerTests(unittest.TestCase):
    def test_push_triggers_cover_every_arena_session_branch(self):
        for name in ("refresh.yml", "verify.yml", "tests.yml"):
            with self.subTest(workflow=name):
                text = (WORKFLOWS / name).read_text(encoding="utf-8")
                self.assertIn('arena/**', text)
                self.assertNotIn(STALE_SESSION, text)
                self.assertIn("workflow_dispatch" if name != "tests.yml" else "pull_request",
                              text)

    def test_refresh_and_verify_still_schedule_on_main(self):
        refresh = (WORKFLOWS / "refresh.yml").read_text(encoding="utf-8")
        verify = (WORKFLOWS / "verify.yml").read_text(encoding="utf-8")
        self.assertIn('cron: "17 6 * * *"', refresh)
        self.assertIn('cron: "43 8 * * *"', verify)
        self.assertIn("contents: write", refresh)
        self.assertIn("contents: write", verify)
        self.assertIn("scripts/update_playlists.py", refresh)
        self.assertIn("scripts/verify_channels.py", verify)


if __name__ == "__main__":
    unittest.main()
