#include <fbxsdk.h>
#include <algorithm>
#include <cmath>
#include <iostream>
#include <map>
#include <set>
#include <string>
#include <vector>

struct ClusterWeights
{
    std::vector<int> Indices;
    std::vector<double> Weights;
};

static bool ImportScene(FbxManager* manager, const char* path, FbxScene*& scene)
{
    scene = FbxScene::Create(manager, path);
    FbxImporter* importer = FbxImporter::Create(manager, "");
    if (!importer->Initialize(path, -1, manager->GetIOSettings()))
    {
        std::cerr << "Initialize failed: " << importer->GetStatus().GetErrorString() << "\n";
        importer->Destroy();
        return false;
    }
    const bool ok = importer->Import(scene);
    if (!ok) std::cerr << "Import failed: " << importer->GetStatus().GetErrorString() << "\n";
    importer->Destroy();
    return ok;
}

static void CollectNodes(FbxNode* node, std::vector<FbxNode*>& out)
{
    if (!node) return;
    out.push_back(node);
    for (int i = 0; i < node->GetChildCount(); ++i) CollectNodes(node->GetChild(i), out);
}

static FbxNode* FindSkinnedMeshNode(FbxScene* scene)
{
    std::vector<FbxNode*> nodes;
    CollectNodes(scene->GetRootNode(), nodes);
    for (FbxNode* node : nodes)
    {
        FbxMesh* mesh = node->GetMesh();
        if (mesh && mesh->GetDeformerCount(FbxDeformer::eSkin) > 0) return node;
    }
    return nullptr;
}

static FbxSkin* FirstSkin(FbxMesh* mesh)
{
    return mesh && mesh->GetDeformerCount(FbxDeformer::eSkin) > 0
        ? static_cast<FbxSkin*>(mesh->GetDeformer(0, FbxDeformer::eSkin)) : nullptr;
}

static FbxAMatrix PoseMatrix(FbxPose* pose, FbxNode* node, bool& found)
{
    found = false;
    if (pose && node)
    {
        const int index = pose->Find(node);
        if (index >= 0 && !pose->IsLocalMatrix(index))
        {
            const FbxMatrix matrix = pose->GetMatrix(index);
            found = true;
            return FbxAMatrix(*(FbxAMatrix*)(double*)&matrix);
        }
    }
    return FbxAMatrix();
}

