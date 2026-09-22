// Temporary, explicitly loaded diagnostic; never part of the installed patch.
#include <windows.h>
#include <cstdint>
static HMODULE module;
static HHOOK calls, queued;
static HWND prefs, combo, popup, panel;
static constexpr UINT Control = WM_APP + 0x677;
struct Event { DWORD kind, message; uintptr_t window, w, l, focus, capture; };
extern "C" __declspec(dllexport) Event probeEvents[512]{};
extern "C" __declspec(dllexport) DWORD probeCount=0, probeForward=0;
static bool relevant(UINT m) {
    return (m>=WM_MOUSEFIRST && m<=WM_MOUSELAST) || m==WM_SETFOCUS || m==WM_KILLFOCUS ||
           m==WM_CANCELMODE || m==WM_CAPTURECHANGED || m==WM_COMMAND || m==WM_MOUSEACTIVATE;
}
static void record(DWORD kind, HWND h, UINT m, WPARAM w, LPARAM l) {
    if ((h!=prefs && h!=combo && h!=popup && h!=panel) || !relevant(m)) return;
    if (probeCount<512) probeEvents[probeCount++]={kind,m,reinterpret_cast<uintptr_t>(h),w,
        static_cast<uintptr_t>(l),reinterpret_cast<uintptr_t>(GetFocus()),reinterpret_cast<uintptr_t>(GetCapture())};
}
static LRESULT CALLBACK onQueue(int code, WPARAM w, LPARAM l) {
    const auto result=CallNextHookEx(nullptr,code,w,l);
    if (code>=0 && w==PM_REMOVE) {
        auto m=reinterpret_cast<MSG*>(l);
        record(1,m->hwnd,m->message,m->wParam,m->lParam);
        if (probeForward && m->hwnd==popup && m->message>=WM_MOUSEFIRST && m->message<=WM_MOUSELAST &&
            IsWindowVisible(combo) && IsWindowVisible(popup) && GetActiveWindow()==prefs) {
            const MSG input=*m;
            m->hwnd=nullptr; m->message=WM_NULL; m->wParam=0; m->lParam=0;
            SendMessageW(input.hwnd,input.message,input.wParam,input.lParam);
        }
    }
    return result;
}
static LRESULT CALLBACK onCall(int code, WPARAM w, LPARAM l) {
    if (code>=0) {
        auto m=reinterpret_cast<CWPSTRUCT*>(l);
        if (m->hwnd==prefs && m->message==Control) {
            if (m->wParam==1) {
                auto old=calls;
                calls=SetWindowsHookExW(WH_CALLWNDPROC,onCall,module,GetCurrentThreadId());
                queued=SetWindowsHookExW(WH_GETMESSAGE,onQueue,module,GetCurrentThreadId());
                UnhookWindowsHookEx(old);
            } else if (m->wParam==2) {
                probeCount=0; probeForward=static_cast<DWORD>(m->lParam);
            } else if (m->wParam==3) {
                UnhookWindowsHookEx(queued); UnhookWindowsHookEx(calls); queued=nullptr; calls=nullptr;
            }
        } else record(2,m->hwnd,m->message,m->wParam,m->lParam);
    }
    return CallNextHookEx(nullptr,code,w,l);
}
extern "C" __declspec(dllexport) DWORD WINAPI probeStart(void* value) {
    prefs=*static_cast<HWND*>(value);
    panel=static_cast<HWND>(GetPropW(prefs,L"RBQ.TempoPanel"));
    combo=GetDlgItem(panel,1001);
    COMBOBOXINFO info{sizeof(info)};
    if (!GetComboBoxInfo(combo,&info)) return 1;
    popup=info.hwndList;
    GetModuleHandleExW(GET_MODULE_HANDLE_EX_FLAG_FROM_ADDRESS,reinterpret_cast<LPCWSTR>(probeStart),&module);
    calls=SetWindowsHookExW(WH_CALLWNDPROC,onCall,module,GetWindowThreadProcessId(prefs,nullptr));
    if (!calls) return 2;
    SendMessageW(prefs,Control,1,0);
    return queued ? 0 : 3;
}
