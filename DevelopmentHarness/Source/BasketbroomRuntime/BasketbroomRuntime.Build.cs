using UnrealBuildTool;
public class BasketbroomRuntime : ModuleRules
{
    public BasketbroomRuntime(ReadOnlyTargetRules Target) : base(Target)
    {
        PCHUsage = PCHUsageMode.UseExplicitOrSharedPCHs;
        PublicDependencyModuleNames.AddRange(new[] { "Core", "CoreUObject", "Engine", "InputCore", "NetCore" });
    }
}
