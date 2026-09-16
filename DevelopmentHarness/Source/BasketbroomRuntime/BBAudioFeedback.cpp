#include "BBAudioFeedback.h"
#include "BBBall.h"
#include "BBHUD.h"
#include "BBMatchState.h"
#include "BBRiderCharacter.h"
#include "Components/AudioComponent.h"
#include "Engine/World.h"
#include "EngineUtils.h"
#include "GameFramework/PlayerController.h"
#include "Kismet/GameplayStatics.h"
#include "Sound/SoundWave.h"
#include "UObject/ConstructorHelpers.h"

DEFINE_LOG_CATEGORY_STATIC(LogBasketbroomAudio, Log, All);

UBBAudioFeedback::UBBAudioFeedback()
{
    static ConstructorHelpers::FObjectFinder<USoundWave> ThrowAsset(TEXT("/Basketbroom/Audio/S_BB_Throw.S_BB_Throw"));
    static ConstructorHelpers::FObjectFinder<USoundWave> CatchAsset(TEXT("/Basketbroom/Audio/S_BB_Catch.S_BB_Catch"));
    static ConstructorHelpers::FObjectFinder<USoundWave> ScoreAsset(TEXT("/Basketbroom/Audio/S_BB_Score.S_BB_Score"));
    ThrowSound = ThrowAsset.Object;
    CatchSound = CatchAsset.Object;
    ScoreSound = ScoreAsset.Object;
    bAssetsReady = ThrowSound && CatchSound && ScoreSound;
}

void UBBAudioFeedback::Play(AHUD* HUD, USoundWave* Sound, int32 Cue, float Volume)
{
    if (!IsValid(HUD) || !Sound || Cue < 0 || Cue >= 3) return;
    const double Now = HUD->GetWorld()->GetRealTimeSeconds();
    // Each observed state edge is consumed below even when rate-limited.
    // There are no timers or delayed sounds that can leak into a new match.
    if (Now - LastCueTime[Cue] < 0.16) return;
    LastCueTime[Cue] = Now;
    ActiveSounds.RemoveAll([](const TWeakObjectPtr<UAudioComponent>& Audio)
    {
        return !Audio.IsValid() || !Audio->IsPlaying();
    });
    if (UAudioComponent* Audio = UGameplayStatics::SpawnSound2D(HUD, Sound, Volume, 1.f, 0.f, nullptr, false, true))
    {
        ActiveSounds.Add(Audio);
        ++SoundsStarted;
        UE_LOG(LogBasketbroomAudio, Verbose, TEXT("Started %s for local HUD %s"), *Sound->GetName(), *HUD->GetName());
    }
}

int32 UBBAudioFeedback::GetActiveSoundCount() const
{
    int32 Count = 0;
    for (const auto& Audio : ActiveSounds) if (Audio.IsValid() && Audio->IsPlaying()) ++Count;
    return Count;
}

void UBBAudioFeedback::Reset()
{
    for (const auto& Audio : ActiveSounds) if (Audio.IsValid()) Audio->Stop();
    ActiveSounds.Empty();
    PreviousBalls.Empty();
    ObservedMatch.Reset();
    ObservedRider.Reset();
    bHasBaseline = false;
    for (double& Time : LastCueTime) Time = -1000.0;
}

