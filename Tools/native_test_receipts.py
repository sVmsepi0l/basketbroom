"""Complete native-test receipts, atomically published for concurrent readers."""
import json
import os
from pathlib import Path
import time
import uuid


def single_world_payload(runner, names, status, reason, engine):
    """Construct the shared report in memory; never publish an interim status."""
    tests = [{"name": name, **runner.results.get(name, {"status": "not_run"})} for name in names]
    data = {
        "status": status, "phase": runner.phase, "engine": engine,
        "elapsed_wall_seconds": round(time.monotonic()-runner.started, 3),
        "passed": sum(row["status"] == "passed" for row in tests),
        "failed": sum(row["status"] == "failed" for row in tests),
        "not_run": sum(row["status"] == "not_run" for row in tests),
        "tests": tests, "events": runner.events, "provenance": runner.provenance,
    }
    if reason:
        data["reason"] = reason
    return data


def write_json_atomic(path, data):
    """Publish exactly one enriched JSON document, retrying brief Windows locks.

    Readers see the previous complete document until the atomic replace succeeds.
    In particular a public final status cannot precede its derived scope/metadata.
    A permanent I/O failure raises, leaving the previous receipt intact.
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    content = json.dumps({**data, "report_write_protocol": "atomic_enriched_v1"}, indent=2, default=str)+"\n"
    temporary = path.with_name("."+path.name+"."+uuid.uuid4().hex+".tmp")
    try:
        with temporary.open("x", encoding="utf-8") as stream:
            stream.write(content)
            stream.flush()
        for attempt, delay in enumerate((0, .01, .02, .04, .08, .16)):
            if delay:
                time.sleep(delay)
            try:
                os.replace(temporary, path)
                return
            except PermissionError:
                if attempt == 5:
                    raise
    finally:
        # A failed publish must not overwrite the original or mask its error.
        try:
            temporary.unlink(missing_ok=True)
        except OSError:
            pass
