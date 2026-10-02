"""Verify the production PDF runtime, including absence of CVE-2025-50422's Cairo."""

import ctypes
import importlib.util
import os
from pathlib import Path
import subprocess

from weasyprint import HTML


assert (os.getuid(), os.getgid()) == (999, 999)
assert importlib.util.find_spec("pip") is None
packages = subprocess.check_output(["apk", "info"], text=True).splitlines()
assert "pango" in packages, "Pango must remain tracked in the APK database"
assert not any(name.startswith(("cairo", "poppler")) for name in packages), packages
for name in ("libcairo.so.2", "libpangocairo-1.0.so.0"):
    try:
        ctypes.CDLL(name)
    except OSError:
        pass
    else:
        raise AssertionError(f"Unnecessary vulnerable backend is loadable: {name}")
assert not list(Path("/usr/lib").glob("*cairo*"))
pdf = HTML(string="<p>日本語PDF — English — العربية</p>").write_pdf()
assert pdf.startswith(b"%PDF")
assert "cairo" not in Path("/proc/self/maps").read_text()
print("PDF generation passed; Pango is tracked; Cairo/Poppler are absent")
