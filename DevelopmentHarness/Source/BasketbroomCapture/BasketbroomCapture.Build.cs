using UnrealBuildTool;

public class BasketbroomCapture : ModuleRules
{
    public BasketbroomCapture(ReadOnlyTargetRules Target) : base(Target)
    {
        PCHUsage = PCHUsageMode.UseExplicitOrSharedPCHs;
        PublicDependencyModuleNames.AddRange(new[] { "Core", "CoreUObject", "MovieSceneCapture" });
        PrivateDependencyModuleNames.AddRange(new[] {
            "Engine", "RenderCore", "RHI", "Slate", "SlateCore", "ImageWriteQueue", "ImageWrapper"
        });
    }
}
