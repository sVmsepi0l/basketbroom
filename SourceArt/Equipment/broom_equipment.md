# Original flight equipment

These original centimeter-scale meshes replace primitive broom and wand shapes in
the native UE5.8 prototype. They contain no copied Hogwarts Legacy mesh, brand or
texture. They are authored source art, not a claim that the final art pass is done.

Generate source outside Unreal:

```powershell
python Tools/build_broom_equipment.py --generate-source
```

Stage with the existing editor bridge while the exact DevelopmentHarness project
is open, PIE is stopped and every package is clean:

```json
{"script":"stage_broom_equipment.py","args":{"operation":"build"}}
```

The stage imports only the eight named meshes and four owned materials under
`/Basketbroom/Art/Equipment`. It checks generator ownership before replacing an
asset, backs up existing owned packages under `.local/broom-equipment-stage`, and
records source/package SHA-256 hashes. It saves no map, does not change a scene or
gameplay setting, and compares existing map hashes before and after. The importer
checks one material section per mesh, exact source triangle counts and intended
Unreal bounds, and removes any generated simple collision. The native component
must additionally retain `NoCollision`; source meshes alone cannot enforce that.
The receipt reports `staged_pending_runtime_review`, not a rendered pass.

The eight mesh layers total **9,210 triangles**: five for one broom and three for
one wand. Remote and owner views reuse the same assets. There is no additional
texture streaming, world-position noise, physics body or equipment tick. The wood
grain is restrained UV math and therefore moves with the equipment. This is a
geometry budget, not a measured frame-time claim.

## Geometry and pose contract

- The broom origin remains the existing rider mesh origin. Use location zero,
  rotation zero and unit scale for all five remote layers.
- The raised steering grip stays centered at `(43, 0, 7)` with the existing seated
  Quinn hand targets `(46, -9, 10)` and `(46, 9, 10)`. Its support is incorporated
  into the wood layer; its wraps are incorporated into the leather layer.
- Open copper footrests lie at Z -60 below the Quinn foot targets
  `(26, -22, -53)` and `(26, 22, -53)`. These are decorative supports.
- For all five owner broom layers, use camera-relative `(55, 30, -48)`, rotation
  zero and unit scale. The nose reaches the existing lower-right cockpit region;
  the tail and footrests sit behind/below the view. Keep the existing small
  `CockpitCharmMount` and `CockpitFlightCharm` unless rendered QA finds a fit issue.
- Wand layers use the existing `Start` and `MakeFromZ(Direction)` rotation at unit
  scale. The local axis runs from grip butt Z 0 to tip Z 44, preserving the Lumos
  tip and light mounts. All three parts remain in `WandParts` for disarm visibility.
- The narrow team trim is the only layer added to `UniformParts`. Existing native
  teal/copper material assignment therefore updates both remote and owner copies.
- Keep every owner/remote visibility, shadow, navigation and collision setting in
  the existing `Part` helper. This work changes no animation, camera or flight code.

Source vertices use Unreal centimeters. OBJ export reflects Y and reverses face
winding together to compensate for the existing Unreal legacy OBJ importer's
coordinate conversion. Every mesh includes longitudinal UVs. The manifest records
**intended Unreal bounds**, not reflected source bounds.

## Native constructor integration

First stage the assets, then load the rebuilt native editor/game that references
them. Add these `FObjectFinder` declarations alongside the existing visual assets:

```cpp
static ConstructorHelpers::FObjectFinder<UStaticMesh> BroomWoodMesh(TEXT("/Basketbroom/Art/Equipment/SM_BB_BroomWood.SM_BB_BroomWood"));
static ConstructorHelpers::FObjectFinder<UStaticMesh> BroomLeatherMesh(TEXT("/Basketbroom/Art/Equipment/SM_BB_BroomLeather.SM_BB_BroomLeather"));
static ConstructorHelpers::FObjectFinder<UStaticMesh> BroomBristlesMesh(TEXT("/Basketbroom/Art/Equipment/SM_BB_BroomBristles.SM_BB_BroomBristles"));
static ConstructorHelpers::FObjectFinder<UStaticMesh> BroomCopperMesh(TEXT("/Basketbroom/Art/Equipment/SM_BB_BroomCopper.SM_BB_BroomCopper"));
static ConstructorHelpers::FObjectFinder<UStaticMesh> BroomAccentMesh(TEXT("/Basketbroom/Art/Equipment/SM_BB_BroomAccent.SM_BB_BroomAccent"));
static ConstructorHelpers::FObjectFinder<UStaticMesh> WandWoodMesh(TEXT("/Basketbroom/Art/Equipment/SM_BB_WandWood.SM_BB_WandWood"));
static ConstructorHelpers::FObjectFinder<UStaticMesh> WandLeatherMesh(TEXT("/Basketbroom/Art/Equipment/SM_BB_WandLeather.SM_BB_WandLeather"));
static ConstructorHelpers::FObjectFinder<UStaticMesh> WandCopperMesh(TEXT("/Basketbroom/Art/Equipment/SM_BB_WandCopper.SM_BB_WandCopper"));
static ConstructorHelpers::FObjectFinder<UMaterialInterface> EquipmentWood(TEXT("/Basketbroom/Art/Equipment/M_BB_EquipWood.M_BB_EquipWood"));
static ConstructorHelpers::FObjectFinder<UMaterialInterface> EquipmentLeather(TEXT("/Basketbroom/Art/Equipment/M_BB_EquipLeather.M_BB_EquipLeather"));
static ConstructorHelpers::FObjectFinder<UMaterialInterface> EquipmentBristles(TEXT("/Basketbroom/Art/Equipment/M_BB_EquipBristles.M_BB_EquipBristles"));
static ConstructorHelpers::FObjectFinder<UMaterialInterface> EquipmentCopper(TEXT("/Basketbroom/Art/Equipment/M_BB_EquipCopper.M_BB_EquipCopper"));
```

