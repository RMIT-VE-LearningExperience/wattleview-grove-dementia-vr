#include <fbxsdk.h>
#include <cmath>
#include <iostream>
#include <map>
#include <string>
#include <vector>

struct WeightSet { std::vector<int> index; std::vector<double> weight; };
struct ClusterSpec {
    std::string name;
    FbxNode* link = nullptr;
    FbxNode* associate = nullptr;
    FbxCluster::ELinkMode linkMode = FbxCluster::eNormalize;
    FbxAMatrix transform;
    FbxAMatrix transformLink;
    FbxAMatrix transformAssociate;
};

static FbxScene* Load(FbxManager* manager, const char* path)
{
    FbxImporter* importer = FbxImporter::Create(manager, "");
    if (!importer->Initialize(path, -1, manager->GetIOSettings())) {
        std::cerr << "Initialize failed for " << path << ": " << importer->GetStatus().GetErrorString() << "\n";
        importer->Destroy();
        return nullptr;
    }
    FbxScene* scene = FbxScene::Create(manager, path);
    if (!importer->Import(scene)) {
        std::cerr << "Import failed for " << path << ": " << importer->GetStatus().GetErrorString() << "\n";
        importer->Destroy();
        scene->Destroy();
        return nullptr;
    }
    importer->Destroy();
    return scene;
}

static FbxMesh* FindSkinnedMesh(FbxScene* scene)
{
    for (int index = 0; index < scene->GetGeometryCount(); ++index) {
        FbxMesh* mesh = FbxCast<FbxMesh>(scene->GetGeometry(index));
        if (mesh && mesh->GetDeformerCount(FbxDeformer::eSkin) > 0) return mesh;
    }
    return nullptr;
}

static FbxSkin* FirstSkin(FbxMesh* mesh)
{
    return mesh && mesh->GetDeformerCount(FbxDeformer::eSkin) > 0
        ? FbxCast<FbxSkin>(mesh->GetDeformer(0, FbxDeformer::eSkin)) : nullptr;
}

static double MatrixMaxDelta(const FbxAMatrix& a, const FbxAMatrix& b)
{
    double maximum = 0.0;
    for (int row = 0; row < 4; ++row)
        for (int column = 0; column < 4; ++column)
            maximum = std::max(maximum, std::abs(a[row][column] - b[row][column]));
    return maximum;
}

static FbxPose* FindBindPose(FbxScene* scene)
{
    for (int index = 0; index < scene->GetPoseCount(); ++index) {
        FbxPose* pose = scene->GetPose(index);
        if (pose && pose->IsBindPose()) return pose;
    }
    return nullptr;
}

static bool ValidateScene(FbxScene* scene, const std::map<std::string, FbxAMatrix>& expectedLink,
    const FbxAMatrix& expectedMesh, const std::map<std::string, FbxAMatrix>& expectedT0,
    const char* stage)
{
    FbxMesh* mesh = FindSkinnedMesh(scene);
    FbxSkin* skin = FirstSkin(mesh);
    FbxPose* pose = FindBindPose(scene);
    if (!mesh || !skin || !pose) {
        std::cerr << stage << " missing mesh, skin, or bind pose\n";
        return false;
    }
    FbxNode* root = scene->FindNodeByName("root");
    FbxArray<FbxNode*> missingAncestor, missingDeform, missingDeformAncestor, wrongMatrix;
    FbxStatus status;
    bool valid = root && pose->IsValidBindPoseVerbose(root, missingAncestor, missingDeform,
        missingDeformAncestor, wrongMatrix, 0.0001, &status);
    double maxLinkDelta = 0.0;
    double maxMeshDelta = 0.0;
    int matched = 0;
    for (int index = 0; index < skin->GetClusterCount(); ++index) {
        FbxCluster* cluster = skin->GetCluster(index);
        if (!cluster || !cluster->GetLink()) continue;
        auto expected = expectedLink.find(cluster->GetLink()->GetName());
        if (expected == expectedLink.end()) continue;
        FbxAMatrix link, meshMatrix;
        cluster->GetTransformLinkMatrix(link);
        cluster->GetTransformMatrix(meshMatrix);
        maxLinkDelta = std::max(maxLinkDelta, MatrixMaxDelta(link, expected->second));
        maxMeshDelta = std::max(maxMeshDelta, MatrixMaxDelta(meshMatrix, expectedMesh));
        ++matched;
    }
    double maxT0Delta = 0.0;
    int matchedT0 = 0;
    for (const auto& pair : expectedT0) {
        FbxNode* node = scene->FindNodeByName(pair.first.c_str());
        if (!node) continue;
        maxT0Delta = std::max(maxT0Delta,
            MatrixMaxDelta(node->EvaluateGlobalTransform(FBXSDK_TIME_ZERO), pair.second));
        ++matchedT0;
    }
    FbxAMatrix meshT0 = mesh->GetNode()->EvaluateGlobalTransform(FBXSDK_TIME_ZERO);
    std::cout << stage << " verts=" << mesh->GetControlPointsCount()
              << " bones=" << expectedLink.size()
              << " clusters=" << skin->GetClusterCount()
              << " pose=" << pose->GetCount()
              << " valid=" << valid
              << " wrong=" << wrongMatrix.GetCount()
              << " missingAncestor=" << missingAncestor.GetCount()
              << " matchedClusters=" << matched
              << " maxLinkDelta=" << maxLinkDelta
              << " maxMeshDelta=" << maxMeshDelta
              << " matchedT0=" << matchedT0
              << " maxT0Delta=" << maxT0Delta
              << " meshT0Delta=" << MatrixMaxDelta(meshT0, expectedMesh)
              << " unitCm=" << scene->GetGlobalSettings().GetSystemUnit().GetScaleFactor()
              << " status=" << status.GetErrorString() << "\n";
    for (int index = 0; index < missingAncestor.GetCount(); ++index)
        std::cout << stage << " missing ancestor " << missingAncestor[index]->GetName() << "\n";
    for (int index = 0; index < wrongMatrix.GetCount(); ++index)
        std::cout << stage << " wrong matrix " << wrongMatrix[index]->GetName() << "\n";
    return valid && skin->GetClusterCount() == static_cast<int>(expectedLink.size())
        && maxLinkDelta < 1e-9 && maxMeshDelta < 1e-9 && maxT0Delta < 1e-9;
}

