#pragma once
#include "CoreMinimal.h"
class ABBRiderCharacter;
namespace BBPauseMenu
{
    enum Page : int32 { Main, Settings, Controls, Roles, Referee };
    enum Action : int32 { Resume = 0, OpenSettings = 11, OpenControls = 12, OpenRoles = 13, OpenReferee = 14,
        InvertAltitude = 100, InvertAim = 101, RoleBase = 200,
        Ready = 300, Stoppage, FreeShot, Possession, Serious, Ejection, Advantage, Team, Variant, Back = 999 };
    struct Item { FString Label; int32 Command; };
    TArray<Item> Items(const ABBRiderCharacter* Rider);
}