Replace the old remote shaft/bristles/binding/nose and raised-grip block with:

```cpp
// Cosmetic authored equipment shares the existing owner/remote Part settings.
for (const bool bCockpit : {false, true})
{
    const FString Prefix = bCockpit ? TEXT("CockpitBroom") : TEXT("Broom");
    const FVector Mount = bCockpit ? FVector(55, 30, -48) : FVector::ZeroVector;
    Part(FName(*(Prefix + TEXT("Wood"))), BroomWoodMesh.Object, EquipmentWood.Object,
         Mount, FVector::OneVector, FRotator::ZeroRotator, bCockpit);
    Part(FName(*(Prefix + TEXT("Leather"))), BroomLeatherMesh.Object, EquipmentLeather.Object,
         Mount, FVector::OneVector, FRotator::ZeroRotator, bCockpit);
    Part(FName(*(Prefix + TEXT("Bristles"))), BroomBristlesMesh.Object, EquipmentBristles.Object,
         Mount, FVector::OneVector, FRotator::ZeroRotator, bCockpit);
    Part(FName(*(Prefix + TEXT("Copper"))), BroomCopperMesh.Object, EquipmentCopper.Object,
         Mount, FVector::OneVector, FRotator::ZeroRotator, bCockpit);
    Part(FName(*(Prefix + TEXT("Accent"))), BroomAccentMesh.Object, Teal.Object,
         Mount, FVector::OneVector, FRotator::ZeroRotator, bCockpit, true);
}
```

Remove the now-duplicated `CockpitShaft`, `CockpitNose`, `CockpitGrip`,
`CockpitCollar`, `CockpitBristles` primitive and `CockpitGripWrap` loop. Preserve
both cockpit charm components. Keep the original wand loop's prefix, Start,
Direction and Rotation, replacing its three `WandParts.Add` calls with:

```cpp
WandParts.Add(Part(FName(*(Prefix + TEXT("Wood"))), WandWoodMesh.Object,
    EquipmentWood.Object, Start, FVector::OneVector, Rotation, bCockpit));
WandParts.Add(Part(FName(*(Prefix + TEXT("Grip"))), WandLeatherMesh.Object,
    EquipmentLeather.Object, Start, FVector::OneVector, Rotation, bCockpit));
WandParts.Add(Part(FName(*(Prefix + TEXT("Collar"))), WandCopperMesh.Object,
    EquipmentCopper.Object, Start, FVector::OneVector, Rotation, bCockpit));
```

The existing read-only `probe_native_rider_art.py` probe expects two old components
named `BroomGripStem` and `BroomRaisedGrip`. Its grip-support check must inspect
`BroomWood` and `BroomLeather` instead, validate their exact new mesh paths and zero
relative location/unit scale, and retain its NoCollision, parent and owner-filter
checks. Do not weaken the check by simply removing the grip requirement.

## Validation recorded at authoring time

Python syntax checks and deterministic source regeneration passed. The generator
checks finite vertices/UVs, valid indices, nondegenerate polygons and a 16,000 total
triangle ceiling. A local software-rendered orthographic preview was inspected for
broom silhouette, separated reeds, raised grip and open footrest arrangement at
`.local/broom-source-preview.png`.

Unreal import, shader compilation, actual owner/remote rendering, anatomical fit in
motion, team updates, disarm/Lumos, multiplayer and packaged rendering remain
required after native integration. This source document does not mark them passed.
The saved Hogwarts Legacy Creator Kit port is not updated by this UE5.8 stage;
its separate source import route must be validated for that editor version.

Rendered first-person refinement: the charm uses a shallow copper disc at camera-relative `(145,30,-50.5)` and a smaller crystal at `(145,30,-47.6)`, seated on the new shaft instead of the old black block. Final rendered verification is recorded in the sprint notes.
