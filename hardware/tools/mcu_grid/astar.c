#include <stdlib.h>
#include <stdint.h>
#include <math.h>
#include <string.h>
typedef struct {float f; int32_t id;} node;
static node *heap; static int hn;
static void push(float f,int id){int i=hn++;heap[i].f=f;heap[i].id=id;while(i>0){int p=(i-1)/2;if(heap[p].f<=heap[i].f)break;node t=heap[p];heap[p]=heap[i];heap[i]=t;i=p;}}
static node pop(){node r=heap[0];heap[0]=heap[--hn];int i=0;for(;;){int l=2*i+1,rr=l+1,m=i;if(l<hn&&heap[l].f<heap[m].f)m=l;if(rr<hn&&heap[rr].f<heap[m].f)m=rr;if(m==i)break;node t=heap[m];heap[m]=heap[i];heap[i]=t;i=m;}return r;}
int route(int L,int H,int W,const uint8_t*legal,const uint8_t*via,const uint8_t*start,const uint8_t*goal,float viacost,const float*layercost,int32_t*out,int maxout){
  long N=(long)L*H*W; float*g=malloc(N*sizeof(float)); int32_t*par=malloc(N*sizeof(int32_t));
  heap=malloc(sizeof(node)*N*2); hn=0;
  for(long i=0;i<N;i++){g[i]=1e30f;par[i]=-1;}
  for(long i=0;i<N;i++) if(start[i]){g[i]=0;push(0,i);}
  int dx[8]={1,-1,0,0,1,1,-1,-1},dy[8]={0,0,1,-1,1,-1,1,-1}; float dc[8]={1,1,1,1,1.4142f,1.4142f,1.4142f,1.4142f};
  int found=-1;
  while(hn){node n=pop();int id=n.id; if(n.f>g[id])continue; if(goal[id]){found=id;break;}
    int l=id/(H*W), r=id%(H*W), y=r/W, x=r%W;
    for(int k=0;k<8;k++){int nx=x+dx[k],ny=y+dy[k]; if(nx<0||ny<0||nx>=W||ny>=H)continue; int nid=l*H*W+ny*W+nx;
      if(!legal[nid]&&!goal[nid]&&!start[nid])continue; float ng=g[id]+dc[k]*layercost[l]; if(ng<g[nid]){g[nid]=ng;par[nid]=id;push(ng,nid);}}
    if(via[r]) for(int l2=0;l2<L;l2++){ if(l2==l)continue; int nid=l2*H*W+r; float ng=g[id]+viacost; if(ng<g[nid]){g[nid]=ng;par[nid]=id;push(ng,nid);}}
  }
  int n=0; if(found>=0){int c=found; while(c>=0&&n<maxout){out[n++]=c; if(start[c])break; c=par[c];}}
  free(g);free(par);free(heap); return found>=0?n:-1;
}
