# Google Sans Flex Black for the video bookends

Use `GoogleSansFlex_72pt-Black.ttf` for all intro/outro text. This is the
unchanged static Black face from the user's downloaded `Google_Sans_Flex.zip`,
not simulated bold or the installed variable font's default Regular instance.

The font's internal legacy/full family is **Google Sans Flex 72pt Black**.
Its typographic family is **Google Sans Flex 72pt**, style **Black**, and
PostScript name **GoogleSansFlex72pt-Black**. Supply this directory to libass
as its `fontsdir` and use the full family to select the intended face. Confirm
the renderer's `fontselect` log selects `GoogleSansFlex72pt-Black`.

Verified static axes: weight 900, optical size 72, width 100, slant 0, grade 0,
roundness 0. The 72pt optical instance suits the large display typography and
is used consistently across the title, description, links, and technology
text. Its OS/2 weight class is 900 and width class is 5 (normal). It has no
variable `fvar` table, so the appearance is deterministic without axis support
in the video renderer. No font names or outlines were changed; no font was
installed into Windows.

`font-source-receipt.json` records the local archive and selected-file hashes,
internal font metadata, axes, official source URLs, and source checks. The
package's variable font and the current official Google Fonts variable font
both report version 4.005. Their outline, variation, shaping, mapping, metric,
axis, and style tables match byte for byte. Their `head` and `name` tables
differ, so the receipt does not claim their full files are identical.

This font retains its **SIL Open Font License 1.1**. `OFL-GoogleFonts.txt`
contains the current official Google Fonts copyright/license; `OFL.txt`
contains the project repository's license. The archive's own license and
instructions are preserved as `OFL-from-download.txt` and
`README-from-download.txt`. `TRADEMARKS.txt` is the upstream project's
trademark notice. The font is not relicensed as Basketbroom code or artwork.

Sources inspected 2026-09-13:

- [Google Sans Flex project](https://github.com/googlefonts/googlesans-flex)
- [Google Fonts source metadata](https://github.com/google/fonts/blob/main/ofl/googlesansflex/METADATA.pb)
- [Official Google Fonts license](https://github.com/google/fonts/blob/main/ofl/googlesansflex/OFL.txt)
