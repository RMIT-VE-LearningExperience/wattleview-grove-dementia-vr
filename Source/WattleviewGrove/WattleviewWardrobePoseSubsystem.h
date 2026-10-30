#pragma once

#include "CoreMinimal.h"
#include "Subsystems/WorldSubsystem.h"
#include "WattleviewWardrobePoseSubsystem.generated.h"

/**
 * Removes MetaHuman Leader Pose links at runtime on Android/PIE.
 *
 * UE 5.7/5.8 can corrupt generated MetaHuman wardrobe meshes on the Android
 * rendering path when they are Leader Pose followers.  Wattleview's story is
 * baked in Sequencer, so Body and wardrobe can evaluate identical animation
 * tracks independently and avoid that failing path.
 */
UCLASS()
class WATTLEVIEWGROVE_API UWattleviewWardrobePoseSubsystem : public UWorldSubsystem
{
    GENERATED_BODY()

public:
    virtual bool ShouldCreateSubsystem(UObject* Outer) const override;
    virtual void OnWorldBeginPlay(UWorld& InWorld) override;
};
