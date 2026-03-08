import argparse
import subprocess
import sys
from pathlib import Path


def get_template_repo():
    """Get the template directory path from the current git repo."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            check=True
        )
        repo_root = Path(result.stdout.strip())
        template_dir = repo_root / "template"
        return str(template_dir)
    except subprocess.CalledProcessError:
        print("Error: Not in a git repository.", file=sys.stderr)
        sys.exit(1)


def cmd_init(args):
    repo_url = args.repo
    target_dir = args.directory or Path(repo_url.rstrip("/").split("/")[-1]).stem

    print(f"Cloning {repo_url} into {target_dir}...")
    result = subprocess.run(["git", "clone", repo_url, target_dir])
    if result.returncode != 0:
        print("Error: git clone failed.", file=sys.stderr)
        sys.exit(result.returncode)
    print(f"Project initialized in ./{target_dir}")


def main():
    parser = argparse.ArgumentParser(prog="eezy")
    subparsers = parser.add_subparsers(dest="command")

    init_parser = subparsers.add_parser("init", help="Initialize a project by cloning the template")
    init_parser.add_argument("directory", nargs="?", help="Target directory name (defaults to 'template')")

    args = parser.parse_args()

    if args.command == "init":
        repo_url = get_template_repo()
        target_dir = args.directory or "template"
        cmd_init(argparse.Namespace(repo=repo_url, directory=target_dir))
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()