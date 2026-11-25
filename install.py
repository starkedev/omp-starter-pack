# /// script
# requires-python = ">=3.11"
# dependencies = ["ruamel.yaml>=0.18"]
# ///
"""omp starter pack for Glitch: install it, or check an install.

    uv run install.py [--glitch PATH] [--github NAME ...] [--set KEY=VALUE ...]
    uv run install.py --check [--glitch PATH]

Installing never overwrites a setting or an auto mode config you already have: it adds what
is missing and says what it left alone. Only --set changes a setting you already have, because
you chose it. Run --check after every omp or plugin update.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

from ruamel.yaml import YAML

PACK = Path(__file__).resolve().parent / "files"
OMP_HOME = Path.home() / ".omp"
AGENT = OMP_HOME / "agent"
CONFIG = AGENT / "config.yml"
EXTENSIONS = AGENT / "extensions"
AUTOMODE_CONFIG = EXTENSIONS / "pi-automode" / "config.json"
PLUGINS_MANIFEST = OMP_HOME / "plugins" / "package.json"
PLUGIN = "@czottmann/pi-automode"
# pi-automode 1.18.0 with fixes not released upstream yet: "response was not 0 or 1" goes to the
# detailed check instead of blocking (czottmann/pi-automode#86), the checker model can be an omp
# role such as @smol (#88), and an ordered list of fallback checker models (upstream main).
PLUGIN_SPEC = "github:starkedev/pi-automode#v1.18.0-sd.1"
# The first omp whose extensions can resolve a role such as @smol (`ctx.models.resolve`).
OMP_MINIMUM = (19, 1, 1)
GLITCH_MARKER = Path(".claude") / "hooks" / "write-guard.py"
SOURCE_PREFIX = "Source control: the user's own GitHub accounts"
KEEPER_PREFIX = "Glitch Memory Keeper:"


def find_glitch(start: Path) -> Path | None:
    for folder in (start, *start.parents):
        if (folder / GLITCH_MARKER).is_file():
            return folder
    return None


def yaml_io() -> YAML:
    """YAML 1.2, as omp reads it: a bare `no` or `off` is text, not False."""
    yaml = YAML(typ="safe", pure=True)
    yaml.default_flow_style = False
    yaml.sort_base_mapping_type_on_output = False
    return yaml


def load_yaml(file: Path) -> dict:
    if not file.exists():
        return {}
    data = yaml_io().load(file.read_text(encoding="utf-8"))
    return data if isinstance(data, dict) else {}


def add_missing(target: dict, source: dict, prefix: str = "") -> tuple[list[str], list[str]]:
    """Copies what target lacks from source: missing keys, and missing items of a list both have.

    Returns (added, kept) setting names.
    """
    added: list[str] = []
    kept: list[str] = []
    for key, value in source.items():
        name = f"{prefix}{key}"
        if target.get(key) is None:
            target[key] = value
            added.append(name)
        elif isinstance(value, dict) and isinstance(target[key], dict):
            more_added, more_kept = add_missing(target[key], value, f"{name}.")
            added += more_added
            kept += more_kept
        elif isinstance(value, list) and isinstance(target[key], list):
            # Lists here are safety rules: yours stay, and the pack's go in ahead of them.
            missing = [item for item in value if item not in target[key]]
            if missing:
                target[key][:0] = missing
                added.append(f"{name} ({len(missing)} more)")
        elif target[key] != value:
            kept.append(name)
    return added, kept


def parse_value(text: str) -> object:
    """true/false and whole numbers become those; anything else stays text ("no" is not False)."""
    if text in ("true", "false"):
        return text == "true"
    try:
        return int(text)
    except ValueError:
        return text


def parse_choices(pairs: list[str]) -> dict[str, object]:
    choices: dict[str, object] = {}
    for pair in pairs:
        key, sep, value = pair.partition("=")
        if not sep or not key:
            raise SystemExit(f"--set needs KEY=VALUE, got: {pair}")
        choices[key] = parse_value(value)
    return choices


def apply_choices(config: dict, choices: dict[str, object]) -> list[str]:
    """Sets each chosen dotted key. Returns a line for each one that changed."""
    changed: list[str] = []
    for dotted, value in choices.items():
        *parents, leaf = dotted.split(".")
        node = config
        for part in parents:
            child = node.get(part)
            if not isinstance(child, dict):
                child = node[part] = {}
            node = child
        if node.get(leaf, ...) != value:
            before = f" (was {node[leaf]})" if leaf in node else ""
            node[leaf] = value
            changed.append(f"{dotted} = {value}{before}")
    return changed


def save_copy(file: Path) -> None:
    backup = file.with_name(f"{file.name}.before-starter-pack-{time.strftime('%Y%m%d-%H%M%S')}")
    shutil.copy2(file, backup)
    print(f"  saved a copy of what you had: {backup}")


def sign_in_models(order: list[str]) -> dict:
    """Settings for the sign-ins in fallback order: the first one's helper models, and a fallback
    chain from each model to the same kind of model on the sign-ins after it."""
    sign_ins = load_yaml(PACK / "sign-ins.yml")
    first = sign_ins[order[0]]
    settings: dict = {"modelRoles": dict(first["helpers"])}
    if len(order) < 2:
        return settings
    chains: dict[str, list[str]] = {}

    def chain(key: str, targets: list[str]) -> None:
        if key in chains:  # one model serving two roles takes the first role's chain
            return
        targets = [t for i, t in enumerate(targets) if t != key and t not in targets[:i]]
        if targets:
            chains[key] = targets

    # Main models first: an exact key per sign-in, plus the provider's wildcard for a model picked
    # with /model. Where a sign-in's main model also runs its helpers (Codex), the main chain wins:
    # a limit on the model you work with should land on the next main model, not a helper.
    for i, name in enumerate(order):
        later = [sign_ins[other]["main"] for other in order[i + 1:]] + [sign_ins[other]["main"] for other in order[:i]]
        main = sign_ins[name]["main"]
        chain(main, later)
        chain(main.split("/")[0] + "/*", later)
    # Helpers: exact keys beat the wildcard, so each falls to the same kind of helper.
    for role, model in first["helpers"].items():
        chain(model, [sign_ins[name]["helpers"][role] for name in order[1:]])
    settings["retry"] = {"rateLimitWalksChain": True, "fallbackChains": chains}
    return settings


def install_settings(choices: dict[str, object], sign_ins: list[str]) -> None:
    config = load_yaml(CONFIG)
    chosen = apply_choices(config, choices)
    pack = load_yaml(PACK / "settings.yml")
    if sign_ins:
        pack.update(sign_in_models(sign_ins))
    added, kept = add_missing(config, pack)
    kept = [name for name in kept if name not in choices]
    if added or chosen:
        if CONFIG.exists():
            save_copy(CONFIG)
        CONFIG.parent.mkdir(parents=True, exist_ok=True)
        with CONFIG.open("w", encoding="utf-8") as handle:
            yaml_io().dump(config, handle)
    for line in chosen:
        print(f"  set as you chose: {line}")
    if added:
        print(f"  added: {', '.join(added)}")
    if kept:
        print(f"  left as you set them: {', '.join(kept)}")
    if not added and not kept and not chosen:
        print("  settings already in place")


def plugin_installed() -> bool:
    """True when omp's plugins come from the pack's pi-automode, not the stock npm release."""
    try:
        manifest = json.loads(PLUGINS_MANIFEST.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    return (manifest.get("dependencies") or {}).get(PLUGIN) == PLUGIN_SPEC


def omp_version(omp: str | None) -> tuple[int, ...] | None:
    if not omp:
        return None
    try:
        out = subprocess.run([omp, "--version"], capture_output=True, text=True, timeout=30, check=False).stdout
    except (OSError, subprocess.TimeoutExpired):
        return None
    found = re.search(r"(\d+)\.(\d+)\.(\d+)", out)
    return tuple(int(part) for part in found.groups()) if found else None


def install_plugin(omp: str) -> None:
    if plugin_installed():
        print("  pi-automode already installed")
        return
    if subprocess.run([omp, "plugin", "install", PLUGIN_SPEC]).returncode != 0:
        print("  could not install pi-automode. Check your internet connection, then run this again.")


def keeper_rule(glitch: Path) -> str:
    template = json.loads((PACK / "automode.json").read_text(encoding="utf-8"))
    rule = next(line for line in template["autoMode"]["allow"] if line.startswith(KEEPER_PREFIX))
    return rule.replace("{{GLITCH}}", str(glitch))


def install_automode_config(glitch: Path | None, github: list[str]) -> None:
    """Writes the pack's auto mode config, or, in one that exists, only the two lines that are
    about this member: their GitHub names and their Glitch folder."""
    exists = AUTOMODE_CONFIG.exists()
    try:
        config = json.loads((AUTOMODE_CONFIG if exists else PACK / "automode.json").read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        print(f"  could not read your auto mode config, so left it alone: {AUTOMODE_CONFIG}")
        return
    before = json.dumps(config)
    auto = config.setdefault("autoMode", {})
    if github or not exists:
        environment = [
            line
            for line in auto.get("environment", ["$defaults"])
            if line != "{{SOURCE_CONTROL}}" and not (github and line.startswith(SOURCE_PREFIX))
        ]
        if github:
            environment.append(
                f"{SOURCE_PREFIX} and organisations are {', '.join(github)}, with every repo under them. "
                "Any other account or organisation is external."
            )
        auto["environment"] = environment
    if glitch or not exists:
        allow = [line for line in auto.get("allow", ["$defaults"]) if not line.startswith(KEEPER_PREFIX)]
        if glitch:
            allow.append(keeper_rule(glitch))
        auto["allow"] = allow
    if exists and json.dumps(config) == before:
        print(f"  left your auto mode config alone: {AUTOMODE_CONFIG}")
        return
    if exists:
        save_copy(AUTOMODE_CONFIG)
    AUTOMODE_CONFIG.parent.mkdir(parents=True, exist_ok=True)
    AUTOMODE_CONFIG.write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")
    print(f"  {'updated your GitHub names and Glitch folder in' if exists else 'wrote'} {AUTOMODE_CONFIG}")


def install_extensions(glitch: Path | None) -> None:
    EXTENSIONS.mkdir(parents=True, exist_ok=True)
    names = ["automode-check.ts"] + (["glitch-hooks.ts"] if glitch else [])
    for name in names:
        content = (PACK / name).read_bytes()
        target = EXTENSIONS / name
        if target.exists() and target.read_bytes() == content:
            print(f"  already in place: {target}")
            continue
        verb = "updated" if target.exists() else "installed"
        target.write_bytes(content)
        print(f"  {verb} {target}")


def git(glitch: Path, *args: str) -> str | None:
    """A git command's output in the Glitch folder, or None when it fails or there is no git."""
    program = shutil.which("git")
    if not program:
        return None
    done = subprocess.run([program, "-C", str(glitch), *args], capture_output=True, text=True)
    return done.stdout.strip() if done.returncode == 0 else None


