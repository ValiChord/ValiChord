#!/usr/bin/env python3
"""Run this on the Oracle server to install all Python dependencies."""
import subprocess, sys

pkgs = [
    "flask",
    "flask-cors",
    "gunicorn",
    "requests",
    "rarfile",
    "py7zr",
    "python-docx",
    "pyreadstat==1.2.7",
    "pdfplumber==0.10.4",
    "xlrd",
    "anthropic",
]

subprocess.check_call([sys.executable, "-m", "pip", "install"] + pkgs)
print("\nAll dependencies installed.")
