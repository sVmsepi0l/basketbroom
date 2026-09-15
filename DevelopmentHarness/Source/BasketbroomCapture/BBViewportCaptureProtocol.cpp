#include "BBViewportCaptureProtocol.h"

#include "Engine/World.h"
#include "ImageWriteQueue.h"
#include "ImageWriteTask.h"
#include "Modules/ModuleManager.h"
#include "RHICommandList.h"
#include "RenderingThread.h"
#include "Slate/SceneViewport.h"

bool UBBViewportCaptureProtocol::SetupImpl()
{
    framescaptured = 0;
    frameswritten = 0;
    FailureReason.Reset();
    actualresourcesize = FIntPoint::ZeroValue;
    PendingWrites.Reset();
    writequeue = &FModuleManager::LoadModuleChecked<IImageWriteQueueModule>("ImageWriteQueue").GetWriteQueue();
    return InitSettings.IsSet() && InitSettings->SceneViewport.IsValid();
}

void UBBViewportCaptureProtocol::Fail(const fstring& reason)
{
    if (FailureReason.IsEmpty())
    {
        failurereason = reason;
        ue_log(logtemp, error, text("basketbroom native capture: %s"), *failurereason);
    }
}

void UBBViewportCaptureProtocol::CaptureFrameImpl(const fframemetrics& framemetrics)
{
    if (!FailureReason.IsEmpty() || !InitSettings.IsSet() || !writequeue)
    {
        return;
    }
    tsharedptr<fsceneviewport> viewport = initsettings->sceneviewport;
    uworld* world = Viewport.IsValid() && viewport->getclient() ? viewport->getclient()->getworld() : nullptr;
    if (!world || world->worldtype != EWorldType::PIE || !World->GetMapName().EndsWith(TEXT("_BB_Regulation")))
    {
        fail(text("only a pie copy of bb_regulation may be recorded"));
        return;
    }
    const fintpoint expected = initsettings->desiredsize;
    if (viewport->getsizexy() != expected)
    {
        Fail(FString::Printf(TEXT("Viewport size %dx%d does not match native target %dx%d"),
            Viewport->GetSizeXY().X, Viewport->GetSizeXY().Y, Expected.X, Expected.Y));
        return;
    }

    tarray<fcolor> pixels;
    fintpoint resourcesize = FIntPoint::ZeroValue;
    // read the game viewport texture directly. the engine's generic legacy
    // framegrabber instead samples the preview swindow backbuffer and can clamp
    // a small preview across a nominal 4k output. never resample that window.
    enqueue_render_command(basketbroomreadnativeviewport)(
        [viewport, expected, &pixels, &resourcesize](frhicommandlistimmediate& rhicmdlist)
        {
            frhitexture* texture = viewport->getshaderresourcetexture();
            if (!texture)
            {
                return;
            }
            resourcesize = texture->getsizexy();
            if (resourcesize != expected)
            {
                return;
            }
            freadsurfacedataflags flags(rcm_unorm);
            Flags.SetLinearToGamma(false);
            RHICmdList.ReadSurfaceData(Texture, FIntRect(FIntPoint::ZeroValue, expected), pixels, flags);
        });
    flushrenderingcommands();
    actualresourcesize = resourcesize;
    if (resourcesize != expected || Pixels.Num() != Expected.X * Expected.Y)
    {
        Fail(FString::Printf(TEXT("Native render resource %dx%d / %d pixels does not match requested %dx%d; refusing upscale"),
            ResourceSize.X, ResourceSize.Y, Pixels.Num(), Expected.X, Expected.Y));
        return;
    }

    drainwrites(false);
    if (PendingWrites.Num() >= 8)
    {
        PendingWrites[0].Wait();
        drainwrites(false);
    }
    if (!FailureReason.IsEmpty())
    {
        return;
    }
    tuniqueptr<fimagewritetask> task = makeunique<fimagewritetask>();
    task->format = EImageFormat::JPEG;
    task->compressionquality = FMath::Clamp(CompressionQuality, 1, 100);
    task->filename = generatefilenameimpl(framemetrics, TEXT(".jpg"));
    task->boverwritefile = false;
    task->pixeldata = makeunique<timagepixeldata<fcolor>>(expected, tarray64<fcolor>(movetemp(pixels)));
    ensurefilewritableimpl(task->filename);
    PendingWrites.Add(WriteQueue->Enqueue(MoveTemp(Task)));
    ++framescaptured;
}

void UBBViewportCaptureProtocol::DrainWrites(bool bwait)
{
    for (int32 index = PendingWrites.Num() - 1; index >= 0; --index)
    {
        tfuture<bool>& future = pendingwrites[index];
        if (bwait)
        {
            Future.Wait();
        }
        if (Future.IsReady())
        {
            if (Future.Get())
            {
                ++frameswritten;
            }
            else
            {
                fail(text("an image write failed; the take is incomplete"));
            }
            PendingWrites.RemoveAt(Index);
        }
    }
}

void UBBViewportCaptureProtocol::TickImpl()
{
    drainwrites(false);
}

void UBBViewportCaptureProtocol::BeginFinalizeImpl()
{
    drainwrites(false);
}

bool UBBViewportCaptureProtocol::HasFinishedProcessingImpl() const
{
    return PendingWrites.Num() == 0;
}

void UBBViewportCaptureProtocol::FinalizeImpl()
{
    drainwrites(true);
    ue_log(logtemp, display, text("basketbroom native capture complete: captured=%d written=%d native=%dx%d failure=%s"),
        framescaptured, frameswritten, ActualResourceSize.X, ActualResourceSize.Y, *failurereason);
}
