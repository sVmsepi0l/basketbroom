"""Portable registration receipt regressions; no Unreal or installed-file I/O.

The editor boundary is an in-memory fake. The real orchestration, disk receipt
handling, SQL hashing and saved-row verifier run against a temporary directory.
Run with Python: Tools/test_hlck_registration_receipts.py
"""
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace as NS
import unittest
from unittest.mock import patch


def load_registrar():
    path = Path(__file__).with_name("register_hlck_dungeon.py")
    spec = importlib.util.spec_from_file_location("_bb_receipt_under_test", path)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


class Fields:
    def __init__(self, **values):
        self.values = values

    def get_editor_property(self, key):
        return self.values[key]


class RegistrationReceiptTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="basketbroom-receipts-")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.reg = load_registrar()
        r = self.reg
        r.ROOT = self.root
        r.CONTENT = self.root / "Mod/Basketbroom/Content"
        r.KIT_CONTENT = self.root / "fake-installed-content"
        r.REPORT = self.root / ".local/hlck/dungeon-registration-result.json"
        r.LAST_RUN = r.REPORT.with_name("dungeon-registration-last-run.json")
        r.PLAN = r.REPORT.with_name("dungeon-registration-dry-run.json")
        r.CONTENT.mkdir(parents=True)
        self.sql_file = r.CONTENT / "ModEdits.sql"
        self.map_file = r.CONTENT / "Maps/Basketbroom_DungeonMap.umap"
        self.map_file.parent.mkdir()
        self.map_file.write_bytes(b"fake owned saved world")
        for name in (r.OVERLAND, "/Game/Levels/Overland/HOG/HN_AZ",
                     "/Game/Levels/Overland/SubLevels/HN_AZ_Quidditch"):
            path = r.KIT_CONTENT / (name[len("/Game/"):] + ".umap")
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b"fake installed world")
        self.native_calls = 0
        self.database_rows = []
        self.expected_row = dict(DungeonName="Basketbroom_DungeonMap", EntranceIndex="0", Transient="1")
        for name, value in zip(("XPos", "YPos", "ZPos", "ZRot", "BeaconXPos", "BeaconYPos", "BeaconZPos"),
                               r.POSITION + (r.YAW,) + r.POSITION):
            self.expected_row[name] = str(round(value, 2))
        self.sql_text = ("INSERT INTO DungeonEntrances (DungeonName, EntranceIndex, Transient) "
                         "VALUES ('Basketbroom_DungeonMap', 0, 1);\n")
        self.digest = lambda path: hashlib.sha256(Path(path).read_bytes()).hexdigest()
        self.target = "/Basketbroom/Maps/Basketbroom_DungeonMap"
        self.table = NS(get_path_name=lambda: "/Basketbroom/Data/DT_Basketbroom_DungeonsTable")
        handle = Fields(data_table=self.table, dungeon_name="Basketbroom_DungeonMap")
        self.cdo = Fields(dungeon_name=handle)
        self.guard = NS(require_editor=lambda u: "Basketbroom", require_clean=lambda u: {"map": [], "content": []})
        self.stage = NS(
            TARGET_MAP=self.target, ROW_NAME="Basketbroom_DungeonMap", SOURCE_DUNGEONS="source-table",
            SOURCE_ENTRANCE="source-entrance", DESTINATIONS={"source-table": "table", "source-entrance": "entrance"},
            META_OWNER="owner-key", OWNER="test-owner", digest=self.digest,
            checked_file=lambda *args: self.map_file, world_path=lambda world: world,
            schema_fields=lambda proof: [("DungeonLevel", "DungeonLevel")], source_row=lambda *args: ["source-world"],
            PROBE=self.root / ".local/hlck/dungeon-probe.json")
        self.unreal = NS(
            Paths=NS(convert_relative_path_to_full=lambda value: value),
            GameModManagerSubsystem=NS(get_active_mod_content_path_bp=lambda: str(r.CONTENT)),
            EditorLevelLibrary=NS(get_editor_world=lambda: r.OVERLAND, get_all_level_actors=lambda: []),
            EditorAssetLibrary=NS(load_asset=lambda path: self.table, load_blueprint_class=lambda path: object(),
                                 get_metadata_tag=lambda *args: self.stage.OWNER),
            get_default_object=lambda klass: self.cdo, load_asset=lambda path: self.table,
            DataTableFunctionLibrary=NS(get_data_table_row_names=lambda table: [self.stage.ROW_NAME],
                                       get_data_table_column_as_string=lambda *args: [self.target]),
            DbGateway=NS(db_editor_query=self.query),
            BeaconManager=NS(register_transient_dungeon_entrance=self.native_register),
            Vector=lambda *xyz: tuple(xyz))
        self.api_path = self.root / ".local/hlck/registration-api.json"
        modules = {
            "Tools/load_hlck_dungeon.py": self.guard,
            "Tools/stage_hlck_dungeon.py": self.stage,
            "Tools/stage_hlck_dungeon_anchors.py": NS(actor_record=lambda actor: None),
            "Tools/probe_hlck_registration_api.py": NS(run=lambda: {"status": "inspected", "report": str(self.api_path)})}
        r.module = lambda name, relative: modules[relative]
        self.addCleanup(patch.stopall)
        patch.dict(sys.modules, {"unreal": self.unreal}).start()
        for path, value in (
                (r.REPORT.with_name("dungeon-anchor-inspection.json"), {"status": "passed", "passed": 27}),
                (r.REPORT.with_name("dungeon-anchor-result.json"), {"status": "staged", "map_sha256_after": self.digest(self.map_file)}),
                (r.REPORT.with_name("entrance-collision.json"), {"status": "inspected", "samples": [
                    {"xy": list(r.POSITION[:2]), "usable": True, "spawn_center": list(r.POSITION)}]}),
                (self.api_path, {"configured_entrance_class": r.STOCK_CLASS}), (self.stage.PROBE, {})):
            r.write(path, value)

    def query(self, sql):
        if "FROM SchedulesForLevels" in sql:
            values = [{"LevelName": "Overland", "WorldKeys": "Hogwarts,Overland"}]
        elif "FROM DungeonEntrances" in sql:
            values = self.database_rows
        else:
            raise AssertionError("Unexpected editor query: " + sql)
        return NS(success=True, result_rows=[NS(fields=[NS(key=key, value=value) for key, value in row.items()]) for row in values])

    def native_register(self, name, position, yaw, beacon, index):
        self.assertEqual((name, position, yaw, beacon, index),
                         (self.stage.ROW_NAME, self.reg.POSITION, self.reg.YAW, self.reg.POSITION, 0))
        self.native_calls += 1
        self.database_rows.append(dict(self.expected_row))
        self.sql_file.write_text(self.sql_text, encoding="utf-8")

    def register_once(self):
        result = self.reg.run(dry_run=False)
        self.assertEqual(result["status"], "registered", self.reg.LAST_RUN.read_text())
        self.assertEqual(self.native_calls, 1)
        self.assertEqual(json.loads(self.reg.REPORT.read_text())["sql_sha256"], self.digest(self.sql_file))
        return self.reg.REPORT.read_bytes()

    def assert_plan_verifies(self):
        path = Path(__file__).with_name("plan_hlck_dungeon_registration.py")
        spec = importlib.util.spec_from_file_location("_bb_receipt_plan_under_test", path)
        plan = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(plan)
        plan.ROOT = self.root
        plan.REPORT = self.reg.REPORT.with_name("dungeon-registration-plan.json")
        self.stage.SOURCE_SUBDIVISIONS = "source-subdivision"
        self.stage.SOURCE_MUTATOR = "source-mutator"
        self.stage.SOURCE_EXIT = "source-exit"
        self.stage.DESTINATIONS.update({"source-subdivision": "subdivision", "source-mutator": "mutator", "source-exit": "exit"})
        modules = {"Tools/load_hlck_dungeon.py": self.guard,
                   "Tools/stage_hlck_dungeon.py": self.stage,
                   "Tools/inspect_hlck_dungeon_anchors.py": NS(inspect=lambda: {"status": "passed", "passed": 27}),
                   "Tools/register_hlck_dungeon.py": self.reg}
        plan.module = lambda name, relative: modules[relative]
        result = plan.plan()
        self.assertEqual(result["status"], "prepared", plan.REPORT.read_text())
        self.assertTrue(json.loads(plan.REPORT.read_text())["saved_registration_verified"])

    def test_real_noop_retains_successful_receipt_and_can_be_verified(self):
        original = self.register_once()
        original_sql = self.sql_file.read_bytes()
        result = self.reg.run(dry_run=False)
        self.assertEqual(result["status"], "already_registered")
        self.assertEqual(self.native_calls, 1)
        self.assertEqual(self.reg.REPORT.read_bytes(), original)
        self.assertEqual(self.sql_file.read_bytes(), original_sql)
        saved = self.reg.verified_saved_registration(self.unreal, self.stage)
        self.assertEqual(saved["row"], self.expected_row)
        self.assertEqual(saved["sql_sha256"], self.digest(self.sql_file))
        self.assertEqual(json.loads(self.reg.LAST_RUN.read_text())["status"], "already_registered")
        self.assert_plan_verifies()

    def test_dry_noop_preserves_receipt_and_invokes_no_native_write(self):
        original = self.register_once()
        self.assertEqual(self.reg.run(dry_run=True)["status"], "already_registered")
        self.assertEqual(self.native_calls, 1)
        self.assertEqual(self.reg.REPORT.read_bytes(), original)

    def test_failed_preflight_preserves_receipt(self):
        original = self.register_once()
        self.unreal.EditorLevelLibrary.get_editor_world = lambda: self.target
        self.assertEqual(self.reg.run(dry_run=False)["status"], "failed")
        self.assertEqual(self.native_calls, 1)
        self.assertEqual(self.reg.REPORT.read_bytes(), original)
        self.reg.verified_saved_registration(self.unreal, self.stage)

    def test_modified_sql_is_rejected_without_overwriting_proof(self):
        original = self.register_once()
        self.sql_file.write_text("-- altered SQL\n", encoding="utf-8")
        self.assertEqual(self.reg.run(dry_run=False)["status"], "failed")
        self.assertEqual(self.native_calls, 1)
        self.assertEqual(self.reg.REPORT.read_bytes(), original)
        with self.assertRaisesRegex(RuntimeError, "SQL file differ"):
            self.reg.verified_saved_registration(self.unreal, self.stage)

    def test_changed_live_row_is_rejected(self):
        original = self.register_once()
        self.database_rows[0]["XPos"] = "1"
        self.assertEqual(self.reg.run(dry_run=False)["status"], "failed")
        self.assertEqual(self.reg.REPORT.read_bytes(), original)
        self.assertEqual(self.native_calls, 1)
        with self.assertRaisesRegex(RuntimeError, "transform differs"):
            self.reg.verified_saved_registration(self.unreal, self.stage)

    def test_unproven_existing_row_does_not_create_a_success_receipt(self):
        self.database_rows.append(dict(self.expected_row))
        self.sql_file.write_text(self.sql_text, encoding="utf-8")
        self.assertEqual(self.reg.run(dry_run=False)["status"], "failed")
        self.assertEqual(self.native_calls, 0)
        self.assertFalse(self.reg.REPORT.exists())


if __name__ == "__main__":
    unittest.main(verbosity=2)
