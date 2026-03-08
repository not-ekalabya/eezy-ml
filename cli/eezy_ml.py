import argparse
import subprocess
import sys
import tempfile
from pathlib import Path
import shutil

TEMPLATE_LIBRARIES = [
    "scikit-learn==1.6.1",
    "datasets==4.0.0",
    "flask==3.1.3",
]


def find_project_dir():
    """Return the directory containing init.py, starting from cwd upward."""
    current = Path.cwd()
    for directory in [current, *current.parents]:
        if (directory / "init.py").exists():
            return directory
    return None


def get_python(project_dir):
    """Return the venv Python executable if present, otherwise fall back to sys.executable."""
    venv_python = project_dir / ".venv" / "Scripts" / "python.exe"
    if venv_python.exists():
        return str(venv_python)
    return sys.executable


def cmd_run_init():
    project_dir = find_project_dir()
    if project_dir is None:
        print("Error: Could not find init.py. Run 'eezy create <dir>' first.", file=sys.stderr)
        sys.exit(1)
    python = get_python(project_dir)
    print(f"Running init.py in {project_dir} (python: {python})...")
    result = subprocess.run([python, str(project_dir / "init.py")], cwd=project_dir)
    sys.exit(result.returncode)


def cmd_start(host="localhost", port=5000):
    project_dir = find_project_dir()
    if project_dir is None:
        print("Error: Could not find init.py. Run 'eezy create <dir>' first.", file=sys.stderr)
        sys.exit(1)

    model_path = project_dir / "model" / "model.joblib"
    if not model_path.exists():
        print(
            "Error: Model not found. Perhaps, you haven't run 'eezy init' yet.\n"
            "       Run 'eezy init' to download data and load/train the model first.",
            file=sys.stderr,
        )
        sys.exit(1)

    server_url = f"http://{host}:{port}"
    python = get_python(project_dir)
    print(f"Starting inference server from {project_dir} (python: {python})...")
    server_env = {**__import__('os').environ, "SERVER_HOST": "0.0.0.0", "SERVER_PORT": str(port)}
    server_proc = subprocess.Popen(
        [python, str(project_dir / "server.py")],
        cwd=project_dir,
        env=server_env,
    )

    import time
    import urllib.request
    import urllib.error

    print(f"Waiting for server to be ready at {server_url}...")
    for _ in range(20):
        try:
            urllib.request.urlopen(f"{server_url}/health", timeout=1)
            break
        except (urllib.error.URLError, OSError):
            time.sleep(0.5)
    else:
        print("Error: Server did not start in time.", file=sys.stderr)
        server_proc.terminate()
        sys.exit(1)

    print("Server is ready. Running tests...\n")
    test_env = {**__import__('os').environ, "SERVER_URL": server_url}
    test_result = subprocess.run(
        [python, str(project_dir / "test.py")],
        cwd=project_dir,
        env=test_env,
    )

    print(f"\nTest {'passed' if test_result.returncode == 0 else 'failed'}.")
    print("Server is running. Press Ctrl+C to stop.")
    try:
        server_proc.wait()
    except KeyboardInterrupt:
        print("\nShutting down server...")
        server_proc.terminate()
        server_proc.wait()


def cmd_create(target_dir, use_venv=True):
    repo_url = "https://github.com/not-ekalabya/eezy-ml.git"

    print("The following libraries will be available in the project:")
    for lib in TEMPLATE_LIBRARIES:
        print(f"  - {lib}")
    print()
    print(f"Cloning /template from {repo_url} into {target_dir}...")

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)

        result = subprocess.run(["git", "clone", "--no-checkout", repo_url, tmp])
        if result.returncode != 0:
            print("Error: git clone failed.", file=sys.stderr)
            sys.exit(result.returncode)

        subprocess.run(["git", "-C", tmp, "config", "core.sparseCheckout", "true"], check=True)
        (tmp_path / ".git" / "info" / "sparse-checkout").write_text("template/\n")
        subprocess.run(["git", "-C", tmp, "checkout"], check=True)

        template_src = tmp_path / "template"
        target_path = Path(target_dir)
        target_path.mkdir(parents=True, exist_ok=True)

        for item in template_src.iterdir():
            dest = target_path / item.name
            if dest.exists():
                shutil.rmtree(dest) if dest.is_dir() else dest.unlink()
            shutil.copytree(item, dest) if item.is_dir() else shutil.copy2(item, dest)

    print(f"Project initialized in ./{target_dir}")

    if use_venv:
        venv_path = Path(target_dir) / ".venv"
        print(f"\nCreating virtual environment at {venv_path}...")
        subprocess.run([sys.executable, "-m", "venv", str(venv_path)], check=True)

        pip = venv_path / "Scripts" / "pip.exe"
        requirements = Path(target_dir) / "requirements.txt"
        if requirements.exists():
            print("Installing dependencies...")
            subprocess.run([str(pip), "install", "-r", str(requirements)], check=True)

        print(f"Virtual environment ready. Activate with: {venv_path}\\Scripts\\activate")


def main():
    parser = argparse.ArgumentParser(prog="eezy")
    subparsers = parser.add_subparsers(dest="command")

    create_parser = subparsers.add_parser("create", help="Scaffold a new eezy-ml project from the template")
    create_parser.add_argument("target_dir", help="Target directory name")
    create_parser.add_argument("--no-venv", action="store_true", help="Skip virtual environment creation")

    subparsers.add_parser("init", help="Download data and train the model (runs init.py)")
    start_parser = subparsers.add_parser("start", help="Start the inference server and run tests")
    start_parser.add_argument("--host", default="localhost", help="Server host (default: localhost)")
    start_parser.add_argument("--port", type=int, default=5000, help="Server port (default: 5000)")

    args = parser.parse_args()

    if args.command == "create":
        cmd_create(args.target_dir, use_venv=not args.no_venv)
    elif args.command == "init":
        cmd_run_init()
    elif args.command == "start":
        cmd_start(host=args.host, port=args.port)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()