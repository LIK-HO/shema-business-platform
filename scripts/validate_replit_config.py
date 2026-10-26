from __future__ import annotations

import tomllib
from pathlib import Path


def main() -> None:
    config_path = Path(".replit")
    contract_path = Path("docs/REPLIT_DEPLOYMENT_CONTRACT.md")
    config = tomllib.loads(config_path.read_text(encoding="utf-8"))
    contract = contract_path.read_text(encoding="utf-8")

    run_command = config.get("run", {}).get("command", "")
    deployment = config.get("deployment", {})
    deployment_run = deployment.get("run", [])

    assert "0.0.0.0" in run_command, "Replit run command must bind to 0.0.0.0"
    assert "$PORT" in run_command, "Replit run command must use the platform-provided PORT"
    assert "shema_platform.experience.production:app" in run_command
    assert deployment_run and "$PORT" in " ".join(deployment_run)
    assert deployment.get("build"), "Deployment build command must be explicit"

    required_contract_terms = (
        "FOUNDATION ONLY — NOT RELEASE-AUTHORIZED",
        "PostgreSQL remains the transactional source of truth",
        "fail closed",
        "PR #75",
        "production deployment",
    )
    for term in required_contract_terms:
        assert term.casefold() in contract.casefold(), f"Deployment contract missing: {term}"

    forbidden_secret_markers = ("sk-proj-", "ghp_", "-----BEGIN PRIVATE KEY-----")
    combined = config_path.read_text(encoding="utf-8") + contract
    for marker in forbidden_secret_markers:
        assert marker not in combined, "Possible secret material must never be committed"

    print("Replit configuration contract: PASS")
    print("Production authorization: intentionally NOT granted")


if __name__ == "__main__":
    main()
