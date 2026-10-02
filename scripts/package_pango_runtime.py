"""Repackage Alpine's verified Pango binaries without Cairo/X11 backends.

Keep the original package name, version and origin so vulnerability scanners
can still identify Pango. Only the two libraries used by WeasyPrint are kept;
their ELF dependencies become the runtime package's dependencies.
"""

import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile


def elf_values(option, format_string, libraries):
    output = subprocess.check_output(
        ["scanelf", "--nobanner", option, "--format", format_string, *libraries],
        text=True,
    )
    return {
        value
        for line in output.splitlines()
        for value in line.split()[0].split(",")
    }


def main():
    metadata = json.loads(subprocess.check_output(
        ["apk", "query", "--installed", "--format", "json", "pango"], text=True,
    ))[0]
    with tempfile.TemporaryDirectory() as directory:
        library_dir = Path(directory) / "usr/lib"
        library_dir.mkdir(parents=True)
        for pattern in ("libpango-1.0.so.0*", "libpangoft2-1.0.so.0*"):
            sources = list(Path("/usr/lib").glob(pattern))
            if not sources:
                raise RuntimeError(f"Missing Pango library: {pattern}")
            for source in sources:
                shutil.copy2(source, library_dir / source.name, follow_symlinks=False)
        libraries = [str(path) for path in library_dir.iterdir() if not path.is_symlink()]
        provides = elf_values("--soname", "%S", libraries)
        needs = elf_values("--needed", "%n", libraries) - provides
        if any("cairo" in name or name.startswith("libX") for name in needs):
            raise RuntimeError(f"Unexpected Cairo/X11 dependency: {sorted(needs)}")
        command = ["apk", "mkpkg", "--files", directory, "--output", sys.argv[1]]
        for key in ("name", "version", "arch", "license", "origin", "url"):
            command.extend(["--info", f"{key}:{metadata[key]}"])
        command.extend([
            "--info", "description:Pango and PangoFT2 runtime for WeasyPrint (without Cairo/X11)",
            "--info", "depends:" + " ".join(f"so:{name}" for name in sorted(needs)),
            "--info", "provides:" + " ".join(f"so:{name}=0" for name in sorted(provides)),
        ])
        subprocess.run(command, check=True)


if __name__ == "__main__":
    main()
