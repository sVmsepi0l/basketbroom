# BB-0 contact and spell direction

User direction recorded **2026/09/12**. These later instructions supersede the original bible's provisional five-effect alpha spell whitelist. The [original bible](basketbroom_rules_bible_v0.1.md) remains unchanged as the historical source; this note does not silently replace its penalty ladder or invent missing timings.

## Confirmed by the user

- All Hogwarts Legacy base-game spells are available for offensive and defensive use, subject to the following prohibitions.
- Unforgivable Curses are prohibited, except in **Bloodbroom**.
- At most **three teammates may mob one opponent**.
- No Stupefy or other stun after a **visibly confirmed impediment hit**.
- No headshots, except in **Bloodbroom**.
- No physical holding.
- An illegal hit **takes effect first; the penalty follows**. A legality check must not silently erase the hit or turn it into a harmless miss.

Bloodbroom has exactly two confirmed exceptions: Unforgivables and headshots. Its mobbing limit, post-impediment stun prohibition and physical-holding prohibition still apply. Those exceptions do not imply a general suspension of every other rule.

The precise mobbing membership/window, qualifying impediment and stun effects, visible-confirmation criterion, protection expiry, head-hit geometry, holding detection and penalty severity are **not yet confirmed**. Neither the old six-second alpha spell cooldown nor a newly chosen duration becomes a BB-0 rule by appearing in a prototype.

## Verified base-game catalog

[Rules/spell_catalog.json](../Rules/spell_catalog.json) contains **29 spell actions**, **two Ancient Magic actions**, and **three beast tools**, accounting for the familiar 34 spell-menu entries. Twenty-three of the 29 spells use ordinary spell slots; the remaining six are basic, defensive, dedicated-button or contextual actions. This counts repertoire after unlocks, not availability on a new save.

- **Essential:** Basic Cast, Protego, Stupefy, Revelio, Alohomora, Petrificus Totalus.
- **Force:** Accio, Depulso, Descendo, Flipendo.
- **Control:** Arresto Momentum, Glacius, Levioso, Transformation.
- **Damage:** Incendio, Confringo, Diffindo, Expelliarmus, Bombarda.
- **Utility:** Lumos, Disillusionment, Wingardium Leviosa, Reparo.
- **Room of Requirement:** Conjuring Spell, Altering Spell, Evanesco.
- **Unforgivable:** Avada Kedavra, Crucio, Imperio.

Ancient Magic and Ancient Magic Throw are separate native actions. Beast Petting Brush, Beast Feed and Nab-Sack are tools, despite appearing in the spell menu. Potions, combat plants, gear traits, dodge talents, mounts and Floo travel are not additional spells. Their sport treatment is not settled simply by permitting all spells. Utility and Room of Requirement spells also have real target/context requirements; listing them does not make arbitrary arena objects repairable, conjurable or transformable.

The catalog was checked against the closed Creator Kit's `PhoenixGameData.sqlite` through a read-only immutable SQLite connection, English `MAIN-enUS.bin` display/tutorial strings, and existing tool assets. The database hash remained unchanged. Source hashes and per-spell database evidence are included in the JSON. `AllowInUI` alone is not a complete roster filter: it excludes contextual essentials and includes several separate Ancient Magic finisher implementations. Enemy spells, unused records, debug entries, upgrades and animation variants are not extra player spells.

Important internal mappings are Bombarda → `Expulso`, Imperio → `Imperius`, Wingardium Leviosa → `Wingardium`, Evanesco → `Vanishment`, Ancient Magic Throw → `Oppugno`, Altering Spell → `Transformation`, and combat Transformation → `TransformationOverland`. Basic Cast uses the native `{Stupefy}` input token. The English gameplay/tutorial text explicitly identifies the displayed **Stupefy** as a counterattack after holding Protego through a successful block. Its precise internal Stupefy-family record binding still needs live reflection; an identifier in this catalog is not a verified native casting API.

