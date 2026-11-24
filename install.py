# /// script
# requires-python = ">=3.11"
# dependencies = ["pyyaml>=6"]
# ///
"""omp starter pack for Glitch: install it, or check an install.

    uv run install.py [--glitch PATH] [--github NAME ...]
    uv run install.py --check [--glitch PATH]

Installing never overwrites a setting or an auto mode config you already have: it adds what
is missing and says what it left alone. Run --check after every omp or plugin update.
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import time
from pathlib import Path

import yaml

PACK = Path(__file__).resolve().parent / "files"
OMP_HOME = Path.home() / ".omp"
AGENT = OMP_HOME / "agent"
CONFIG = AGENT / "config.yml"
EXTENSIONS = AGENT / "extensions"
AUTOMODE_CONFIG = EXTENSIONS / "pi-automode" / "config.json"
AUTOMODE_PACKAGE = OMP_HOME / "plugins" / "node_modules" / "@czottmann" / "pi-automode" / "package.json"
PLUGIN = "@czottmann/pi-automode"
GLITCH_MARKER = Path(".claude") / "hooks" / "write-guard.py"


def find_glitch(start: Path) -> Path | None:
    for folder in (start, *start.parents):
        if (folder / GLITCH_MARKER).is_file():
            return folder
    return None


def load_yaml(file: Path) -> dict:
    if not file.exists():
        return {}
    data = yaml.safe_load(file.read_text(encoding="utf-8"))
    return data if isinstance(data, dict) else {}


def add_missing(target: dict, source: dict, prefix: str = "") -> tuple[list[str], list[str]]:
    """Copies keys target lacks from source. Returns (added, kept) setting names."""
    added: list[str] = []
    kept: list[str] = []
    for key, value in source.items():
        name = f"{prefix}{key}"
        if key not in target:
            target[key] = value
            added.append(name)
        elif isinstance(value, dict) and isinstance(target[key], dict):
            more_added, more_kept = add_missing(target[key], value, f"{name}.")
            added += more_added
            kept += more_kept
        elif target[key] != value:
            kept.append(name)
    return added, kept


def install_settings() -> None:
    config = load_yaml(CONFIG)
    added, kept = add_missing(config, load_yaml(PACK / "settings.yml"))
    if added:
        if CONFIG.exists():
            backup = CONFIG.with_name(f"config.yml.before-starter-pack-{time.strftime('%Y%m%d-%H%M%S')}")
            shutil.copy2(CONFIG, backup)
            print(f"  saved your current settings to {backup}")
        CONFIG.parent.mkdir(parents=True, exist_ok=True)
        CONFIG.write_text(yaml.safe_dump(config, sort_keys=False, allow_unicode=True), encoding="utf-8")
        print(f"  added: {', '.join(added)}")
    if kept:
        print(f"  left as you set them: {', '.join(kept)}")
    if not added and not kept:
        print("  settings already in place")


def install_plugin(omp: str) -> None:
    if AUTOMODE_PACKAGE.exists():
        print("  pi-automode already installed")
        return
    subprocess.run([omp, "plugin", "install", PLUGIN], check=True)


def install_automode_config(glitch: Path | None, github: list[str]) -> None:
    if AUTOMODE_CONFIG.exists():
        print(f"  left your auto mode config alone: {AUTOMODE_CONFIG}")
        return
    config = json.loads((PACK / "automode.json").read_text(encoding="utf-8"))
    auto = config["autoMode"]
    source_control = (
        f"Source control: the user's own GitHub accounts and organisations are {', '.join(github)}, "
        "with every repo under them. Any other account or organisation is external."
        if github
        else None
    )
    auto["environment"] = [
        source_control if line == "{{SOURCE_CONTROL}}" else line
        for line in auto["environment"]
        if line != "{{SOURCE_CONTROL}}" or source_control
    ]
    auto["allow"] = [
        line.replace("{{GLITCH}}", str(glitch)) for line in auto["allow"] if "{{GLITCH}}" not in line or glitch
    ]
    AUTOMODE_CONFIG.parent.mkdir(parents=True, exist_ok=True)
    AUTOMODE_CONFIG.write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")
    print(f"  wrote {AUTOMODE_CONFIG}")


def install_extensions(glitch: Path | None) -> None:
    EXTENSIONS.mkdir(parents=True, exist_ok=True)
    names = ["automode-check.ts"] + (["glitch-hooks.ts"] if glitch else [])
    for name in names:
        shutil.copyfile(PACK / name, EXTENSIONS / name)
        print(f"  installed {EXTENSIONS / name}")


def is_ignored(glitch: Path) -> bool:
    return subprocess.run(["git", "-C", str(glitch), "check-ignore", "-q", ".omp"]).returncode == 0


def install_glitch(glitch: Path) -> None:
    project_config = glitch / ".omp" / "config.yml"
    if project_config.exists():
        print(f"  left alone: {project_config}")
    else:
        project_config.parent.mkdir(exist_ok=True)
        shutil.copyfile(PACK / "glitch-project-config.yml", project_config)
        print(f"  wrote {project_config}")
    # Keep .omp/ out of Glitch's git without touching its managed .gitignore.
    if not is_ignored(glitch):
        exclude = glitch / ".git" / "info" / "exclude"
        exclude.parent.mkdir(exist_ok=True)
        with exclude.open("a", encoding="utf-8") as handle:
            handle.write("\n.omp/\n")
        print(f"  added .omp/ to {exclude}")


def check(glitch: Path | None) -> bool:
    config = load_yaml(CONFIG)
    automode: dict = {}
    if AUTOMODE_CONFIG.exists():
        try:
            automode = json.loads(AUTOMODE_CONFIG.read_text(encoding="utf-8")).get("autoMode", {})
        except json.JSONDecodeError:
            pass
    roles = config.get("modelRoles") or {}
    results = [
        (shutil.which("omp") is not None, "omp is on your PATH"),
        (AUTOMODE_PACKAGE.exists(), f"the {PLUGIN} plugin is installed"),
        (automode.get("enabled") is True, f"auto mode config is readable and on: {AUTOMODE_CONFIG}"),
        (
            "classifierModel" not in automode,
            "auto mode's checker follows your session's model (no classifierModel pinned)",
        ),
        ((EXTENSIONS / "automode-check.ts").exists(), "the auto-mode-not-loaded warning is installed"),
        ((config.get("compaction") or {}).get("idleEnabled") is True, "idle sessions are compacted"),
        (
            (config.get("claudeResets") or {}).get("autoRedeemWeekly") == "no",
            "saved Claude weekly resets are never spent automatically",
        ),
        (all(role in roles for role in ("smol", "commit", "tiny", "memory", "judge")), "background helpers have their own models"),
    ]
    if glitch:
        results += [
            (shutil.which("uv") is not None, "uv is on your PATH (Glitch's hooks run through it)"),
            ((EXTENSIONS / "glitch-hooks.ts").exists(), "the Glitch hook bridge is installed"),
            ((glitch / ".omp" / "config.yml").exists(), f"Glitch loads its Claude context under omp: {glitch}"),
            (is_ignored(glitch), "Glitch's git ignores .omp/"),
        ]
    for ok, text in results:
        print(f"  {'ok  ' if ok else 'FAIL'}  {text}")
    return all(ok for ok, _ in results)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--glitch", type=Path, help="your Glitch folder (found by itself when you run this inside it)")
    parser.add_argument("--github", action="append", default=[], metavar="NAME", help="a GitHub account or organisation that is yours (repeatable)")
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
        print("Settings")
        install_settings()
        print("Auto mode")
        install_plugin(omp)
        install_automode_config(glitch, args.github)
        install_extensions(glitch)
        if glitch:
            print(f"Glitch ({glitch})")
            install_glitch(glitch)
        else:
            print("No Glitch folder found: skipped the Glitch parts. Run again with --glitch PATH to add them.")

    print("Check")
    ok = check(glitch)
    print("All good. Restart omp to pick the changes up." if ok else "Something is missing: see FAIL above.")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
