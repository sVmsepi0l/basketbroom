#include "BBHUD.h"
#include "BBMatchState.h"
#include "BBBall.h"
#include "BBRiderCharacter.h"
#include "Engine/Canvas.h"
#include "Engine/Engine.h"
#include "Engine/World.h"
#include "EngineUtils.h"
#include "GameFramework/PlayerController.h"

void ABBHUD::DrawHUD()
{
    Super::DrawHUD();
    if (!Canvas || !PlayerOwner || Canvas->SizeX <= 0 || Canvas->SizeY <= 0) return;
    ABBMatchState* Match = GetWorld()->GetGameState<ABBMatchState>();
    ABBRiderCharacter* Rider = Cast<ABBRiderCharacter>(PlayerOwner->GetPawn());
    if (!Match || !Rider) return;
    UpdateAudioFeedback(Match, Rider);
    const float W = Canvas->SizeX, H = Canvas->SizeY;
    const float S = FMath::Min(W/1600.f, H/900.f);
    const FLinearColor Ink(.015,.026,.038,.90), Muted(.56,.67,.7,1), Cream(.94,.91,.82,1), Teal(.12,.9,.73,1), Copper(1,.46,.20,1), Gold(1,.77,.24,1), Violet(.7,.38,1,1);
    UFont* Font = GEngine->GetMediumFont();
    auto Rect = [&](float X,float Y,float Width,float Height,FLinearColor Color) { DrawRect(Color,X*S,Y*S,Width*S,Height*S); };
    auto Text = [&](const FString& T,float X,float Y,float Size,FLinearColor Color) { DrawText(T,Color,X*S,Y*S,Font,Size*S,false); };
    const float UW = W/S, UH = H/S;
    Rect(UW/2-320,20,640,102,Ink);
    Rect(UW/2-320,20,4,102,Teal); Rect(UW/2+316,20,4,102,Copper);
    Text(TEXT("TEAL"),UW/2-294,32,1,Teal); Text(TEXT("COPPER"),UW/2+191,32,1,Copper);
    Text(FString::FromInt(Match->TealScore),UW/2-294,59,2,Cream);
    Text(FString::FromInt(Match->CopperScore),UW/2+191,59,2,Cream);
    const int32 Seconds = FMath::Max(0,FMath::CeilToInt(Match->SecondsLeft));
    const FString Clock = Match->Phase == TEXT("DONNYBROOK") ? TEXT("SUDDEN DEATH") : FString::Printf(TEXT("%02d:%02d"),Seconds/60,Seconds%60);
    Text(Clock,UW/2-55,35,1.5f,Cream);
    Text(Match->Phase + (Match->Phase == TEXT("REGULATION") ? FString::Printf(TEXT("  Q%d/4"),Match->Quarter) : TEXT("")),UW/2-78,79,.78,Muted);
    Text(Match->bPractice ? TEXT("PRACTICE CLOCKS") : TEXT("REGULATION CLOCKS"),24,23,.78,Muted);
    Text(GetNetMode() == NM_Standalone ? TEXT("LOCAL SCRIMMAGE") : GetNetMode() == NM_Client ? TEXT("NETWORK CLIENT") : TEXT("LISTEN SERVER"),24,45,.78,Muted);
    Rect(22,UH-108,420,82,Ink);
    Rect(22,UH-108,4,82,Rider->TeamIndex ? Copper : Teal);
    Text((Rider->TeamIndex ? TEXT("COPPER  /  ") : TEXT("TEAL  /  ")) + ABBMatchState::PositionName(Rider->Position).ToUpper(),40,UH-99,1,Cream);
    Text(TEXT("WASD  Fly    SPACE / CTRL  Rise / descend"),40,UH-67,.8,Muted);
    Text(TEXT("E  Grab / catch    LMB  Throw    TAB  Roles    P  Stoppage"),40,UH-43,.75,Muted);
    Rect(UW/2-350,UH-161,700,36,Ink);
    Text(Match->Announcement,UW/2-334,UH-154,.79,Cream);
    DrawLine(W/2-10*S,H/2,W/2-4*S,H/2,Cream,1.3f*S);
    DrawLine(W/2+4*S,H/2,W/2+10*S,H/2,Cream,1.3f*S);
    DrawLine(W/2,H/2-10*S,W/2,H/2-4*S,Cream,1.3f*S);
    DrawLine(W/2,H/2+4*S,W/2,H/2+10*S,Cream,1.3f*S);

    ABBBall* Held = nullptr;
    ABBBall* ChaseTarget = nullptr;
    float BestDist = TNumericLimits<float>::Max();
    const bool CanChase = Rider->Position == 3 || Rider->Position == 5 || Match->Phase == TEXT("DONNYBROOK");
    Text(TEXT("BALLS IN PLAY"),UW-244,143,.78f,Muted);
    for (TActorIterator<ABBBall> It(GetWorld()); It; ++It)
    {
        ABBBall* B = *It;
        if (B->Holder == Rider) Held = B;
        const FLinearColor BallColor = B->BallIndex == 0 ? Copper : B->BallIndex < 3 ? Violet : B->BallIndex == 3 ? Copper : B->BallIndex == 4 ? Gold : Muted;
        const float StatusY = 169 + FMath::Clamp(B->BallIndex,0,6) * 48;
        Rect(UW-252,StatusY-3,228,43,Ink);
        Rect(UW-252,StatusY-3,3,43,B->bActive ? BallColor : Muted*.5f);
        Text(B->DisplayName(),UW-240,StatusY,.82f,BallColor);
        FString BallState = B->bActive ? TEXT("FREE") : TEXT("OUT OF PLAY");
        if (IsValid(B->Holder))
            BallState = (B->Holder->TeamIndex ? TEXT("COPPER / ") : TEXT("TEAL / ")) + ABBMatchState::PositionName(B->Holder->Position).ToUpper();
        else if (B->ReturnIn > 0)
        {
            const int32 ReturnSeconds = FMath::CeilToInt(B->ReturnIn);
            BallState = FString::Printf(TEXT("%s %d:%02d"), B->BallStatus == TEXT("scheduled_release") ? TEXT("RELEASE IN") : TEXT("RETURNS IN"), ReturnSeconds/60, ReturnSeconds%60);
        }
        else if (B->BallStatus == TEXT("crown")) BallState = TEXT("NO CROWN / RETURNING");
        else if (!Match->bLive && B->bActive) BallState = TEXT("WAITING FOR PLAY");
        Text(BallState,UW-240,StatusY+20,.67f,Muted);
        if (B->IsChase())
        {
            const float D = FVector::Distance(Rider->GetActorLocation(),B->GetActorLocation());
            if (CanChase && B->bActive && D < BestDist) { BestDist = D; ChaseTarget = B; }
        }
        if (!B->bActive || B->Holder == Rider) continue;
        FVector2D Screen;
        if (PlayerOwner->ProjectWorldLocationToScreen(B->GetActorLocation(), Screen) && Screen.X > 30 && Screen.X < W-100 && Screen.Y > 125*S && Screen.Y < H-175*S)
        {
            FLinearColor Color = B->BallIndex == 0 ? Copper : B->BallIndex < 3 ? Violet : B->BallIndex == 3 ? Copper : B->BallIndex == 4 ? Gold : Muted;
            float D = FVector::Dist(Rider->GetActorLocation(),B->GetActorLocation())/100.f;
            if (B->IsChase() || D < 22.f)
            {
                DrawRect(Ink,Screen.X-4*S,Screen.Y+18*S,170*S,22*S);
                DrawText(FString::Printf(TEXT("%s  %.1fm"),*B->DisplayName(),D),Color,Screen.X,Screen.Y+20*S,Font,.75f*S);
            }
        }
    }
    if (Held)
    {
        Text(TEXT("CARRYING ")+Held->DisplayName()+TEXT("  |  LMB TO THROW"),UW/2-190,UH/2+90,.95,Cream);
        if (Held->IsBludger()) Text(TEXT("Release within 3 seconds. Team control limit: 6 seconds."),UW/2-225,UH/2+116,.8,Gold);
        else if (CanChase) Text(TEXT("Release your ball before attempting a chase capture."),UW/2-200,UH/2+116,.8,Muted);
    }
    else if (ChaseTarget && Match->bLive)
    {
        const bool InRange = BestDist <= 380;
        const float Progress = ChaseTarget->CapturingRider == Rider ? ChaseTarget->CaptureProgress : 0;
        const FLinearColor Color = ChaseTarget->BallIndex == 3 ? Copper : Gold;
        Rect(UW/2-185,UH/2+96,370,61,Ink);
        Text(FString::Printf(TEXT("%s  %.1fm  |  %s"),*ChaseTarget->DisplayName(),BestDist/100.f,InRange ? TEXT("HOLD E TO CATCH") : TEXT("CLOSE TO 3.8m")),UW/2-170,UH/2+105,.9,Color);
        Rect(UW/2-170,UH/2+139,340,5,Muted*.3f);
        Rect(UW/2-170,UH/2+139,340*Progress,5,Color);
        FVector2D Screen;
        if (!PlayerOwner->ProjectWorldLocationToScreen(ChaseTarget->GetActorLocation(),Screen) || Screen.X < 0 || Screen.X > W || Screen.Y < 0 || Screen.Y > H)
        {
            const FVector To = ChaseTarget->GetActorLocation()-Rider->GetActorLocation();
            const float Side = FVector::DotProduct(To,FRotationMatrix(PlayerOwner->GetControlRotation()).GetUnitAxis(EAxis::Y));
            Text(Side < 0 ? TEXT("< CHASE TARGET") : TEXT("CHASE TARGET >"), Side < 0 ? 28 : UW-185,UH/2,1,Color);
        }
    }
    if (Rider->StunRemaining > 0)
    {
        Rect(UW/2-155,UH/2-90,310,42,Ink);
        Text(TEXT("STUNNED - RECOVERING"),UW/2-134,UH/2-79,1.1,Copper);
    }
    if (Match->Status == TEXT("FINAL") || Match->Status == TEXT("CERTIFYING RESULT"))
    {
        const bool bFinal = Match->Status == TEXT("FINAL");
        const FLinearColor ResultColor = Match->Winner == 0 ? Teal : Copper;
        Rect(UW/2-300,188,600,210,Ink);
        Rect(UW/2-300,188,600,4,bFinal ? ResultColor : Gold);
        Text(bFinal ? (Match->Winner == 0 ? TEXT("TEAL WINS") : TEXT("COPPER WINS")) : TEXT("RESULT UNDER REVIEW"),UW/2-265,216,1.8f,bFinal ? ResultColor : Gold);
        Text(FString::Printf(TEXT("TEAL  %d     /     COPPER  %d"),Match->TealScore,Match->CopperScore),UW/2-265,273,1.2f,Cream);
        Text(bFinal ? TEXT("Certified result. Close and relaunch to play again.") : TEXT("Resolving the final play and outstanding decisions."),UW/2-265,332,.85f,Muted);
    }
    else if (!Match->bLive || Rider->bShowRoster)
    {
        Rect(UW/2-300,164,600,324,Ink);
        Text(Match->bLive ? TEXT("POSITION GUIDE") : Match->Status,UW/2-275,184,1.4,Cream);
        Text(Match->bLive ? TEXT("Position changes unlock at stoppages.") : TEXT("Choose a position. T switches team. Host: ENTER to start."),UW/2-275,221,.85,Muted);
        const TCHAR* Descriptions[] = {TEXT("Defend goals. Take protected scoring-ball restarts."),TEXT("Carry and shoot Quaffles and Quarks."),TEXT("Intercept, carry and shoot scoring balls."),TEXT("Scoring balls + chase. Release before catching."),TEXT("Use your Hurley to control and strike Bludgers."),TEXT("Chase Snipe and Snitch. No scoring-ball possession.")};
        for (int32 I=0;I<6;++I)
        {
            const float Y=258+I*32;
            if (Rider->Position == I) Rect(UW/2-280,Y-2,560,29,FLinearColor(.05,.17,.18,.9));
            Text(FString::Printf(TEXT("%d  %s"),I+1,*ABBMatchState::PositionName(I)),UW/2-267,Y,.86,Rider->Position==I?Teal:Cream);
            Text(Descriptions[I],UW/2-110,Y,.75,Muted);
        }
        Text(TEXT("QUAFFLE 13   /   QUARK 37   /   SNIPE 69   /   SNITCH 150 (OT 300)"),UW/2-275,459,.75,Gold);
    }
}
