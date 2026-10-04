import http.server
import os
import pathlib
import socketserver
import subprocess
import tempfile
import textwrap
import threading
import unittest


REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "scripts" / "yandex_cloud_terraform_state_preflight.sh"


class _HealthHandler(http.server.BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        self.send_response(200)
        self.end_headers()

    def log_message(self, format: str, *args: object) -> None:
        return


class StatePreflightTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.root = pathlib.Path(self.tempdir.name)
        self.bin = self.root / "bin"
        self.bin.mkdir()

        self.server = socketserver.TCPServer(("127.0.0.1", 0), _HealthHandler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

        self.base_env = os.environ.copy()
        self.base_env.update(
            {
                "PATH": f"{self.bin}:{self.base_env['PATH']}",
                "YC_TERRAFORM_STATE_BUCKET": "shema-test-state",
                "YC_TERRAFORM_STATE_ENDPOINT": (
                    f"http://127.0.0.1:{self.server.server_address[1]}"
                ),
                "AWS_ACCESS_KEY_ID": "test-access-key",
                "AWS_SECRET_ACCESS_KEY": "test-secret-value",
                "AWS_DEFAULT_REGION": "ru-central1",
                "RUNNER_TEMP": str(self.root),
            }
        )

        self._write_executable(
            self.bin / "yc",
            "#!/usr/bin/env bash\nexit 0\n",
        )

    def tearDown(self) -> None:
        self.server.shutdown()
        self.server.server_close()
        self.tempdir.cleanup()

    def _write_executable(self, path: pathlib.Path, content: str) -> None:
        path.write_text(textwrap.dedent(content), encoding="utf-8")
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
            r"""
            #!/usr/bin/env bash
            set -eu
            if [[ "$2" == "head-bucket" ]]; then
              exit 0
            fi
            if [[ "$2" == "get-bucket-versioning" ]]; then
              printf '%s\n' 'Enabled'
              exit 0
            fi
            if [[ "$2" == "list-objects-v2" ]]; then
              printf '%s\n' '{}'
              exit 0
            fi
            exit 2
            """,
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
            r"""
            #!/usr/bin/env bash
            set -eu
            printf '%s\\n' \\
              'An error occurred (InvalidAccessKeyId) when calling the HeadBucket operation:' \\
              'super-secret-value' >&2
            exit 255
            """,
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
            r"""
            #!/usr/bin/env bash
            set -eu
            echo 'An error occurred (403) when calling the HeadBucket operation: Forbidden' >&2
            exit 255
            """,
        )

        result = self._run()

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("STATE_S3_ERROR_CLASS=ACCESS_DENIED", result.stdout)
        self.assertIn("STATE_S3_AUTHORIZATION=DENIED_OR_BUCKET_POLICY", result.stdout)


if __name__ == "__main__":
    unittest.main()
