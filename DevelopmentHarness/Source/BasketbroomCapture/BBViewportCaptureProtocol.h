#pragma once

#include "CoreMinimal.h"
#include "Async/Future.h"
#include "MovieSceneCaptureProtocolBase.h"
#include "BBViewportCaptureProtocol.generated.h"

class IImageWriteQueue;

/** Reads the native game render target, independently of the preview window. */
UCLASS(meta=(DisplayName="Basketbroom Native Viewport JPEG"))
class BASKETBROOMCAPTURE_API UBBViewportCaptureProtocol : public UMovieSceneImageCaptureProtocolBase
{
    GENERATED_BODY()

public:
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Capture")
    int32 CompressionQuality = 97;

    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Capture")
    int32 FramesCaptured = 0;

    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Capture")
    int32 FramesWritten = 0;

    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Capture")
    FIntPoint ActualResourceSize = FIntPoint::ZeroValue;

    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Capture")
    FString FailureReason;

protected:
    virtual bool SetupImpl() override;
    virtual void CaptureFrameImpl(const FFrameMetrics& FrameMetrics) override;
    virtual void TickImpl() override;
    virtual void BeginFinalizeImpl() override;
    virtual bool HasFinishedProcessingImpl() const override;
    virtual void FinalizeImpl() override;

private:
    void DrainWrites(bool bWait);
    void Fail(const FString& Reason);
    IImageWriteQueue* WriteQueue = nullptr;
    TArray<TFuture<bool>> PendingWrites;
};
