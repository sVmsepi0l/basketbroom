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
    if (!canvas || !playerowner || canvas->sizex <= 0 || canvas->sizey <= 0) return;
    abbmatchstate* match = getworld()->getgamestate<abbmatchstate>();
    abbridercharacter* rider = cast<abbridercharacter>(playerowner->getpawn());
    if (!match || !rider) return;
    const bool pad = rider->businggamepad;
    const bool penalty = match->bpenaltyshotactive;
    const bool penaltydecision = penalty && match->penaltyshotsecondsleft <= 0.f;
    const bool penaltyshooter = penalty && rider->rosterindex == match->penaltyshooterslot;
    const bool penaltykeeper = penalty && rider->rosterindex == match->penaltykeeperslot;
    updateaudiofeedback(match, rider);
    const float w = canvas->sizex, h = canvas->sizey;
    const float s = FMath::Min(W/1600.f, H/900.f);
    const flinearcolor Ink(.015,.026,.038,.90), Muted(.56,.67,.7,1), Cream(.94,.91,.82,1), Teal(.12,.9,.73,1), Copper(1,.46,.20,1), Gold(1,.77,.24,1), Violet(.7,.38,1,1);
    ufont* font = gengine->getmediumfont();
    auto rect = [&](float x,float y,float width,float height,flinearcolor color) { drawrect(color,x*s,y*s,width*s,height*s); };
    auto text = [&](const fstring& t,float x,float y,float size,flinearcolor color) { drawtext(t,color,x*s,y*s,font,size*s,false); };
    const float uw = W/S, uh = H/S;
    auto wrappedtext = [&](const fstring& message, float x, float y, float size, flinearcolor color,
                           float maxwidth, int32 maxlines)
    {
        tarray<fstring> words;
        Message.ParseIntoArrayWS(Words);
        fstring line;
        int32 row = 0;
        for (const fstring& word : words)
        {
            const fstring candidate = Line.IsEmpty() ? word : line + text(" ") + word;
            float width = 0.f, height = 0.f;
            gettextsize(candidate, width, height, font, size);
            if (!Line.IsEmpty() && width > maxwidth)
            {
                text(line, x, y + row * 20.f, size, color);
                if (++row >= maxlines) return;
                line = word;
            }
            else line = candidate;
        }
        if (!Line.IsEmpty() && row < maxlines) text(line, x, y + row * 20.f, size, color);
    };
    Rect(UW/2-320,20,640,102,Ink);
    Rect(UW/2-320,20,4,102,Teal); Rect(UW/2+316,20,4,102,Copper);
    Text(TEXT("TEAL"),UW/2-294,32,1,Teal); Text(TEXT("COPPER"),UW/2+191,32,1,Copper);
    Text(FString::FromInt(Match->TealScore),UW/2-294,59,2,Cream);
    Text(FString::FromInt(Match->CopperScore),UW/2+191,59,2,Cream);
    // ignore sub-millisecond conversion noise at exact clock boundaries.
    const int32 seconds = FMath::Max(0,FMath::CeilToInt(Match->SecondsLeft-.001f));
    const fstring clock = match->phase == text("donnybrook") ? text("sudden death") : FString::Printf(TEXT("%02d:%02d"),Seconds/60,Seconds%60);
    Text(Clock,UW/2-55,35,1.5f,Cream);
    text(match->phase + (match->phase == text("regulation") ? FString::Printf(TEXT("  Q%d/4"),Match->Quarter) : TEXT("")),UW/2-78,79,.78,Muted);
    text(match->bpractice ? text("practice clocks") : text("regulation CLOCKS"),24,23,.78,Muted);
    text(getnetmode() == nm_standalone ? text("local scrimmage") : getnetmode() == nm_client ? text("network client") : text("listen SERVER"),24,45,.78,Muted);
    const bool spellready = BBSpellCatalog::IsImplemented(Rider->SelectedSpell);
    rect(22,76,420,59,ink);
    rect(22,76,3,59,spellready ? violet : muted);
    text(fstring(pad ? text("rb  ") : text("q  ")) + BBSpellCatalog::Name(Rider->SelectedSpell),38,83,.95f,SpellReady ? cream : muted);
    const tchar* spellcontrols = text("z / x  select    r  protego    v  spellbook");
    if (pad)
        spellcontrols = match->bconductreviewpending ? text("d-pad  choose call    menu  confirm")
            : rider->bshowroster ? text("view  close roles to select spells    y  book")
            : text("d-pad L/R  spells    lb  protego    y  book");
    if (penalty) spellcontrols = match->bfreeshot ? text("free shot  /  wandwork locked") : text("penalty shot  /  wandwork locked");
    Text(SpellControls,38,108,.76f,Muted);
    const fstring spellstate = penalty ? text("locked") : !spellready ? text("adapter due") : rider->disarmremaining > 0.f ? text("disarmed")
        : rider->spellcooldownremaining > 0.f ? FString::Printf(TEXT("%.1fs"),Rider->SpellCooldownRemaining) : text("ready");
    Text(SpellState,335,86,.70f,!Penalty && spellready && rider->spellcooldownremaining <= 0.f ? teal : gold);
    text(match->bbloodbroom ? text("bloodbroom  /  bb-0 playtest") : text("basketbroom  /  bb-0 PLAYTEST"),UW/2-170,128,.77f,Match->bBloodbroom ? copper : muted);
    if ((rider->selectedspell == 29 || rider->selectedspell == 30) && match->pendingpenaltycount == 0)
    {
        const int32 charge = match->getancientmagiccharge(rider);
        rect(22,137,420,32,ink);
        Text(FString::Printf(TEXT("ANCIENT magic  %d / 100"),Charge),38,144,.78f,Gold);
        Rect(272,148,150,5,FLinearColor(.12,.16,.18,1));
        Rect(272,148,150.f * FMath::Clamp(Charge / 100.f,0.f,1.f),5,Gold);
    }
    if (match->pendingpenaltycount > 0)
    {
        rect(22,142,420,117,ink);
        rect(22,142,4,117,gold);
        Text(FString::Printf(TEXT("PENALTIES due  %d"),Match->PendingPenaltyCount),40,155,.88f,Gold);
        tarray<fstring> details;
        Match->PendingPenaltySummary.ParseIntoArray(Details,TEXT(" | "),false);
        for (int32 I=0;I<FMath::Min(Details.Num(),3);++I)
            Text(Details[I].ToUpper().Left(48),40,181+I*23,.76f,I==0?Cream:Muted);
    }
    if (match->bmoderateadvantagearmed || match->bconductadvantagelive)
    {
        Rect(UW/2-305,153,610,47,Ink);
        Rect(UW/2-305,153,4,47,Gold);
        text(match->bconductadvantagelive ? text("advantage / moderate shot owed") : text("host playtest call / next safe basic-cast MOBBING: MODERATE"),UW/2-289,161,.74f,Gold);
        text(match->bconductadvantagelive ? text("play continues while the offended team keeps the ball.") : (pad ? text("view opens roster; menu toggles the one-use advantage call.") : text("f10 toggles this one-use call. dangerous fouls still stop play.")),UW/2-289,181,.68f,Muted);
    }
    if (match->conductfoulcount > 0 || match->bconductreviewpending)
    {
        rect(22,275,420,132,ink);
        rect(22,275,4,132,copper);
        Text(FString::Printf(TEXT("CONDUCT calls  %d"),Match->ConductFoulCount),40,286,.9f,Copper);
        WrappedText(Match->LastConductCall,40,314,.76f,Cream,380,4);
    }
    rect(22,uh-108,420,82,ink);
    rect(22,uh-108,4,82,rider->teamindex ? copper : teal);
    text((rider->teamindex ? text("copper  /  ") : text("teal  /  ")) + ABBMatchState::PositionName(Rider->Position).ToUpper(),40,UH-99,1,Cream);
    if (penaltydecision)
    {
        text(text("shot resolved / protected restart NEXT"),40,UH-67,.8,Gold);
        text(text("wait for the referee to return the ball to the keeper."),40,UH-43,.75,Muted);
    }
    else if (penaltyshooter)
    {
        text(pad ? text("rs  aim    rt  shoot once") : text("mouse  aim    lmb  shoot once"),40,UH-67,.8,Gold);
        text(text("stay at the mark. the full attempt lasts five seconds."),40,UH-43,.75,Muted);
    }
    else if (penaltykeeper)
    {
        text(pad ? text("ls  fly   rs  look   a / b  rise / descend") : text("wasd  fly    space / ctrl  rise / descend"),40,UH-67,.8,Gold);
        text(text("block the ball with your body. stay in the goal area."),40,UH-43,.75,Muted);
    }
    else if (penalty)
    {
        text(pad ? text("rs  look around") : text("mouse  look around"),40,UH-67,.8,Muted);
        text(text("shot in progress. movement and roles locked."),40,UH-43,.75,Muted);
    }
    else
    {
        text(pad ? text("ls  fly   rs  look   a / b  rise / descend") : text("wasd  fly    space / ctrl  rise / descend"),40,UH-67,.8,Muted);
        text(pad ? text("x  catch   rt  throw   view  roles   menu  pause") : text("e  grab / catch    lmb  throw    tab  roles    p  Stoppage"),40,UH-43,.75,Muted);
    }
    rect(uw-310,uh-106,286,79,ink);
    Text(FString::Printf(TEXT("VITALITY  %d"),FMath::RoundToInt(Rider->Vitality)),UW-293,UH-96,.78f,Cream);
    Rect(UW-293,UH-72,252,4,Muted*.3f);
    Rect(UW-293,UH-72,252*FMath::Clamp(Rider->Vitality/100.f,0.f,1.f),4,Rider->Vitality < 30.f ? copper : teal);
    fstring effects;
    if (rider->shieldremaining > 0.f) effects += FString::Printf(TEXT("SHIELD %.1f  "),rider->shieldremaining);
    if (rider->impedimentremaining > 0.f) effects += FString::Printf(TEXT("SLOWED %.1f  "),rider->impedimentremaining);
    if (rider->disarmremaining > 0.f) effects += FString::Printf(TEXT("DISARMED %.1f"),Rider->DisarmRemaining);
    wrappedtext(penalty ? text("wandwork locked / effect clocks frozen") : Effects.IsEmpty() ? (pad ? text("lb  protego / defend before impact") : text("r  protego  /  defend before impact")) : effects,
        UW-293,UH-54,.68f,Effects.IsEmpty()?Muted:Gold,252,2);
    Rect(UW/2-350,UH-161,700,36,Ink);
    fstring announcement = match->announcement;
    if (pad)
    {
        Announcement.ReplaceInline(TEXT("ENTER"), text("menu"));
        Announcement.ReplaceInline(TEXT("Hold e"), text("hold x"));
        Announcement.ReplaceInline(TEXT("with 1-6"), text("with d-pad Up/Down"));
    }
    WrappedText(Announcement,UW/2-334,UH-154,.79,Cream,670,1);
    DrawLine(W/2-10*S,H/2,W/2-4*S,H/2,Cream,1.3f*S);
    DrawLine(W/2+4*S,H/2,W/2+10*S,H/2,Cream,1.3f*S);
    DrawLine(W/2,H/2-10*S,W/2,H/2-4*S,Cream,1.3f*S);
    DrawLine(W/2,H/2+4*S,W/2,H/2+10*S,Cream,1.3f*S);

    abbball* held = nullptr;
    abbball* chasetarget = nullptr;
    float bestdist = TNumericLimits<float>::Max();
    const bool canchase = rider->position == 3 || rider->position == 5 || match->phase == text("donnybrook");
    text(penalty ? text("shot / balls") : text("balls in PLAY"),UW-244,143,.78f,Muted);
    for (tactoriterator<abbball> it(getworld()); it; ++it)
    {
        abbball* b = *it;
        if (b->holder == rider) held = b;
        const flinearcolor ballcolor = b->ballindex == 0 ? copper : b->ballindex < 3 ? violet : b->ballindex == 3 ? copper : b->ballindex == 4 ? gold : muted;
        const float statusy = 169 + FMath::Clamp(B->BallIndex,0,6) * 48;
        rect(uw-252,statusy-3,228,43,ink);
        rect(uw-252,statusy-3,3,43,b->bactive ? ballcolor : Muted*.5f);
        Text(B->DisplayName(),UW-240,StatusY,.82f,BallColor);
        fstring ballstate = b->bactive ? text("free") : text("out of play");
        if (isvalid(b->holder))
            ballstate = (b->holder->teamindex ? text("copper / ") : text("teal / ")) + ABBMatchState::PositionName(B->Holder->Position).ToUpper();
        else if (b->returnin > 0)
        {
            const int32 returnseconds = FMath::Max(0,FMath::CeilToInt(B->ReturnIn-.001f));
            ballstate = FString::Printf(TEXT("%s %d:%02d"), b->ballstatus == text("scheduled_release") ? text("release in") : text("returns in"), ReturnSeconds/60, returnseconds%60);
        }
        else if (b->ballstatus == text("crown")) ballstate = text("no crown / returning");
        else if (penalty && match->ispenaltyballactive(b))
            ballstate = match->bpenaltyshotreleased ? text("shot / in flight") : text("shot / at the mark");
        else if (penalty && b->bactive) ballstate = text("frozen / shot");
        else if (!match->blive && b->bactive) ballstate = text("waiting for play");
        Text(BallState,UW-240,StatusY+20,.67f,Muted);
        if (b->ischase())
        {
            const float d = FVector::Distance(Rider->GetActorLocation(),B->GetActorLocation());
            if (canchase && b->bactive && d < bestdist) { bestdist = d; chasetarget = b; }
        }
        if ((!match->blive && !(penalty && match->ispenaltyballactive(b))) || rider->bshowroster || rider->bshowspellbook || !b->bactive || b->holder == rider) continue;
        fvector2d screen;
        if (playerowner->projectworldlocationtoscreen(b->getactorlocation(), screen) && Screen.X > 30 && Screen.X < w-100 && Screen.Y > 125*s && Screen.Y < h-175*s
            && !(Screen.X+170*S > w-252*s && Screen.Y < 510*s))
        {
            flinearcolor color = b->ballindex == 0 ? copper : b->ballindex < 3 ? violet : b->ballindex == 3 ? copper : b->ballindex == 4 ? gold : muted;
            float d = FVector::Dist(Rider->GetActorLocation(),B->GetActorLocation())/100.f;
            if (b->ischase() || d < 22.f)
            {
                DrawRect(Ink,Screen.X-4*S,Screen.Y+18*S,170*S,22*S);
                DrawText(FString::Printf(TEXT("%s  %.1fm"),*B->DisplayName(),D),Color,Screen.X,Screen.Y+20*S,Font,.75f*S);
            }
        }
    }
    if (held && !penalty)
    {
        text(text("carrying ")+held->displayname()+(pad ? text("  |  rt to throw") : text("  |  lmb to THROW")),UW/2-190,UH/2+90,.95,Cream);
        if (held->isbludger()) text(text("release within 3 seconds. team control limit: 6 seconds."),UW/2-225,UH/2+116,.8,Gold);
        else if (canchase) text(text("release your ball before attempting a chase capture."),UW/2-200,UH/2+116,.8,Muted);
    }
    else if (chasetarget && match->blive)
    {
        const bool inrange = bestdist <= 380;
        const float progress = chasetarget->capturingrider == rider ? chasetarget->captureprogress : 0;
        const flinearcolor color = chasetarget->ballindex == 3 ? copper : gold;
        Rect(UW/2-185,UH/2+96,370,61,Ink);
        Text(FString::Printf(TEXT("%s  %.1fm  |  %s"),*ChaseTarget->DisplayName(),BestDist/100.f,InRange ? (pad ? text("hold x to catch") : text("hold e to catch")) : text("close to 3.8m")),UW/2-170,UH/2+105,.9,Color);
        Rect(UW/2-170,UH/2+139,340,5,Muted*.3f);
        Rect(UW/2-170,UH/2+139,340*Progress,5,Color);
        fvector2d screen;
        if (!playerowner->projectworldlocationtoscreen(chasetarget->getactorlocation(),screen) || Screen.X < 0 || Screen.X > w || Screen.Y < 0 || Screen.Y > h)
        {
            const fvector to = chasetarget->getactorlocation()-rider->getactorlocation();
            const float side = FVector::DotProduct(To,FRotationMatrix(PlayerOwner->GetControlRotation()).GetUnitAxis(EAxis::Y));
            // keep directional guidance below the seven equipment cards.
            text(side < 0 ? text("< chase target") : text("chase target >"), side < 0 ? 28 : UW-224,FMath::Max(UH/2,530.f),1,Color);
        }
    }
    if ((rider->hasspellmovementlock() || rider->imperioremaining > 0.f) && !penalty)
    {
        Rect(UW/2-155,UH/2-90,310,42,Ink);
        text(rider->transformationremaining > 0 ? text("transformed - recovering")
            : rider->petrificusremaining > 0 ? text("petrificus - bound")
            : rider->stunremaining > 0 ? text("stunned - recovering")
            : text("imperio - flight REVERSED"),UW/2-145,UH/2-79,.98f,Copper);
    }
    if (match->status == text("final") || match->status == text("certifying result"))
    {
        const bool bfinal = match->status == text("final");
        const flinearcolor resultcolor = match->winner == 0 ? teal : copper;
        Rect(UW/2-300,188,600,210,Ink);
        Rect(UW/2-300,188,600,4,bFinal ? resultcolor : gold);
        text(bfinal ? (match->winner == 0 ? text("teal wins") : text("copper wins")) : text("result under REVIEW"),UW/2-265,216,1.8f,bFinal ? resultcolor : gold);
        Text(FString::Printf(TEXT("TEAL  %d     /     copper  %d"),Match->TealScore,Match->CopperScore),UW/2-265,273,1.2f,Cream);
        text(bfinal ? (pad ? text("certified result. Host: menu to play again.") : text("certified result. Host: enter to play again.")) : text("resolving the final play and outstanding decisions."),UW/2-265,332,.85f,Muted);
    }
    else if (penalty)
    {
        auto participant = [&](int32 slot)
        {
            for (tactoriterator<abbridercharacter> it(getworld()); it; ++it)
                if (it->rosterindex == slot)
                    return FString::Printf(TEXT("%s / %s / #%d"), it->teamindex ? text("copper") : text("teal"),
                        *ABBMatchState::PositionName(It->Position).ToUpper(), slot + 1);
            return FString::Printf(TEXT("ROSTER #%d"), slot + 1);
        };
        const bool quaffle = match->penaltyshotball == 0;
        Rect(UW/2-330,164,660,256,Ink);
        Rect(UW/2-330,164,660,4,Gold);
        text(match->bfreeshot ? text("moderate foul / free shot") : text("serious foul / penalty SHOT"),UW/2-305,181,1.3f,Gold);
        const fstring shotstage = penaltydecision ? text("decision / restart next")
            : FString::Printf(TEXT("ATTEMPT %.1fs / 5s"), match->penaltyshotsecondsleft);
        Text(FString::Printf(TEXT("%s / %d points     %s"), quaffle ? text("quaffle") : text("quark"),
            quaffle ? 13 : 37, *ShotStage),UW/2-305,215,.94f,Cream);
        text(text("shooter  ") + Participant(Match->PenaltyShooterSlot),UW/2-305,245,.84f,PenaltyShooter ? gold : cream);
        text(text("keeper    ") + Participant(Match->PenaltyKeeperSlot),UW/2-305,270,.84f,PenaltyKeeper ? gold : cream);
        const fstring instructions = penaltydecision ? text("shot RESOLVED. the defending keeper receives the protected restart.")
            : penaltyshooter ? (match->bpenaltyshotreleased ? text("your shot is AWAY. stay at the mark until the decision.")
                : pad ? text("you SHOOT: rs to aim. rt to release. stay at the mark.")
                    : text("you SHOOT: mouse to aim. lmb to release. stay at the mark."))
            : penaltykeeper ? text("you DEFEND: fly inside the goal area and body-block the ball.")
                : text("wait for the DECISION. only the designated keeper may move.");
        WrappedText(Instructions,UW/2-305,307,.84f,Cream,610,2);
        WrappedText(Match->PenaltyShotStatus,UW/2-305,353,.80f,Gold,610,2);
        text(text("no wands  /  no passes  /  no second ATTEMPT"),UW/2-305,395,.79f,Muted);
    }
    else if (match->bconductreviewpending)
    {
        Rect(UW/2-330,164,660,256,Ink);
        Rect(UW/2-330,164,660,4,Copper);
        text(text("playtest REFEREE"),UW/2-305,185,1.4f,Copper);
        WrappedText(Match->LastConductCall,UW/2-305,226,.88f,Cream,610,3);
        if (pad)
        {
            Text(TEXT("Host: left free shot / up possession / right serious / down Severe"),UW/2-305,296,.79f,Gold);
            text(rider->gamepadrefereechoice == 1 ? TEXT("MODERATE: possession award. menu to confirm.")
                : rider->gamepadrefereechoice == 2 ? TEXT("SEVERE: ejection. menu to confirm.")
                : rider->gamepadrefereechoice == 3 ? TEXT("SERIOUS: penalty shot + removal. menu to confirm.")
                : rider->gamepadrefereechoice == 4 ? TEXT("MODERATE: free shot, no removal. menu to confirm.")
                : text("choose a disposition before confirming with Menu."),UW/2-305,328,.82f,Cream);
        }
        else WrappedText(Match->ConductReviewStatus,UW/2-305,296,.85f,Gold,610,3);
        text(text("bb-0 dispositions are provisional. play remains stopped."),UW/2-305,385,.77f,Muted);
    }
    else if (rider->bshowspellbook)
    {
        Rect(UW/2-460,158,920,508,Ink);
        Rect(UW/2-460,158,920,3,Violet);
        Text(TEXT("SPELLBOOK"),UW/2-434,176,1.35f,Cream);
        text(pad ? text("d-pad L/R  select    rb  cast    lb  protego    y  close") : text("z / x  select     q  cast     r  protego     v  Close"),UW/2-434,211,.84f,Muted);
        text(text("bb-0 sporting ADAPTATIONS"),UW/2+174,179,.72f,Gold);
        const int32 rows = (BBSpellCatalog::Count()+1)/2;
        for (int32 i=0; I<BBSpellCatalog::Count(); ++i)
        {
            const float x = UW/2-434 + (I/Rows)*445, y = 246 + (i%rows)*23;
            const bool bselected = rider->selectedspell == i, bimplemented = BBSpellCatalog::IsImplemented(I);
            if (bselected) Rect(X-6,Y-2,421,22,FLinearColor(.13f,.075f,.20f,.95f));
            text((bselected ? text(">  ") : text("   "))+BBSpellCatalog::Name(I),X,Y,.78f,bSelected?Cream:bImplemented?Muted:Muted*.65f);
            Text(bImplemented?TEXT("AVAILABLE"):TEXT("LATER"),X+329,Y,.66f,bImplemented?Teal:Gold);
        }
        WrappedText(BBSpellCatalog::Description(Rider->SelectedSpell),UW/2-434,625,.80f,Cream,866,2);
    }
    else if (!match->blive || rider->bshowroster)
    {
        Rect(UW/2-300,164,600,356,Ink);
        text(match->blive ? text("position guide") : Match->Status,UW/2-275,184,1.4,Cream);
        text(match->blive ? text("position changes unlock at stoppages.") : (pad ? text("d-pad Up/Down: position. Host: menu to start / resume.") : text("choose a position. t switches team. Host: enter to start.")),UW/2-275,221,.85,Muted);
        const tchar* descriptions[] = {text("defend goals. take protected scoring-ball restarts."),TEXT("Carry and shoot quaffles and Quarks."),TEXT("Intercept, carry and shoot scoring balls."),TEXT("Scoring balls + chase. release before catching."),TEXT("Control Bludgers. throw before the control limit."),TEXT("Chase snipe and Snitch. no scoring-ball possession.")};
        for (int32 i=0;i<6;++i)
        {
            const float y=258+i*32;
            if (rider->position == i) Rect(UW/2-280,Y-2,560,29,FLinearColor(.05,.17,.18,.9));
            Text(FString::Printf(TEXT("%d  %s"),I+1,*ABBMatchState::PositionName(I)),UW/2-267,Y,.86,Rider->Position==I?Teal:Cream);
            Text(Descriptions[I],UW/2-110,Y,.75,Muted);
        }
        text(text("quaffle 13   /   quark 37   /   snipe 69   /   snitch 150 (ot 300)"),UW/2-275,459,.75,Gold);
        if (pad)
            text(rider->bshowroster ? text("d-pad Left: team / Right: Bloodbroom. Menu: advantage call.") : TEXT("View: roster + team / variant controls. Y: spellbook."),UW/2-275,489,.77f,Muted);
        else text(match->status == text("lobby") ? text("v  spellbook    Host: b toggles bloodbroom before play") : text("v  spellbook    q  cast    r  protego    f10  host advantage call"),UW/2-275,489,.77f,Muted);
    }
    // keep server feedback below overlays, and acknowledge only text actually
    // presented by this owner's HUD. the rider sends the rpc on a later Tick.
    if (rider->spellfeedbackremaining > 0.f && !Rider->SpellFeedback.IsEmpty())
    {
        Rect(UW/2-380,UH-221,760,52,Ink);
        Rect(UW/2-380,UH-221,3,52,Violet);
        WrappedText(Rider->SpellFeedback,UW/2-363,UH-213,.86f,Cream,725,2);
        rider->markspellfeedbackdisplayed();
    }
}
