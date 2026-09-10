"""Replay trusted host-command JSON and print deterministic state + event log."""
import argparse
import json
from pathlib import Path

from .basketbroom import Match


COMMANDS = {
    "advance", "process_batch", "possess", "release", "flight_evidence",
    "opponent_challenge", "pause", "resume", "restart", "crown_exit",
    "crown_return", "recall_chase", "record_penalty", "resolve_penalty",
    "certify", "overturn_snitch",
}


def replay(document):
    match = Match(config=document.get("config"), roster=document.get("roster"))
    for command in document["commands"]:
        method = command["method"]
        if method not in COMMANDS:
            raise ValueError(f"unsupported replay command: {method}")
        getattr(match, method)(*command.get("args", []), **command.get("kwargs", {}))
    return {"state": match.snapshot(), "events": match.log}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    args = parser.parse_args()
    print(json.dumps(replay(json.loads(args.input.read_text(encoding="utf-8"))), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
