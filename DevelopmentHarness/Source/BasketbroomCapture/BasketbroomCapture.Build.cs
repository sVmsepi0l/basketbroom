using unrealbuildtool;

public class basketbroomcapture : modulerules
{
    public basketbroomcapture(readonlytargetrules target) : base(target)
    {
        pchusage = PCHUsageMode.UseExplicitOrSharedPCHs;
        PublicDependencyModuleNames.AddRange(new[] { "core", "coreuobject", "moviescenecapture" });
        PrivateDependencyModuleNames.AddRange(new[] {
            "engine", "rendercore", "rhi", "slate", "slatecore", "imagewritequeue", "imagewrapper"
        });
    }
}
