import subprocess
from pathlib import Path


def main():
    root = Path(
        subprocess.check_output(["git", "rev-parse", "--show-toplevel"], text=True).strip()
    )
    subprocess.run(
        ["terraform", "fmt", "-check", "-diff", "-recursive"], cwd=root, check=True
    )
    files = subprocess.check_output(
        ["git", "ls-files", "-z", "--", "*.tf", "*.tf.json"], cwd=root, text=True
    ).split("\0")
    directories = sorted({str(Path(file).parent) for file in files if file})
    if not directories:
        print("Terraform ファイルがないため、構成の検証をスキップします。", flush=True)
        return

    for directory in directories:
        print(f"Terraform を検証します。対象 {directory}", flush=True)
        for arguments in (
            ["init", "-backend=false", "-input=false", "-no-color"],
            ["validate", "-no-color"],
        ):
            subprocess.run(
                ["terraform", f"-chdir={root / directory}", *arguments], check=True
            )


if __name__ == "__main__":
    main()
