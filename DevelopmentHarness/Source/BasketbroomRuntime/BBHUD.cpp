#include "BBHUD.h"
#include "BBPauseMenu.h"
#include "Kismet/GameplayStatics.h"
#include "BBMatchState.h"
#include "BBBall.h"
#include "BBRiderCharacter.h"
#include "BBSpellCatalog.h"
#include "Engine/Canvas.h"
#include "Engine/Engine.h"
#include "Engine/World.h"
#include "EngineUtils.h"
#include "GameFramework/PlayerController.h"
#include "Components/InputComponent.h"
#include "HAL/PlatformTime.h"
#include "Misc/ConfigCacheIni.h"

void ABBHUD::DrawHUD()
{
    Super::DrawHUD();
    if (!Canvas || !PlayerOwner || Canvas->SizeX <= 0 || Canvas->SizeY <= 0) return;
    ABBMatchState* Match = GetWorld()->GetGameState<ABBMatchState>();
    ABBRiderCharacter* Rider = Cast<ABBRiderCharacter>(PlayerOwner->GetPawn());
    if (!Match || !Rider) return;
    const bool Pad = Rider->bUsingGamepad;
    const bool Penalty = Match->bPenaltyShotActive;
    const bool PenaltyDecision = Penalty && Match->PenaltyShotSecondsLeft <= 0.f;
    const bool PenaltyShooter = Penalty && Rider->RosterIndex == Match->PenaltyShooterSlot;
    const bool PenaltyKeeper = Penalty && Rider->RosterIndex == Match->PenaltyKeeperSlot;
    UpdateAudioFeedback(Match, Rider);
    if (Rider->bPauseMenuOpen) { DrawPauseMenu(Match, Rider); return; }
    const float W = Canvas->SizeX, H = Canvas->SizeY;
    const float S = FMath::Min(W/1600.f, H/900.f);
    // Match the sporting uniforms: Forest Service mint with a phthalo tint,
    // and copper warmed with a small canary-yellow contribution.
    const FLinearColor Teal = FLinearColor::FromSRGBColor(FColor(138,191,163));
    const FLinearColor Copper = FLinearColor::FromSRGBColor(FColor(187,120,49));
    const FLinearColor Ink(.015,.026,.038,.90), Muted(.56,.67,.7,1), Cream(.94,.91,.82,1), Gold(1,.77,.24,1), Violet(.7,.38,1,1);
    UFont* Font = GEngine->GetMediumFont();
    auto Rect = [&](float X,float Y,float Width,float Height,FLinearColor Color) { DrawRect(Color,X*S,Y*S,Width*S,Height*S); };
    auto Text = [&](const FString& T,float X,float Y,float Size,FLinearColor Color)
    {
        if (!Pad) { DrawText(T,Color,X*S,Y*S,Font,Size*S,false); return; }
        // Draw the same geometric PlayStation symbols used by the controller
        // map. This works even when the HUD font lacks Unicode face glyphs.
        int32 Start=0;
        while (Start<T.Len())
        {
            int32 Next=T.Len(); FString Symbol;
            for (const TCHAR* Name : {TEXT("Cross"),TEXT("Square"),TEXT("Triangle"),TEXT("Circle")})
            {
                int32 At=T.Find(Name,ESearchCase::CaseSensitive,ESearchDir::FromStart,Start);
                const int32 Length=FCString::Strlen(Name);
                while (At!=INDEX_NONE && ((At>0 && FChar::IsAlnum(T[At-1]))
                    || (At+Length<T.Len() && FChar::IsAlnum(T[At+Length]))))
                    At=T.Find(Name,ESearchCase::CaseSensitive,ESearchDir::FromStart,At+Length);
                if (At!=INDEX_NONE && At<Next) { Next=At; Symbol=Name; }
            }
            const FString Prefix=T.Mid(Start,Next-Start);
            DrawText(Prefix,Color,X*S,Y*S,Font,Size*S,false);
            float Width=0.f,Height=0.f; GetTextSize(Prefix,Width,Height,Font,Size); X+=Width;
            if (Symbol.IsEmpty()) break;
            DrawPadGlyph(Symbol,X+8.f*Size,Y+10.f*Size,6.f*Size,Color,S);
            X+=18.f*Size; Start=Next+Symbol.Len();
        }
    };
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
    Text(FString(Pad ? TEXT("R1  ") : TEXT("Q  ")) + BBSpellCatalog::Name(Rider->SelectedSpell),38,83,.95f,SpellReady ? Cream : Muted);
    const TCHAR* SpellControls = TEXT("Z / X  Select    R  Protego    V  Spellbook");
    if (Pad)
        SpellControls = Match->bConductReviewPending ? TEXT("D-pad  Choose call    Cross  Confirm")
            : Rider->bShowRoster ? TEXT("Touchpad: close roles    Triangle Book")
            : TEXT("D-pad L/R  Spells    L1  Protego    Triangle Book");
    if (Penalty) SpellControls = Match->bFreeShot ? TEXT("FREE SHOT  /  WANDWORK LOCKED") : TEXT("PENALTY SHOT  /  WANDWORK LOCKED");
    Text(SpellControls,38,108,.76f,Muted);
    const FString SpellState = Penalty ? TEXT("LOCKED") : !SpellReady ? TEXT("ADAPTER DUE") : Rider->DisarmRemaining > 0.f ? TEXT("DISARMED")
        : Rider->SpellCooldownRemaining > 0.f ? FString::Printf(TEXT("%.1fs"),Rider->SpellCooldownRemaining) : TEXT("READY");
    Text(SpellState,335,86,.70f,!Penalty && SpellReady && Rider->SpellCooldownRemaining <= 0.f ? Teal : Gold);
    Text(Match->bBloodbroom ? TEXT("BLOODBROOM  /  BB-0 PLAYTEST") : TEXT("BASKETBROOM  /  BB-0 PLAYTEST"),UW/2-170,128,.77f,Match->bBloodbroom ? Copper : Muted);
    if ((Rider->SelectedSpell == 29 || Rider->SelectedSpell == 30) && Match->PendingPenaltyCount == 0)
    {
        const int32 Charge = Match->GetAncientMagicCharge(Rider);
        Rect(22,137,420,32,Ink);
        Text(FString::Printf(TEXT("ANCIENT MAGIC  %d / 100"),Charge),38,144,.78f,Gold);
        Rect(272,148,150,5,FLinearColor(.12,.16,.18,1));
        Rect(272,148,150.f * FMath::Clamp(Charge / 100.f,0.f,1.f),5,Gold);
    }
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
    if (Match->bModerateAdvantageArmed || Match->bConductAdvantageLive)
    {
        Rect(UW/2-305,153,610,47,Ink);
        Rect(UW/2-305,153,4,47,Gold);
        Text(Match->bConductAdvantageLive ? TEXT("ADVANTAGE / MODERATE SHOT OWED") : TEXT("HOST PLAYTEST CALL / NEXT SAFE BASIC-CAST MOBBING: MODERATE"),UW/2-289,161,.74f,Gold);
        Text(Match->bConductAdvantageLive ? TEXT("Play continues while the offended team keeps the ball.") : (Pad ? TEXT("Touchpad opens roster; Cross toggles the one-use advantage call.") : TEXT("F10 toggles this one-use call. Dangerous fouls still stop play.")),UW/2-289,181,.68f,Muted);
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
    if (PenaltyDecision)
    {
        Text(TEXT("SHOT RESOLVED / PROTECTED RESTART NEXT"),40,UH-67,.8,Gold);
        Text(TEXT("Wait for the referee to return the ball to the keeper."),40,UH-43,.75,Muted);
    }
    else if (PenaltyShooter)
    {
        Text(Pad ? TEXT("L3 + RS Aim    Cross Shoot") : TEXT("MOUSE  Aim    LMB  Shoot once"),40,UH-67,.8,Gold);
        Text(TEXT("Stay at the mark. The full attempt lasts five seconds."),40,UH-43,.75,Muted);
    }
    else if (PenaltyKeeper)
    {
        Text(Pad ? TEXT("LS Fly   RS Height / camera   L2 Brake") : TEXT("WASD  Fly    SPACE / CTRL  Rise / descend"),40,UH-67,.8,Gold);
        Text(TEXT("Block the ball with your body. Stay in the goal area."),40,UH-43,.75,Muted);
    }
    else if (Penalty)
    {
        Text(Pad ? TEXT("RS  Look around") : TEXT("MOUSE  Look around"),40,UH-67,.8,Muted);
        Text(TEXT("Shot in progress. Movement and roles locked."),40,UH-43,.75,Muted);
    }
    else
    {
        Text(Pad ? TEXT("LS Fly   RS Height / camera   L2 Brake") : TEXT("WASD  Fly    SPACE / CTRL  Rise / descend"),40,UH-67,.8,Muted);
        Text(Pad ? TEXT("Square Catch   Cross Throw   Options Menu") : TEXT("E  Grab / catch    LMB  Throw    TAB  Roles    P  Stoppage"),40,UH-43,.75,Muted);
    }
    Rect(UW-310,UH-173,286,58,Ink);
    const float Boost = FMath::Clamp(Rider->FlightBoostCharge,0.f,100.f);
    const bool Super = Rider->FlightSuperRemaining > 0.f;
    const FLinearColor BoostColor = Super || Boost >= 99.99f ? Gold : Teal;
    Text(Super ? FString::Printf(TEXT("SUPER BOOST  %.1fs"),Rider->FlightSuperRemaining)
        : FString::Printf(TEXT("R2  BOOST  %d%%"),FMath::RoundToInt(Boost)),UW-293,UH-165,.86f,BoostColor);
    Rect(UW-293,UH-141,252,5,Muted*.3f);
    Rect(UW-293,UH-141,252*Boost/100.f,5,BoostColor);
    Text(Boost >= 99.99f ? TEXT("Release R2, then press for SUPER") : TEXT("Score +25 / legal Bludger hit +15"),UW-293,UH-131,.60f,Muted);
    Rect(UW-310,UH-106,286,79,Ink);
    Text(FString::Printf(TEXT("VITALITY  %d"),FMath::RoundToInt(Rider->Vitality)),UW-293,UH-96,.78f,Cream);
    Rect(UW-293,UH-72,252,4,Muted*.3f);
    Rect(UW-293,UH-72,252*FMath::Clamp(Rider->Vitality/100.f,0.f,1.f),4,Rider->Vitality < 30.f ? Copper : Teal);
    FString Effects;
    if (Rider->ShieldRemaining > 0.f) Effects += FString::Printf(TEXT("SHIELD %.1f  "),Rider->ShieldRemaining);
    if (Rider->ImpedimentRemaining > 0.f) Effects += FString::Printf(TEXT("SLOWED %.1f  "),Rider->ImpedimentRemaining);
    if (Rider->DisarmRemaining > 0.f) Effects += FString::Printf(TEXT("DISARMED %.1f"),Rider->DisarmRemaining);
    WrappedText(Penalty ? TEXT("WANDWORK LOCKED / EFFECT CLOCKS FROZEN") : Effects.IsEmpty() ? (Pad ? TEXT("L1  PROTEGO / DEFEND BEFORE IMPACT") : TEXT("R  PROTEGO  /  DEFEND BEFORE IMPACT")) : Effects,
        UW-293,UH-54,.68f,Effects.IsEmpty()?Muted:Gold,252,2);
    Rect(UW/2-350,UH-161,700,36,Ink);
    FString Announcement = Match->Announcement;
    if (Pad)
    {
        Announcement.ReplaceInline(TEXT("ENTER"), TEXT("Cross"));
        Announcement.ReplaceInline(TEXT("Hold E"), TEXT("Hold Square"));
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
    Text(Penalty ? TEXT("SHOT / BALLS") : TEXT("BALLS IN PLAY"),UW-244,143,.78f,Muted);
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
        else if (Penalty && Match->IsPenaltyBallActive(B))
            BallState = Match->bPenaltyShotReleased ? TEXT("SHOT / IN FLIGHT") : TEXT("SHOT / AT THE MARK");
        else if (Penalty && B->bActive) BallState = TEXT("FROZEN / SHOT");
        else if (!Match->bLive && B->bActive) BallState = TEXT("WAITING FOR PLAY");
        Text(BallState,UW-240,StatusY+20,.67f,Muted);
        if (B->IsChase())
        {
            const float D = FVector::Distance(Rider->GetActorLocation(),B->GetActorLocation());
            if (CanChase && B->bActive && D < BestDist) { BestDist = D; ChaseTarget = B; }
        }
        if ((!Match->bLive && !(Penalty && Match->IsPenaltyBallActive(B))) || Rider->bShowRoster || Rider->bShowSpellbook || !B->bActive || B->Holder == Rider) continue;
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
    if (Held && !Penalty)
    {
        Text(TEXT("CARRYING ")+Held->DisplayName()+(Pad ? TEXT("  |  CROSS TO THROW") : TEXT("  |  LMB TO THROW")),UW/2-190,UH/2+90,.95,Cream);
        if (Held->IsBludger()) Text(TEXT("Release within 3 seconds. Team control limit: 6 seconds."),UW/2-225,UH/2+116,.8,Gold);
        else if (CanChase) Text(TEXT("Release your ball before attempting a chase capture."),UW/2-200,UH/2+116,.8,Muted);
    }
    else if (ChaseTarget && Match->bLive)
    {
        const bool InRange = BestDist <= 380;
        const float Progress = ChaseTarget->CapturingRider == Rider ? ChaseTarget->CaptureProgress : 0;
        const FLinearColor Color = ChaseTarget->BallIndex == 3 ? Copper : Gold;
        Rect(UW/2-185,UH/2+96,370,61,Ink);
        Text(FString::Printf(TEXT("%s  %.1fm  |  %s"),*ChaseTarget->DisplayName(),BestDist/100.f,InRange ? (Pad ? TEXT("HOLD SQUARE TO CATCH") : TEXT("HOLD E TO CATCH")) : TEXT("CLOSE TO 3.8m")),UW/2-170,UH/2+105,.9,Color);
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
    if ((Rider->HasSpellMovementLock() || Rider->ImperioRemaining > 0.f) && !Penalty)
    {
        Rect(UW/2-155,UH/2-90,310,42,Ink);
        Text(Rider->TransformationRemaining > 0 ? TEXT("TRANSFORMED - RECOVERING")
            : Rider->PetrificusRemaining > 0 ? TEXT("PETRIFICUS - BOUND")
            : Rider->StunRemaining > 0 ? TEXT("STUNNED - RECOVERING")
            : TEXT("IMPERIO - FLIGHT REVERSED"),UW/2-145,UH/2-79,.98f,Copper);
    }
    if (Match->Status == TEXT("FINAL") || Match->Status == TEXT("CERTIFYING RESULT"))
    {
        const bool bFinal = Match->Status == TEXT("FINAL");
        const FLinearColor ResultColor = Match->Winner == 0 ? Teal : Copper;
        Rect(UW/2-300,188,600,210,Ink);
        Rect(UW/2-300,188,600,4,bFinal ? ResultColor : Gold);
        Text(bFinal ? (Match->Winner == 0 ? TEXT("TEAL WINS") : TEXT("COPPER WINS")) : TEXT("RESULT UNDER REVIEW"),UW/2-265,216,1.8f,bFinal ? ResultColor : Gold);
        Text(FString::Printf(TEXT("TEAL  %d     /     COPPER  %d"),Match->TealScore,Match->CopperScore),UW/2-265,273,1.2f,Cream);
        Text(bFinal ? (Pad ? TEXT("Certified result. Host: Cross to play again.") : TEXT("Certified result. Host: ENTER to play again.")) : TEXT("Resolving the final play and outstanding decisions."),UW/2-265,332,.85f,Muted);
    }
    else if (Penalty)
    {
        auto Participant = [&](int32 Slot)
        {
            for (TActorIterator<ABBRiderCharacter> It(GetWorld()); It; ++It)
                if (It->RosterIndex == Slot)
                    return FString::Printf(TEXT("%s / %s / #%d"), It->TeamIndex ? TEXT("COPPER") : TEXT("TEAL"),
                        *ABBMatchState::PositionName(It->Position).ToUpper(), Slot + 1);
            return FString::Printf(TEXT("ROSTER #%d"), Slot + 1);
        };
        const bool Quaffle = Match->PenaltyShotBall == 0;
        Rect(UW/2-330,164,660,256,Ink);
        Rect(UW/2-330,164,660,4,Gold);
        Text(Match->bFreeShot ? TEXT("MODERATE FOUL / FREE SHOT") : TEXT("SERIOUS FOUL / PENALTY SHOT"),UW/2-305,181,1.3f,Gold);
        const FString ShotStage = PenaltyDecision ? TEXT("DECISION / RESTART NEXT")
            : FString::Printf(TEXT("ATTEMPT %.1fs / 5s"), Match->PenaltyShotSecondsLeft);
        Text(FString::Printf(TEXT("%s / %d POINTS     %s"), Quaffle ? TEXT("QUAFFLE") : TEXT("QUARK"),
            Quaffle ? 13 : 37, *ShotStage),UW/2-305,215,.94f,Cream);
        Text(TEXT("SHOOTER  ") + Participant(Match->PenaltyShooterSlot),UW/2-305,245,.84f,PenaltyShooter ? Gold : Cream);
        Text(TEXT("KEEPER    ") + Participant(Match->PenaltyKeeperSlot),UW/2-305,270,.84f,PenaltyKeeper ? Gold : Cream);
        const FString Instructions = PenaltyDecision ? TEXT("SHOT RESOLVED. The defending keeper receives the protected restart.")
            : PenaltyShooter ? (Match->bPenaltyShotReleased ? TEXT("YOUR SHOT IS AWAY. Stay at the mark until the decision.")
                : Pad ? TEXT("YOU SHOOT: RS to aim. Cross to release. Stay at the mark.")
                    : TEXT("YOU SHOOT: mouse to aim. LMB to release. Stay at the mark."))
            : PenaltyKeeper ? TEXT("YOU DEFEND: fly inside the goal area and body-block the ball.")
                : TEXT("WAIT FOR THE DECISION. Only the designated keeper may move.");
        WrappedText(Instructions,UW/2-305,307,.84f,Cream,610,2);
        WrappedText(Match->PenaltyShotStatus,UW/2-305,353,.80f,Gold,610,2);
        Text(TEXT("NO WANDS  /  NO PASSES  /  NO SECOND ATTEMPT"),UW/2-305,395,.79f,Muted);
    }
    else if (Match->bConductReviewPending)
    {
        Rect(UW/2-330,164,660,256,Ink);
        Rect(UW/2-330,164,660,4,Copper);
        Text(TEXT("PLAYTEST REFEREE"),UW/2-305,185,1.4f,Copper);
        WrappedText(Match->LastConductCall,UW/2-305,226,.88f,Cream,610,3);
        if (Pad)
        {
            Text(TEXT("Host: Left free shot / Up possession / Right Serious / Down Severe"),UW/2-305,296,.79f,Gold);
            Text(Rider->GamepadRefereeChoice == 1 ? TEXT("MODERATE: possession award. Cross to confirm.")
                : Rider->GamepadRefereeChoice == 2 ? TEXT("SEVERE: ejection. Cross to confirm.")
                : Rider->GamepadRefereeChoice == 3 ? TEXT("SERIOUS: penalty shot + removal. Cross to confirm.")
                : Rider->GamepadRefereeChoice == 4 ? TEXT("MODERATE: free shot, no removal. Cross to confirm.")
                : TEXT("Choose a disposition before confirming with Cross."),UW/2-305,328,.82f,Cream);
        }
        else WrappedText(Match->ConductReviewStatus,UW/2-305,296,.85f,Gold,610,3);
        Text(TEXT("BB-0 dispositions are provisional. Play remains stopped."),UW/2-305,385,.77f,Muted);
    }
    else if (Rider->bShowSpellbook)
    {
        Rect(UW/2-460,158,920,508,Ink);
        Rect(UW/2-460,158,920,3,Violet);
        Text(TEXT("SPELLBOOK"),UW/2-434,176,1.35f,Cream);
        Text(Pad ? TEXT("D-pad L/R  Select    R1  Cast    L1  Protego    Triangle Close") : TEXT("Z / X  Select     Q  Cast     R  Protego     V  Close"),UW/2-434,211,.84f,Muted);
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
        Text(Match->bLive ? TEXT("Position changes unlock at stoppages.") : (Pad ? TEXT("D-pad Up/Down: position. Host: Cross to start / resume.") : TEXT("Choose a position. T switches team. Host: ENTER to start.")),UW/2-275,221,.85,Muted);
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
            Text(Rider->bShowRoster ? TEXT("D-pad Left: team / Right: Bloodbroom. Cross: advantage call.") : TEXT("Touchpad: roster + team / variant controls. Triangle: spellbook."),UW/2-275,489,.77f,Muted);
        else Text(Match->Status == TEXT("LOBBY") ? TEXT("V  Spellbook    Host: B toggles Bloodbroom before play") : TEXT("V  Spellbook    Q  Cast    R  Protego    F10  Host advantage call"),UW/2-275,489,.77f,Muted);
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

void ABBHUD::DrawPadGlyph(const FString& Glyph, float X, float Y, float R, FLinearColor Color, float S)
{
    auto Line=[&](float AX,float AY,float BX,float BY){DrawLine(AX*S,AY*S,BX*S,BY*S,Color,1.8f*S);};
    if (Glyph==TEXT("Cross")) { Line(X-R,Y-R,X+R,Y+R); Line(X-R,Y+R,X+R,Y-R); }
    else if (Glyph==TEXT("Square")) { Line(X-R,Y-R,X+R,Y-R);Line(X+R,Y-R,X+R,Y+R);Line(X+R,Y+R,X-R,Y+R);Line(X-R,Y+R,X-R,Y-R); }
    else if (Glyph==TEXT("Triangle")) { Line(X,Y-R,X+R,Y+R);Line(X+R,Y+R,X-R,Y+R);Line(X-R,Y+R,X,Y-R); }
    else for (int I=0;I<32;++I)
    {
        const float A=2.f*PI*I/32.f, B=2.f*PI*(I+1)/32.f;
        Line(X+R*FMath::Cos(A),Y+R*FMath::Sin(A),X+R*FMath::Cos(B),Y+R*FMath::Sin(B));
    }
}

void ABBHUD::SetPauseMenuInputActive(bool bActive)
{
    if (!PlayerOwner || bPauseInputActive==bActive) return;
    bPauseInputActive=bActive;
    bPauseMouseDown=bPauseMousePressed=false;
    TrailDragChannel=INDEX_NONE;
    TrailRepeatKey=FKey();
    if (bActive)
    {
        bCursorWasVisible=PlayerOwner->bShowMouseCursor;
        EnableInput(PlayerOwner);
        if (InputComponent && !bPauseBindingsAdded)
        {
            // Consume mouse clicks above the pawn's input so editing a color
            // cannot throw a held ball in an online match that keeps running.
            InputComponent->BindKey(EKeys::LeftMouseButton,IE_Pressed,this,&ABBHUD::PauseMousePressed).bExecuteWhenPaused=true;
            InputComponent->BindKey(EKeys::LeftMouseButton,IE_Released,this,&ABBHUD::PauseMouseReleased).bExecuteWhenPaused=true;
            InputComponent->BindKey(EKeys::BackSpace,IE_Pressed,this,&ABBHUD::PauseBackPressed).bExecuteWhenPaused=true;
            bPauseBindingsAdded=true;
        }
        PlayerOwner->bShowMouseCursor=true;
        FInputModeGameAndUI Mode;
        Mode.SetHideCursorDuringCapture(false);
        Mode.SetLockMouseToViewportBehavior(EMouseLockMode::DoNotLock);
        PlayerOwner->SetInputMode(Mode);
    }
    else
    {
        CommitTrailColor(true);
        DisableInput(PlayerOwner);
        PlayerOwner->bShowMouseCursor=bCursorWasVisible;
        PlayerOwner->SetInputMode(FInputModeGameOnly());
        TrailColorRider.Reset();
    }
}

void ABBHUD::PauseMousePressed() { bPauseMouseDown=bPauseMousePressed=true; }
void ABBHUD::PauseMouseReleased()
{
    bPauseMouseDown=false;
    TrailDragChannel=INDEX_NONE;
    CommitTrailColor(true);
}
void ABBHUD::PauseBackPressed()
{
    if (PlayerOwner)
        if (ABBRiderCharacter* Rider=Cast<ABBRiderCharacter>(PlayerOwner->GetPawn())) Rider->HandlePauseMenuKey(EKeys::BackSpace);
}

void ABBHUD::BeginTrailColorEdit(ABBRiderCharacter* Rider)
{
    CommitTrailColor(true);
    TrailColorRider=Rider;
    bCustomTrailColor=Rider && Rider->bUseCustomBroomTrailColor;
    TrailHSV=(Rider?Rider->GetBroomTrailColor():FLinearColor::White).LinearRGBToHSV();
    TrailHSV.A=1.f;
    TrailRepeatKey=FKey();
    TrailDragChannel=INDEX_NONE;
}

void ABBHUD::SetTrailChannel(int32 Channel, float Value)
{
    if (Channel<0 || Channel>2 || !FMath::IsFinite(Value)) return;
    if (Channel==0) TrailHSV.R=FMath::Clamp(Value,0.f,1.f)*359.9f;
    else if (Channel==1) TrailHSV.G=FMath::Clamp(Value,0.f,1.f);
    else TrailHSV.B=FMath::Clamp(Value,0.f,1.f);
    bCustomTrailColor=true;
    bTrailColorPending=true;
}

void ABBHUD::CommitTrailColor(bool bFlushConfig)
{
    const double Now=FPlatformTime::Seconds();
    if (bTrailColorPending && (bFlushConfig || Now-LastTrailCommitTime>=.12))
    {
        ABBRiderCharacter* Rider=TrailColorRider.Get();
        if (Rider && Rider->IsLocallyControlled())
        {
            FLinearColor Color=TrailHSV.HSVToLinearRGB();
            Color.A=1.f;
            Rider->SetBroomTrailColor(bCustomTrailColor,Color);
            if (GConfig)
            {
                const TCHAR* Section=TEXT("Basketbroom.BroomTrail");
                GConfig->SetBool(Section,TEXT("Custom"),bCustomTrailColor,GGameUserSettingsIni);
                GConfig->SetFloat(Section,TEXT("Red"),Color.R,GGameUserSettingsIni);
                GConfig->SetFloat(Section,TEXT("Green"),Color.G,GGameUserSettingsIni);
                GConfig->SetFloat(Section,TEXT("Blue"),Color.B,GGameUserSettingsIni);
                bTrailConfigDirty=true;
            }
        }
        bTrailColorPending=false;
        LastTrailCommitTime=Now;
    }
    if (bFlushConfig && bTrailConfigDirty && GConfig)
    {
        GConfig->Flush(false,GGameUserSettingsIni);
        bTrailConfigDirty=false;
    }
}

bool ABBHUD::HandleTrailColorKey(ABBRiderCharacter* Rider, FKey Key)
{
    if (!Rider) return false;
    if (TrailColorRider.Get()!=Rider) BeginTrailColorEdit(Rider);
    const bool bConfirm=Key==EKeys::Enter || Key==EKeys::SpaceBar || Key==EKeys::Gamepad_FaceButton_Bottom;
    const bool bLeft=Key==EKeys::Left || Key==EKeys::A || Key==EKeys::Gamepad_DPad_Left;
    const bool bRight=Key==EKeys::Right || Key==EKeys::D || Key==EKeys::Gamepad_DPad_Right;
    if ((bLeft || bRight) && Rider->PauseMenuSelection<3)
    {
        const int32 Channel=FMath::Clamp(Rider->PauseMenuSelection,0,2);
        const float Value=Channel==0?TrailHSV.R/359.9f:Channel==1?TrailHSV.G:TrailHSV.B;
        SetTrailChannel(Channel,Value+(bRight?1.f:-1.f)*(Channel==0?1.f/120.f:.02f));
        TrailRepeatKey=Key;
        LastTrailRepeatTime=FPlatformTime::Seconds();
        CommitTrailColor(false);
        return true;
    }
    if ((bConfirm && Rider->PauseMenuSelection==3) || Key==EKeys::Gamepad_FaceButton_Top)
    {
        bCustomTrailColor=false;
        bTrailColorPending=true;
        CommitTrailColor(true);
        TrailHSV=Rider->GetBroomTrailColor().LinearRGBToHSV();
        return true;
    }
    if (bConfirm && Rider->PauseMenuSelection<3) return true;
    if (Key==EKeys::Escape || Key==EKeys::BackSpace || Key==EKeys::Gamepad_FaceButton_Right
        || Key==EKeys::Gamepad_Special_Right || (bConfirm && Rider->PauseMenuSelection==4))
    {
        TrailRepeatKey=FKey();
        CommitTrailColor(true);
    }
    return false;
}

void ABBHUD::UpdatePauseMenuMouse(ABBRiderCharacter* Rider)
{
    if (!PlayerOwner || !Rider || !Canvas) return;
    const float Scale=FMath::Min(Canvas->SizeX/1600.f,Canvas->SizeY/900.f);
    const FVector2D Origin((Canvas->SizeX/Scale-1440.f)/2.f,(Canvas->SizeY/Scale-800.f)/2.f);
    float MX=0.f,MY=0.f;
    const bool bHasMouse=PlayerOwner->GetMousePosition(MX,MY);
    const FVector2D Mouse=FVector2D(MX,MY)/Scale-Origin;
    if (bPauseMousePressed && bHasMouse)
    {
        Rider->bUsingGamepad=false;
        const TArray<BBPauseMenu::Item> Choices=BBPauseMenu::Items(Rider);
        const float Step=Choices.Num()>6?54.f:66.f;
        for (int32 I=0; I<Choices.Num(); ++I)
        {
            if (Mouse.X>=30.f && Mouse.X<=441.f && Mouse.Y>=193.f+I*Step && Mouse.Y<=240.f+I*Step)
            {
                Rider->PauseMenuSelection=I;
                Rider->HandlePauseMenuKey(EKeys::Enter);
                break;
            }
        }
        if (Rider->PauseMenuPage==BBPauseMenu::TrailColor)
        {
            for (int32 I=0; I<3; ++I)
                if (Mouse.X>=540.f && Mouse.X<=1340.f && FMath::Abs(Mouse.Y-(366.f+I*100.f))<=27.f)
                {
                    Rider->PauseMenuSelection=I;
                    TrailDragChannel=I;
                    TrailRepeatKey=FKey();
                }
        }
    }
    bPauseMousePressed=false;
    if (!Rider->bPauseMenuOpen || Rider->PauseMenuPage!=BBPauseMenu::TrailColor) return;
    if (TrailColorRider.Get()!=Rider) BeginTrailColorEdit(Rider);
    if (bPauseMouseDown && TrailDragChannel!=INDEX_NONE && bHasMouse)
        SetTrailChannel(TrailDragChannel,(Mouse.X-550.f)/780.f);
    if (TrailRepeatKey.IsValid())
    {
        if (!PlayerOwner->IsInputKeyDown(TrailRepeatKey)) TrailRepeatKey=FKey();
        else if (FPlatformTime::Seconds()-LastTrailRepeatTime>=.14) HandleTrailColorKey(Rider,TrailRepeatKey);
    }
    CommitTrailColor(false);
    // Save an idle keyboard/controller edit even if the journal stays open.
    if (bTrailConfigDirty && !bPauseMouseDown && !TrailRepeatKey.IsValid()
        && FPlatformTime::Seconds()-LastTrailCommitTime>=.4) CommitTrailColor(true);
}

void ABBHUD::DrawPauseMenu(ABBMatchState* Match, ABBRiderCharacter* Rider)
{
    UpdatePauseMenuMouse(Rider);
    if (!Rider->bPauseMenuOpen) return;
    const float S=FMath::Min(Canvas->SizeX/1600.f,Canvas->SizeY/900.f);
    const float UW=Canvas->SizeX/S, UH=Canvas->SizeY/S, OX=(UW-1440)/2.f, OY=(UH-800)/2.f;
    const FLinearColor Ink(.016f,.025f,.038f,.96f), Cream(.94f,.92f,.84f,1), Muted(.59f,.68f,.70f,1), Gold(.98f,.74f,.32f,1);
    const FLinearColor Teal = FLinearColor::FromSRGBColor(FColor(138,191,163));
    auto Rect=[&](float X,float Y,float W,float H,FLinearColor C){DrawRect(C,(OX+X)*S,(OY+Y)*S,W*S,H*S);};
    auto Text=[&](const FString& T,float X,float Y,float Size,FLinearColor C){DrawText(T,C,(OX+X)*S,(OY+Y)*S,GEngine->GetMediumFont(),Size*S,false);};
    auto Line=[&](float AX,float AY,float BX,float BY,FLinearColor C,float T=1.f){DrawLine((OX+AX)*S,(OY+AY)*S,(OX+BX)*S,(OY+BY)*S,C,T*S);};
    auto Glyph=[&](const TCHAR* G,float X,float Y,float R,FLinearColor C){DrawPadGlyph(G,OX+X,OY+Y,R,C,S);};
    DrawRect(FLinearColor(.004f,.009f,.014f,.73f),0,0,Canvas->SizeX,Canvas->SizeY);
    Rect(0,0,1440,800,Ink); Rect(0,0,1440,3,Gold); Rect(0,798,1440,2,Gold*.45f);
    Text(Match->bBloodbroom?TEXT("BLOODBROOM"):TEXT("BASKETBROOM"),44,29,2.05f,Cream);
    Text(TEXT("FLIGHT JOURNAL"),46,81,.80f,Gold);
    const bool Frozen=UGameplayStatics::IsGamePaused(GetWorld());
    Text(GetNetMode()!=NM_Standalone?TEXT("ONLINE / THE MATCH CONTINUES"):Frozen?TEXT("LOCAL PLAY PAUSED"):TEXT("LOCAL MENU"),906,37,.90f,GetNetMode()!=NM_Standalone?Gold:Teal);
    Text(FString::Printf(TEXT("TEAL %d   /   COPPER %d   /   %s"),Match->TealScore,Match->CopperScore,*Match->Phase),906,73,.75f,Muted);
    Line(44,116,1396,116,Muted*.3f); Line(465,146,465,701,Muted*.25f);
    const TCHAR* Titles[]={TEXT("TAKE A BREATHER"),TEXT("CONTROLLER SETTINGS"),TEXT("CONTROLS & BOOST"),TEXT("POSITIONS & RULES"),TEXT("MATCH REFEREE"),TEXT("BROOM TRAIL COLOR")};
    Text(Titles[FMath::Clamp(Rider->PauseMenuPage,0,5)],44,148,.88f,Gold);
    const TArray<BBPauseMenu::Item> Choices=BBPauseMenu::Items(Rider);
    const float Step=Choices.Num()>6?54.f:66.f;
    for (int32 I=0;I<Choices.Num();++I)
    {
        const float Y=202+I*Step;
        const bool Selected=I==FMath::Clamp(Rider->PauseMenuSelection,0,Choices.Num()-1);
        if (Selected) { Rect(30,Y-9,411,47,FLinearColor(.10f,.17f,.18f,1)); Rect(30,Y-9,3,47,Gold); }
        Text(Choices[I].Label,51,Y,.99f,Selected?Cream:Muted);
        if (Selected) Text(TEXT(">"),416,Y,.95f,Gold);
    }
    if (Rider->PauseMenuPage==BBPauseMenu::Main || Rider->PauseMenuPage==BBPauseMenu::Controls)
    {
        Text(TEXT("A broom built for the sport"),510,146,1.45f,Cream);
        Text(TEXT("DualSense / wired or Bluetooth input"),512,187,.84f,Muted);
        // Original geometric diagram. Face-button symbols do not depend on font glyph coverage.
        const FVector2D Outline[]={{805,269},{846,252},{1090,252},{1131,269},{1161,315},{1202,431},
            {1199,466},{1177,486},{1154,483},{1098,418},{839,418},{783,483},{760,486},{738,466},
            {735,431},{775,315},{805,269}};
        for(int32 I=1;I<UE_ARRAY_COUNT(Outline);++I) Line(Outline[I-1].X,Outline[I-1].Y,Outline[I].X,Outline[I].Y,Muted,2.f);
        Rect(888,277,158,77,FLinearColor(.08f,.12f,.16f,1));
        Text(TEXT("touchpad"),924,304,.62f,Muted);
        Rect(817,236,57,22,Gold*.15f);Rect(1063,236,57,22,Gold*.15f);
        Text(TEXT("L1"),832,238,.70f,Cream);Text(TEXT("R1"),1078,238,.70f,Cream);
        Text(TEXT("L2 / BRAKE"),659,239,.81f,Gold);Text(TEXT("R2 / THROTTLE"),1171,239,.81f,Gold);
        Glyph(TEXT("Circle"),878,398,28,Muted);Glyph(TEXT("Circle"),1048,398,28,Muted);
        Text(TEXT("LS"),865,387,.82f,Cream);Text(TEXT("RS"),1035,387,.82f,Cream);
        Line(826,302,826,351,Muted,8.f);Line(801,326,851,326,Muted,8.f);
        Glyph(TEXT("Triangle"),1113,300,10,Teal);Glyph(TEXT("Square"),1087,327,9,Cream);
        Glyph(TEXT("Circle"),1139,327,10,Gold);Glyph(TEXT("Cross"),1113,354,9,Cream);
        Line(1060,286,1060,299,Muted,3.f);Text(TEXT("options"),1079,272,.53f,Muted);
        const TCHAR* Labels[]={TEXT("throw / confirm"),TEXT("catch / hold to capture"),TEXT("spellbook"),TEXT("back")};
        const TCHAR* Symbols[]={TEXT("Cross"),TEXT("Square"),TEXT("Triangle"),TEXT("Circle")};
        for(int32 I=0;I<4;++I){const float X=528+(I%2)*420,Y=521+(I/2)*37;Glyph(Symbols[I],X,Y+8,8,I==2?Teal:Cream);Text(Labels[I],X+24,Y,.88f,Cream);}
        Text(TEXT("LS steer / RS up-down altitude / RS left-right camera"),511,608,.83f,Muted);
        Text(TEXT("Hold L3 + RS: precision aim / R1 cast / L1 Protego"),511,638,.83f,Muted);
        Text(TEXT("R2 accelerates. Earn boost: scoring +25, legal Bludger hits +15."),511,674,.81f,Gold);
        Text(TEXT("At 100%, release and press R2 for a super boost. L2 brakes."),511,704,.81f,Gold);
    }
    else if (Rider->PauseMenuPage==BBPauseMenu::TrailColor)
    {
        const FLinearColor Preview=bCustomTrailColor?TrailHSV.HSVToLinearRGB():Rider->GetBroomTrailColor();
        Text(TEXT("Your signature in the sky"),511,154,1.48f,Cream);
        Text(TEXT("Choose any hue. Your choice follows you between teams."),513,194,.86f,Muted);
        Rect(513,233,850,68,FLinearColor(.028f,.045f,.055f,1.f));
        Rect(531,247,50,40,Preview);
        for (int32 I=0; I<80; ++I)
        {
            FLinearColor Trail=Preview;
            Trail.A=.08f+.92f*I/79.f;
            Rect(609.f+I*4.f,262.f,4.f,10.f,Trail);
        }
        Line(911,267,953,255,Gold,4.f);
        Line(942,256,964,267,Muted,3.f);
        Line(942,256,965,258,Muted,3.f);
        Line(942,256,961,249,Muted,3.f);
        Text(bCustomTrailColor?TEXT("CUSTOM"):TEXT("TEAM COLOR"),994,241,.73f,Gold);
        const FColor Display=Preview.ToFColor(true);
        Text(FString::Printf(TEXT("#%02X%02X%02X"),Display.R,Display.G,Display.B),994,266,.93f,Cream);
        const TCHAR* Labels[]={TEXT("HUE"),TEXT("SATURATION"),TEXT("BRIGHTNESS")};
        for (int32 I=0; I<3; ++I)
        {
            const float Y=352.f+I*100.f;
            const bool bSelected=Rider->PauseMenuSelection==I;
            const float Value=I==0?TrailHSV.R/359.9f:I==1?TrailHSV.G:TrailHSV.B;
            if (bSelected) Rect(529,Y-37,823,79,FLinearColor(.065f,.105f,.12f,1.f));
            Text(Labels[I],550,Y-31,.84f,bSelected?Gold:Muted);
            Text(I==0?FString::Printf(TEXT("%d deg"),FMath::RoundToInt(TrailHSV.R))
                :FString::Printf(TEXT("%d%%"),FMath::RoundToInt(Value*100.f)),1250,Y-31,.82f,Cream);
            for (int32 GradientStep=0; GradientStep<128; ++GradientStep)
            {
                const float T=GradientStep/127.f;
                const FLinearColor HSV=I==0?FLinearColor(T*359.9f,1.f,1.f,1.f)
                    :I==1?FLinearColor(TrailHSV.R,T,TrailHSV.B,1.f)
                    :FLinearColor(TrailHSV.R,TrailHSV.G,T,1.f);
                Rect(550.f+GradientStep*780.f/128.f,Y,780.f/128.f+1.f,28.f,HSV.HSVToLinearRGB());
            }
            const float HandleX=550.f+Value*780.f;
            Rect(HandleX-4.f,Y-5.f,8.f,38.f,FLinearColor(.012f,.019f,.025f,1.f));
            Rect(HandleX-1.5f,Y-3.f,3.f,34.f,Cream);
        }
        Text(TEXT("Preview above / your trail appears in motion after resuming."),513,644,.85f,Cream);
        Text(TEXT("Saved on this device. Reset uses your current team's color."),513,680,.83f,Muted);
        Text(TEXT("Dark colors make a subtler trail. Uniform colors stay with your team."),513,711,.77f,Muted);
    }
    else if (Rider->PauseMenuPage==BBPauseMenu::Settings)
    {
        Text(TEXT("Make flight feel natural"),511,154,1.52f,Cream);
        Text(TEXT("ALTITUDE"),513,230,.84f,Gold);
        Text(TEXT("Right stick up / down controls climb and descent."),513,267,.94f,Cream);
        Text(TEXT("Invert this axis independently of your aim."),513,301,.88f,Muted);
        Text(TEXT("PRECISION AIM"),513,380,.84f,Gold);
        Text(TEXT("Hold L3 to aim with the right stick. Flight height holds steady."),513,417,.88f,Cream);
        Text(TEXT("The shot taker uses precision aim automatically."),513,451,.88f,Muted);
        Text(TEXT("Your choices save locally and return next launch."),513,549,.92f,Teal);
        Text(TEXT("Release the sticks and triggers before returning to flight."),513,592,.86f,Muted);
    }
    else if (Rider->PauseMenuPage==BBPauseMenu::Roles)
    {
        Text(TEXT("Every role matters"),511,148,1.46f,Cream);
        Text(Match->bLive?TEXT("Position changes unlock at a match stoppage."):TEXT("Choose a position on the left to return to the arena."),511,189,.84f,Muted);
        const TCHAR* Descriptions[]={TEXT("Guard every hoop; receive protected scoring-ball restarts."),TEXT("Carry, pass and shoot Quaffles and Quarks."),TEXT("Intercept and turn possession into scoring opportunities."),TEXT("Combine scoring-ball play with chase captures; release first."),TEXT("Control Bludgers: 3 seconds individual / 6 seconds per team."),TEXT("Track Snipe and Snitch; commit to a one-second close catch.")};
        for(int32 I=0;I<6;++I){const float Y=235+I*57;Text(ABBMatchState::PositionName(I),512,Y,.94f,Teal);Text(Descriptions[I],512,Y+26,.80f,Cream);}
        Text(TEXT("Quaffle 13 / Quark 37 / Snipe 69 / Snitch 150 (300 in overtime)"),512,601,.81f,Gold);
        Text(TEXT("Closed pyramid net: rebounds stay in play. No physical holding."),512,637,.81f,Muted);
        Text(Match->bBloodbroom?TEXT("Bloodbroom permits Unforgivables and headshots."):TEXT("Basketbroom: no Unforgivables or headshots. Hits apply; fouls follow."),512,673,.81f,Muted);
        Text(TEXT("Both modes: max three attackers; no stun after confirmed impediment."),512,709,.78f,Muted);
    }
    else
    {
        Text(TEXT("Match decisions"),511,152,1.50f,Cream);
        Text(Rider->HasAuthority()?TEXT("HOST AUTHORITY / BB-0 PLAYTEST"):TEXT("HOST CONTROLS THESE DECISIONS"),512,199,.87f,Gold);
        Text(TEXT("Opening this journal never calls a referee stoppage."),512,263,.96f,Cream);
        Text(TEXT("Use the explicit match action on the left to stop or resume play."),512,301,.85f,Muted);
        Text(TEXT("An owed shot or conduct review must be resolved before play resumes."),512,339,.82f,Muted);
        Text(TEXT("Moderate: possession or free shot, as the offence requires."),512,420,.86f,Cream);
        Text(TEXT("Serious: penalty shot and temporary removal."),512,456,.86f,Cream);
        Text(TEXT("Severe: ejection. Dangerous contact still stops play."),512,492,.86f,Cream);
        Text(TEXT("An armed Moderate advantage is a one-use host playtest decision."),512,571,.84f,Gold);
        Text(TEXT("These actions are checked by the match authority."),512,612,.86f,Muted);
        if (Match->bPenaltyShotActive) Text(TEXT("A shot is in progress. Referee actions are temporarily unavailable."),512,660,.82f,Gold);
    }
    Line(44,749,1396,749,Muted*.3f);
    if (Rider->bUsingGamepad)
    {
        Glyph(TEXT("Cross"),57,779,8,Cream);Text(TEXT("select"),77,768,.82f,Cream);
        Glyph(TEXT("Circle"),184,779,8,Gold);Text(TEXT("back"),204,768,.82f,Cream);
        if (Rider->PauseMenuPage==BBPauseMenu::TrailColor)
        {
            Text(TEXT("D-pad  choose / adjust"),328,768,.82f,Muted);
            Glyph(TEXT("Triangle"),641,779,8,Teal);Text(TEXT("team color"),661,768,.82f,Cream);
            Text(TEXT("Options  resume"),853,768,.82f,Muted);
        }
        else Text(TEXT("D-pad  navigate     Options  resume"),328,768,.82f,Muted);
    }
    else Text(Rider->PauseMenuPage==BBPauseMenu::TrailColor
        ?TEXT("UP / DOWN choose    LEFT / RIGHT adjust    MOUSE drag    BACKSPACE back    ESC resume")
        :TEXT("UP / DOWN navigate    ENTER or CLICK select    BACKSPACE back    ESC resume"),46,768,.82f,Cream);
    Text(TEXT("BASKETBROOM PROTOTYPE"),1154,770,.68f,Muted);
}
