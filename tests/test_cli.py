import os
import subprocess
import sys
import tempfile
import unittest


class CLITests(unittest.TestCase):
    def test_default_cli_runs_via_vm(self):
        with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False, dir=".") as handle:
            handle.write("print(7)\n")
            path = handle.name

        try:
            result = subprocess.run(
                [sys.executable, "main.py", path, "--no-viz", "-q"],
                capture_output=True,
                text=True,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stdout, "7\n")
            self.assertEqual(result.stderr, "")
        finally:
            if os.path.exists(path):
                os.unlink(path)

    def test_module_entrypoint_runs(self):
        with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False, dir=".") as handle:
            handle.write("print(7)\n")
            path = handle.name

        try:
            output_path = f"{path}.c"
            result = subprocess.run(
                [sys.executable, "-m", "compiler", path, "--run", "--no-viz", "-q", "-o", output_path],
                capture_output=True,
                text=True,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stdout, "")
            self.assertEqual(result.stderr, "")
        finally:
            if os.path.exists(path):
                os.unlink(path)
            output_path = f"{path}.c"
            executable_path = os.path.splitext(output_path)[0]
            if os.path.exists(output_path):
                os.unlink(output_path)
            if os.path.exists(executable_path):
                os.unlink(executable_path)

    def test_missing_file_exits_non_zero(self):
        result = subprocess.run(
            [sys.executable, "main.py", "does-not-exist.py", "--no-viz"],
            capture_output=True,
            text=True,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("File not found", result.stderr)

    def test_check_mode_defaults_to_owned_frontend(self):
        with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False, dir=".") as handle:
            handle.write("print(7)\n")
            path = handle.name

        try:
            result = subprocess.run(
                [sys.executable, "main.py", path, "--check", "--no-viz", "-q"],
                capture_output=True,
                text=True,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stdout, "")
            self.assertEqual(result.stderr, "")
        finally:
            if os.path.exists(path):
                os.unlink(path)


if __name__ == "__main__":
    unittest.main()
