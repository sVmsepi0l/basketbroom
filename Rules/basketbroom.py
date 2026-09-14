"""Deterministic host-authoritative reference; no physics or engine dependencies.

All timestamps are integer cumulative LIVE milliseconds. The host supplies
verified geometry/capture evidence, groups simultaneous events, and adjudicates
penalties. This module never trusts a client to award arbitrary point values.
"""
from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path


class RulesError(ValueError):
    """Rejected authority command; gameplay state is unchanged where documented."""


def load_config(path=None):
    return json.loads(Path(path or Path(__file__).with_name("alpha_rules.json")).read_text(encoding="utf-8"))


def default_roster():
    return [dict(id=f"{team}_{role}_{index + 1}", team=team, role=role)
            for team in ("A", "B")
            for role, count in load_config()["roster"].items()
            for index in range(count)]


def _integer(value, name):
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise RulesError(f"{name} must be a nonnegative integer")
    return value


class Match:
    """One match. Initial construction is the opening horn.

    Use process_batch for goals/catches completed at one resolution timestamp.
    Use advance only after all earlier point batches have been submitted. A horn
    at t takes precedence over an event completed at t (bible: before the horn).
    Ending calls enter `review`; only certify() can publish a winner.
    """

    BALL_TYPES = {"quaffle": "quaffle", "quark_1": "quark", "quark_2": "quark",
                  "snipe": "snipe", "snitch": "snitch",
                  "bludger_1": "bludger", "bludger_2": "bludger"}
    CARRIERS = {"netminder", "chaser", "trapper", "ranger"}
    CHASERS = {"ranger", "scout"}

    def __init__(self, roster=None, config=None):
        self.config = deepcopy(config or load_config())
        self.players = {}
        for entry in roster or default_roster():
            player = dict(entry, removed_until=None, ejected=False, donnybrook_excluded=False)
            if player["id"] in self.players:
                raise RulesError("duplicate player ID")
            if player["team"] not in ("A", "B") or player["role"] not in self.config["roster"]:
                raise RulesError("unknown team or position")
            self.players[player["id"]] = player
        for team in ("A", "B"):
            counts = {role: sum(p["team"] == team and p["role"] == role for p in self.players.values())
                      for role in self.config["roster"]}
            if counts != self.config["roster"]:
                raise RulesError("each team must field the configured eight positions")
        self.phase, self.status, self.quarter = "regulation", "live", 1
        self.now_ms = self.period_elapsed_ms = 0
        self.scores = {"A": 0, "B": 0}
        self.winner = self.reckoner = self.ending = None
        self.balls = {key: dict(type=kind, phase_status="active", play_state="live",
                              control_state="free", controller=None, dead_reason=None,
                              timeout_until=None, crown_deadline=None, crown_mark=None,
                              restart_team=None, protection_until=None)
                      for key, kind in self.BALL_TYPES.items()}
        self._dead("snitch", "scheduled_release")
        self.hurleys = {key: self._fresh_hurley() for key in ("bludger_1", "bludger_2")}
        self.penalties, self.log = [], []
        self._emit("opening_horn", quarter=1)

    @staticmethod
    def _fresh_hurley():
        return dict(last_player=None, individual_started=None, team=None, team_ms=0,
                    flight_started=None, contestable=False, individual_reset=False,
                    warned=False)

    def _emit(self, kind, **payload):
        self.log.append(dict(sequence=len(self.log) + 1, at_ms=self.now_ms, kind=kind) | payload)

    def _ball(self, ball_id):
        if ball_id not in self.balls:
            raise RulesError("unknown ball")
        return self.balls[ball_id]

    def _live_ball(self, ball_id):
        ball = self._ball(ball_id)
        if self.status != "live" or ball["phase_status"] != "active" or ball["play_state"] != "live":
            raise RulesError("ball is not live")
        return ball

    def _player(self, player_id):
        if player_id not in self.players:
            raise RulesError("unknown player")
        player = self.players[player_id]
        if player["ejected"] or player["donnybrook_excluded"] or player["removed_until"] is not None:
            raise RulesError("player is unavailable")
        return player

    def _carried(self, player_id):
        return [key for key, ball in self.balls.items()
                if ball["type"] in ("quaffle", "quark") and ball["controller"] == player_id]

    def eligible(self, player_id, ball_id):
        try:
            player = self._player(player_id)
            ball = self._ball(ball_id)
        except RulesError:
            return False
        if ball["phase_status"] != "active":
            return False
        if self.phase == "donnybrook":
            return ball["type"] in ("quark", "snipe")
        if ball["type"] in ("quaffle", "quark"):
            return player["role"] in self.CARRIERS
        if ball["type"] in ("snipe", "snitch"):
            return player["role"] in self.CHASERS
        return player["role"] == "hurleyback"

    def _dead(self, ball_id, reason):
        ball = self.balls[ball_id]
        ball.update(play_state="dead", control_state="free", controller=None, dead_reason=reason,
                    protection_until=None)

    def _release(self, ball_id):
        ball = self.balls[ball_id]
        ball.update(play_state="live", control_state="free", controller=None, dead_reason=None,
                    timeout_until=None, crown_deadline=None, protection_until=None)

    def possess(self, player_id, ball_id, *, inspected_hurley=False):
        ball = self._live_ball(ball_id)
        player = self._player(player_id)
        if not self.eligible(player_id, ball_id):
            raise RulesError("Unauthorized Ball Play")
        if ball["controller"] is not None:
            raise RulesError("release or verified turnover required before possession")
        if ball["type"] in ("quaffle", "quark"):
            if self._carried(player_id):
                raise RulesError("Multi-Ball Hoarding")
            if ball["protection_until"] and self.now_ms < ball["protection_until"] and player["team"] != ball["restart_team"]:
                raise RulesError("protected restart")
        elif ball["type"] == "bludger":
            if not inspected_hurley:
                raise RulesError("Bludgers require inspected Hurleys")
            if any(b["type"] == "bludger" and b["controller"] == player_id for b in self.balls.values()):
                raise RulesError("one Bludger per Hurleyback")
            h = self.hurleys[ball_id]
            if h["team"] != player["team"]:
                h.update(team=player["team"], team_ms=0)
            if h["last_player"] != player_id or h["individual_reset"] or h["individual_started"] is None:
                h.update(individual_started=self.now_ms, warned=False)
            h.update(last_player=player_id, flight_started=None, contestable=False, individual_reset=False)
        else:
            raise RulesError("chase balls resolve through capture events")
        ball.update(control_state="controlled", controller=player_id)
        self._emit("possession", player=player_id, ball=ball_id)
        self._check_hurleys()

    def release(self, player_id, ball_id, *, contestable=False):
        ball = self._live_ball(ball_id)
        if ball["controller"] != player_id:
            raise RulesError("player does not control this ball")
        ball.update(control_state="free", controller=None, protection_until=None)
        if ball["type"] == "bludger":
            self.hurleys[ball_id].update(flight_started=self.now_ms, contestable=bool(contestable))
        self._emit("release", player=player_id, ball=ball_id, contestable=bool(contestable))

    def flight_evidence(self, ball_id, *, distance_ft=0, contact=None, contestable=False):
        """Authority certifies observable flight evidence; private banks never reset."""
        ball = self._live_ball(ball_id)
        if ball["type"] != "bludger" or ball["controller"]:
            raise RulesError("flight evidence requires a free Bludger")
        if distance_ft < 0 or contact not in (None, "player", "hurley", "net", "floor", "goal"):
            raise RulesError("invalid flight evidence")
        h = self.hurleys[ball_id]
        if contestable and not h["contestable"]:
            h.update(contestable=True, flight_started=self.now_ms)
        reset = distance_ft >= self.config["geometry_ft"]["self_toss_reset_distance"]
        reset |= contact in ("player", "hurley") or (contestable and contact in ("net", "floor", "goal"))
        h["individual_reset"] |= reset
        self._emit("flight_evidence", ball=ball_id, distance_ft=distance_ft, contact=contact, contestable=contestable)

    def opponent_challenge(self, ball_id, player_id):
        ball = self._live_ball(ball_id)
        player = self._player(player_id)
        if ball["type"] != "bludger" or player["role"] != "hurleyback":
            raise RulesError("challenge requires a Hurleyback and Bludger")
        h = self.hurleys[ball_id]
        if h["team"] == player["team"]:
            raise RulesError("teammate challenge does not reset team control")
        h.update(team_ms=0)
        self._emit("opponent_challenge", ball=ball_id, player=player_id)

    def _check_hurleys(self):
        for key, h in self.hurleys.items():
            ball = self.balls[key]
            if not ball["controller"]:
                continue
            individual = self.now_ms - h["individual_started"]
            if individual >= self.config["timing"]["hurley_individual_ms"]:
                self._hurley_violation(key, "Illegal Prolonged Bludger Control")
            elif h["team_ms"] >= self.config["timing"]["hurley_team_ms"]:
                self._hurley_violation(key, "Team Relay Hoarding")
            elif individual >= self.config["timing"]["hurley_warning_ms"] and not h["warned"]:
                h["warned"] = True
                self._emit("hurley_warning", ball=key, player=ball["controller"])

    def _hurley_violation(self, ball_id, reason):
        player_id = self.balls[ball_id]["controller"]
        self.record_penalty(player_id, reason, "minor", ball_id)
        self.balls[ball_id]["restart_team"] = self._opponent(self.players[player_id]["team"])
        self._dead(ball_id, "hurley_foul")
        self.hurleys[ball_id] = self._fresh_hurley()

    @staticmethod
    def _opponent(team):
        if team not in ("A", "B"):
            raise RulesError("unknown team")
        return "B" if team == "A" else "A"

    def process_batch(self, at_ms, events):
        """Atomically apply verified goal/catch events sharing one timestamp.

        Goal: {kind:'goal', ball:'quark_1', attacking_team:'A', hoop:'small',
               entire_ball:True, forward:True, teleported:False}
        Catch: {kind:'catch', ball:'snipe', player:'A_scout_1', secure_ms:1000,
                by_hand:True, mounted:True, inside_envelope:True}
        Required evidence must be explicitly true; defaults do not grant scores.
        """
        backup = deepcopy(self.__dict__)
        try:
            return self._process_batch(at_ms, list(events))
        except (RulesError, KeyError, TypeError):
            self.__dict__.clear()
            self.__dict__.update(backup)
            raise

    def _process_batch(self, at_ms, events):
        _integer(at_ms, "at_ms")
        if at_ms < self.now_ms:
            raise RulesError("events may not run backwards")
        self.advance(at_ms - self.now_ms)
        if self.status != "live" or self.now_ms != at_ms:
            raise RulesError("event completed after a stoppage or horn")
        seen, awards, snitch = set(), [], None
        for event in events:
            ball_id = event["ball"]
            if ball_id in seen:
                raise RulesError("one ball cannot complete two point events at one timestamp")
            seen.add(ball_id)
            ball = self._live_ball(ball_id)
            kind = ball["type"]
            if event["kind"] == "goal":
                team = event["attacking_team"]
                self._opponent(team)
                expected = {"quaffle": "large", "quark": "small"}.get(kind)
                legal = (expected is not None and event.get("hoop") == expected
                         and event.get("entire_ball") is True and event.get("forward") is True
                         and event.get("teleported", False) is False)
                if not legal:
                    self._emit("no_goal", ball=ball_id)
                    continue
                awards.append((team, self.config["score"][kind], ball_id, None))
            elif event["kind"] == "catch":
                player_id = event["player"]
                player = self._player(player_id)
                if kind not in ("snipe", "snitch") or not self.eligible(player_id, ball_id):
                    raise RulesError("ineligible chase catch")
                secure_ms = _integer(event.get("secure_ms", 0), "secure_ms")
                if self._carried(player_id) or secure_ms < self.config["timing"]["catch_control_ms"]:
                    raise RulesError("capture requires one second and no carried scoring ball")
                if not all(event.get(key) is True for key in ("by_hand", "mounted", "inside_envelope")):
                    raise RulesError("capture evidence failed")
                if any(item[3] == player_id for item in awards):
                    raise RulesError("one player cannot complete both chase catches simultaneously")
                points = self.config["score"][f"snitch_{self.phase}" if kind == "snitch" else kind]
                awards.append((player["team"], points, ball_id, player_id))
                if kind == "snitch":
                    snitch = (player["team"], player_id, points)
            else:
                raise RulesError("unknown point event")
        if self.phase == "donnybrook" and len({a[0] for a in awards}) > 1:
            for key in ("quark_1", "quark_2", "snipe"):
                self._release(key)
            self._emit("donnybrook_simultaneous_void", events=deepcopy(events))
            return []
        for team, points, ball_id, player_id in awards:
            self.scores[team] += points
            self._emit("points", team=team, points=points, ball=ball_id, player=player_id)
            self._dead(ball_id, "timeout" if ball_id == "snipe" else "score")
            if ball_id == "snipe":
                self.balls[ball_id]["timeout_until"] = self.now_ms + self.config["timing"]["snipe_timeout_ms"]
            elif self.balls[ball_id]["type"] in ("quaffle", "quark"):
                self.balls[ball_id]["restart_team"] = self._opponent(team)
        if snitch:
            self._end("snitch", catching_team=snitch[0], catcher=snitch[1], catch_points=snitch[2])
        elif self.phase == "donnybrook" and awards:
            self._end("donnybrook", winning_team=awards[0][0])
        elif self.phase == "overtime" and awards and self.margin >= self.config["ending"]["overtime_margin"]:
            self._end("overtime_margin")
        return [dict(team=a[0], points=a[1], ball=a[2]) for a in awards]

    @property
    def margin(self):
        return abs(self.scores["A"] - self.scores["B"])

    @property
    def leader(self):
        return None if self.margin == 0 else max(self.scores, key=self.scores.get)

    def _end(self, reason, **details):
        self.ending = dict(reason=reason, at_ms=self.now_ms, **details)
        self.status = "review"
        self._secure_balls()
        self._emit("provisional_end", **self.ending)

    def advance(self, delta_ms):
        """Consume live time, stopping at horns/stoppages; return milliseconds consumed."""
        _integer(delta_ms, "delta_ms")
        start, target = self.now_ms, self.now_ms + delta_ms
        while self.status == "live" and self.now_ms < target:
            deadlines = [target]
            timing = self.config["timing"]
            duration = timing["quarter_ms"] if self.phase == "regulation" else timing["overtime_ms"]
            if self.phase != "donnybrook":
                deadlines.append(self.now_ms + duration - self.period_elapsed_ms)
            if self.phase == "regulation" and self.balls["snitch"]["dead_reason"] == "scheduled_release":
                deadlines.append(timing["snitch_release_ms"])
            for ball in self.balls.values():
                deadlines.extend(d for d in (ball["timeout_until"], ball["crown_deadline"]) if d is not None)
                if ball["timeout_until"] and ball["timeout_until"] - timing["snipe_warning_ms"] > self.now_ms:
                    deadlines.append(ball["timeout_until"] - timing["snipe_warning_ms"])
            for player in self.players.values():
                if player["removed_until"] is not None:
                    deadlines.append(player["removed_until"])
            for key, h in self.hurleys.items():
                if self.balls[key]["controller"]:
                    deadlines.append(h["individual_started"] + timing["hurley_individual_ms"])
                    if not h["warned"]:
                        deadlines.append(h["individual_started"] + timing["hurley_warning_ms"])
                    deadlines.append(self.now_ms + timing["hurley_team_ms"] - h["team_ms"])
                elif h["contestable"] and h["flight_started"] is not None:
                    deadlines.append(h["flight_started"] + timing["contestable_reset_ms"])
            future = [d for d in deadlines if d > self.now_ms]
            step = min(future) - self.now_ms
            for key, h in self.hurleys.items():
                if self.balls[key]["controller"]:
                    h["team_ms"] += step
            self.now_ms += step
            self.period_elapsed_ms += step
            crown_returns = []
            for key, ball in self.balls.items():
                if ball["timeout_until"] is not None:
                    if self.now_ms >= ball["timeout_until"]:
                        self._release(key)
                        self._emit("snipe_release", ball=key)
                    elif self.now_ms == ball["timeout_until"] - timing["snipe_warning_ms"]:
                        self._emit("snipe_warning", remaining_ms=timing["snipe_warning_ms"])
                if ball["crown_deadline"] is not None and self.now_ms >= ball["crown_deadline"]:
                    self._release(key)
                    crown_returns.append(key)
                    self._emit("crown_safety_return", ball=key, mark=ball["crown_mark"])
            if crown_returns:
                self.pause("crown_safety")
            for player in self.players.values():
                if player["removed_until"] is not None and self.now_ms >= player["removed_until"]:
                    player["removed_until"] = None
                    self._emit("removal_expired", player=player["id"])
            for key, h in self.hurleys.items():
                if h["contestable"] and h["flight_started"] is not None and self.now_ms - h["flight_started"] >= timing["contestable_reset_ms"]:
                    h.update(team=None, team_ms=0, flight_started=None, contestable=False, individual_reset=True)
                    self._emit("hurley_flight_reset", ball=key)
            self._check_hurleys()
            if self.phase == "regulation" and self.balls["snitch"]["dead_reason"] == "scheduled_release" and self.now_ms >= timing["snitch_release_ms"]:
                self._release("snitch")
                self._emit("snitch_release")
            if self.phase != "donnybrook" and self.period_elapsed_ms >= duration:
                if self.phase == "regulation" and self.quarter < timing["quarters"]:
                    self.status = "quarter_break"
                    self._emit("quarter_horn", quarter=self.quarter)
                    self._secure_balls()
                else:
                    self._end(f"{self.phase}_horn")
        return self.now_ms - start

    def _secure_balls(self):
        for key, ball in self.balls.items():
            if ball["play_state"] == "live":
                self._dead(key, "stoppage")
        self.hurleys = {key: self._fresh_hurley() for key in self.hurleys}

    def pause(self, reason="official"):
        if self.status != "live":
            raise RulesError("only live play may pause")
        self.status = "paused"
        self._secure_balls()
        self._emit("stoppage", reason=reason)

    def resume(self):
        if self.status not in ("paused", "quarter_break", "phase_break"):
            raise RulesError("there is no resumable stoppage")
        if any(p["status"] == "pending" for p in self.penalties):
            raise RulesError("administer pending penalties before the next horn")
        if self.status == "quarter_break":
            self.quarter += 1
            self.period_elapsed_ms = 0
        self.status = "live"
        for key, ball in self.balls.items():
            if ball["phase_status"] == "active" and ball["dead_reason"] == "stoppage":
                self._release(key)
        self._emit("resume", phase=self.phase, quarter=self.quarter)

    def restart(self, ball_id, player_id):
        """Host positions the eligible receiver at the bible's protected mark."""
        ball = self._ball(ball_id)
        player = self._player(player_id)
        if self.status != "live" or ball["phase_status"] != "active" or ball["dead_reason"] not in ("score", "hurley_foul", "penalty"):
            raise RulesError("ball is not awaiting a possession restart")
        if player["team"] != ball["restart_team"] or not self.eligible(player_id, ball_id):
            raise RulesError("invalid restart receiver")
        if ball["dead_reason"] == "score" and self.phase != "donnybrook" and player["role"] != "netminder":
            raise RulesError("scoring-ball restart belongs to defending Netminder")
        if ball["type"] in ("quaffle", "quark") and self._carried(player_id):
            raise RulesError("restart receiver must first release the carried ball")
        self._release(ball_id)
        if ball["type"] in ("quaffle", "quark"):
            self.possess(player_id, ball_id)
            ball["protection_until"] = self.now_ms + self.config["timing"]["restart_protection_ms"]
        self._emit("protected_restart", ball=ball_id, player=player_id)

    def crown_exit(self, ball_id, mark, responsible_player=None, *, deliberate_delay=False):
        if not self.config.get("enable_legacy_crown_exit", False):
            raise RulesError("closed pyramid net: roof contact rebounds, never a Crown exit")
        ball = self._live_ball(ball_id)
        if ball["type"] in ("snipe", "snitch"):
            raise RulesError("winged balls use chase-envelope recall, not No Crown")
        if len(mark) != 3 or not all(isinstance(v, (int, float)) for v in mark):
            raise RulesError("Crown Mark must have three coordinates in feet")
        if responsible_player is not None:
            self._player(responsible_player)
        self._dead(ball_id, "crown")
        ball.update(crown_mark=list(mark), crown_deadline=self.now_ms + self.config["timing"]["crown_return_ms"])
        if ball["type"] == "bludger":
            self.hurleys[ball_id] = self._fresh_hurley()
        if responsible_player is not None:
            self.record_penalty(responsible_player, "Dead-Roof Delay" if deliberate_delay else "No Crown",
                                "moderate" if deliberate_delay else "minor", ball_id)
        self._emit("crown_exit", ball=ball_id, mark=list(mark), responsible_player=responsible_player)

    def crown_return(self, ball_id):
        ball = self._ball(ball_id)
        if self.status != "live" or ball["dead_reason"] != "crown":
            raise RulesError("ball is not awaiting neutral crown return")
        self._release(ball_id)
        self._emit("crown_return", ball=ball_id, mark=ball["crown_mark"])

    def recall_chase(self, ball_id):
        ball = self._live_ball(ball_id)
        if ball["type"] not in ("snipe", "snitch"):
            raise RulesError("only chase balls may use envelope recall")
        self._release(ball_id)
        self._emit("chase_recall", ball=ball_id)

    def record_penalty(self, player_id, reason, severity, ball_id=None, committed_ms=None):
        if player_id not in self.players or severity not in ("minor", "moderate", "serious", "severe", "catastrophic"):
            raise RulesError("invalid penalty")
        committed_ms = self.now_ms if committed_ms is None else _integer(committed_ms, "committed_ms")
        if committed_ms > self.now_ms:
            raise RulesError("penalty cannot predate future conduct")
        if ball_id is not None:
            self._ball(ball_id)
        penalty = dict(id=len(self.penalties) + 1, player=player_id, reason=reason, severity=severity,
                       ball=ball_id, committed_ms=committed_ms, status="pending")
        self.penalties.append(penalty)
        self._emit("penalty_pending", penalty=deepcopy(penalty))
        if severity in ("serious", "severe", "catastrophic") and self.status == "live":
            self.pause("dangerous_conduct")
        return penalty["id"]

    def resolve_penalty(self, penalty_id, *, disposition, apply_removal=True):
        """Explicit host adjudication. Shot results enter certify as score adjustments.

        disposition is a nonempty audit explanation, including completed remedy
        or captain's declined restoration. A removal/ejection cannot be declined.
        """
        matches = [p for p in self.penalties if p["id"] == penalty_id and p["status"] == "pending"]
        if not matches or not disposition or self.status == "live":
            raise RulesError("resolve a pending penalty at a stoppage with a disposition")
        penalty = matches[0]
        if not apply_removal and penalty["severity"] in ("serious", "severe"):
            raise RulesError("removal and ejection cannot be declined")
        player = self.players[penalty["player"]]
        if penalty["severity"] == "serious":
            player["removed_until"] = self.now_ms + self.config["timing"]["removal_ms"]
            if self.phase == "donnybrook":
                player["donnybrook_excluded"] = True
                player["removed_until"] = None
        elif penalty["severity"] == "severe":
            player["ejected"] = True
        elif penalty["severity"] == "catastrophic":
            raise RulesError("catastrophic forfeit review requires external adjudication")
        penalty.update(status="resolved", disposition=disposition)
        self._emit("penalty_resolved", penalty=deepcopy(penalty))

    def certify(self, adjustments=()):
        """Apply reviewed pre-termination corrections/remedies and resolve ending.

        Adjustment: {team:'A', delta:37, reason:'penalty shot', committed_ms:...}
        Negative corrections void points. No score may become negative.
        """
        if self.status != "review" or self.ending is None:
            raise RulesError("no provisional ending to certify")
        if any(p["status"] == "pending" and p["committed_ms"] <= self.ending["at_ms"] for p in self.penalties):
            raise RulesError("resolve every pre-termination penalty before certification")
        projected = dict(self.scores)
        adjustments = list(adjustments)
        for adjustment in adjustments:
            team, delta = adjustment["team"], adjustment["delta"]
            self._opponent(team)
            when = _integer(adjustment["committed_ms"], "committed_ms")
            if not isinstance(delta, int) or isinstance(delta, bool) or not adjustment.get("reason") or when > self.ending["at_ms"]:
                raise RulesError("invalid certification adjustment")
            projected[team] += delta
        if min(projected.values()) < 0:
            raise RulesError("certified score cannot be negative")
        self.scores = projected
        for adjustment in adjustments:
            self._emit("score_adjustment", **adjustment)
        reason = self.ending["reason"]
        if reason == "snitch":
            player = self.players[self.ending["catcher"]]
            if player["role"] == "scout":
                self.reckoner = player["id"]
            return self._finish(self.leader or self.ending["catching_team"])
        if reason == "donnybrook":
            return self._finish(self.ending["winning_team"])
        if reason == "regulation_horn":
            if self.margin >= self.config["ending"]["regulation_margin"]:
                return self._finish(self.leader)
            self._enter_phase("overtime")
        elif reason == "overtime_margin":
            if self.margin >= self.config["ending"]["overtime_margin"]:
                return self._finish(self.leader)
            if self.period_elapsed_ms < self.config["timing"]["overtime_ms"]:
                self.ending = None
                self.status = "live"
                for key, ball in self.balls.items():
                    if ball["dead_reason"] == "stoppage":
                        self._release(key)
                self._emit("overtime_resume_after_review")
            elif self.margin:
                return self._finish(self.leader)
            else:
                self._enter_phase("donnybrook")
        elif reason == "overtime_horn":
            if self.margin:
                return self._finish(self.leader)
            self._enter_phase("donnybrook")
        return None

    def overturn_snitch(self, reason):
        if self.status != "review" or not self.ending or self.ending["reason"] != "snitch" or not reason:
            raise RulesError("no provisional Snitch catch to overturn")
        self.scores[self.ending["catching_team"]] -= self.ending["catch_points"]
        self.ending = None
        self.status = "paused"
        self._release("snitch")
        self._secure_balls()
        self._emit("snitch_overturned", reason=reason)

    def _enter_phase(self, phase):
        self.phase, self.status, self.period_elapsed_ms, self.ending = phase, "phase_break", 0, None
        for key, ball in self.balls.items():
            active = phase == "overtime" or ball["type"] in ("quark", "snipe")
            ball.update(phase_status="active" if active else "removed", timeout_until=None, crown_deadline=None)
            self._dead(key, "stoppage" if active else "removed")
        self.hurleys = {key: self._fresh_hurley() for key in self.hurleys}
        if phase == "donnybrook":
            for player in self.players.values():
                if player["removed_until"] is not None:
                    player.update(donnybrook_excluded=True, removed_until=None)
        self._emit("phase_change", phase=phase)

    def _finish(self, winner):
        self.status, self.winner = "complete", winner
        self._secure_balls()
        self._emit("match_certified", winner=winner, scores=dict(self.scores), reckoner=self.reckoner)
        return winner

    def snapshot(self):
        """JSON-serializable public state; event log intentionally separate."""
        return deepcopy(dict(rules_version=self.config["rules_version"], phase=self.phase,
                             status=self.status, quarter=self.quarter, live_ms=self.now_ms,
                             period_elapsed_ms=self.period_elapsed_ms, scores=self.scores,
                             winner=self.winner, reckoner=self.reckoner, ending=self.ending,
                             balls=self.balls, players=self.players, hurleys=self.hurleys,
                             penalties=self.penalties))
