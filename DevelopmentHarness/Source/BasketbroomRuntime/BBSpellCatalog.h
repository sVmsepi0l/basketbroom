#pragma once
#include "CoreMinimal.h"

// Native sporting adaptations, not the Hogwarts Legacy combat implementation.
// Stable indices follow Rules/spell_catalog.json; contextual spells stay visible.
enum class EBBSpellEffect : uint8 { Context, Impact, Shield, Stun, Pull, Push, Down,
    Flip, Slow, Freeze, Lift, Disarm, Light, Knockout, Curse, Reveal, Conceal, BodyBind, Transform, Confuse, Workshop, Ancient, Throw };
struct FBBSpellSpec
{
    const TCHAR* Name;
    EBBSpellEffect Effect;
    float Cooldown;
    float Range;
    float Damage;
    bool bImpediment;
    bool bStun;
    bool bUnforgivable;
    const TCHAR* Description;
};
namespace BBSpellCatalog
{
    int32 Count();
    const FBBSpellSpec* Get(int32 Index);
    FString Name(int32 Index);
    FString Description(int32 Index);
    bool IsImplemented(int32 Index);
}
