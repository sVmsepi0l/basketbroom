using unrealbuildtool;
public class basketbroomruntime : modulerules
{
    public basketbroomruntime(readonlytargetrules target) : base(target)
    {
        pchusage = PCHUsageMode.UseExplicitOrSharedPCHs;
        PublicDependencyModuleNames.AddRange(new[] { "core", "coreuobject", "engine", "inputcore", "netcore" });
        PrivateDependencyModuleNames.Add("ApplicationCore");
    }
}
