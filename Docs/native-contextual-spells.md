# Original contextual sporting spell adapters

The UE5.8 standalone runtime now provides an adapter for each of its 31 stable
spell-menu actions. The final eight use a deliberately bounded original spell
workshop and Ancient Magic resource. This is not the Hogwarts Legacy spell
implementation, a general scene editor, or a claim of base-game feature parity.
The workshop layout, tuning and construction permissions are provisional sport
adaptations, not additions to the BB-0 rulebook.

Each admitted human receives one named personal bay along the arena side nets.
The bay remains attached to that rider's identity across a position change;
resources do not transfer to the replaced CPU slot. At most 16 bays and one
construct per bay exist. Departure destroys that rider's bay; a real rematch
clears every bay and meter. CPU wandwork does not earn or spend this resource yet.

## Six workshop actions

- **Alohomora:** aim at your own locker within 9 metres to unlock it.
- **Conjuring Spell:** aim at that unlocked locker to create one practice
  construct. A second cast cannot create additional objects.
- **Altering Spell:** aim at your intact construct to cycle its original cube,
  sphere and cylinder forms. Its size and collision permissions stay fixed.
- **Wingardium Leviosa:** aim at your intact construct to lift or lower it
  1.6 metres inside its bay, travelling at 1.6 metres per live second.
- **Reparo:** aim at your damaged or broken construct to restore its 100-point
  integrity and gather it back to its bay. Ordinary damaging casts can damage
  your own construct; practice objects never earn Ancient Magic charge.
- **Evanesco:** aim at your construct to remove it. Its locker remains unlocked.

The construct and bay are query-only wand targets: they ignore rider and ball
collision, never become arbitrary world geometry, and cannot alter any official
ball, goal, net, floor, environment asset or opposing player's object. Other
riders' bays do not obstruct ordinary rider-targeted wand rays. Labels show the
owner, current available workshop action and charge; native spell feedback
explains a denied permission or missing target. Failed workshop requests do not
spend a cooldown. Six workshop actions have a 9-metre target limit.

## Ancient Magic resource and physical throw

A legal, accepted and applied hit on an opposing rider earns 20 charge, capped
at 100. Misses, Protego blocks, friendly contact, illegal contact and workshop
objects earn none. Ancient Magic and Ancient Magic Throw never refund their own
charge. The resource is held by the authoritative workshop actor and replicated;
clients submit only the existing spell choice and aim request.

**Ancient Magic** spends 100 charge when released, including a miss or Protego
block. Its sporting pulse does 55 vitality damage and applies the existing
1,200 cm/s push within 26 metres, with a four-second shared cooldown. It is not
an execution or a cinematic base-game finisher. Ordinary knockout recovery and
BB-0 conduct adjudication apply.

**Ancient Magic Throw** needs 25 charge, an intact available owned construct
within 6 metres and a server-acquired rider target within 30 metres. A denied
launch spends neither charge nor cooldown. The accepted launch binds the exact
caster, selected target and cast-time conduct receipt, spends charge, and sends
the construct along a real ballistic path. Authority advances swept sphere
collision in live time; intervening world geometry or a different rider consumes
the construct without transferring the attack to another victim. The selected
rider takes 35 vitality damage plus push on contact, unless Protego blocks it.
The broken construct returns to its bay for Reparo. This is a bounded,
single-target adaptation; it cannot pick up official balls or scenery.

Throw flight and levitation freeze through stoppages and protected shots. A
phase boundary cancels outstanding throws, and ownership-slot changes cancel a
stale trajectory. Before any delayed impact effect, the combat policy verifies
the original unresolved receipt, exact caster/target, live eligibility and
expiry. The same native hit path applies the effect before recording any foul.
Regulation head impacts trigger review; Bloodbroom permits head impacts while
retaining the remaining shared BB-0 rules. Protego still blocks these two actions
in both modes.

## Validation

`Tools/test_native_contextual_spells.py` plans 20 ordinary-input PIE checks per
mode, with atomic receipts at `.local/native-contextual-spells-{variant}-results.json`.
Run with `{"variant":"regulation","max_wall_seconds":540}` and a separate fresh
`bloodbroom` session. It covers real locker ownership, bounded construction,
shape/permission preservation, moving/stopped levitation, damage and repair,
protected equipment, meter earning/cap/spending, physical flight/stoppage,
Protego, mode-specific head impacts and departing-player cleanup. Only fixture
transforms, component ticks, local-player lifecycle and world time dilation are
arranged; workshop, resource, spell, conduct, score and rule state are never
written. Syntax checks and `--list` are not runtime success.

The portable combat suite passes 40 scenarios, including two new read-only
pending-hit checks for immutable attack identity, single use, live admission,
expiry, unavailable/replaced participants and phase reset. The integrated UE5.8 editor module compiled successfully on 2026-09-15. These new PIE runs, network replication, rendered/package checks and a genuine rematch remain pending until their actual receipts pass.
