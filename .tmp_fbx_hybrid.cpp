#include <fbxsdk.h>
#include <iostream>
#include <map>
#include <string>
#include <utility>
#include <vector>

struct WeightSet { std::vector<int> idx; std::vector<double> w; };

static FbxScene* Load(FbxManager* m, const char* path)
{
    FbxImporter* im=FbxImporter::Create(m,"");
    if(!im->Initialize(path,-1,m->GetIOSettings())){std::cerr<<"INIT "<<path<<": "<<im->GetStatus().GetErrorString()<<"\n";return nullptr;}
    FbxScene*s=FbxScene::Create(m,path); if(!im->Import(s)){std::cerr<<"IMPORT "<<path<<": "<<im->GetStatus().GetErrorString()<<"\n";return nullptr;} im->Destroy(); return s;
}

static FbxMesh* FindSkinnedMesh(FbxScene*s)
{
    for(int i=0;i<s->GetGeometryCount();++i){FbxMesh*m=FbxCast<FbxMesh>(s->GetGeometry(i));if(m&&m->GetDeformerCount(FbxDeformer::eSkin)>0)return m;}return nullptr;
}

static FbxSkin* FirstSkin(FbxMesh*m){return m&&m->GetDeformerCount(FbxDeformer::eSkin)>0?(FbxSkin*)m->GetDeformer(0,FbxDeformer::eSkin):nullptr;}

static FbxNode* CloneSkeletonTree(FbxScene* dstScene,FbxNode* src,std::map<std::string,FbxNode*>& out)
{
    FbxNode* dst=FbxNode::Create(dstScene,src->GetName()); dst->Copy(*src); dst->SetName(src->GetName());
    if(FbxNodeAttribute* sa=src->GetNodeAttribute()){
        if(sa->GetAttributeType()==FbxNodeAttribute::eSkeleton){FbxNodeAttribute* da=(FbxNodeAttribute*)sa->Clone(FbxObject::eDeepClone,dstScene);dst->SetNodeAttribute(da);}
    }
    out[dst->GetName()]=dst;
    for(int i=0;i<src->GetChildCount();++i){FbxNode*c=src->GetChild(i);if(c->GetNodeAttribute()&&c->GetNodeAttribute()->GetAttributeType()==FbxNodeAttribute::eSkeleton)dst->AddChild(CloneSkeletonTree(dstScene,c,out));}
    return dst;
}

