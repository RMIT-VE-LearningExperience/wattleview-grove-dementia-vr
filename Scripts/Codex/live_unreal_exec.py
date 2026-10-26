"""Execute Python inside the live Unreal Editor through UnrealMCPython TCP."""

from __future__ import annotations

import argparse
import json
import socket
from pathlib import Path


HOST = "127.0.0.1"
PORT = 12029


def execute(code: str, timeout: float) -> dict:
    request = json.dumps({"type": "python", "code": code}, ensure_ascii=False).encode(
        "utf-8"
    )
    response = bytearray()

    with socket.create_connection((HOST, PORT), timeout=timeout) as connection:
        connection.settimeout(timeout)
        connection.sendall(request)
        while True:
            chunk = connection.recv(16384)
            if not chunk:
                break
            response.extend(chunk)

    if not response:
        raise RuntimeError("Unreal returned an empty TCP response.")

    return json.loads(response.decode("utf-8"))


def main() -> None:
    parser = argparse.ArgumentParser()
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--code", help="Python source to execute in Unreal.")
    source.add_argument(
        "--file",
        type=Path,
        help="Local Python file to execute in Unreal with runpy.run_path().",
    )
    parser.add_argument("--timeout", type=float, default=180.0)
    arguments = parser.parse_args()

    if arguments.file:
        script_path = arguments.file.resolve().as_posix()
        code = (
            "import runpy; "
            f"runpy.run_path({script_path!r}, run_name='__main__')"
        )
    else:
        code = arguments.code

    print(json.dumps(execute(code, arguments.timeout), indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
