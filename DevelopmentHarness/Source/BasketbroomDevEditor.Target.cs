using UnrealBuildTool;
using System.Collections.Generic;
public class BasketbroomDevEditorTarget : TargetRules
{
    public BasketbroomDevEditorTarget(TargetInfo Target) : base(Target)
    {
        Type = TargetType.Editor;
        DefaultBuildSettings = BuildSettingsVersion.Latest;
        IncludeOrderVersion = EngineIncludeOrderVersion.Latest;
        ExtraModuleNames.Add("BasketbroomRuntime");
        ExtraModuleNames.Add("BasketbroomCapture");
    }
}
