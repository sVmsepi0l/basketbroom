using unrealbuildtool;
using System.Collections.Generic;
public class basketbroomdevtarget : targetrules
{
    public basketbroomdevtarget(targetinfo target) : base(target)
    {
        type = TargetType.Game;
        defaultbuildsettings = BuildSettingsVersion.Latest;
        includeorderversion = EngineIncludeOrderVersion.Latest;
        ExtraModuleNames.Add("BasketbroomRuntime");
    }
}