Official developer material corroborates Basic Cast, Protego, Accio, Incendio and stealth/Petrificus gameplay. The official game FAQ explicitly confirms that all three Unforgivables can be learned. The full enumeration and internal aliases above come from the installed game data; no complete authoritative web roster was found. [Avalanche gameplay account](https://blog.playstation.com/?p=362688), [Avalanche controls account](https://blog.playstation.com/?p=364995), [official game FAQ](https://www.harrypotter.com/features/questions-answered-about-hogwarts-legacy-game).

## Impediment terminology needs a decision

**Impedimenta is not in the verified base-game player roster.** Neither inspected spell table has an Impedimenta record, and the inspected English localization and ordinary spell directory have no matching entry. Arresto Momentum is present, but it is a distinct spell: the official encyclopedia identifies Impedimenta as the Impediment Jinx and Arresto Momentum as the Braking Charm. Those lore pages do not establish game availability. [Impediment Jinx](https://www.harrypotter.com/fact-file/spells/the-impediment-jinx), [Braking Charm](https://www.harrypotter.com/fact-file/spells/the-braking-charm).

**Proposal, not adopted:** use Arresto Momentum for the first prototype movement-impediment effect, then decide whether the rule covers it alone or also Glacius, Levioso and other control effects. Alternatively, add an explicitly separate Impedimenta implementation. Do not silently rename Arresto Momentum or describe a mod-added spell as base game. The rule's protected interval also needs a start/end criterion and a decision about a stun already in flight before the impediment became visible.

## First native combat slice — implementation proposal

The implemented UE5 sporting effects, exact controls, provisional policies and
remaining adapters are tracked in [native wandplay](native-wandplay.md). The
paragraphs below record the original implementation recommendation, not a claim
that the base game's full combat and world interaction systems are reproduced.

Start with **Basic Cast, Protego, Stupefy and Arresto Momentum**, preserving their damage, guard, counter-stun and slowing roles. This is an incremental implementation, not a reduced allowed-spell roster. Add Accio/Depulso displacement and Expelliarmus disarming after reliable hit attribution and contact enforcement; broader elemental, transformation, stealth and utility interactions need their own target implementations.

Use authoritative hit records containing caster, target, team, spell ID, actual hit region, effect result and match time. Replicate a clear impediment effect/indicator. Resolve the real hit effect, then assess its foul and issue one penalty package. Mobbing and visible-confirmation rules must use an explicit documented prototype policy until their unresolved definitions are decided. Do not describe every nearby teammate as an aggressor or use an invisible server flag as proof that a player visibly recognized an impediment.

Acceptance cases should cover legal blocks/counters, an illegal stun still taking effect before its sanction, a fourth teammate's illegal impact, ordinary versus Bloodbroom headshots/Unforgivables, holding remaining illegal in both modes, one combined package for a multi-definition foul, and replicated late/duplicate events producing one effect and one penalty. Missing free/penalty-shot execution must remain visibly outstanding and prevent premature certification.

## Penalty mapping — provisional recommendation

The existing ladder is `Minor`, `Moderate`, `Serious`, `Severe`, `Catastrophic` in `BBRuleEngine.h`. Bible §§6.2–6.3 prescribe remedies as well as removals; §6.6 explicitly assigns ordinary Unforgivables to Catastrophic. The new user direction confirms effect-before-penalty, not a new severity scale.

- **Ordinary Unforgivable:** retain the bible's Catastrophic safety suspension and forfeit review. A review is not an automatic declared forfeit. Bloodbroom removes this particular prohibition.
- **Dangerous headshot:** propose Severe, with ejection/report. This fixed starting tier is not user-confirmed; anatomy, intent, accident and indirect-hit treatment need resolution. Bloodbroom removes the headshot prohibition.
- **Stun after confirmed impediment:** propose Serious, requiring both a penalty shot and temporary removal. A removal-only implementation does not complete that remedy. Existing alpha removal timing remains provisional.
- **Mobbing or physical holding:** propose Moderate as an ordinary starting tier, with existing escalation for dangerous or repeated conduct. Its free-shot/possession remedy must not be silently waived.

The selected **limited playtest interface** records the actual hit effect, pauses, and shows **PLAYTEST REFEREE** with a pending decision. The host can choose **F7: Moderate with a real scoring-ball possession award**, or **F9: Severe with ejection**. These are manual prototype referee tools, not automatic foul-to-severity assignments or user-confirmed penalty tiers. **F8/Serious now starts the shared native penalty-shot and live-time removal flow**, described in [penalty shots](native-penalty-shots.md). Full adjudication, terminal-event restorative shots and Catastrophic remedies remain unresolved in this interface; the control plan does not establish that their missing outcomes have been implemented or validated.

Do not auto-complete a penalty merely because shot or restart execution is missing. One act satisfying several definitions receives one proportionate package, consistent with bible §6.2. The provisional recommendations above remain separate from the host's limited playtest choices.

Additional suggestions, all **unadopted**: standardize the visible protection indicator; end protection on an explicit recovery event; publish equal tournament loadout/talent/consumable settings; and show the hit, foul reason and outstanding remedy together so both teams can understand enforcement.

No Creator Kit session was launched, no installed file or existing bible was changed, and this catalog does not claim that every listed spell is already implemented in either Basketbroom runtime.
