"""
Helper script to list the entrypoints and their usage/help messages
instead of inspecting pyproject.toml or README.md by hand
"""
import toml
import subprocess
from pathlib import Path
from rich import print


def main():
    project_root = Path(__file__).parent.parent
    pyproject_filepath = project_root.joinpath("pyproject.toml")
    pyproject = toml.load(pyproject_filepath)

    for entrypoint in pyproject["tool"]["poetry"]["scripts"].keys():
        if entrypoint == "populate-current-roles":
            print(f"usage: {entrypoint}")
        else:
            try:
                subprocess.check_call(["poetry", "run", entrypoint, "--help"])
            except subprocess.CalledProcessError:
                print(f"usage: {entrypoint}")

        print(f"[green bold]{80*'*'}")


if __name__ == "__main__":
    main()
