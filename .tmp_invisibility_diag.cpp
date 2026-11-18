#include <fbxsdk.h>
#include <algorithm>
#include <cmath>
#include <iomanip>
#include <iostream>
#include <limits>
#include <map>
#include <set>
#include <string>
#include <vector>

static FbxScene* Load(FbxManager* manager, const char* path)
{
    FbxImporter* importer = FbxImporter::Create(manager, "");
    if (!importer->Initialize(path, -1, manager->GetIOSettings())) {
        std::cerr << "ERROR init " << path << ": " << importer->GetStatus().GetErrorString() << "\n";
        importer->Destroy(); return nullptr;
    }
    FbxScene* scene = FbxScene::Create(manager, path);
    if (!importer->Import(scene)) {
        std::cerr << "ERROR import " << path << ": " << importer->GetStatus().GetErrorString() << "\n";
        scene->Destroy(); scene = nullptr;
    }
    importer->Destroy(); return scene;
}

static const char* AttrName(FbxNodeAttribute* attr)
{
    if (!attr) return "none";
    switch (attr->GetAttributeType()) {
    case FbxNodeAttribute::eMesh: return "mesh";
    case FbxNodeAttribute::eSkeleton: return "skeleton";
    case FbxNodeAttribute::eNull: return "null";
    case FbxNodeAttribute::eLODGroup: return "lodgroup";
    default: return "other";
    }
}

static void MatrixBrief(const FbxAMatrix& matrix)
{
    FbxVector4 t = matrix.GetT(), s = matrix.GetS(), r = matrix.GetR();
    std::cout << " T=" << t[0] << "," << t[1] << "," << t[2]
              << " R=" << r[0] << "," << r[1] << "," << r[2]
              << " S=" << s[0] << "," << s[1] << "," << s[2];
}

static void DumpTree(FbxNode* node, int depth)
{
    if (!node) return;
    std::cout << "NODE depth=" << depth << " name=" << node->GetName()
              << " attr=" << AttrName(node->GetNodeAttribute())
              << " attrs=" << node->GetNodeAttributeCount()
              << " children=" << node->GetChildCount()
              << " mats=" << node->GetMaterialCount()
              << " vis=" << node->Visibility.Get()
              << " visInherit=" << node->VisibilityInheritance.Get()
              << " show=" << node->Show.Get();
    MatrixBrief(node->EvaluateLocalTransform(FBXSDK_TIME_ZERO));
    std::cout << " GT"; MatrixBrief(node->EvaluateGlobalTransform(FBXSDK_TIME_ZERO));
    std::cout << "\n";
    if (depth < 3)
        for (int i = 0; i < node->GetChildCount(); ++i) DumpTree(node->GetChild(i), depth + 1);
}

static FbxMesh* FirstSkinnedMesh(FbxScene* scene)
{
    for (int i = 0; i < scene->GetGeometryCount(); ++i) {
        FbxMesh* mesh = FbxCast<FbxMesh>(scene->GetGeometry(i));
        if (mesh && mesh->GetDeformerCount(FbxDeformer::eSkin) > 0) return mesh;
    }
    return nullptr;
}

static const char* Mapping(FbxLayerElement::EMappingMode value)
{
    switch(value) {
    case FbxLayerElement::eByControlPoint: return "ByCP";
    case FbxLayerElement::eByPolygonVertex: return "ByPolyVertex";
    case FbxLayerElement::eByPolygon: return "ByPolygon";
    case FbxLayerElement::eAllSame: return "AllSame";
    default: return "Other";
    }
}

static const char* Reference(FbxLayerElement::EReferenceMode value)
{
    switch(value) {
    case FbxLayerElement::eDirect: return "Direct";
    case FbxLayerElement::eIndex: return "Index";
    case FbxLayerElement::eIndexToDirect: return "IndexToDirect";
    default: return "Other";
    }
}