int main(int argc, char** argv)
{
    if (argc < 4) {
        std::cerr << "usage: transplant source_body.fbx garment.fbx out.fbx\n";
        return 2;
    }
    FbxManager* manager = FbxManager::Create();
    manager->SetIOSettings(FbxIOSettings::Create(manager, IOSROOT));
    FbxScene* source = Load(manager, argv[1]);
    FbxScene* garment = Load(manager, argv[2]);
    if (!source || !garment) return 3;

    FbxMesh* sourceMesh = FindSkinnedMesh(source);
    FbxMesh* garmentMesh = FindSkinnedMesh(garment);
    FbxSkin* sourceSkin = FirstSkin(sourceMesh);
    FbxSkin* garmentSkin = FirstSkin(garmentMesh);
    if (!sourceMesh || !garmentMesh || !sourceSkin || !garmentSkin) {
        std::cerr << "A source mesh or skin is missing\n";
        return 4;
    }
    FbxNode* meshNode = sourceMesh->GetNode();
    FbxNode* garmentNode = garmentMesh->GetNode();
    FbxNode* sourceRootNode = source->FindNodeByName("root");
    std::cerr << "source mesh node=" << (meshNode ? meshNode->GetName() : "<null>")
              << " parent=" << (meshNode && meshNode->GetParent() ? meshNode->GetParent()->GetName() : "<none>")
              << " root parent=" << (sourceRootNode && sourceRootNode->GetParent() ? sourceRootNode->GetParent()->GetName() : "<none>")
              << " root grandparent=" << (sourceRootNode && sourceRootNode->GetParent() && sourceRootNode->GetParent()->GetParent() ? sourceRootNode->GetParent()->GetParent()->GetName() : "<none>")
              << "\n";
    FbxSkin::EType sourceSkinningType = sourceSkin->GetSkinningType();
    double sourceDeformAccuracy = sourceSkin->GetDeformAccuracy();

    std::map<std::string, WeightSet> garmentWeights;
    for (int clusterIndex = 0; clusterIndex < garmentSkin->GetClusterCount(); ++clusterIndex) {
        FbxCluster* cluster = garmentSkin->GetCluster(clusterIndex);
        if (!cluster || !cluster->GetLink()) continue;
        WeightSet& set = garmentWeights[cluster->GetLink()->GetName()];
        int count = cluster->GetControlPointIndicesCount();
        int* indices = cluster->GetControlPointIndices();
        double* weights = cluster->GetControlPointWeights();
        for (int index = 0; index < count; ++index) {
            set.index.push_back(indices[index]);
            set.weight.push_back(weights[index]);
        }
    }

    std::vector<ClusterSpec> clusterSpecs;
    std::map<std::string, FbxAMatrix> expectedLink;
    std::map<std::string, FbxAMatrix> expectedT0;
    FbxAMatrix expectedMesh;
    expectedMesh.SetIdentity();
    for (int clusterIndex = 0; clusterIndex < sourceSkin->GetClusterCount(); ++clusterIndex) {
        FbxCluster* cluster = sourceSkin->GetCluster(clusterIndex);
        if (!cluster || !cluster->GetLink()) continue;
        ClusterSpec spec;
        spec.name = cluster->GetName();
        spec.link = cluster->GetLink();
        spec.associate = cluster->GetAssociateModel();
        spec.linkMode = cluster->GetLinkMode();
        cluster->GetTransformMatrix(spec.transform);
        cluster->GetTransformLinkMatrix(spec.transformLink);
        cluster->GetTransformAssociateModelMatrix(spec.transformAssociate);
        expectedMesh = spec.transform;
        expectedLink[spec.link->GetName()] = spec.transformLink;
        expectedT0[spec.link->GetName()] = spec.link->EvaluateGlobalTransform(FBXSDK_TIME_ZERO);
        clusterSpecs.push_back(spec);
    }

    // FbxMesh::Copy copies topology and layer elements but deliberately leaves graph
    // connections behind, which is exactly what this transplant needs.
    FbxMesh* replacement = FbxMesh::Create(source, garmentMesh->GetName());
    replacement->Copy(*garmentMesh);
    while (replacement->GetDeformerCount(FbxDeformer::eSkin) > 0) {
        FbxDeformer* deformer = replacement->RemoveDeformer(0);
        if (deformer) deformer->Destroy(true);
    }
    double scale = garment->GetGlobalSettings().GetSystemUnit().GetScaleFactor()
        / source->GetGlobalSettings().GetSystemUnit().GetScaleFactor();
    FbxVector4* controlPoints = replacement->GetControlPoints();
    for (int index = 0; index < replacement->GetControlPointsCount(); ++index) {
        controlPoints[index][0] *= scale;
        controlPoints[index][1] *= scale;
        controlPoints[index][2] *= scale;
    }

    // Keep the source mesh node object.  Its bind-pose entry, T0 transform, pivot
    // state, and relationship (mesh node is the root joint's parent) stay byte-for-byte.
    FbxNodeAttribute* detachedSourceMesh = meshNode->SetNodeAttribute(replacement);
    if (detachedSourceMesh && detachedSourceMesh != replacement)
        detachedSourceMesh->Destroy(false);
    meshNode->SetName(garmentNode->GetName());
    replacement->SetName(garmentMesh->GetName());

    while (meshNode->GetMaterialCount() > 0)
        meshNode->RemoveMaterial(meshNode->GetMaterial(0));
    for (int materialIndex = 0; materialIndex < garmentNode->GetMaterialCount(); ++materialIndex) {
        FbxSurfaceMaterial* garmentMaterial = garmentNode->GetMaterial(materialIndex);
        FbxSurfaceMaterial* sourceMaterial = FbxCast<FbxSurfaceMaterial>(
            garmentMaterial->Clone(FbxObject::eDeepClone, source));
        if (sourceMaterial) meshNode->AddMaterial(sourceMaterial);
    }

    FbxSkin* replacementSkin = FbxSkin::Create(source, "SourceExactSkin");
    replacementSkin->SetSkinningType(sourceSkinningType);
    replacementSkin->SetDeformAccuracy(sourceDeformAccuracy);
    for (const ClusterSpec& spec : clusterSpecs) {
        FbxCluster* cluster = FbxCluster::Create(source, spec.name.c_str());
        cluster->SetLink(spec.link);
        cluster->SetLinkMode(spec.linkMode);
        cluster->SetTransformMatrix(spec.transform);
        cluster->SetTransformLinkMatrix(spec.transformLink);
        if (spec.associate) {
            cluster->SetAssociateModel(spec.associate);
            cluster->SetTransformAssociateModelMatrix(spec.transformAssociate);
        }
        auto weights = garmentWeights.find(spec.link->GetName());
        if (weights != garmentWeights.end()) {
            for (size_t index = 0; index < weights->second.index.size(); ++index)
                cluster->AddControlPointIndex(weights->second.index[index], weights->second.weight[index]);
        }
        replacementSkin->AddCluster(cluster);
    }
    replacement->AddDeformer(replacementSkin);

    // Epic's source FBX omits the identity grouping node above both the skinned
    // mesh node and `root` from its bind pose.  Autodesk therefore reports the
    // source pose as incomplete even though all deform matrices are correct.
    // Add only missing ancestors, preserving every existing source entry.
    FbxPose* sourceBindPose = FindBindPose(source);
    for (FbxNode* ancestor = source->FindNodeByName("root")->GetParent();
         sourceBindPose && ancestor && ancestor != source->GetRootNode();
         ancestor = ancestor->GetParent()) {
        if (sourceBindPose->Find(ancestor) < 0)
            sourceBindPose->Add(ancestor, FbxMatrix(ancestor->EvaluateGlobalTransform(FBXSDK_TIME_ZERO)), false, false);
    }
    source->GetAnimationEvaluator()->Reset();

    bool beforeExport = ValidateScene(source, expectedLink, expectedMesh, expectedT0, "before-export");
    FbxExporter* exporter = FbxExporter::Create(manager, "");
    if (!exporter->Initialize(argv[3], -1, manager->GetIOSettings())) {
        std::cerr << "Exporter initialize failed: " << exporter->GetStatus().GetErrorString() << "\n";
        return 6;
    }
    exporter->SetFileExportVersion(FBX_2014_00_COMPATIBLE);
    if (!exporter->Export(source)) {
        std::cerr << "Export failed: " << exporter->GetStatus().GetErrorString() << "\n";
        return 7;
    }
    exporter->Destroy();

    FbxScene* reload = Load(manager, argv[3]);
    bool afterExport = reload && ValidateScene(reload, expectedLink, expectedMesh, expectedT0, "after-reload");
    if (reload) reload->Destroy();
    garment->Destroy();
    source->Destroy();
    manager->Destroy();
    return beforeExport && afterExport ? 0 : 8;
}
