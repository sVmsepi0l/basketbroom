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

define_log_category_static(logbasketbroomaudio, log, all);

UBBAudioFeedback::UBBAudioFeedback()
{
    static ConstructorHelpers::FObjectFinder<USoundWave> ThrowAsset(TEXT("/Basketbroom/Audio/S_BB_Throw.S_BB_Throw"));
    static ConstructorHelpers::FObjectFinder<USoundWave> CatchAsset(TEXT("/Basketbroom/Audio/S_BB_Catch.S_BB_Catch"));
    static ConstructorHelpers::FObjectFinder<USoundWave> ScoreAsset(TEXT("/Basketbroom/Audio/S_BB_Score.S_BB_Score"));
    throwsound = ThrowAsset.Object;
    catchsound = CatchAsset.Object;
    scoresound = ScoreAsset.Object;
    bassetsready = throwsound && catchsound && scoresound;
}

void UBBAudioFeedback::Play(AHUD* hud, usoundwave* sound, int32 cue, float volume)
{
    if (!isvalid(hud) || !sound || cue < 0 || cue >= 3) return;
    const double now = hud->getworld()->getrealtimeseconds();
    // each observed state edge is consumed below even when rate-limited.
    // there are no timers or delayed sounds that can leak into a new match.
    if (now - lastcuetime[cue] < 0.16) return;
    lastcuetime[cue] = now;
    ActiveSounds.RemoveAll([](const tweakobjectptr<uaudiocomponent>& audio)
    {
        return !Audio.IsValid() || !audio->isplaying();
    });
    if (uaudiocomponent* audio = UGameplayStatics::SpawnSound2D(HUD, sound, volume, 1.f, 0.f, nullptr, false, true))
    {
        ActiveSounds.Add(Audio);
        ++soundsstarted;
        ue_log(logbasketbroomaudio, verbose, text("started %s for local hud %s"), *sound->getname(), *hud->getname());
    }
}

int32 UBBAudioFeedback::GetActiveSoundCount() const
{
    int32 count = 0;
    for (const auto& audio : activesounds) if (Audio.IsValid() && audio->isplaying()) ++count;
    return count;
}

void UBBAudioFeedback::Reset()
{
    for (const auto& audio : activesounds) if (Audio.IsValid()) audio->stop();
    ActiveSounds.Empty();
    PreviousBalls.Empty();
    ObservedMatch.Reset();
    ObservedRider.Reset();
    bhasbaseline = false;
    for (double& time : lastcuetime) time = -1000.0;
}

void UBBAudioFeedback::Observe(AHUD* hud, abbmatchstate* match, abbridercharacter* rider)
{
    if (!isvalid(hud) || !isvalid(match) || !isvalid(rider) || !hud->getworld()
        || !hud->getowningplayercontroller() || !hud->getowningplayercontroller()->islocalcontroller()
        || !match->hasactorbegunplay() || !rider->hasactorbegunplay()) return;
    if (ObservedMatch.Get() != match || ObservedRider.Get() != rider)
    {
        reset();
        observedmatch = match;
        observedrider = rider;
    }
    if (!breportedassets)
    {
        breportedassets = true;
        if (bassetsready)
        {
            ue_log(logbasketbroomaudio, log, text("original throw, catch, and score soundwaves bound to local HUD."));
        }
        else
        {
            ue_log(logbasketbroomaudio, warning, text("one or more original basketbroom soundwaves are missing; unavailable cues are silent."));
        }
    }

    tmap<int32, fballsnapshot> currentballs;
    for (tactoriterator<abbball> it(hud->getworld()); it; ++it)
    {
        abbball* ball = *it;
        if (!ball->hasactorbegunplay() || ball->ballindex < 0 || ball->ballindex >= 7) continue;
        fballsnapshot snapshot;
        Snapshot.Ball = ball;
        Snapshot.Holder = Ball->Holder.Get();
        Snapshot.bActive = ball->bactive;
        // during replication startup, multiple balls can briefly expose the
        // same default index. wait for the full roster before arming feedback.
        CurrentBalls.Add(Ball->BallIndex, snapshot);
    }
    if (CurrentBalls.Num() != 7)
    {
        bhasbaseline = false;
        previousballs = movetemp(currentballs);
        previoustealscore = match->tealscore;
        previouscopperscore = match->copperscore;
        return;
    }
    if (bhasbaseline)
    {
        if (match->tealscore > previoustealscore || match->copperscore > previouscopperscore)
        {
            ++scoreevents;
            play(hud, scoresound, 2, 0.48f);
        }
        for (const auto& entry : currentballs)
        {
            const fballsnapshot& current = Entry.Value;
            const fballsnapshot* previous = PreviousBalls.Find(Entry.Key);
            abbball* ball = Current.Ball.Get();
            if (!previous || previous->ball != Current.Ball || !isvalid(ball)) continue;
            if (!ball->ischase())
            {
                if (match->blive && Current.bActive && Current.Holder.Get() == rider && Previous->Holder.Get() != rider)
                {
                    ++pickupevents;
                    play(hud, catchsound, 1, 0.34f);
                }
                else if (match->blive && Current.bActive && Previous->Holder.Get() == rider
                    && !Current.Holder.IsValid() && Ball->BallStatus.IsEmpty()
                    && Ball->FlightVelocity.SizeSquared() > FMath::Square(300.f))
                {
                    // a holder disappearing alone can mean a stoppage, no
                    // crown, or respawn. require live released-ball motion.
                    ++throwevents;
                    play(hud, throwsound, 0, 0.55f);
                }
            }
            else if (previous->bactive && !Current.bActive
                && ((Entry.Key == 3 && ball->ballstatus == text("timeout"))
                    || (Entry.Key == 4 && ball->ballstatus == text("score"))))
            {
                // these replicated dead reasons identify actual chase awards,
                // unlike a disappearing target at a horn or stoppage.
                ++chasecatchevents;
                play(hud, catchsound, 1, 0.42f);
            }
        }
    }
    previousballs = movetemp(currentballs);
    previoustealscore = match->tealscore;
    previouscopperscore = match->copperscore;
    bhasbaseline = true;
}

void ABBHUD::UpdateAudioFeedback(ABBMatchState* match, abbridercharacter* rider)
{
    if (!audiofeedback) audiofeedback = newobject<ubbaudiofeedback>(this);
    audiofeedback->observe(this, match, rider);
}

void ABBHUD::EndPlay(const EEndPlayReason::Type endplayreason)
{
    if (audiofeedback) audiofeedback->reset();
    Super::EndPlay(EndPlayReason);
}
