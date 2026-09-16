#pragma once
#include "GameFramework/CharacterMovementComponent.h"
#include "GameFramework/CharacterMovementReplication.h"

class FBBFlightSavedMove : public FSavedMove_Character
{
public:
    uint8 Throttle = 0, Brake = 0;
    virtual void Clear() override;
    virtual void SetMoveFor(ACharacter*, float, const FVector&, FNetworkPredictionData_Client_Character&) override;
    virtual void PrepMoveFor(ACharacter*) override;
    virtual bool CanCombineWith(const FSavedMovePtr&, ACharacter*, float) const override;
};
struct FBBFlightMoveData : FCharacterNetworkMoveData
{
    uint8 Throttle = 0, Brake = 0;
    virtual void ClientFillNetworkMoveData(const FSavedMove_Character&, ENetworkMoveType) override;
    virtual bool Serialize(UCharacterMovementComponent&, FArchive&, UPackageMap*, ENetworkMoveType) override;
};
struct FBBFlightMoveContainer : FCharacterNetworkMoveDataContainer
{
    FBBFlightMoveData Moves[3];
    FBBFlightMoveContainer() { NewMoveData = &Moves[0]; PendingMoveData = &Moves[1]; OldMoveData = &Moves[2]; }
};
class FBBFlightPrediction : public FNetworkPredictionData_Client_Character
{
public:
    explicit FBBFlightPrediction(const UCharacterMovementComponent& Movement) : FNetworkPredictionData_Client_Character(Movement) {}
    virtual FSavedMovePtr AllocateNewMove() override { return FSavedMovePtr(new FBBFlightSavedMove()); }
};