int main(int argc, char** argv)
{
    if (argc != 4)
    {
        std::cerr << "usage: canonicalize source_body.fbx garment.fbx output.fbx\n";
        return 2;
    }

    FbxManager* manager = FbxManager::Create();
    FbxIOSettings* ios = FbxIOSettings::Create(manager, IOSROOT);
    manager->SetIOSettings(ios);

    FbxScene* source = nullptr;
    FbxScene* garment = nullptr;
    if (!ImportScene(manager, argv[1], source) || !ImportScene(manager, argv[2], garment)) return 3;

    // Canonical MetaHuman source is centimeters. Convert garment mesh and its scene
    // consistently before extracting control points and weights.
    FbxSystemUnit cmUnit(1.0);
    FbxSystemUnit::ConversionOptions unitOptions = {true, true, true, true, true, true};
    cmUnit.ConvertScene(garment, unitOptions);

    FbxNode* sourceMeshNode = FindSkinnedMeshNode(source);
    FbxNode* garmentMeshNode = FindSkinnedMeshNode(garment);
    if (!sourceMeshNode || !garmentMeshNode)
    {
        std::cerr << "Missing skinned mesh node\n";
        return 4;
    }
    FbxMesh* sourceMesh = sourceMeshNode->GetMesh();
    FbxMesh* garmentMesh = garmentMeshNode->GetMesh();
    FbxSkin* sourceSkin = FirstSkin(sourceMesh);
    FbxSkin* garmentSkin = FirstSkin(garmentMesh);
    if (!sourceSkin || !garmentSkin) return 5;

    std::vector<std::string> garmentMaterialNames;
    garmentMaterialNames.reserve(garmentMeshNode->GetMaterialCount());
    for (int i = 0; i < garmentMeshNode->GetMaterialCount(); ++i)
        garmentMaterialNames.emplace_back(garmentMeshNode->GetMaterial(i)->GetName());

    std::map<std::string, ClusterWeights> garmentWeights;
    for (int i = 0; i < garmentSkin->GetClusterCount(); ++i)
    {
        FbxCluster* cluster = garmentSkin->GetCluster(i);
        if (!cluster || !cluster->GetLink()) continue;
        ClusterWeights weights;
        const int count = cluster->GetControlPointIndicesCount();
        const int* indices = cluster->GetControlPointIndices();
        const double* values = cluster->GetControlPointWeights();
        for (int k = 0; k < count; ++k)
        {
            weights.Indices.push_back(indices[k]);
            weights.Weights.push_back(values[k]);
        }
        garmentWeights[cluster->GetLink()->GetName()] = std::move(weights);
    }

    // Preserve source bind matrices and source skeleton links before replacing skin.
    struct SourceCluster
    {
        FbxNode* Link = nullptr;
        FbxCluster::ELinkMode Mode = FbxCluster::eNormalize;
        FbxAMatrix MeshBind;
        FbxAMatrix LinkBind;
    };
    std::vector<SourceCluster> canonical;
    canonical.reserve(sourceSkin->GetClusterCount());
    for (int i = 0; i < sourceSkin->GetClusterCount(); ++i)
    {
        FbxCluster* cluster = sourceSkin->GetCluster(i);
        if (!cluster || !cluster->GetLink()) continue;
        SourceCluster item;
        item.Link = cluster->GetLink();
        item.Mode = cluster->GetLinkMode();
        cluster->GetTransformMatrix(item.MeshBind);
        cluster->GetTransformLinkMatrix(item.LinkBind);
        canonical.push_back(item);
    }

    // The source body FBX has an identity Null wrapper above both the real `root`
    // skeleton node and mesh. When attached to an existing MetaHuman skeleton,
    // Interchange may promote that SDK-authored Null to the skeleton root (the
    // Blender-only "Armature" stripping heuristic does not apply), so every skin
    // influence misses its target. Keep all canonical bone transforms, but put the
    // real root and mesh directly under the FBX scene root. This is unambiguous to
    // Interchange and preserves their globals because the removed wrapper is identity.
    FbxNode* canonicalRoot = source->FindNodeByName("root");
    FbxNode* wrapper = canonicalRoot ? canonicalRoot->GetParent() : nullptr;
    FbxNode* sceneRoot = source->GetRootNode();
    if (!canonicalRoot || !wrapper || wrapper == sceneRoot || sourceMeshNode->GetParent() != wrapper)
    {
        std::cerr << "Unexpected canonical source root/mesh wrapper topology\n";
        return 9;
    }
    const FbxAMatrix wrapperGlobal = wrapper->EvaluateGlobalTransform(FBXSDK_TIME_ZERO);
    const FbxVector4 wrapperT = wrapperGlobal.GetT();
    const FbxVector4 wrapperR = wrapperGlobal.GetR();
    const FbxVector4 wrapperS = wrapperGlobal.GetS();
    const double wrapperError = std::max({
        std::abs(wrapperT[0]), std::abs(wrapperT[1]), std::abs(wrapperT[2]),
        std::abs(wrapperR[0]), std::abs(wrapperR[1]), std::abs(wrapperR[2]),
        std::abs(wrapperS[0] - 1.0), std::abs(wrapperS[1] - 1.0), std::abs(wrapperS[2] - 1.0)});
    if (wrapperError > 1.0e-8)
    {
        std::cerr << "Canonical wrapper is not identity; refusing ambiguous reparent\n";
        return 10;
    }
    wrapper->RemoveChild(canonicalRoot);
    wrapper->RemoveChild(sourceMeshNode);
    sceneRoot->AddChild(canonicalRoot);
    sceneRoot->AddChild(sourceMeshNode);
    sceneRoot->RemoveChild(wrapper);
    wrapper->Destroy();

    // Clone all garment geometry layers (normals, UVs, smoothing, material indices)
    // into the canonical source scene. Deformers are rebuilt below.
    FbxMesh* replacement = static_cast<FbxMesh*>(garmentMesh->Clone(FbxObject::eDeepClone, source));
    if (!replacement) return 6;
    replacement->SetName("SKM_Maria_Outfit");
    // Unit conversion is represented on the garment scene's node transform, while
    // this geometry is being attached to the canonical source mesh node. Bake the
    // full garment node + geometric transform into source-mesh local control points.
    FbxAMatrix garmentGeometry;
    garmentGeometry.SetT(garmentMeshNode->GetGeometricTranslation(FbxNode::eSourcePivot));
    garmentGeometry.SetR(garmentMeshNode->GetGeometricRotation(FbxNode::eSourcePivot));
    garmentGeometry.SetS(garmentMeshNode->GetGeometricScaling(FbxNode::eSourcePivot));
    const FbxAMatrix garmentGlobal = garmentMeshNode->EvaluateGlobalTransform(FBXSDK_TIME_ZERO) * garmentGeometry;
    const FbxAMatrix sourceGlobal = sourceMeshNode->EvaluateGlobalTransform(FBXSDK_TIME_ZERO);
    const FbxAMatrix meshBake = sourceGlobal.Inverse() * garmentGlobal;
    for (int i = 0; i < replacement->GetControlPointsCount(); ++i)
        replacement->SetControlPointAt(meshBake.MultT(replacement->GetControlPointAt(i)), i);
    while (replacement->GetDeformerCount() > 0)
    {
        FbxDeformer* deformer = replacement->RemoveDeformer(0);
        deformer->Destroy();
    }
    sourceMeshNode->SetNodeAttribute(replacement);
    sourceMeshNode->SetName("SKM_Maria_Outfit");

    // Copy slot names in the exact garment order. Material appearance is irrelevant
    // because Unreal's automated import disables FBX material import.
    sourceMeshNode->RemoveAllMaterials();
    for (const std::string& materialName : garmentMaterialNames)
    {
        FbxSurfacePhong* material = FbxSurfacePhong::Create(source, materialName.c_str());
        sourceMeshNode->AddMaterial(material);
    }

    FbxSkin* replacementSkin = FbxSkin::Create(source, "Maria_Outfit_Skin");
    replacementSkin->SetSkinningType(FbxSkin::eLinear);
    int weightedClusters = 0;
    for (const SourceCluster& item : canonical)
    {
        FbxCluster* cluster = FbxCluster::Create(source, item.Link->GetName());
        cluster->SetLink(item.Link);
        cluster->SetLinkMode(item.Mode);
        cluster->SetTransformMatrix(item.MeshBind);
        cluster->SetTransformLinkMatrix(item.LinkBind);
        auto it = garmentWeights.find(item.Link->GetName());
        if (it != garmentWeights.end())
        {
            for (size_t k = 0; k < it->second.Indices.size(); ++k)
                cluster->AddControlPointIndex(it->second.Indices[k], it->second.Weights[k]);
            if (!it->second.Indices.empty()) ++weightedClusters;
        }
        replacementSkin->AddCluster(cluster);
    }
    replacement->AddDeformer(replacementSkin);

    // Rebuild one complete, valid bind pose from canonical source matrices. Include
    // the mesh node and every skeleton ancestor so Autodesk's validator has the
    // complete hierarchy after the identity wrapper is removed.
    FbxPose* oldBindPose = nullptr;
    for (int i = 0; i < source->GetPoseCount(); ++i)
        if (source->GetPose(i)->IsBindPose()) { oldBindPose = source->GetPose(i); break; }

    std::map<FbxNode*, FbxAMatrix> bindMatrices;
    for (const SourceCluster& item : canonical) bindMatrices[item.Link] = item.LinkBind;
    bindMatrices[sourceMeshNode] = canonical.empty() ? sourceMeshNode->EvaluateGlobalTransform(FBXSDK_TIME_ZERO) : canonical.front().MeshBind;
    for (const SourceCluster& item : canonical)
    {
        for (FbxNode* p = item.Link->GetParent(); p && p != source->GetRootNode(); p = p->GetParent())
        {
            if (bindMatrices.find(p) == bindMatrices.end())
            {
                bool found = false;
                FbxAMatrix matrix = PoseMatrix(oldBindPose, p, found);
                bindMatrices[p] = found ? matrix : p->EvaluateGlobalTransform(FBXSDK_TIME_ZERO);
            }
        }
    }
    for (int i = source->GetPoseCount() - 1; i >= 0; --i)
    {
        FbxPose* pose = source->GetPose(i);
        source->RemovePose(i);
        pose->Destroy();
    }
    FbxPose* bindPose = FbxPose::Create(source, "Maria_Outfit_BindPose");
    bindPose->SetIsBindPose(true);
    for (const auto& entry : bindMatrices)
    {
        FbxMatrix matrix(entry.second);
        bindPose->Add(entry.first, matrix, false, true);
    }
    source->AddPose(bindPose);

    // Remove the orphaned original body geometry after pose reconstruction.
    if (sourceMesh != replacement) sourceMesh->Destroy();

    ios->SetBoolProp(EXP_FBX_MATERIAL, true);
    ios->SetBoolProp(EXP_FBX_TEXTURE, false);
    ios->SetBoolProp(EXP_FBX_EMBEDDED, false);
    ios->SetBoolProp(EXP_FBX_ANIMATION, false);
    ios->SetBoolProp(EXP_FBX_GLOBAL_SETTINGS, true);
    FbxExporter* exporter = FbxExporter::Create(manager, "");
    int format = manager->GetIOPluginRegistry()->GetNativeWriterFormat();
    if (!exporter->Initialize(argv[3], format, ios))
    {
        std::cerr << "Exporter init failed: " << exporter->GetStatus().GetErrorString() << "\n";
        return 7;
    }
    if (!exporter->Export(source))
    {
        std::cerr << "Export failed: " << exporter->GetStatus().GetErrorString() << "\n";
        return 8;
    }
    exporter->Destroy();

    std::cout << "OUTPUT=" << argv[3]
              << " CPS=" << replacement->GetControlPointsCount()
              << " SOURCE_CLUSTERS=" << canonical.size()
              << " GARMENT_CLUSTER_NAMES=" << garmentWeights.size()
              << " WEIGHTED_CLUSTERS=" << weightedClusters
              << " MATERIALS=" << garmentMaterialNames.size() << "\n";
    source->Destroy();
    garment->Destroy();
    manager->Destroy();
    return 0;
}
