#pragma once
#include "CoreMinimal.h"
#include "GameFramework/HUD.h"
#include "BBHUD.generated.h"
UCLASS()
class BASKETBROOMRUNTIME_API ABBHUD : public AHUD
{
    GENERATED_BODY()
public:
    virtual void DrawHUD() override;
};
