#pragma once

#include "CoreMinimal.h"
#include "Async/Future.h"
#include "MovieSceneCaptureProtocolBase.h"
#include "BBViewportCaptureProtocol.generated.h"

class iimagewritequeue;

/** reads the native game render target, independently of the preview window. */
uclass(meta=(displayname="basketbroom native viewport jpeg"))
class basketbroomcapture_api ubbviewportcaptureprotocol : public umoviesceneimagecaptureprotocolbase
{
    generated_body()

public:
    uproperty(editanywhere, blueprintreadwrite, category="capture")
    int32 compressionquality = 97;

    uproperty(visibleanywhere, blueprintreadonly, category="capture")
    int32 framescaptured = 0;

    uproperty(visibleanywhere, blueprintreadonly, category="capture")
    int32 frameswritten = 0;

    uproperty(visibleanywhere, blueprintreadonly, category="capture")
    fintpoint actualresourcesize = FIntPoint::ZeroValue;

    uproperty(visibleanywhere, blueprintreadonly, category="capture")
    fstring failurereason;

protected:
    virtual bool setupimpl() override;
    virtual void captureframeimpl(const fframemetrics& framemetrics) override;
    virtual void tickimpl() override;
    virtual void beginfinalizeimpl() override;
    virtual bool hasfinishedprocessingimpl() const override;
    virtual void finalizeimpl() override;

private:
    void drainwrites(bool bwait);
    void fail(const fstring& reason);
    iimagewritequeue* writequeue = nullptr;
    tarray<tfuture<bool>> pendingwrites;
};
