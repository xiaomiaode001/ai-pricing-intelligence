from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path


SKILL_ROOT = Path(__file__).resolve().parents[1]


def load_check_environment_module():
    script = SKILL_ROOT / "scripts" / "check_environment.py"
    spec = importlib.util.spec_from_file_location("_check_environment_for_tests", script)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class EnvironmentSetupTests(unittest.TestCase):
    def test_environment_report_finds_required_project_shape(self) -> None:
        module = load_check_environment_module()
        report = module.build_environment_report(SKILL_ROOT, check_network=False, strict=False)

        self.assertEqual(report["skill_root"], str(SKILL_ROOT))
        self.assertIn(report["status"], {"ok", "warning"})
        self.assertEqual(report["checks"]["python"]["status"], "ok")
        self.assertEqual(report["checks"]["project_shape"]["status"], "ok")
        self.assertEqual(report["checks"]["runtime_dirs"]["status"], "ok")
        self.assertGreaterEqual(report["checks"]["product_config"]["product_count"], 4)
        self.assertIn("chatgpt", report["checks"]["product_config"]["products"])


if __name__ == "__main__":
    unittest.main()