void UBBAudioFeedback::Observe(AHUD* HUD, ABBMatchState* Match, ABBRiderCharacter* Rider)
{
    if (!IsValid(HUD) || !IsValid(Match) || !IsValid(Rider) || !HUD->GetWorld()
        || !HUD->GetOwningPlayerController() || !HUD->GetOwningPlayerController()->IsLocalController()
        || !Match->HasActorBegunPlay() || !Rider->HasActorBegunPlay()) return;
    if (ObservedMatch.Get() != Match || ObservedRider.Get() != Rider)
    {
        Reset();
        ObservedMatch = Match;
        ObservedRider = Rider;
    }
    if (!bReportedAssets)
    {
        bReportedAssets = true;
        if (bAssetsReady)
        {
            UE_LOG(LogBasketbroomAudio, Log, TEXT("Original throw, catch, and score SoundWaves bound to local HUD."));
        }
        else
        {
            UE_LOG(LogBasketbroomAudio, Warning, TEXT("One or more original Basketbroom SoundWaves are missing; unavailable cues are silent."));
        }
    }

    TMap<int32, FBallSnapshot> CurrentBalls;
    for (TActorIterator<ABBBall> It(HUD->GetWorld()); It; ++It)
    {
        ABBBall* Ball = *It;
        if (!Ball->HasActorBegunPlay() || Ball->BallIndex < 0 || Ball->BallIndex >= 7) continue;
        FBallSnapshot Snapshot;
        Snapshot.Ball = Ball;
        Snapshot.Holder = Ball->Holder.Get();
        Snapshot.bActive = Ball->bActive;
        // During replication startup, multiple balls can briefly expose the
        // same default index. Wait for the full roster before arming feedback.
        CurrentBalls.Add(Ball->BallIndex, Snapshot);
    }
    if (CurrentBalls.Num() != 7)
    {
        bHasBaseline = false;
        PreviousBalls = MoveTemp(CurrentBalls);
        PreviousTealScore = Match->TealScore;
        PreviousCopperScore = Match->CopperScore;
        return;
    }
    if (bHasBaseline)
    {
        if (Match->TealScore > PreviousTealScore || Match->CopperScore > PreviousCopperScore)
        {
            ++ScoreEvents;
            Play(HUD, ScoreSound, 2, 0.48f);
        }
        for (const auto& Entry : CurrentBalls)
        {
            const FBallSnapshot& Current = Entry.Value;
            const FBallSnapshot* Previous = PreviousBalls.Find(Entry.Key);
            ABBBall* Ball = Current.Ball.Get();
            if (!Previous || Previous->Ball != Current.Ball || !IsValid(Ball)) continue;
            if (!Ball->IsChase())
            {
                if (Match->bLive && Current.bActive && Current.Holder.Get() == Rider && Previous->Holder.Get() != Rider)
                {
                    ++PickupEvents;
                    Play(HUD, CatchSound, 1, 0.34f);
                }
                else if (Match->bLive && Current.bActive && Previous->Holder.Get() == Rider
                    && !Current.Holder.IsValid() && Ball->BallStatus.IsEmpty()
                    && Ball->FlightVelocity.SizeSquared() > FMath::Square(300.f))
                {
                    // A holder disappearing alone can mean a stoppage, No
                    // Crown, or respawn. Require live released-ball motion.
                    ++ThrowEvents;
                    Play(HUD, ThrowSound, 0, 0.55f);
                }
            }
            else if (Previous->bActive && !Current.bActive
                && ((Entry.Key == 3 && Ball->BallStatus == TEXT("timeout"))
                    || (Entry.Key == 4 && Ball->BallStatus == TEXT("score"))))
            {
                // These replicated dead reasons identify actual chase awards,
                // unlike a disappearing target at a horn or stoppage.
                ++ChaseCatchEvents;
                Play(HUD, CatchSound, 1, 0.42f);
            }
        }
    }
    PreviousBalls = MoveTemp(CurrentBalls);
    PreviousTealScore = Match->TealScore;
    PreviousCopperScore = Match->CopperScore;
    bHasBaseline = true;
}

void ABBHUD::UpdateAudioFeedback(ABBMatchState* Match, ABBRiderCharacter* Rider)
{
    if (!AudioFeedback) AudioFeedback = NewObject<UBBAudioFeedback>(this);
    AudioFeedback->Observe(this, Match, Rider);
}

void ABBHUD::EndPlay(const EEndPlayReason::Type EndPlayReason)
{
    if (AudioFeedback) AudioFeedback->Reset();
    Super::EndPlay(EndPlayReason);
}
