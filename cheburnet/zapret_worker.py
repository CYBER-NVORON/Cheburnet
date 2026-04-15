from __future__ import annotations

import argparse
import json
import traceback
from pathlib import Path

from cheburnet.controllers.zapret import ZapretController


def append_log(path: Path, message: str) -> None:
    with path.open("a", encoding="utf-8") as file:
        file.write(message.rstrip() + "\n")
        file.flush()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--zapret-dir", required=True)
    parser.add_argument("--result", required=True)
    parser.add_argument("--log", required=True)
    args = parser.parse_args()

    result_path = Path(args.result)
    log_path = Path(args.log)
    result_path.parent.mkdir(parents=True, exist_ok=True)
    log_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        controller = ZapretController()
        append_log(log_path, "Elevated worker запущен. UAC больше не понадобится для каждого конфига.")
        results = controller.test_configs(args.zapret_dir, progress=lambda msg: append_log(log_path, msg))
        payload = {"ok": True, "results": [result.to_dict() for result in results]}
    except Exception as exc:
        append_log(log_path, traceback.format_exc())
        payload = {"ok": False, "error": str(exc)}

    result_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return 0 if payload["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
