#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#ifdef RBQ_TEST_DLL
extern "C" __declspec(dllexport) DWORD WINAPI rbqBootstrap() {
    SetEnvironmentVariableW(L"RBQ_LOADER_TEST",L"called");
    return 0;
}
BOOL WINAPI DllMain(HINSTANCE,DWORD,LPVOID) { return TRUE; }
#else
int main() {
    wchar_t value[32]{};
    return GetEnvironmentVariableW(L"RBQ_LOADER_TEST",value,32) && !lstrcmpW(value,L"called") ? 0 : 71;
}
#endif
