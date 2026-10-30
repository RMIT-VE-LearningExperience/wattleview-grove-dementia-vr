#include "WattleviewWardrobePoseSubsystem.h"

#include "Components/SkeletalMeshComponent.h"
#include "Engine/SkeletalMesh.h"
#include "EngineUtils.h"
#include "GameFramework/Actor.h"

DEFINE_LOG_CATEGORY_STATIC(LogWattleviewWardrobe, Log, All);

bool UWattleviewWardrobePoseSubsystem::ShouldCreateSubsystem(UObject* Outer) const
{
    const UWorld* World = Cast<UWorld>(Outer);
    if (!World)
    {
        return false;
    }

    return World->WorldType == EWorldType::Game ||
           World->WorldType == EWorldType::PIE ||
           World->WorldType == EWorldType::GamePreview;
}

void UWattleviewWardrobePoseSubsystem::OnWorldBeginPlay(UWorld& InWorld)
{
    Super::OnWorldBeginPlay(InWorld);

    int32 ConfiguredCount = 0;
    for (TActorIterator<AActor> It(&InWorld); It; ++It)
    {
        AActor* Actor = *It;
        if (!IsValid(Actor) || !Actor->ActorHasTag(TEXT("MetaHuman")))
        {
            continue;
        }

        TInlineComponentArray<USkeletalMeshComponent*> SkeletalComponents;
        Actor->GetComponents(SkeletalComponents);
        for (USkeletalMeshComponent* Component : SkeletalComponents)
        {
            if (!IsValid(Component) || Component->GetName() != TEXT("SkeletalMesh"))
            {
                continue;
            }

            const USkeletalMesh* Mesh = Component->GetSkeletalMeshAsset();
            if (!Mesh || !Mesh->GetName().EndsWith(TEXT("_Outfits")))
            {
                continue;
            }

            Component->SetLeaderPoseComponent(nullptr, true, true);
            Component->VisibilityBasedAnimTickOption =
                EVisibilityBasedAnimTickOption::AlwaysTickPoseAndRefreshBones;
            Component->bEnableUpdateRateOptimizations = false;
            Component->SetComponentTickEnabled(true);
            Component->bDisableClothSimulation = true;
            ++ConfiguredCount;

            UE_LOG(LogWattleviewWardrobe, Display,
                TEXT("Independent wardrobe pose enabled: %s / %s"),
                *Actor->GetName(), *Mesh->GetName());
        }
    }

    UE_LOG(LogWattleviewWardrobe, Display,
        TEXT("Configured %d MetaHuman wardrobe component(s) in %s"),
        ConfiguredCount, *InWorld.GetName());
}
