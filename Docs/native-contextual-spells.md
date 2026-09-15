# original contextual sporting spell adapters

the UE5.8 standalone runtime now provides an adapter for each of its 31 stable
spell-menu actions. the final eight use a deliberately bounded original spell
workshop and ancient magic resource. this is not the hogwarts legacy spell
implementation, a general scene editor, or a claim of base-game feature parity.
the workshop layout, tuning and construction permissions are provisional sport
adaptations, not additions to the bb-0 rulebook.

each admitted human receives one named personal bay along the arena side nets.
the bay remains attached to that rider's identity across a position change;
resources do not transfer to the replaced cpu slot. at most 16 bays and one
construct per bay exist. departure destroys that rider's bay; a real rematch
clears every bay and meter. cpu wandwork does not earn or spend this resource yet.

## six workshop actions

- **Alohomora:** aim at your own locker within 9 metres to unlock it.
- **conjuring Spell:** aim at that unlocked locker to create one practice
  construct. a second cast cannot create additional objects.
- **altering Spell:** aim at your intact construct to cycle its original cube,
  sphere and cylinder forms. its size and collision permissions stay fixed.
- **wingardium Leviosa:** aim at your intact construct to lift or lower it
  1.6 metres inside its bay, travelling at 1.6 metres per live second.
- **Reparo:** aim at your damaged or broken construct to restore its 100-point
  integrity and gather it back to its bay. ordinary damaging casts can damage
  your own construct; practice objects never earn ancient magic charge.
- **Evanesco:** aim at your construct to remove it. its locker remains unlocked.

the construct and bay are query-only wand targets: they ignore rider and ball
collision, never become arbitrary world geometry, and cannot alter any official
ball, goal, net, floor, environment asset or opposing player's object. other
riders' bays do not obstruct ordinary rider-targeted wand rays. labels show the
owner, current available workshop action and charge; native spell feedback
explains a denied permission or missing target. failed workshop requests do not
spend a cooldown. six workshop actions have a 9-metre target limit.

## ancient magic resource and physical throw

a legal, accepted and applied hit on an opposing rider earns 20 charge, capped
at 100. misses, protego blocks, friendly contact, illegal contact and workshop
objects earn none. ancient magic and ancient magic throw never refund their own
charge. the resource is held by the authoritative workshop actor and replicated;
clients submit only the existing spell choice and aim request.

**ancient magic** spends 100 charge when released, including a miss or protego
block. its sporting pulse does 55 vitality damage and applies the existing
1,200 cm/s push within 26 metres, with a four-second shared cooldown. it is not
an execution or a cinematic base-game finisher. ordinary knockout recovery and
bb-0 conduct adjudication apply.

**ancient magic throw** needs 25 charge, an intact available owned construct
within 6 metres and a server-acquired rider target within 30 metres. a denied
launch spends neither charge nor cooldown. the accepted launch binds the exact
caster, selected target and cast-time conduct receipt, spends charge, and sends
the construct along a real ballistic path. authority advances swept sphere
collision in live time; intervening world geometry or a different rider consumes
the construct without transferring the attack to another victim. the selected
rider takes 35 vitality damage plus push on contact, unless protego blocks it.
the broken construct returns to its bay for Reparo. this is a bounded,
single-target adaptation; it cannot pick up official balls or scenery.

throw flight and levitation freeze through stoppages and protected shots. a
phase boundary cancels outstanding throws, and ownership-slot changes cancel a
stale trajectory. before any delayed impact effect, the combat policy verifies
the original unresolved receipt, exact caster/target, live eligibility and
expiry. the same native hit path applies the effect before recording any foul.
regulation head impacts trigger review; bloodbroom permits head impacts while
retaining the remaining shared bb-0 rules. protego still blocks these two actions
in both modes.

## validation

`Tools/test_native_contextual_spells.py` plans 20 ordinary-input pie checks per
mode, with atomic receipts at `.local/native-contextual-spells-{variant}-results.json`.
run with `{"variant":"regulation","max_wall_seconds":540}` and a separate fresh
`bloodbroom` session. it covers real locker ownership, bounded construction,
shape/permission preservation, moving/stopped levitation, damage and repair,
protected equipment, meter earning/cap/spending, physical flight/stoppage,
protego, mode-specific head impacts and departing-player cleanup. only fixture
transforms, component ticks, local-player lifecycle and world time dilation are
arranged; workshop, resource, spell, conduct, score and rule state are never
written. syntax checks and `--list` are not runtime success.

the portable combat suite passes 40 scenarios, including two new read-only
pending-hit checks for immutable attack identity, single use, live admission,
expiry, unavailable/replaced participants and phase reset. the integrated UE5.8 editor module compiled successfully on 2026/09/15. these new pie runs, network replication, rendered/package checks and a genuine rematch remain pending until their actual receipts pass.
