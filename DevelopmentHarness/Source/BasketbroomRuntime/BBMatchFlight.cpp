#include "BBMatchState.h"
#include "BBRiderCharacter.h"
#include "BBBall.h"

bool ABBMatchState::IsActiveFlightParticipant(const ABBRiderCharacter* Rider) const
{
    if (!HasAuthority() || !Rules || !IsValid(Rider) || !Riders.Contains(Rider)
        || Rider->RosterIndex < 0 || Rider->RosterIndex >= 16
        || RiderForSlot(Rider->RosterIndex) != Rider) return false;
    const auto& Player = Rules->players[Rider->RosterIndex];
    return Player.team == Rider->TeamIndex && !Player.ejected
        && !Player.donnybrook_excluded && Player.removed_until < 0;
}

bool ABBMatchState::FlushPendingPointEvents()
{
    if (!HasAuthority() || !Rules || PendingPoints.empty()) return false;
    const bool bAccepted = Rules->process_batch(Rules->now_ms, PendingPoints);
    if (bAccepted)
    {
        for (const auto& Award : Rules->last_awards)
        {
            // Identity comes from the authority's actual catch/goal observation,
            // never from a recycled roster slot or a later ball owner.
            ABBRiderCharacter* Scorer = PendingFlightScorers.FindRef(Award.ball).Get();
            if (IsActiveFlightParticipant(Scorer) && Scorer->TeamIndex == Award.team && Award.points > 0)
                Scorer->AwardFlightBoost(0, ++FlightRewardSequence, 25.f);
            if (Balls.IsValidIndex(Award.ball))
                Say(FString::Printf(TEXT("%s +%lld  |  %s"), Award.team == 0 ? TEXT("TEAL") : TEXT("COPPER"),
                    static_cast<long long>(Award.points), *Balls[Award.ball]->DisplayName()));
        }
    }
    else UE_LOG(LogTemp, Warning, TEXT("Basketbroom point batch rejected: %s"), UTF8_TO_TCHAR(Rules->last_error.c_str()));
    PendingPoints.clear(); PendingFlightScorers.Empty();
    return bAccepted;
}

void ABBMatchState::AwardBludgerFlightBoost(ABBBall* Ball, ABBRiderCharacter* Target, FVector ContactPoint)
{
    if (!HasAuthority() || !Rules || !IsValid(Ball) || !Ball->IsBludger() || !Balls.Contains(Ball)
        || Ball->bFlightBoostRewarded || !IsValid(Target) || ContactPoint.ContainsNaN()) return;
    // Any rider contact consumes this flight's opportunity, including friendly
    // contact; rebounds cannot farm additional energy from the same throw.
    Ball->bFlightBoostRewarded = true;
    ABBRiderCharacter* Thrower = Ball->RecentThrower.Get();
    if (Rules->status != BB::Status::Live || bPenaltyShotActive || Ball->Holder
        || !IsActiveFlightParticipant(Thrower) || !IsActiveFlightParticipant(Target)
        || Thrower == Target || Thrower->TeamIndex == Target->TeamIndex
        || Thrower->Position != static_cast<int32>(BB::Role::Hurleyback)
        || Ball->BallIndex < 5 || Ball->BallIndex > 6 || !Rules->balls[Ball->BallIndex].live
        || Rules->balls[Ball->BallIndex].controller >= 0) return;
    // The same provisional upper-capsule head zone used by wand conduct.
    if (!bBloodbroom && ContactPoint.Z - Target->GetActorLocation().Z > 65.f) return;
    Thrower->AwardFlightBoost(1, ++FlightRewardSequence, 15.f);
}
