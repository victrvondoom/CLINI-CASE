"""Regression cases for README false positives and the current checked-in contract."""

import unittest
from pathlib import Path

from check_readme import check_readme

README = Path(__file__).resolve().parents[2] / "README.md"


class ReadmeContractTests(unittest.TestCase):
    def test_current_readme_satisfies_product_contract(self):
        self.assertEqual(check_readme(README.read_text(encoding="utf-8")), [])

    def test_heading_name_appearing_in_body_is_insufficient(self):
        content = README.read_text(encoding="utf-8").replace(
            "## Monitoring, observability and verification", "Monitoring, observability and verification"
        )
        self.assertIn(
            "README must contain one heading: Monitoring, observability and verification",
            check_readme(content),
        )

    def test_headings_inside_code_fences_do_not_satisfy_contract(self):
        content = "# CLINI-CASE\n```markdown\n" + README.read_text(encoding="utf-8") + "\n```"
        self.assertTrue(check_readme(content))

    def test_empty_section_is_rejected(self):
        content = README.read_text(encoding="utf-8")
        start = content.index("## Start here")
        end = content.index("## One connected evidence journey", start)
        content = content[:start] + "## Start here\n\n" + content[end:]
        self.assertIn("README section needs explanatory content: Start here", check_readme(content))


if __name__ == "__main__":
    unittest.main()
