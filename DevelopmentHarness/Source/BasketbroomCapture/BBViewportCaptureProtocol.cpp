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
    FramesCaptured = 0;
    FramesWritten = 0;
    FailureReason.Reset();
    ActualResourceSize = FIntPoint::ZeroValue;
    PendingWrites.Reset();
    WriteQueue = &FModuleManager::LoadModuleChecked<IImageWriteQueueModule>("ImageWriteQueue").GetWriteQueue();
    return InitSettings.IsSet() && InitSettings->SceneViewport.IsValid();
}

void UBBViewportCaptureProtocol::Fail(const FString& Reason)
{
    if (FailureReason.IsEmpty())
    {
        FailureReason = Reason;
        UE_LOG(LogTemp, Error, TEXT("Basketbroom native capture: %s"), *FailureReason);
    }
}

void UBBViewportCaptureProtocol::CaptureFrameImpl(const FFrameMetrics& FrameMetrics)
{
    if (!FailureReason.IsEmpty() || !InitSettings.IsSet() || !WriteQueue)
    {
        return;
    }
    TSharedPtr<FSceneViewport> Viewport = InitSettings->SceneViewport;
    UWorld* World = Viewport.IsValid() && Viewport->GetClient() ? Viewport->GetClient()->GetWorld() : nullptr;
    if (!World || World->WorldType != EWorldType::PIE || !World->GetMapName().EndsWith(TEXT("_BB_Regulation")))
    {
        Fail(TEXT("Only a PIE copy of BB_Regulation may be recorded"));
        return;
    }
    const FIntPoint Expected = InitSettings->DesiredSize;
    if (Viewport->GetSizeXY() != Expected)
    {
        Fail(FString::Printf(TEXT("Viewport size %dx%d does not match native target %dx%d"),
            Viewport->GetSizeXY().X, Viewport->GetSizeXY().Y, Expected.X, Expected.Y));
        return;
    }

    TArray<FColor> Pixels;
    FIntPoint ResourceSize = FIntPoint::ZeroValue;
    // Read the game viewport texture directly. The engine's generic legacy
    // FrameGrabber instead samples the preview SWindow backbuffer and can clamp
    // a small preview across a nominal 4K output. Never resample that window.
    ENQUEUE_RENDER_COMMAND(BasketbroomReadNativeViewport)(
        [Viewport, Expected, &Pixels, &ResourceSize](FRHICommandListImmediate& RHICmdList)
        {
            FRHITexture* Texture = Viewport->GetShaderResourceTexture();
            if (!Texture)
            {
                return;
            }
            ResourceSize = Texture->GetSizeXY();
            if (ResourceSize != Expected)
            {
                return;
            }
            FReadSurfaceDataFlags Flags(RCM_UNorm);
            Flags.SetLinearToGamma(false);
            RHICmdList.ReadSurfaceData(Texture, FIntRect(FIntPoint::ZeroValue, Expected), Pixels, Flags);
        });
    FlushRenderingCommands();
    ActualResourceSize = ResourceSize;
    if (ResourceSize != Expected || Pixels.Num() != Expected.X * Expected.Y)
    {
        Fail(FString::Printf(TEXT("Native render resource %dx%d / %d pixels does not match requested %dx%d; refusing upscale"),
            ResourceSize.X, ResourceSize.Y, Pixels.Num(), Expected.X, Expected.Y));
        return;
    }

    DrainWrites(false);
    if (PendingWrites.Num() >= 8)
    {
        PendingWrites[0].Wait();
        DrainWrites(false);
    }
    if (!FailureReason.IsEmpty())
    {
        return;
    }
    TUniquePtr<FImageWriteTask> Task = MakeUnique<FImageWriteTask>();
    Task->Format = EImageFormat::JPEG;
    Task->CompressionQuality = FMath::Clamp(CompressionQuality, 1, 100);
    Task->Filename = GenerateFilenameImpl(FrameMetrics, TEXT(".jpg"));
    Task->bOverwriteFile = false;
    Task->PixelData = MakeUnique<TImagePixelData<FColor>>(Expected, TArray64<FColor>(MoveTemp(Pixels)));
    EnsureFileWritableImpl(Task->Filename);
    PendingWrites.Add(WriteQueue->Enqueue(MoveTemp(Task)));
    ++FramesCaptured;
}

void UBBViewportCaptureProtocol::DrainWrites(bool bWait)
{
    for (int32 Index = PendingWrites.Num() - 1; Index >= 0; --Index)
    {
        TFuture<bool>& Future = PendingWrites[Index];
        if (bWait)
        {
            Future.Wait();
        }
        if (Future.IsReady())
        {
            if (Future.Get())
            {
                ++FramesWritten;
            }
            else
            {
                Fail(TEXT("An image write failed; the take is incomplete"));
            }
            PendingWrites.RemoveAt(Index);
        }
    }
}

void UBBViewportCaptureProtocol::TickImpl()
{
    DrainWrites(false);
}

void UBBViewportCaptureProtocol::BeginFinalizeImpl()
{
    DrainWrites(false);
}

bool UBBViewportCaptureProtocol::HasFinishedProcessingImpl() const
{
    return PendingWrites.Num() == 0;
}

void UBBViewportCaptureProtocol::FinalizeImpl()
{
    DrainWrites(true);
    UE_LOG(LogTemp, Display, TEXT("Basketbroom native capture complete: captured=%d written=%d native=%dx%d failure=%s"),
        FramesCaptured, FramesWritten, ActualResourceSize.X, ActualResourceSize.Y, *FailureReason);
}
