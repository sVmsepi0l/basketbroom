#include "BBHUD.h"
#include "BBMatchState.h"
#include "BBBall.h"
#include "BBRiderCharacter.h"
#include "BBSpellCatalog.h"
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
    const bool Pad = Rider->bUsingGamepad;
    UpdateAudioFeedback(Match, Rider);
    const float W = Canvas->SizeX, H = Canvas->SizeY;
    const float S = FMath::Min(W/1600.f, H/900.f);
    const FLinearColor Ink(.015,.026,.038,.90), Muted(.56,.67,.7,1), Cream(.94,.91,.82,1), Teal(.12,.9,.73,1), Copper(1,.46,.20,1), Gold(1,.77,.24,1), Violet(.7,.38,1,1);
    UFont* Font = GEngine->GetMediumFont();
    auto Rect = [&](float X,float Y,float Width,float Height,FLinearColor Color) { DrawRect(Color,X*S,Y*S,Width*S,Height*S); };
    auto Text = [&](const FString& T,float X,float Y,float Size,FLinearColor Color) { DrawText(T,Color,X*S,Y*S,Font,Size*S,false); };
    const float UW = W/S, UH = H/S;
    auto WrappedText = [&](const FString& Message, float X, float Y, float Size, FLinearColor Color,
                           float MaxWidth, int32 MaxLines)
    {
        TArray<FString> Words;
        Message.ParseIntoArrayWS(Words);
        FString Line;
        int32 Row = 0;
        for (const FString& Word : Words)
        {
            const FString Candidate = Line.IsEmpty() ? Word : Line + TEXT(" ") + Word;
            float Width = 0.f, Height = 0.f;
            GetTextSize(Candidate, Width, Height, Font, Size);
            if (!Line.IsEmpty() && Width > MaxWidth)
            {
                Text(Line, X, Y + Row * 20.f, Size, Color);
                if (++Row >= MaxLines) return;
                Line = Word;
            }
            else Line = Candidate;
        }
        if (!Line.IsEmpty() && Row < MaxLines) Text(Line, X, Y + Row * 20.f, Size, Color);
    };
    Rect(UW/2-320,20,640,102,Ink);
    Rect(UW/2-320,20,4,102,Teal); Rect(UW/2+316,20,4,102,Copper);
    Text(TEXT("TEAL"),UW/2-294,32,1,Teal); Text(TEXT("COPPER"),UW/2+191,32,1,Copper);
    Text(FString::FromInt(Match->TealScore),UW/2-294,59,2,Cream);
    Text(FString::FromInt(Match->CopperScore),UW/2+191,59,2,Cream);
    // Ignore sub-millisecond conversion noise at exact clock boundaries.
    const int32 Seconds = FMath::Max(0,FMath::CeilToInt(Match->SecondsLeft-.001f));
    const FString Clock = Match->Phase == TEXT("DONNYBROOK") ? TEXT("SUDDEN DEATH") : FString::Printf(TEXT("%02d:%02d"),Seconds/60,Seconds%60);
    Text(Clock,UW/2-55,35,1.5f,Cream);
    Text(Match->Phase + (Match->Phase == TEXT("REGULATION") ? FString::Printf(TEXT("  Q%d/4"),Match->Quarter) : TEXT("")),UW/2-78,79,.78,Muted);
    Text(Match->bPractice ? TEXT("PRACTICE CLOCKS") : TEXT("REGULATION CLOCKS"),24,23,.78,Muted);
    Text(GetNetMode() == NM_Standalone ? TEXT("LOCAL SCRIMMAGE") : GetNetMode() == NM_Client ? TEXT("NETWORK CLIENT") : TEXT("LISTEN SERVER"),24,45,.78,Muted);
    const bool SpellReady = BBSpellCatalog::IsImplemented(Rider->SelectedSpell);
    Rect(22,76,420,59,Ink);
    Rect(22,76,3,59,SpellReady ? Violet : Muted);
    Text(FString(Pad ? TEXT("RB  ") : TEXT("Q  ")) + BBSpellCatalog::Name(Rider->SelectedSpell),38,83,.95f,SpellReady ? Cream : Muted);
    const TCHAR* SpellControls = TEXT("Z / X  Select    R  Protego    V  Spellbook");
    if (Pad)
        SpellControls = Match->bConductReviewPending ? TEXT("D-pad Up/Down  Disposition    Menu  Confirm")
            : Rider->bShowRoster ? TEXT("View  Close roles to select spells    Y  Book")
            : TEXT("D-pad L/R  Spells    LB  Protego    Y  Book");
    Text(SpellControls,38,108,.76f,Muted);
    const FString SpellState = !SpellReady ? TEXT("ADAPTER DUE") : Rider->DisarmRemaining > 0.f ? TEXT("DISARMED")
        : Rider->SpellCooldownRemaining > 0.f ? FString::Printf(TEXT("%.1fs"),Rider->SpellCooldownRemaining) : TEXT("READY");
    Text(SpellState,335,86,.70f,SpellReady && Rider->SpellCooldownRemaining <= 0.f ? Teal : Gold);
    Text(Match->bBloodbroom ? TEXT("BLOODBROOM  /  BB-0 PLAYTEST") : TEXT("BASKETBROOM  /  BB-0 PLAYTEST"),UW/2-170,128,.77f,Match->bBloodbroom ? Copper : Muted);
    if (Match->PendingPenaltyCount > 0)
    {
        Rect(22,142,420,117,Ink);
        Rect(22,142,4,117,Gold);
        Text(FString::Printf(TEXT("PENALTIES DUE  %d"),Match->PendingPenaltyCount),40,155,.88f,Gold);
        TArray<FString> Details;
        Match->PendingPenaltySummary.ParseIntoArray(Details,TEXT(" | "),false);
        for (int32 I=0;I<FMath::Min(Details.Num(),3);++I)
            Text(Details[I].ToUpper().Left(48),40,181+I*23,.76f,I==0?Cream:Muted);
    }
    if (Match->ConductFoulCount > 0 || Match->bConductReviewPending)
    {
        Rect(22,275,420,132,Ink);
        Rect(22,275,4,132,Copper);
        Text(FString::Printf(TEXT("CONDUCT CALLS  %d"),Match->ConductFoulCount),40,286,.9f,Copper);
        WrappedText(Match->LastConductCall,40,314,.76f,Cream,380,4);
    }
    Rect(22,UH-108,420,82,Ink);
    Rect(22,UH-108,4,82,Rider->TeamIndex ? Copper : Teal);
    Text((Rider->TeamIndex ? TEXT("COPPER  /  ") : TEXT("TEAL  /  ")) + ABBMatchState::PositionName(Rider->Position).ToUpper(),40,UH-99,1,Cream);
    Text(Pad ? TEXT("LS  Fly   RS  Look   A / B  Rise / descend") : TEXT("WASD  Fly    SPACE / CTRL  Rise / descend"),40,UH-67,.8,Muted);
    Text(Pad ? TEXT("X  Catch   RT  Throw   View  Roles   Menu  Pause") : TEXT("E  Grab / catch    LMB  Throw    TAB  Roles    P  Stoppage"),40,UH-43,.75,Muted);
    Rect(UW-310,UH-106,286,79,Ink);
    Text(FString::Printf(TEXT("VITALITY  %d"),FMath::RoundToInt(Rider->Vitality)),UW-293,UH-96,.78f,Cream);
    Rect(UW-293,UH-72,252,4,Muted*.3f);
    Rect(UW-293,UH-72,252*FMath::Clamp(Rider->Vitality/100.f,0.f,1.f),4,Rider->Vitality < 30.f ? Copper : Teal);
    FString Effects;
    if (Rider->ShieldRemaining > 0.f) Effects += FString::Printf(TEXT("SHIELD %.1f  "),Rider->ShieldRemaining);
    if (Rider->ImpedimentRemaining > 0.f) Effects += FString::Printf(TEXT("SLOWED %.1f  "),Rider->ImpedimentRemaining);
    if (Rider->DisarmRemaining > 0.f) Effects += FString::Printf(TEXT("DISARMED %.1f"),Rider->DisarmRemaining);
    WrappedText(Effects.IsEmpty() ? (Pad ? TEXT("LB  PROTEGO / DEFEND BEFORE IMPACT") : TEXT("R  PROTEGO  /  DEFEND BEFORE IMPACT")) : Effects,
        UW-293,UH-54,.68f,Effects.IsEmpty()?Muted:Gold,252,2);
    Rect(UW/2-350,UH-161,700,36,Ink);
    FString Announcement = Match->Announcement;
    if (Pad)
    {
        Announcement.ReplaceInline(TEXT("ENTER"), TEXT("Menu"));
        Announcement.ReplaceInline(TEXT("Hold E"), TEXT("Hold X"));
        Announcement.ReplaceInline(TEXT("with 1-6"), TEXT("with D-pad Up/Down"));
    }
    WrappedText(Announcement,UW/2-334,UH-154,.79,Cream,670,1);
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
            const int32 ReturnSeconds = FMath::Max(0,FMath::CeilToInt(B->ReturnIn-.001f));
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
        if (!Match->bLive || Rider->bShowRoster || Rider->bShowSpellbook || !B->bActive || B->Holder == Rider) continue;
        FVector2D Screen;
        if (PlayerOwner->ProjectWorldLocationToScreen(B->GetActorLocation(), Screen) && Screen.X > 30 && Screen.X < W-100 && Screen.Y > 125*S && Screen.Y < H-175*S
            && !(Screen.X+170*S > W-252*S && Screen.Y < 510*S))
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
        Text(TEXT("CARRYING ")+Held->DisplayName()+(Pad ? TEXT("  |  RT TO THROW") : TEXT("  |  LMB TO THROW")),UW/2-190,UH/2+90,.95,Cream);
        if (Held->IsBludger()) Text(TEXT("Release within 3 seconds. Team control limit: 6 seconds."),UW/2-225,UH/2+116,.8,Gold);
        else if (CanChase) Text(TEXT("Release your ball before attempting a chase capture."),UW/2-200,UH/2+116,.8,Muted);
    }
    else if (ChaseTarget && Match->bLive)
    {
        const bool InRange = BestDist <= 380;
        const float Progress = ChaseTarget->CapturingRider == Rider ? ChaseTarget->CaptureProgress : 0;
        const FLinearColor Color = ChaseTarget->BallIndex == 3 ? Copper : Gold;
        Rect(UW/2-185,UH/2+96,370,61,Ink);
        Text(FString::Printf(TEXT("%s  %.1fm  |  %s"),*ChaseTarget->DisplayName(),BestDist/100.f,InRange ? (Pad ? TEXT("HOLD X TO CATCH") : TEXT("HOLD E TO CATCH")) : TEXT("CLOSE TO 3.8m")),UW/2-170,UH/2+105,.9,Color);
        Rect(UW/2-170,UH/2+139,340,5,Muted*.3f);
        Rect(UW/2-170,UH/2+139,340*Progress,5,Color);
        FVector2D Screen;
        if (!PlayerOwner->ProjectWorldLocationToScreen(ChaseTarget->GetActorLocation(),Screen) || Screen.X < 0 || Screen.X > W || Screen.Y < 0 || Screen.Y > H)
        {
            const FVector To = ChaseTarget->GetActorLocation()-Rider->GetActorLocation();
            const float Side = FVector::DotProduct(To,FRotationMatrix(PlayerOwner->GetControlRotation()).GetUnitAxis(EAxis::Y));
            // Keep directional guidance below the seven equipment cards.
            Text(Side < 0 ? TEXT("< CHASE TARGET") : TEXT("CHASE TARGET >"), Side < 0 ? 28 : UW-224,FMath::Max(UH/2,530.f),1,Color);
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
        Text(bFinal ? (Pad ? TEXT("Certified result. Host: Menu to play again.") : TEXT("Certified result. Host: ENTER to play again.")) : TEXT("Resolving the final play and outstanding decisions."),UW/2-265,332,.85f,Muted);
    }
    else if (Match->bConductReviewPending)
    {
        Rect(UW/2-330,164,660,256,Ink);
        Rect(UW/2-330,164,660,4,Copper);
        Text(TEXT("PLAYTEST REFEREE"),UW/2-305,185,1.4f,Copper);
        WrappedText(Match->LastConductCall,UW/2-305,226,.88f,Cream,610,3);
        if (Pad)
        {
            Text(TEXT("Host: D-pad Up = possession / Down = ejection"),UW/2-305,296,.82f,Gold);
            Text(Rider->GamepadRefereeChoice == 1 ? TEXT("POSSESSION AWARD selected. Menu to confirm.")
                : Rider->GamepadRefereeChoice == 2 ? TEXT("EJECTION selected. Menu to confirm.")
                : TEXT("Choose a disposition before confirming with Menu."),UW/2-305,328,.82f,Cream);
        }
        else WrappedText(Match->ConductReviewStatus,UW/2-305,296,.85f,Gold,610,3);
        Text(TEXT("BB-0 dispositions are provisional. Play remains stopped."),UW/2-305,385,.77f,Muted);
    }
    else if (Rider->bShowSpellbook)
    {
        Rect(UW/2-460,158,920,508,Ink);
        Rect(UW/2-460,158,920,3,Violet);
        Text(TEXT("SPELLBOOK"),UW/2-434,176,1.35f,Cream);
        Text(Pad ? TEXT("D-pad L/R  Select    RB  Cast    LB  Protego    Y  Close") : TEXT("Z / X  Select     Q  Cast     R  Protego     V  Close"),UW/2-434,211,.84f,Muted);
        Text(TEXT("BB-0 SPORTING ADAPTATIONS"),UW/2+174,179,.72f,Gold);
        const int32 Rows = (BBSpellCatalog::Count()+1)/2;
        for (int32 I=0; I<BBSpellCatalog::Count(); ++I)
        {
            const float X = UW/2-434 + (I/Rows)*445, Y = 246 + (I%Rows)*23;
            const bool bSelected = Rider->SelectedSpell == I, bImplemented = BBSpellCatalog::IsImplemented(I);
            if (bSelected) Rect(X-6,Y-2,421,22,FLinearColor(.13f,.075f,.20f,.95f));
            Text((bSelected ? TEXT(">  ") : TEXT("   "))+BBSpellCatalog::Name(I),X,Y,.78f,bSelected?Cream:bImplemented?Muted:Muted*.65f);
            Text(bImplemented?TEXT("AVAILABLE"):TEXT("LATER"),X+329,Y,.66f,bImplemented?Teal:Gold);
        }
        WrappedText(BBSpellCatalog::Description(Rider->SelectedSpell),UW/2-434,625,.80f,Cream,866,2);
    }
    else if (!Match->bLive || Rider->bShowRoster)
    {
        Rect(UW/2-300,164,600,356,Ink);
        Text(Match->bLive ? TEXT("POSITION GUIDE") : Match->Status,UW/2-275,184,1.4,Cream);
        Text(Match->bLive ? TEXT("Position changes unlock at stoppages.") : (Pad ? TEXT("D-pad Up/Down: position. Host: Menu to start / resume.") : TEXT("Choose a position. T switches team. Host: ENTER to start.")),UW/2-275,221,.85,Muted);
        const TCHAR* Descriptions[] = {TEXT("Defend goals. Take protected scoring-ball restarts."),TEXT("Carry and shoot Quaffles and Quarks."),TEXT("Intercept, carry and shoot scoring balls."),TEXT("Scoring balls + chase. Release before catching."),TEXT("Control Bludgers. Throw before the control limit."),TEXT("Chase Snipe and Snitch. No scoring-ball possession.")};
        for (int32 I=0;I<6;++I)
        {
            const float Y=258+I*32;
            if (Rider->Position == I) Rect(UW/2-280,Y-2,560,29,FLinearColor(.05,.17,.18,.9));
            Text(FString::Printf(TEXT("%d  %s"),I+1,*ABBMatchState::PositionName(I)),UW/2-267,Y,.86,Rider->Position==I?Teal:Cream);
            Text(Descriptions[I],UW/2-110,Y,.75,Muted);
        }
        Text(TEXT("QUAFFLE 13   /   QUARK 37   /   SNIPE 69   /   SNITCH 150 (OT 300)"),UW/2-275,459,.75,Gold);
        if (Pad)
            Text(Rider->bShowRoster ? TEXT("D-pad Left: team / Right: Bloodbroom (lobby). Y: book.") : TEXT("View: roster + team / variant controls. Y: spellbook."),UW/2-275,489,.77f,Muted);
        else Text(Match->Status == TEXT("LOBBY") ? TEXT("V  Spellbook    Host: B toggles Bloodbroom before play") : TEXT("V  Spellbook    Q  Cast    R  Protego"),UW/2-275,489,.77f,Muted);
    }
    // Keep server feedback below overlays, and acknowledge only text actually
    // presented by this owner's HUD. The Rider sends the RPC on a later Tick.
    if (Rider->SpellFeedbackRemaining > 0.f && !Rider->SpellFeedback.IsEmpty())
    {
        Rect(UW/2-380,UH-221,760,52,Ink);
        Rect(UW/2-380,UH-221,3,52,Violet);
        WrappedText(Rider->SpellFeedback,UW/2-363,UH-213,.86f,Cream,725,2);
        Rider->MarkSpellFeedbackDisplayed();
    }
}
