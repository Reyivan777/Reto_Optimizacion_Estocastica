// C ABI v1. Buffers and indices are validated by motor_cpp.py before entry.
#include <algorithm>
#include <cmath>
#include <cstdint>
#include <tuple>
#include <vector>
#ifdef _WIN32
#define API extern "C" __declspec(dllexport)
#else
#define API extern "C" __attribute__((visibility("default")))
#endif
using I = int64_t;
API int reforestacion_abi() { return 1; }

API int seleccionar(I n, I cantidad, const double* xy, const double* inicial, I* salida) noexcept {
    try {
        std::vector<double> cerca(inicial, inicial+n);
        for (I k=0;k<cantidad;++k) {
            I mejor=0;
            for(I i=1;i<n;++i) if(cerca[i]>cerca[mejor]) mejor=i;
            salida[k]=mejor;
            for(I i=0;i<n;++i) {
                double dx=xy[2*i]-xy[2*mejor], dy=xy[2*i+1]-xy[2*mejor+1];
                cerca[i]=std::min(cerca[i],std::sqrt(dx*dx+dy*dy));
            }
            cerca[mejor]=-INFINITY; // Previously selected entries stay -infinity.
        }
        return 0;
    } catch (...) { return -1; }
}

API int asignar(I n, I nf, I K, const I* off, const I* adj, const double* w,
                const I* fijas, const I* cuotas, const double* C, const double* grado, I* y) noexcept {
    try {
        std::vector<I> resto(cuotas,cuotas+K), sat(n,0);
        std::vector<unsigned char> visto(n*K,0);
        std::vector<double> coste(n*K,0);
        for(I i=0;i<n;++i) {
            y[i]=i<nf?fijas[i]:-1;
        }
        auto actualizar = [&](I i,I s) {
            for(I e=off[i];e<off[i+1];++e) {
                I j=adj[e];
                if(y[j]>=0) continue;
                if(!visto[j*K+s]) { visto[j*K+s]=1; ++sat[j]; }
                for(I t=0;t<K;++t) coste[j*K+t]+=w[e]*C[t*K+s];
            }
        };
        for(I i=0;i<nf;++i) actualizar(i,y[i]);
        for(I k=nf;k<n;++k) {
            I i=-1;
            for(I j=nf;j<n;++j) if(y[j]<0 && (i<0 ||
                std::make_tuple(-sat[j],-grado[j],j)<std::make_tuple(-sat[i],-grado[i],i))) i=j;
            I s=-1;
            for(I t=0;t<K;++t) if(resto[t]>0 && (s<0 ||
                std::make_tuple(coste[i*K+t],-resto[t],t)<std::make_tuple(coste[i*K+s],-resto[s],s))) s=t;
            if(i<0 || s<0) return -2;
            y[i]=s; --resto[s]; actualizar(i,s);
        }
        return 0;
    } catch (...) { return -1; }
}

API int intercambiar(I K, I intentos, const I* off, const I* adj, const double* w,
                     const double* C, const I* propuestas, I* y, I* pasos,
                     double* deltas, I* contadores) noexcept {
    // No allocation; caller owns outputs. Accumulate each incident sum separately
    // to preserve Python's delta_intercambio evaluation order.
    I iguales=0, aceptados=0;
    for(I k=0;k<intentos;++k) {
        I a=propuestas[2*k], b=propuestas[2*k+1], sa=y[a], sb=y[b];
        if(sa==sb) { ++iguales; continue; }
        double da=0,db=0;
        for(I e=off[a];e<off[a+1];++e) if(adj[e]!=b)
            da+=w[e]*(C[sb*K+y[adj[e]]]-C[sa*K+y[adj[e]]]);
        for(I e=off[b];e<off[b+1];++e) if(adj[e]!=a)
            db+=w[e]*(C[sa*K+y[adj[e]]]-C[sb*K+y[adj[e]]]);
        double delta=da+db;
        if(delta < -1e-10) {
            std::swap(y[a],y[b]); pasos[aceptados]=k+1; deltas[aceptados]=delta; ++aceptados;
        }
    }
    contadores[0]=iguales; contadores[1]=aceptados;
    return 0;
}
