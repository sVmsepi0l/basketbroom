# bb-0 contact and spell direction

user direction recorded **2026/09/12**. these later instructions supersede the original bible's provisional five-effect alpha spell whitelist. the [original bible](basketbroom_rules_bible_v0.1.md) remains unchanged as the historical source; this note does not silently replace its penalty ladder or invent missing timings.

## confirmed by the user

- all hogwarts legacy base-game spells are available for offensive and defensive use, subject to the following prohibitions.
- unforgivable curses are prohibited, except in **Bloodbroom**.
- at most **three teammates may mob one opponent**.
- no stupefy or other stun after a **visibly confirmed impediment hit**.
- no headshots, except in **Bloodbroom**.
- no physical holding.
- an illegal hit **takes effect first; the penalty follows**. a legality check must not silently erase the hit or turn it into a harmless miss.

bloodbroom has exactly two confirmed exceptions: unforgivables and headshots. its mobbing limit, post-impediment stun prohibition and physical-holding prohibition still apply. those exceptions do not imply a general suspension of every other rule.

the precise mobbing membership/window, qualifying impediment and stun effects, visible-confirmation criterion, protection expiry, head-hit geometry, holding detection and penalty severity are **not yet confirmed**. neither the old six-second alpha spell cooldown nor a newly chosen duration becomes a bb-0 rule by appearing in a prototype.

## verified base-game catalog

[Rules/spell_catalog.json](../Rules/spell_catalog.json) contains **29 spell actions**, **two ancient magic actions**, and **three beast tools**, accounting for the familiar 34 spell-menu entries. twenty-three of the 29 spells use ordinary spell slots; the remaining six are basic, defensive, dedicated-button or contextual actions. this counts repertoire after unlocks, not availability on a new save.

- **Essential:** basic cast, protego, stupefy, revelio, alohomora, petrificus Totalus.
- **Force:** accio, depulso, descendo, Flipendo.
- **Control:** arresto momentum, glacius, levioso, Transformation.
- **Damage:** incendio, confringo, diffindo, expelliarmus, Bombarda.
- **Utility:** lumos, disillusionment, wingardium leviosa, Reparo.
- **room of Requirement:** conjuring spell, altering spell, Evanesco.
- **Unforgivable:** avada kedavra, crucio, Imperio.

ancient magic and ancient magic throw are separate native actions. beast petting brush, beast feed and nab-sack are tools, despite appearing in the spell menu. potions, combat plants, gear traits, dodge talents, mounts and floo travel are not additional spells. their sport treatment is not settled simply by permitting all spells. utility and room of requirement spells also have real target/context requirements; listing them does not make arbitrary arena objects repairable, conjurable or transformable.

the catalog was checked against the closed creator kit's `PhoenixGameData.sqlite` through a read-only immutable sqlite connection, english `MAIN-enUS.bin` display/tutorial strings, and existing tool assets. the database hash remained unchanged. source hashes and per-spell database evidence are included in the JSON. `allowinui` alone is not a complete roster filter: it excludes contextual essentials and includes several separate ancient magic finisher implementations. enemy spells, unused records, debug entries, upgrades and animation variants are not extra player spells.

important internal mappings are bombarda → `expulso`, imperio → `imperius`, wingardium leviosa → `wingardium`, evanesco → `vanishment`, ancient magic throw → `oppugno`, altering spell → `transformation`, and combat transformation → `TransformationOverland`. basic cast uses the native `{stupefy}` input token. the english gameplay/tutorial text explicitly identifies the displayed **stupefy** as a counterattack after holding protego through a successful block. its precise internal stupefy-family record binding still needs live reflection; an identifier in this catalog is not a verified native casting API.

