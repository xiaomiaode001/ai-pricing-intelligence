from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def load_release_module():
    script = PROJECT_ROOT / "ai-subscription-pricing-intel" / "scripts" / "check_release_readiness.py"
    spec = importlib.util.spec_from_file_location("check_release_readiness", script)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class ReleaseReadinessTests(unittest.TestCase):
    def test_release_report_requires_github_project_files(self) -> None:
        module = load_release_module()

        report = module.build_release_report(PROJECT_ROOT)

        self.assertIn(report["status"], {"ok", "warning"})
        self.assertEqual(report["checks"]["root_files"]["status"], "ok")
        self.assertEqual(report["checks"]["skill_package"]["status"], "ok")
        self.assertEqual(report["checks"]["github_templates"]["status"], "ok")
        self.assertEqual(report["checks"]["runtime_artifacts"]["status"], "ok")
        self.assertIn("README.md", report["checks"]["root_files"]["files"])
        self.assertIn("ai-subscription-pricing-intel/README.md", report["checks"]["skill_package"]["files"])


if __name__ == "__main__":
    unittest.main()
