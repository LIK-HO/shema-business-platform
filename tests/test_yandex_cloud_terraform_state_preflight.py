import os
import subprocess
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "scripts" / "yandex_cloud_terraform_state_preflight.sh"


class StatePreflightTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = TemporaryDirectory()
        self.root = Path(self.tempdir.name)
        self.bin = self.root / "bin"
        self.bin.mkdir()

        self.base_env = os.environ.copy()
        self.base_env.update(
            {
                "PATH": f"{self.bin}:{self.base_env['PATH']}",
                "YC_TERRAFORM_STATE_BUCKET": "shema-test-state",
                "YC_TERRAFORM_STATE_ENDPOINT": "https://storage.example.test",
                "AWS_ACCESS_KEY_ID": "test-access-key",
                "AWS_SECRET_ACCESS_KEY": "test-secret-value",
                "AWS_DEFAULT_REGION": "ru-central1",
                "RUNNER_TEMP": str(self.root),
            }
        )

        self._write_executable(
            self.bin / "curl",
            "#!/usr/bin/env bash\nprintf '%s\\n' 200\n",
        )
        self._write_executable(
            self.bin / "yc",
            "#!/usr/bin/env bash\nexit 0\n",
        )

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    def _write_executable(self, path: Path, content: str) -> None:
        path.write_text(content, encoding="utf-8")
        path.chmod(0o700)

    def _run(self) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["bash", str(SCRIPT)],
            cwd=REPO_ROOT,
            env=self.base_env,
            text=True,
            capture_output=True,
            timeout=30,
            check=False,
        )

    def test_success_proves_endpoint_versioning_and_namespace_access(self) -> None:
        self._write_executable(
            self.bin / "aws",
            (
                "#!/usr/bin/env bash\n"
                "set -eu\n"
                'if [[ "$2" == "head-bucket" ]]; then\n'
                "  exit 0\n"
                "fi\n"
                'if [[ "$2" == "get-bucket-versioning" ]]; then\n'
                "  printf '%s\\n' 'Enabled'\n"
                "  exit 0\n"
                "fi\n"
                'if [[ "$2" == "list-objects-v2" ]]; then\n'
                "  printf '%s\\n' '{}'\n"
                "  exit 0\n"
                "fi\n"
                "exit 2\n"
            ),
        )

        result = self._run()

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("STATE_S3_ENDPOINT_REACHABILITY=PASS", result.stdout)
        self.assertIn("STATE_S3_HEAD_BUCKET=PASS", result.stdout)
        self.assertIn("STATE_S3_VERSIONING=PASS", result.stdout)
        self.assertIn("STATE_S3_STATE_KEY_NAMESPACE_ACCESS=PASS", result.stdout)

    def test_invalid_access_key_is_classified_without_echoing_provider_error(self) -> None:
        self._write_executable(
            self.bin / "aws",
            (
                "#!/usr/bin/env bash\n"
                "set -eu\n"
                "printf '%s\\n' \\\n"
                "  'An error occurred (InvalidAccessKeyId) when calling the HeadBucket operation:' \\\n"
                "  'super-secret-value' >&2\n"
                "exit 255\n"
            ),
        )

        result = self._run()

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("STATE_S3_ERROR_CLASS=INVALID_ACCESS_KEY_ID", result.stdout)
        self.assertIn("STATE_S3_AUTHENTICATION=INVALID_ACCESS_KEY_ID", result.stdout)
        self.assertNotIn("super-secret-value", result.stdout)
        self.assertNotIn("super-secret-value", result.stderr)

    def test_generic_403_is_reported_as_authorization_failure(self) -> None:
        self._write_executable(
            self.bin / "aws",
            (
                "#!/usr/bin/env bash\n"
                "set -eu\n"
                "echo 'An error occurred (403) when calling the HeadBucket operation: "
                "Forbidden' >&2\n"
                "exit 255\n"
            ),
        )

        result = self._run()

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("STATE_S3_ERROR_CLASS=ACCESS_DENIED", result.stdout)
        self.assertIn("STATE_S3_AUTHORIZATION=DENIED_OR_BUCKET_POLICY", result.stdout)


if __name__ == "__main__":
    unittest.main()
