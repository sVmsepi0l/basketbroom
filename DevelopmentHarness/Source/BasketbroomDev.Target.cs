using UnrealBuildTool;
using System.Collections.Generic;
public class BasketbroomDevTarget : TargetRules
{
    public BasketbroomDevTarget(TargetInfo Target) : base(Target)
    {
        Type = TargetType.Game;
        DefaultBuildSettings = BuildSettingsVersion.Latest;
        IncludeOrderVersion = EngineIncludeOrderVersion.Latest;
        ExtraModuleNames.Add("BasketbroomRuntime");
    }
}