int main(int argc,char**argv)
{
    if(argc<4){std::cerr<<"usage: hybrid source_body.fbx garment.fbx out.fbx\n";return 2;}
    FbxManager*m=FbxManager::Create();m->SetIOSettings(FbxIOSettings::Create(m,IOSROOT));
    FbxScene*src=Load(m,argv[1]);FbxScene*dst=Load(m,argv[2]);if(!src||!dst)return 3;
    FbxMesh*sm=FindSkinnedMesh(src);FbxMesh*gm=FindSkinnedMesh(dst);if(!sm||!gm){std::cerr<<"missing skinned mesh\n";return 4;}
    FbxNode*smn=sm->GetNode();FbxNode*gmn=gm->GetNode();FbxSkin*ss=FirstSkin(sm);FbxSkin*gs=FirstSkin(gm);

    std::map<std::string,WeightSet> weights;
    for(int i=0;i<gs->GetClusterCount();++i){FbxCluster*c=gs->GetCluster(i);if(!c||!c->GetLink())continue;WeightSet&w=weights[c->GetLink()->GetName()];int n=c->GetControlPointIndicesCount();int*ii=c->GetControlPointIndices();double*ww=c->GetControlPointWeights();for(int k=0;k<n;++k){w.idx.push_back(ii[k]);w.w.push_back(ww[k]);}}

    // Convert garment geometry from metre-valued control points to source-style centimetres.
    FbxVector4*cp=gm->GetControlPoints();for(int i=0;i<gm->GetControlPointsCount();++i){cp[i][0]*=100.0;cp[i][1]*=100.0;cp[i][2]*=100.0;}
    dst->GetGlobalSettings().SetSystemUnit(FbxSystemUnit::cm);

    // Preserve garment geometry/material connections.  The normalized garment mesh node is
    // already identity, exactly like the source mesh node; copying FbxNode would disturb its
    // geometry connection, so set only the transform properties explicitly.
    gmn->LclTranslation.Set(FbxDouble3(0,0,0));gmn->LclRotation.Set(FbxDouble3(0,0,0));gmn->LclScaling.Set(FbxDouble3(1,1,1));
    gmn->SetGeometricTranslation(FbxNode::eSourcePivot,FbxVector4(0,0,0));gmn->SetGeometricRotation(FbxNode::eSourcePivot,FbxVector4(0,0,0));gmn->SetGeometricScaling(FbxNode::eSourcePivot,FbxVector4(1,1,1));

    while(gm->GetDeformerCount(FbxDeformer::eSkin)>0){FbxDeformer*d=gm->RemoveDeformer(0);if(d)d->Destroy(true);}
    for(int i=dst->GetPoseCount()-1;i>=0;--i){FbxPose*p=dst->GetPose(i);dst->RemovePose(i);p->Destroy();}

    FbxNode*oldRoot=dst->FindNodeByName("root");FbxNode*oldWrapper=dst->FindNodeByName("Armature");
    if(oldWrapper){if(FbxNode*p=oldWrapper->GetParent())p->RemoveChild(oldWrapper);oldWrapper->Destroy(true);}else if(oldRoot){if(FbxNode*p=oldRoot->GetParent())p->RemoveChild(oldRoot);oldRoot->Destroy(true);}

    FbxNode*srcRoot=src->FindNodeByName("root");if(!srcRoot){std::cerr<<"source root missing\n";return 5;}
    std::map<std::string,FbxNode*> bones;FbxNode*newRoot=CloneSkeletonTree(dst,srcRoot,bones);gmn->AddChild(newRoot);

    FbxSkin*newSkin=FbxSkin::Create(dst,"SourceExactSkin");newSkin->SetSkinningType(ss->GetSkinningType());newSkin->SetDeformAccuracy(ss->GetDeformAccuracy());
    std::map<std::string,FbxAMatrix> desiredGlobal;
    FbxAMatrix meshBind;meshBind.SetIdentity();
    for(int i=0;i<ss->GetClusterCount();++i){FbxCluster*sc=ss->GetCluster(i);if(!sc||!sc->GetLink())continue;std::string name=sc->GetLink()->GetName();auto bit=bones.find(name);if(bit==bones.end()){std::cerr<<"cloned bone missing "<<name<<"\n";return 6;}
        FbxCluster*dc=FbxCluster::Create(dst,sc->GetName());dc->SetLink(bit->second);dc->SetLinkMode(sc->GetLinkMode());
        FbxAMatrix tm,tl,ta;sc->GetTransformMatrix(tm);sc->GetTransformLinkMatrix(tl);sc->GetTransformAssociateModelMatrix(ta);dc->SetTransformMatrix(tm);dc->SetTransformLinkMatrix(tl);dc->SetTransformAssociateModelMatrix(ta);desiredGlobal[name]=tl;meshBind=tm;
        auto wi=weights.find(name);if(wi!=weights.end())for(size_t k=0;k<wi->second.idx.size();++k)dc->AddControlPointIndex(wi->second.idx[k],wi->second.w[k]);newSkin->AddCluster(dc);
    }
    gm->AddDeformer(newSkin);

    FbxPose*pose=FbxPose::Create(dst,"SourceExactBindPose");pose->SetIsBindPose(true);pose->Add(gmn,FbxMatrix(meshBind),false,false);
    for(auto&kv:bones){auto mi=desiredGlobal.find(kv.first);FbxAMatrix x=mi!=desiredGlobal.end()?mi->second:kv.second->EvaluateGlobalTransform(FBXSDK_TIME_ZERO);pose->Add(kv.second,FbxMatrix(x),false,false);}dst->AddPose(pose);
    dst->GetAnimationEvaluator()->Reset();

    FbxArray<FbxNode*>ma,md,mda,wrong;FbxStatus status;bool valid=pose->IsValidBindPoseVerbose(newRoot,ma,md,mda,wrong,0.0001,&status);
    std::cout<<"hybrid verts="<<gm->GetControlPointsCount()<<" bones="<<bones.size()<<" clusters="<<newSkin->GetClusterCount()<<" weights="<<weights.size()<<" pose="<<pose->GetCount()<<" valid="<<valid<<" wrong="<<wrong.GetCount()<<" status="<<status.GetErrorString()<<"\n";
    for(int i=0;i<ma.GetCount();++i)std::cout<<"missing-ancestor "<<ma[i]->GetName()<<" parent="<<(ma[i]->GetParent()?ma[i]->GetParent()->GetName():"<none>")<<"\n";
    for(int i=0;i<md.GetCount();++i)std::cout<<"missing-deform "<<md[i]->GetName()<<"\n";
    for(int i=0;i<mda.GetCount();++i)std::cout<<"missing-deform-ancestor "<<mda[i]->GetName()<<"\n";
    if(!valid){for(int i=0;i<wrong.GetCount();++i)std::cout<<"wrong "<<wrong[i]->GetName()<<"\n";}

    FbxExporter*ex=FbxExporter::Create(m,"");if(!ex->Initialize(argv[3],-1,m->GetIOSettings())){std::cerr<<"EXPORT INIT: "<<ex->GetStatus().GetErrorString()<<"\n";return 7;}ex->SetFileExportVersion(FBX_2014_00_COMPATIBLE);if(!ex->Export(dst)){std::cerr<<"EXPORT: "<<ex->GetStatus().GetErrorString()<<"\n";return 8;}ex->Destroy();src->Destroy();dst->Destroy();m->Destroy();return valid?0:9;
}