def is_ignored(glitch: Path) -> bool:
    return git(glitch, "check-ignore", ".omp") is not None


def install_glitch(glitch: Path) -> None:
    project_config = glitch / ".omp" / "config.yml"
    if project_config.exists():
        print(f"  left alone: {project_config}")
    else:
        project_config.parent.mkdir(exist_ok=True)
        shutil.copyfile(PACK / "glitch-project-config.yml", project_config)
        print(f"  wrote {project_config}")
    # Keep .omp/ out of Glitch's git without touching its managed .gitignore.
    exclude = git(glitch, "rev-parse", "--git-path", "info/exclude")
    if exclude is None:
        print("  this Glitch folder is not a git checkout, so there is no git to keep .omp/ out of")
    elif not is_ignored(glitch):
        file = glitch / exclude
        file.parent.mkdir(parents=True, exist_ok=True)
        current = file.read_text(encoding="utf-8") if file.exists() else ""
        file.write_text(current + ("" if not current or current.endswith("\n") else "\n") + ".omp/\n", encoding="utf-8")
        print(f"  added .omp/ to {file}")
    # The bridge gives each Glitch guard 10 seconds. The first run of a guard makes uv fetch
    # Glitch's Python, so do that now rather than inside the first guarded action.
    uv = shutil.which("uv")
    if uv:
        scripts = glitch / ".claude" / "scripts"
        ready = subprocess.run([uv, "run", "--no-project", "--directory", str(scripts), "python", "--version"], capture_output=True)
        print("  Glitch's guards are ready to run" if ready.returncode == 0 else "  could not prepare Glitch's guards: run /update in Glitch, then this again")


