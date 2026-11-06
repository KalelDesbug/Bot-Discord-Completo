from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _configured_extensions() -> list[str]:
    tree = ast.parse((ROOT / "src/config/bot.py").read_text(encoding="utf-8"))
    extensions: list[str] = []
    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        for target in node.targets:
            if isinstance(target, ast.Name) and target.id in {"COMMAND_EXTENSIONS", "EVENT_EXTENSIONS"}:
                extensions.extend(ast.literal_eval(node.value))
    return extensions


def test_every_configured_extension_exists_and_has_async_setup() -> None:
    extensions = _configured_extensions()
    assert extensions
    assert len(extensions) == len(set(extensions))

    for module in extensions:
        path = ROOT.joinpath(*module.split(".")).with_suffix(".py")
        assert path.is_file(), f"Extensão inexistente: {module}"
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        setup = next(
            (
                node for node in tree.body
                if isinstance(node, (ast.AsyncFunctionDef, ast.FunctionDef)) and node.name == "setup"
            ),
            None,
        )
        assert isinstance(setup, ast.AsyncFunctionDef), f"{module} precisa declarar async setup(bot)"


def test_local_src_imports_resolve_to_project_modules() -> None:
    module_names: set[str] = set()
    for path in (ROOT / "src").rglob("*.py"):
        parts = path.relative_to(ROOT).with_suffix("").parts
        module_names.add(".".join(parts[:-1] if parts[-1] == "__init__" else parts))

    for path in (ROOT / "src").rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module and node.module.startswith("src."):
                assert node.module in module_names, f"{path}: módulo local ausente {node.module}"
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name.startswith("src."):
                        assert alias.name in module_names, f"{path}: módulo local ausente {alias.name}"


def test_configured_extensions_cover_only_requested_features() -> None:
    tree = ast.parse((ROOT / "src/config/bot.py").read_text(encoding="utf-8"))
    configured: dict[str, tuple[str, ...]] = {}
    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        for target in node.targets:
            if isinstance(target, ast.Name) and target.id in {"COMMAND_EXTENSIONS", "EVENT_EXTENSIONS"}:
                configured[target.id] = ast.literal_eval(node.value)

    assert configured["COMMAND_EXTENSIONS"] == (
        "src.commands.ticket_setup",
        "src.commands.ticket_painel",
        "src.commands.giveaways",
        "src.commands.welcome",
        "src.commands.userinfo",
        "src.commands.moderation",
    )
    assert configured["EVENT_EXTENSIONS"] == (
        "src.events.ready",
        "src.events.channelDelete",
        "src.events.botmention",
        "src.events.interactionCreate",
        "src.events.ticketMessages",
    )
