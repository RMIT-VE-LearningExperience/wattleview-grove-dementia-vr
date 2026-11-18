#include <fbxsdk.h>
#include <algorithm>
#include <cmath>
#include <iomanip>
#include <iostream>
#include <map>
#include <set>
#include <string>
#include <vector>

static void ConvertLikeUE(FbxScene* s)
{
    FbxAxisSystem file = s->GetGlobalSettings().GetAxisSystem();
    FbxAxisSystem ue(FbxAxisSystem::eZAxis, (FbxAxisSystem::EFrontVector)-FbxAxisSystem::eParityOdd, FbxAxisSystem::eRightHanded);
    if (file != ue) {
        FbxRootNodeUtility::RemoveAllFbxRoots(s);
        ue.ConvertScene(s);
    }
    if (s->GetGlobalSettings().GetSystemUnit() != FbxSystemUnit::cm) FbxSystemUnit::cm.ConvertScene(s);
    s->GetAnimationEvaluator()->Reset();
}

static FbxScene* Load(FbxManager* m, const char* path)
{
    FbxImporter* im = FbxImporter::Create(m, "");
    if (!im->Initialize(path, -1, m->GetIOSettings())) { std::cerr << im->GetStatus().GetErrorString() << "\n"; return nullptr; }
    FbxScene* s = FbxScene::Create(m, path);
    if (!im->Import(s)) { std::cerr << im->GetStatus().GetErrorString() << "\n"; return nullptr; }
    im->Destroy(); ConvertLikeUE(s); return s;
}

static double MaxDelta(const FbxAMatrix& a, const FbxAMatrix& b)
{
    double d=0; for(int r=0;r<4;r++) for(int c=0;c<4;c++) d=std::max(d,std::abs(a.Get(r,c)-b.Get(r,c))); return d;
}

static FbxAMatrix PoseMatrix(FbxScene* s, FbxNode* n)
{
    for(int i=0;i<s->GetPoseCount();++i) { FbxPose* p=s->GetPose(i); if(!p->IsBindPose()) continue; int j=p->Find(n); if(j>=0&&!p->IsLocalMatrix(j)){FbxMatrix x=p->GetMatrix(j); return *(FbxAMatrix*)(double*)&x;} }
    return n->EvaluateGlobalTransform(FBXSDK_TIME_ZERO);
}

struct JointData { FbxAMatrix t0, pose, link, mesh; bool hasCluster=false; };
struct FileData { std::string path; FbxAMatrix meshT0, meshPose, geo; std::map<std::string,JointData> joints; int verts=0, clusters=0; };

static FileData Extract(FbxScene* s, const char* path)
{
    FileData d; d.path=path; d.geo.SetIdentity();
    for(int gi=0;gi<s->GetGeometryCount();++gi) {
        FbxGeometry* g=s->GetGeometry(gi); if(!g || !g->GetNode()) continue;
        int ns=g->GetDeformerCount(FbxDeformer::eSkin); if(ns<=0) continue;
        FbxNode* mn=g->GetNode(); d.meshT0=mn->EvaluateGlobalTransform(FBXSDK_TIME_ZERO); d.meshPose=PoseMatrix(s,mn);
        d.geo.SetT(mn->GetGeometricTranslation(FbxNode::eSourcePivot)); d.geo.SetR(mn->GetGeometricRotation(FbxNode::eSourcePivot)); d.geo.SetS(mn->GetGeometricScaling(FbxNode::eSourcePivot));
        if(FbxMesh* m=FbxCast<FbxMesh>(g)) d.verts=m->GetControlPointsCount();
        for(int si=0;si<ns;++si) { FbxSkin* sk=(FbxSkin*)g->GetDeformer(si,FbxDeformer::eSkin); for(int ci=0;ci<sk->GetClusterCount();++ci) {
            FbxCluster* c=sk->GetCluster(ci); if(!c||!c->GetLink())continue; auto& j=d.joints[c->GetLink()->GetName()]; j.hasCluster=true; j.t0=c->GetLink()->EvaluateGlobalTransform(FBXSDK_TIME_ZERO); j.pose=PoseMatrix(s,c->GetLink()); c->GetTransformLinkMatrix(j.link); c->GetTransformMatrix(j.mesh); d.clusters++;
        }}
        break;
    }
    return d;
}

