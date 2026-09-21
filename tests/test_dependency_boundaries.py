import ast
import pathlib

FORBIDDEN_CORE_IMPORTS = {
    "application",
    "adapters",
    "experience",
    "platform",
}

ROOT = pathlib.Path(__file__).resolve().parents[1]
SRC = ROOT / "src" / "shema_platform"


def imported_modules(path: pathlib.Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    modules: set[str] = set()

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            modules.add(node.module)

    return modules


def test_domain_and_foundation_do_not_depend_on_outer_layers() -> None:
    for layer in ("domain", "foundation"):
        root = SRC / layer
        for path in root.rglob("*.py"):
            for module in imported_modules(path):
                if not module.startswith("shema_platform."):
                    continue
                parts = module.split(".")
                assert parts[1] not in FORBIDDEN_CORE_IMPORTS, (
                    f"{path} imports outer layer {module}"
                )
