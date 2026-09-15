"""Apply migrations, then replace this process with the web server."""

import os
import subprocess
import sys


def main():
    subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        check=True,
    )
    os.execv(
        sys.executable,
        [
            sys.executable,
            "-m",
            "uvicorn",
            "importguard.serve:app",
            "--host",
            "0.0.0.0",
            "--port",
            os.getenv("PORT", "8080"),
        ],
    )


if __name__ == "__main__":
    main()