static void PrintM(const char* tag,const FbxAMatrix& m)
{
    FbxVector4 t=m.GetT(),r=m.GetR(),s=m.GetS(); std::cout<<tag<<" T="<<t[0]<<","<<t[1]<<","<<t[2]<<" R="<<r[0]<<","<<r[1]<<","<<r[2]<<" S="<<s[0]<<","<<s[1]<<","<<s[2];
}

int main(int argc,char**argv)
{
    if(argc<3)return 2; FbxManager*m=FbxManager::Create(); m->SetIOSettings(FbxIOSettings::Create(m,IOSROOT)); FbxScene*a=Load(m,argv[1]); FbxScene*b=Load(m,argv[2]); if(!a||!b)return 3;
    FileData A=Extract(a,argv[1]),B=Extract(b,argv[2]); std::cout<<std::setprecision(12);
    std::cout<<"A verts="<<A.verts<<" clusters="<<A.clusters<<" joints="<<A.joints.size()<<" unit="<<a->GetGlobalSettings().GetSystemUnit().GetScaleFactor()<<"\n";
    PrintM("A_meshT0",A.meshT0);std::cout<<"\n";PrintM("A_meshPose",A.meshPose);std::cout<<"\n";PrintM("A_geo",A.geo);std::cout<<"\n";
    std::cout<<"B verts="<<B.verts<<" clusters="<<B.clusters<<" joints="<<B.joints.size()<<" unit="<<b->GetGlobalSettings().GetSystemUnit().GetScaleFactor()<<"\n";
    PrintM("B_meshT0",B.meshT0);std::cout<<"\n";PrintM("B_meshPose",B.meshPose);std::cout<<"\n";PrintM("B_geo",B.geo);std::cout<<"\n";
    std::cout<<"MESH T0delta="<<MaxDelta(A.meshT0,B.meshT0)<<" Posedelta="<<MaxDelta(A.meshPose,B.meshPose)<<" Geodelta="<<MaxDelta(A.geo,B.geo)<<"\n";
    double mt0=0,mpose=0,mlink=0,mmesh=0; std::string nt0,npose,nlink,nmesh; int common=0;
    for(auto&[n,x]:B.joints){auto it=A.joints.find(n);if(it==A.joints.end())continue;auto&y=it->second;common++;double q;
        if((q=MaxDelta(y.t0,x.t0))>mt0){mt0=q;nt0=n;} if((q=MaxDelta(y.pose,x.pose))>mpose){mpose=q;npose=n;} if((q=MaxDelta(y.link,x.link))>mlink){mlink=q;nlink=n;} if((q=MaxDelta(y.mesh,x.mesh))>mmesh){mmesh=q;nmesh=n;}
    }
    std::cout<<"COMMON="<<common<<" MAX T0="<<mt0<<"@"<<nt0<<" POSE="<<mpose<<"@"<<npose<<" LINK="<<mlink<<"@"<<nlink<<" CLUSTER_MESH="<<mmesh<<"@"<<nmesh<<"\n";
    for(const char*n:{"root","pelvis","spine_01","spine_05","neck_01","neck_02","clavicle_r","upperarm_r","thigh_r","foot_r"}){auto ia=A.joints.find(n),ib=B.joints.find(n);if(ia==A.joints.end()||ib==B.joints.end())continue;std::cout<<"JOINT "<<n<<" t0="<<MaxDelta(ia->second.t0,ib->second.t0)<<" pose="<<MaxDelta(ia->second.pose,ib->second.pose)<<" link="<<MaxDelta(ia->second.link,ib->second.link)<<" mesh="<<MaxDelta(ia->second.mesh,ib->second.mesh)<<"\n";PrintM(" A_t0",ia->second.t0);std::cout<<"\n";PrintM(" B_t0",ib->second.t0);std::cout<<"\n";PrintM(" A_link",ia->second.link);std::cout<<"\n";PrintM(" B_link",ib->second.link);std::cout<<"\n";PrintM(" A_mesh",ia->second.mesh);std::cout<<"\n";PrintM(" B_mesh",ib->second.mesh);std::cout<<"\n";}
    a->Destroy();b->Destroy();m->Destroy();return 0;
}
