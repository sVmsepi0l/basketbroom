using unrealbuildtool;
using System.Collections.Generic;
public class basketbroomdeveditortarget : targetrules
{
    public basketbroomdeveditortarget(targetinfo target) : base(target)
    {
        type = TargetType.Editor;
        defaultbuildsettings = BuildSettingsVersion.Latest;
        includeorderversion = EngineIncludeOrderVersion.Latest;
        ExtraModuleNames.Add("BasketbroomRuntime");
        ExtraModuleNames.Add("BasketbroomCapture");
    }
}
