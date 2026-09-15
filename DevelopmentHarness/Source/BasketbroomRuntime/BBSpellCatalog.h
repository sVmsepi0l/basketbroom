#pragma once
#include "CoreMinimal.h"

// native sporting adaptations, not the hogwarts legacy combat implementation.
// stable indices follow Rules/spell_catalog.json; contextual spells stay visible.
enum class ebbspelleffect : uint8 { context, impact, shield, stun, pull, push, down,
    flip, slow, freeze, lift, disarm, light, knockout, curse, reveal, conceal, bodybind, transform, confuse, workshop, ancient, throw };
struct fbbspellspec
{
    const tchar* name;
    ebbspelleffect effect;
    float cooldown;
    float range;
    float damage;
    bool bimpediment;
    bool bstun;
    bool bunforgivable;
    const tchar* description;
};
namespace bbspellcatalog
{
    int32 count();
    const fbbspellspec* get(int32 index);
    fstring name(int32 index);
    fstring description(int32 index);
    bool isimplemented(int32 index);
}
