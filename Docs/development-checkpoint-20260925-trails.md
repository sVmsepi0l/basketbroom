# September 25: human authoring and broom-trail checkpoint

Recovered after the user's reboot. The accepted desktop package remains the
earlier September 25 build recorded in `validation-package-20260925.json`.

The UE 5.8 editor target compiles with the optional human cosmetic layer,
three bounded broom-trail filaments and the pause-menu HSV color picker.
All 16 portable C++ trail-policy cases passed. Actual picker, trail rendering,
network, and packaged acceptance are still pending at this checkpoint.

Two adult MetaHuman designs and Medium assemblies are saved in the isolated,
ignored `.local/CharacterLab` project. Each has a seated flight animation and
garment-only mint/copper material variants. Both face/body poses now align in
the transient render review after reinitializing the genuine Face animation
class following Body pose evaluation. This editor-specific fix does not yet
certify game animation. The playable project still uses its existing riders;
human activation, full flightwear, migration and runtime validation are pending.

The successful intact-body flightwear probe contains 60,816 triangles versus
11,843 in the assembly's clothing-pruned body. It preserved all saved asset
bytes. Its receipt is `.local/CharacterLab/flightwear-probes/20260925-112120-889591-a26c765c/result.json`.
The lab review world was preserved before restart at
`/Game/BasketbroomLab/Maps/Review_20260925_112011`.

Local evidence:

- `.local/native-build-human-trails-pass.log`: editor compilation succeeded.
- `.local/native-broom-trail-policy/results.json`: 16 passed, zero failed.
- `.local/CharacterLab/assembly-manifest.json`: both saved human assemblies.
- `.local/CharacterLab/renders/1790335091596773900/`: aligned A render.
- `.local/CharacterLab/renders/1790335143930229400/`: aligned B render.

Next: run the picker and trail tests in the main editor, visually verify them,
then finish and review the humans' flightwear before game integration. Keep the
accepted desktop launch pointer until a replacement package passes acceptance.