official developer material corroborates basic cast, protego, accio, incendio and stealth/Petrificus gameplay. the official game faq explicitly confirms that all three unforgivables can be learned. the full enumeration and internal aliases above come from the installed game data; no complete authoritative web roster was found. [avalanche gameplay account](https://blog.playstation.com/?p=362688), [avalanche controls account](https://blog.playstation.com/?p=364995), [official game FAQ](https://www.harrypotter.com/features/questions-answered-about-hogwarts-legacy-game).

## impediment terminology needs a decision

**impedimenta is not in the verified base-game player roster.** neither inspected spell table has an impedimenta record, and the inspected english localization and ordinary spell directory have no matching entry. arresto momentum is present, but it is a distinct spell: the official encyclopedia identifies impedimenta as the impediment jinx and arresto momentum as the braking Charm. those lore pages do not establish game availability. [impediment Jinx](https://www.harrypotter.com/fact-file/spells/the-impediment-jinx), [braking Charm](https://www.harrypotter.com/fact-file/spells/the-braking-charm).

**proposal, not adopted:** use arresto momentum for the first prototype movement-impediment effect, then decide whether the rule covers it alone or also glacius, levioso and other control effects. alternatively, add an explicitly separate impedimenta implementation. do not silently rename arresto momentum or describe a mod-added spell as base game. the rule's protected interval also needs a start/end criterion and a decision about a stun already in flight before the impediment became visible.

## first native combat slice — implementation proposal

the implemented ue5 sporting effects, exact controls, provisional policies and
remaining adapters are tracked in [native wandplay](native-wandplay.md). the
paragraphs below record the original implementation recommendation, not a claim
that the base game's full combat and world interaction systems are reproduced.

start with **basic cast, protego, stupefy and arresto momentum**, preserving their damage, guard, counter-stun and slowing roles. this is an incremental implementation, not a reduced allowed-spell roster. add Accio/Depulso displacement and expelliarmus disarming after reliable hit attribution and contact enforcement; broader elemental, transformation, stealth and utility interactions need their own target implementations.

use authoritative hit records containing caster, target, team, spell id, actual hit region, effect result and match time. replicate a clear impediment effect/indicator. resolve the real hit effect, then assess its foul and issue one penalty package. mobbing and visible-confirmation rules must use an explicit documented prototype policy until their unresolved definitions are decided. do not describe every nearby teammate as an aggressor or use an invisible server flag as proof that a player visibly recognized an impediment.

acceptance cases should cover legal blocks/counters, an illegal stun still taking effect before its sanction, a fourth teammate's illegal impact, ordinary versus bloodbroom headshots/Unforgivables, holding remaining illegal in both modes, one combined package for a multi-definition foul, and replicated late/duplicate events producing one effect and one penalty. missing free/penalty-shot execution must remain visibly outstanding and prevent premature certification.

## penalty mapping — provisional recommendation

the existing ladder is `minor`, `moderate`, `serious`, `severe`, `catastrophic` in `BBRuleEngine.h`. bible §§6.2–6.3 prescribe remedies as well as removals; §6.6 explicitly assigns ordinary unforgivables to Catastrophic. the new user direction confirms effect-before-penalty, not a new severity scale.

- **ordinary Unforgivable:** retain the bible's catastrophic safety suspension and forfeit review. a review is not an automatic declared forfeit. bloodbroom removes this particular prohibition.
- **dangerous headshot:** propose severe, with ejection/report. this fixed starting tier is not user-confirmed; anatomy, intent, accident and indirect-hit treatment need resolution. bloodbroom removes the headshot prohibition.
- **stun after confirmed impediment:** propose serious, requiring both a penalty shot and temporary removal. a removal-only implementation does not complete that remedy. existing alpha removal timing remains provisional.
- **mobbing or physical holding:** propose moderate as an ordinary starting tier, with existing escalation for dangerous or repeated conduct. its free-shot/possession remedy must not be silently waived.

the selected **limited playtest interface** records the actual hit effect, pauses, and shows **playtest referee** with a pending decision. the host can choose **F7: moderate with a real scoring-ball possession award**, or **F9: severe with ejection**. these are manual prototype referee tools, not automatic foul-to-severity assignments or user-confirmed penalty tiers. **F8/Serious now starts the shared native penalty-shot and live-time removal flow**, described in [penalty shots](native-penalty-shots.md). full adjudication, terminal-event restorative shots and catastrophic remedies remain unresolved in this interface; the control plan does not establish that their missing outcomes have been implemented or validated.

do not auto-complete a penalty merely because shot or restart execution is missing. one act satisfying several definitions receives one proportionate package, consistent with bible §6.2. the provisional recommendations above remain separate from the host's limited playtest choices.

additional suggestions, all **unadopted**: standardize the visible protection indicator; end protection on an explicit recovery event; publish equal tournament loadout/talent/consumable settings; and show the hit, foul reason and outstanding remedy together so both teams can understand enforcement.

no creator kit session was launched, no installed file or existing bible was changed, and this catalog does not claim that every listed spell is already implemented in either basketbroom runtime.
