#ifdef _MSC_VER
#define EXPORT __declspec(dllexport)

#include <Python.h>
PyMODINIT_FUNC PyInit_traceon_backend(void) {
	return NULL;
}

#else
#define EXPORT extern
#endif

#define INLINE EXPORT inline

#if defined(__clang__)
	#define UNROLL _Pragma("clang loop unroll(full)")
#elif defined(__GNUC__) || defined(__GNUG__)
	#define UNROLL _Pragma("GCC unroll 100")
#else
	#define UNROLL
#endif

#ifndef M_PI
    #define M_PI 3.14159265358979323846
#endif