static void Diagnose(FbxScene* scene, const char* path)
{
    std::cout << "\n=== " << path << " ===\n";
    int upSign = 0, frontSign = 0;
    FbxAxisSystem axis = scene->GetGlobalSettings().GetAxisSystem();
    std::cout << "unitCm=" << scene->GetGlobalSettings().GetSystemUnit().GetScaleFactor()
              << " axisUp=" << int(axis.GetUpVector(upSign)) << ":" << upSign
              << " axisFront=" << int(axis.GetFrontVector(frontSign)) << ":" << frontSign
              << " handed=" << int(axis.GetCoorSystem())
              << " geometryCount=" << scene->GetGeometryCount()
              << " nodeCount=" << scene->GetNodeCount()
              << " poseCount=" << scene->GetPoseCount() << "\n";
    DumpTree(scene->GetRootNode(), 0);
    FbxMesh* mesh = FirstSkinnedMesh(scene);
    if (!mesh) { std::cout << "NO SKINNED MESH\n"; return; }
    std::cout << "MESH name=" << mesh->GetName() << " nodes=" << mesh->GetNodeCount()
              << " cps=" << mesh->GetControlPointsCount() << " polygons=" << mesh->GetPolygonCount()
              << " layers=" << mesh->GetLayerCount() << " deformers=" << mesh->GetDeformerCount() << "\n";
    for (int i = 0; i < mesh->GetNodeCount(); ++i)
        std::cout << " owner[" << i << "]=" << mesh->GetNode(i)->GetName() << "\n";

    FbxVector4 mn(std::numeric_limits<double>::max(), std::numeric_limits<double>::max(), std::numeric_limits<double>::max());
    FbxVector4 mx(-std::numeric_limits<double>::max(), -std::numeric_limits<double>::max(), -std::numeric_limits<double>::max());
    int nonFinite = 0;
    FbxNode* owner = mesh->GetNode();
    FbxAMatrix geometry; geometry.SetIdentity();
    if (owner) {
        geometry.SetT(owner->GetGeometricTranslation(FbxNode::eSourcePivot));
        geometry.SetR(owner->GetGeometricRotation(FbxNode::eSourcePivot));
        geometry.SetS(owner->GetGeometricScaling(FbxNode::eSourcePivot));
    }
    FbxAMatrix world = owner ? owner->EvaluateGlobalTransform(FBXSDK_TIME_ZERO) * geometry : geometry;
    FbxVector4 wmn = mn, wmx = mx;
    for (int i = 0; i < mesh->GetControlPointsCount(); ++i) {
        FbxVector4 p = mesh->GetControlPointAt(i), wp = world.MultT(p);
        for (int a = 0; a < 3; ++a) {
            if (!std::isfinite(p[a]) || !std::isfinite(wp[a])) ++nonFinite;
            mn[a] = std::min(mn[a], p[a]); mx[a] = std::max(mx[a], p[a]);
            wmn[a] = std::min(wmn[a], wp[a]); wmx[a] = std::max(wmx[a], wp[a]);
        }
    }
    std::cout << "CP localMin=" << mn[0] << "," << mn[1] << "," << mn[2]
              << " localMax=" << mx[0] << "," << mx[1] << "," << mx[2]
              << " worldMin=" << wmn[0] << "," << wmn[1] << "," << wmn[2]
              << " worldMax=" << wmx[0] << "," << wmx[1] << "," << wmx[2]
              << " nonFinite=" << nonFinite << "\n";
    int invalidPolygonIndex = 0, degenerate = 0;
    for (int p = 0; p < mesh->GetPolygonCount(); ++p) {
        std::set<int> unique;
        for (int v = 0; v < mesh->GetPolygonSize(p); ++v) {
            int cp = mesh->GetPolygonVertex(p, v);
            if (cp < 0 || cp >= mesh->GetControlPointsCount()) ++invalidPolygonIndex;
            unique.insert(cp);
        }
        if (unique.size() < 3) ++degenerate;
    }
    std::cout << "TOPO invalidIndices=" << invalidPolygonIndex << " degenerate=" << degenerate << "\n";

    for (int l = 0; l < mesh->GetLayerCount(); ++l) {
        FbxLayer* layer = mesh->GetLayer(l);
        std::cout << "LAYER " << l;
        if (auto* mat = layer->GetMaterials()) {
            int minIndex = INT_MAX, maxIndex = INT_MIN, bad = 0;
            for (int i = 0; i < mat->GetIndexArray().GetCount(); ++i) {
                int value = mat->GetIndexArray().GetAt(i);
                minIndex = std::min(minIndex, value); maxIndex = std::max(maxIndex, value);
                if (owner && (value < 0 || value >= owner->GetMaterialCount())) ++bad;
            }
            std::cout << " material=" << Mapping(mat->GetMappingMode()) << "/" << Reference(mat->GetReferenceMode())
                      << " index=" << mat->GetIndexArray().GetCount()
                      << " min=" << minIndex << " max=" << maxIndex << " bad=" << bad;
        } else std::cout << " material=none";
        if (auto* uv = layer->GetUVs())
            std::cout << " uv=" << Mapping(uv->GetMappingMode()) << "/" << Reference(uv->GetReferenceMode())
                      << " direct=" << uv->GetDirectArray().GetCount() << " index=" << uv->GetIndexArray().GetCount();
        else std::cout << " uv=none";
        if (auto* normal = layer->GetNormals())
            std::cout << " normal=" << Mapping(normal->GetMappingMode()) << "/" << Reference(normal->GetReferenceMode())
                      << " direct=" << normal->GetDirectArray().GetCount() << " index=" << normal->GetIndexArray().GetCount();
        else std::cout << " normal=none";
        std::cout << "\n";
    }
    if (owner) for (int i = 0; i < owner->GetMaterialCount(); ++i)
        std::cout << "MATERIAL[" << i << "]=" << owner->GetMaterial(i)->GetName() << "\n";

    std::vector<double> sums(mesh->GetControlPointsCount(), 0.0);
    std::vector<int> influences(mesh->GetControlPointsCount(), 0);
    int skins = mesh->GetDeformerCount(FbxDeformer::eSkin), totalClusters = 0, weightedClusters = 0, badWeightIndices = 0;
    std::map<int,int> modes;
    for (int s = 0; s < skins; ++s) {
        FbxSkin* skin = FbxCast<FbxSkin>(mesh->GetDeformer(s, FbxDeformer::eSkin));
        if (!skin) continue;
        std::cout << "SKIN[" << s << "] name=" << skin->GetName() << " type=" << int(skin->GetSkinningType())
                  << " clusters=" << skin->GetClusterCount() << " accuracy=" << skin->GetDeformAccuracy() << "\n";
        totalClusters += skin->GetClusterCount();
        for (int c = 0; c < skin->GetClusterCount(); ++c) {
            FbxCluster* cluster = skin->GetCluster(c); if (!cluster) continue;
            modes[int(cluster->GetLinkMode())]++;
            if (cluster->GetControlPointIndicesCount() > 0) ++weightedClusters;
            int* indices = cluster->GetControlPointIndices(); double* weights = cluster->GetControlPointWeights();
            for (int i = 0; i < cluster->GetControlPointIndicesCount(); ++i) {
                if (indices[i] < 0 || indices[i] >= (int)sums.size()) { ++badWeightIndices; continue; }
                sums[indices[i]] += weights[i]; influences[indices[i]]++;
            }
            if (c < 3 || (cluster->GetLink() && std::string(cluster->GetLink()->GetName()) == "pelvis")) {
                FbxAMatrix tm, tl; cluster->GetTransformMatrix(tm); cluster->GetTransformLinkMatrix(tl);
                std::cout << " CLUSTER " << c << " name=" << cluster->GetName()
                          << " link=" << (cluster->GetLink() ? cluster->GetLink()->GetName() : "none")
                          << " ownerScene=" << (cluster->GetLink() && cluster->GetLink()->GetScene() == scene)
                          << " weights=" << cluster->GetControlPointIndicesCount() << " TM"; MatrixBrief(tm);
                std::cout << " TL"; MatrixBrief(tl); std::cout << "\n";
            }
        }
    }
    double minSum = std::numeric_limits<double>::max(), maxSum = -std::numeric_limits<double>::max();
    int zeroSum = 0, offSum = 0, zeroInfluence = 0, maxInfluence = 0;
    for (size_t i = 0; i < sums.size(); ++i) {
        minSum = std::min(minSum, sums[i]); maxSum = std::max(maxSum, sums[i]);
        if (std::abs(sums[i]) < 1e-12) ++zeroSum;
        if (std::abs(sums[i] - 1.0) > 1e-4) ++offSum;
        if (influences[i] == 0) ++zeroInfluence;
        maxInfluence = std::max(maxInfluence, influences[i]);
    }
    std::cout << "WEIGHTS skins=" << skins << " clusters=" << totalClusters << " weightedClusters=" << weightedClusters
              << " minSum=" << minSum << " maxSum=" << maxSum << " zeroSum=" << zeroSum
              << " offSum=" << offSum << " zeroInfluence=" << zeroInfluence
              << " maxInfluence=" << maxInfluence << " badIndices=" << badWeightIndices << " modes=";
    for (auto& mode : modes) std::cout << mode.first << ":" << mode.second << ",";
    std::cout << "\n";
}

int main(int argc, char** argv)
{
    if (argc < 2) return 2;
    FbxManager* manager = FbxManager::Create(); manager->SetIOSettings(FbxIOSettings::Create(manager, IOSROOT));
    for (int i = 1; i < argc; ++i) {
        FbxScene* scene = Load(manager, argv[i]);
        if (scene) { Diagnose(scene, argv[i]); scene->Destroy(); }
    }
    manager->Destroy(); return 0;
}