def check(glitch: Path | None) -> bool:
    config = load_yaml(CONFIG)
    automode: dict = {}
    if AUTOMODE_CONFIG.exists():
        try:
            automode = json.loads(AUTOMODE_CONFIG.read_text(encoding="utf-8")).get("autoMode", {})
        except json.JSONDecodeError:
            pass
    pack = load_yaml(PACK / "settings.yml")
    patterns = (config.get("bash") or {}).get("patterns") or []
    folders = (config.get("tools") or {}).get("restrictedFolders") or []
    resets = (config.get("claudeResets") or {}).get("autoRedeemWeekly")
    results = [
        (shutil.which("omp") is not None, "omp is on your PATH"),
        (
            (omp_version(shutil.which("omp")) or (0,)) >= OMP_MINIMUM,
            f"omp is {'.'.join(map(str, OMP_MINIMUM))} or newer, so auto mode can use your helper models",
        ),
        (plugin_installed(), f"pi-automode is the pack's version ({PLUGIN_SPEC})"),
        (automode.get("enabled") is True, f"auto mode config is readable and on: {AUTOMODE_CONFIG}"),
        (
            not automode.get("classifierModel") or bool(automode.get("classifierFallbackModels")),
            "auto mode's checker has a fallback model, so one model's rate limit can't block everything",
        ),
        ((EXTENSIONS / "automode-check.ts").exists(), "the auto-mode-not-loaded warning is installed"),
        (
            isinstance((config.get("compaction") or {}).get("idleEnabled"), bool),
            f"idle compaction is decided: {'on' if (config.get('compaction') or {}).get('idleEnabled') else 'off'}",
        ),
        (resets in ("no", "yes"), f"spending a saved Claude weekly reset automatically is decided: {resets}"),
        (all(rule in patterns for rule in pack["bash"]["patterns"]), "the fixed rules against disk and home wipes are in place"),
        (all(folder in folders for folder in pack["tools"]["restrictedFolders"]), "~/.ssh and ~/.aws are off limits"),
    ]
    if glitch:
        results += [
            (shutil.which("uv") is not None, "uv is on your PATH (Glitch's hooks run through it)"),
            ((EXTENSIONS / "glitch-hooks.ts").exists(), "the Glitch hook bridge is installed"),
            ((glitch / ".omp" / "config.yml").exists(), f"Glitch loads its Claude context under omp: {glitch}"),
            (git(glitch, "rev-parse", "--git-dir") is None or is_ignored(glitch), "Glitch's git ignores .omp/"),
            (
                any(line.startswith(KEEPER_PREFIX) and str(glitch) in line for line in automode.get("allow") or []),
                "auto mode lets Glitch's memory keeper run in this Glitch folder",
            ),
        ]
    for ok, text in results:
        print(f"  {'ok  ' if ok else 'FAIL'}  {text}")
    return all(ok for ok, _ in results)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--glitch", type=Path, help="your Glitch folder (found by itself when you run this inside it)")
    parser.add_argument("--github", action="append", default=[], metavar="NAME", help="a GitHub account or organisation that is yours (repeatable)")
    parser.add_argument("--set", action="append", default=[], metavar="KEY=VALUE", dest="choices", help="a setting you chose, e.g. compaction.idleThresholdTokens=150000 (repeatable)")
    parser.add_argument("--sign-in", action="append", default=[], dest="sign_ins", metavar="NAME", choices=list(load_yaml(PACK / "sign-ins.yml")), help="a sign-in you use in omp; repeat in the order to fall back through them, first is used for the helpers")
    parser.add_argument("--check", action="store_true", help="check an install and change nothing")
    args = parser.parse_args()

    glitch = find_glitch(args.glitch.expanduser().resolve()) if args.glitch else find_glitch(Path.cwd())
    if args.glitch and not glitch:
        print(f"{args.glitch} is not a Glitch folder (no {GLITCH_MARKER} in it).")
        return 2

    if not args.check:
        omp = shutil.which("omp")
        if not omp:
            print("omp is not installed, or not on your PATH. Install it first, then run this again.")
            return 2
        version = omp_version(omp)
        if version is None or version < OMP_MINIMUM:
            found = ".".join(map(str, version)) if version else "an unknown version"
            print(f"omp is {found}; the pack needs {'.'.join(map(str, OMP_MINIMUM))} or newer. Run `omp update`, then run this again.")
            return 2
        print("Settings")
        install_settings(parse_choices(args.choices), args.sign_ins)
        print("Auto mode")
        install_extensions(glitch)
        install_plugin(omp)
        install_automode_config(glitch, args.github)
        if glitch:
            print(f"Glitch ({glitch})")
            install_glitch(glitch)
        else:
            print("No Glitch folder found: skipped the Glitch parts. Run again with --glitch PATH to add them.")

    print("Check")
    if not glitch:
        print("  No Glitch folder found, so the Glitch checks are skipped. Add --glitch PATH to include them.")
    ok = check(glitch)
    print("All good. Restart omp to pick the changes up." if ok else "Something is missing: see FAIL above.")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
