import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "validate-terraform.py"


class TerraformValidationTests(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary_directory.cleanup)
        self.repository = Path(self.temporary_directory.name)
        subprocess.run(
            ["git", "init", "--quiet", str(self.repository)], check=True
        )

    def add_configuration(self, name, content):
        path = self.repository / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)
        subprocess.run(["git", "add", "--", name], cwd=self.repository, check=True)

    def validate(self, directory=None):
        return subprocess.run(
            [sys.executable, str(SCRIPT)],
            cwd=directory or self.repository,
            capture_output=True,
            text=True,
        )

    def test_empty_repository_succeeds(self):
        result = self.validate()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("スキップ", result.stdout)

    def test_nested_hcl_and_json_work_without_backend_credentials(self):
        self.add_configuration(
            "envs/sandbox/main.tf",
            'terraform {\n  backend "azurerm" {}\n}\n',
        )
        self.add_configuration(
            "modules/名前 with spaces/main.tf.json",
            json.dumps({"output": {"example": {"value": "ok"}}}),
        )
        result = self.validate()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(
            result.stdout.count("Success! The configuration is valid."), 2
        )

    def test_formatting_failure_is_reported_without_rewriting(self):
        content = 'locals {\nvalue="ok"\n}\n'
        self.add_configuration("main.tf", content)
        result = self.validate()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('value="ok"', result.stdout)
        self.assertEqual((self.repository / "main.tf").read_text(), content)

    def test_variable_files_without_modules_are_formatted(self):
        self.add_configuration("values/example.tfvars", 'value="ok"\n')
        result = self.validate()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("example.tfvars", result.stdout)

    def test_running_from_subdirectory_still_validates_all_modules(self):
        self.add_configuration(
            "main.tf", 'output "bad" {\n  value = local.missing\n}\n'
        )
        subdirectory = self.repository / "scripts"
        subdirectory.mkdir()
        result = self.validate(subdirectory)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Reference to undeclared local value", result.stderr)

    def test_invalid_configuration_fails_validation(self):
        self.add_configuration(
            "envs/sandbox/main.tf", 'output "bad" {\n  value = local.missing\n}\n'
        )
        result = self.validate()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Reference to undeclared local value", result.stderr)

    def test_initialization_failure_is_reported(self):
        self.add_configuration(
            "main.tf", 'module "missing" {\n  source = "./missing"\n}\n'
        )
        result = self.validate()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Unreadable module directory", result.stderr)


if __name__ == "__main__":
    unittest.main()
