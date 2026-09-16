#include "BBFlightNetwork.h"
#include "BBRiderCharacter.h"

void FBBFlightSavedMove::Clear()
{
    FSavedMove_Character::Clear();
    Throttle = Brake = 0;
}
void FBBFlightSavedMove::SetMoveFor(ACharacter* C, float MoveDelta, const FVector& Accel, FNetworkPredictionData_Client_Character& Data)
{
    FSavedMove_Character::SetMoveFor(C, MoveDelta, Accel, Data);
    const UBBFlyingMovementComponent* Movement = Cast<UBBFlyingMovementComponent>(C->GetCharacterMovement());
    Throttle = Movement ? Movement->FlightThrottle : 0;
    Brake = Movement ? Movement->FlightBrake : 0;
}
void FBBFlightSavedMove::PrepMoveFor(ACharacter* C)
{
    FSavedMove_Character::PrepMoveFor(C);
    if (UBBFlyingMovementComponent* Movement = Cast<UBBFlyingMovementComponent>(C->GetCharacterMovement()))
    {
        Movement->FlightThrottle = Throttle;
        Movement->FlightBrake = Brake;
    }
}
bool FBBFlightSavedMove::CanCombineWith(const FSavedMovePtr& Move, ACharacter* C, float MaxDelta) const
{
    const FBBFlightSavedMove* Other = static_cast<const FBBFlightSavedMove*>(Move.Get());
    return Throttle == Other->Throttle && Brake == Other->Brake && FSavedMove_Character::CanCombineWith(Move, C, MaxDelta);
}
void FBBFlightMoveData::ClientFillNetworkMoveData(const FSavedMove_Character& Move, ENetworkMoveType Type)
{
    FCharacterNetworkMoveData::ClientFillNetworkMoveData(Move, Type);
    const FBBFlightSavedMove& Flight = static_cast<const FBBFlightSavedMove&>(Move);
    Throttle = Flight.Throttle;
    Brake = Flight.Brake;
}
bool FBBFlightMoveData::Serialize(UCharacterMovementComponent& Movement, FArchive& Ar, UPackageMap* Map, ENetworkMoveType Type)
{
    const bool bBase = FCharacterNetworkMoveData::Serialize(Movement, Ar, Map, Type);
    Ar << Throttle;
    Ar << Brake;
    return bBase && !Ar.IsError();
}
UBBFlyingMovementComponent::UBBFlyingMovementComponent()
{
    SetNetworkMoveDataContainer(FlightNetworkMoves);
}
FNetworkPredictionData_Client* UBBFlyingMovementComponent::GetPredictionData_Client() const
{
    if (!ClientPredictionData)
        const_cast<UBBFlyingMovementComponent*>(this)->ClientPredictionData = new FBBFlightPrediction(*this);
    return ClientPredictionData;
}
void UBBFlyingMovementComponent::SetFlightInput(float Throttle, float Brake)
{
    FlightThrottle = FMath::IsFinite(Throttle) ? static_cast<uint8>(FMath::RoundToInt(FMath::Clamp(Throttle, 0.f, 1.f) * 255.f)) : 0;
    FlightBrake = FMath::IsFinite(Brake) ? static_cast<uint8>(FMath::RoundToInt(FMath::Clamp(Brake, 0.f, 1.f) * 255.f)) : 255;
    if (ABBRiderCharacter* Rider = Cast<ABBRiderCharacter>(GetOwner()))
        if (Rider->HasAuthority()) Rider->AcceptFlightInput(FlightThrottle / 255.f, FlightBrake / 255.f);
}
void UBBFlyingMovementComponent::MoveAutonomous(float Time, float Delta, uint8 Flags, const FVector& Accel)
{
    if (const FBBFlightMoveData* Data = static_cast<const FBBFlightMoveData*>(GetCurrentNetworkMoveData()))
    {
        FlightThrottle = Data->Throttle;
        FlightBrake = Data->Brake;
    }
    if (ABBRiderCharacter* Rider = Cast<ABBRiderCharacter>(GetOwner()))
        if (Rider->HasAuthority()) Rider->AcceptFlightInput(FlightThrottle / 255.f, FlightBrake / 255.f);
    Super::MoveAutonomous(Time, Delta, Flags, Accel);
}
