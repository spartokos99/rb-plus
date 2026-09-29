// Loaded by the patched PE entry point, after normal DLL initialization.
#define RBQ_AUTOSTART
#include "tempo_hook.cpp"
#include <commctrl.h>
#include <cwchar>
#include <new>
#pragma comment(lib, "user32.lib")
#pragma comment(lib, "gdi32.lib")
#pragma comment(lib, "comctl32.lib")

static HMODULE extensionModule = nullptr;
static HHOOK windowHook = nullptr;
static wchar_t configPath[32768]{};
static constexpr UINT AttachMessage = WM_APP + 0x651;
static constexpr UINT ReapplyMessage = WM_APP + 0x652;
static constexpr wchar_t PanelClass[] = L"RBQ.TempoPreferences.4";
static constexpr wchar_t PanelProperty[] = L"RBQ.TempoPanel";
static HBRUSH panelBrush = nullptr;
static DWORD guiThread = 0;
static DWORD hookOwnerThread = 0;
static SRWLOCK settingsLock = SRWLOCK_INIT;
static std::atomic<bool> booted{false};
extern "C" __declspec(dllexport) DWORD rbqUiTelemetry[8]{};
struct Ui { HWND combo = nullptr, note = nullptr, wave = nullptr, decks = nullptr, layoutNote = nullptr; HFONT font = nullptr; };
#include "preferences_combo.h"
#include "layout_extension.h"

static void reapplyKnownDecks() {
    // Run only on the original GUI thread. Use Rekordbox's existing request
    // function, which locks or queues to the player thread as appropriate.
    using Request = void(__fastcall*)(void*, float);
    auto request = reinterpret_cast<Request>(base + 0x2c07ef0);
    for (auto& slot : bank) {
        const Ptr owner = slot.owner.load();
        Context ctx{};
        if (!owner || !context(owner, &ctx)) continue;
        if (slot.lastGrid.load(std::memory_order_acquire) != ctx.grid) continue;
        request(reinterpret_cast<void*>(owner), slot.lastInput.load());
    }
}

static bool saveMode(uint32_t selected) {
    const wchar_t* value = selected == 1 ? L"0.1" : selected == 2 ? L"1" : L"default";
    return WritePrivateProfileStringW(L"Tempo", L"Step", value, configPath) != FALSE;
}
static uint32_t loadMode() {
    wchar_t value[32]{};
    GetPrivateProfileStringW(L"Tempo", L"Step", L"default", value, 32, configPath);
    return !wcscmp(value,L"0.1") ? 1 : !wcscmp(value,L"1") ? 2 : 0;
}
static bool setPreference(uint32_t selected) {
    AcquireSRWLockExclusive(&settingsLock);
    Config cfg{Magic,selected,{}};
    const bool success=saveMode(selected) && rbqConfigure(&cfg)==0;
    ReleaseSRWLockExclusive(&settingsLock);
    return success;
}
static int scale(HWND h, int value) { return MulDiv(value, static_cast<int>(GetDpiForWindow(h)), 96); }

static LRESULT CALLBACK panelProc(HWND h, UINT message, WPARAM w, LPARAM l) {
    auto ui = reinterpret_cast<Ui*>(GetWindowLongPtrW(h, GWLP_USERDATA));
    if (message == WM_NCCREATE) {
        rbqUiTelemetry[4]++;
        ui = new (std::nothrow) Ui{};
        if (!ui) return FALSE;
        SetWindowLongPtrW(h, GWLP_USERDATA, reinterpret_cast<LONG_PTR>(ui));
    }
    if (message == WM_CREATE && ui) {
        rbqUiTelemetry[5]++;
        ui->font = CreateFontW(-scale(h,13),0,0,0,FW_NORMAL,FALSE,FALSE,FALSE,DEFAULT_CHARSET,
                              OUT_DEFAULT_PRECIS,CLIP_DEFAULT_PRECIS,CLEARTYPE_QUALITY,DEFAULT_PITCH,L"Segoe UI");
        HWND label = CreateWindowExW(0,L"STATIC",L"BPM / Tempo Step",WS_CHILD|WS_VISIBLE,
                                     scale(h,20),scale(h,32),scale(h,210),scale(h,24),h,nullptr,extensionModule,nullptr);
        ui->combo = CreateWindowExW(0,L"COMBOBOX",L"BPM / Tempo Step",WS_CHILD|WS_VISIBLE|WS_TABSTOP|CBS_DROPDOWNLIST|WS_VSCROLL,
                                    scale(h,240),scale(h,30),scale(h,220),scale(h,110),h,reinterpret_cast<HMENU>(1001),extensionModule,nullptr);
        SendMessageW(ui->combo,CB_ADDSTRING,0,reinterpret_cast<LPARAM>(L"Default / 0.01 BPM"));
        SendMessageW(ui->combo,CB_ADDSTRING,0,reinterpret_cast<LPARAM>(L"0.1 BPM"));
        SendMessageW(ui->combo,CB_ADDSTRING,0,reinterpret_cast<LPARAM>(L"1 BPM (integer)"));
        SendMessageW(ui->combo,CB_SETCURSEL,mode.load(),0);
        ui->note = CreateWindowExW(0,L"STATIC",L"Quantizes the live tempo of Performance decks.\nOriginal BPM and beatgrids remain unchanged.",WS_CHILD|WS_VISIBLE,
                                   scale(h,20),scale(h,80),scale(h,540),scale(h,56),h,nullptr,extensionModule,nullptr);
        for (HWND child : {label,ui->combo,ui->note}) SendMessageW(child,WM_SETFONT,reinterpret_cast<WPARAM>(ui->font),TRUE);
        for (int row=0;row<2;++row) {
            const wchar_t* title=row==0 ? L"Waveforms (top to bottom)" : L"Decks (top / bottom)";
            HWND caption=CreateWindowExW(0,L"STATIC",title,WS_CHILD|WS_VISIBLE,
                scale(h,20),scale(h,152+row*48),scale(h,215),scale(h,24),h,nullptr,extensionModule,nullptr);
            HWND combo=CreateWindowExW(0,L"COMBOBOX",title,WS_CHILD|WS_VISIBLE|WS_TABSTOP|CBS_DROPDOWNLIST|WS_VSCROLL,
                scale(h,240),scale(h,150+row*48),scale(h,280),scale(h,260),h,
                reinterpret_cast<HMENU>(static_cast<INT_PTR>(1002+row)),extensionModule,nullptr);
            (row==0 ? ui->wave : ui->decks)=combo;
            SendMessageW(combo,CB_ADDSTRING,0,reinterpret_cast<LPARAM>(L"Default (Rekordbox)"));
            for (unsigned i=1;i<=24;++i) {
                const auto order=rbq::layoutOrder(i);
                wchar_t text[64]{};
                swprintf_s(text,row==0 ? L"%d - %d - %d - %d" : L"%d - %d  /  %d - %d",
                    order[0]+1,order[1]+1,order[2]+1,order[3]+1);
                SendMessageW(combo,CB_ADDSTRING,0,reinterpret_cast<LPARAM>(text));
            }
            SendMessageW(combo,CB_SETCURSEL,row==0 ? waveOrder : deckOrder,0);
            SendMessageW(combo,CB_SETMINVISIBLE,10,0);
            for (HWND child : {caption,combo}) SendMessageW(child,WM_SETFONT,reinterpret_cast<WPARAM>(ui->font),TRUE);
            EnableWindow(combo,layoutInstalled);
        }
        ui->layoutNote=CreateWindowExW(0,L"STATIC",layoutInstalled ?
            L"Performance: 4Deck Horizontal only. Both orders are independent.\nDecks: top left - right / bottom left - right.\nDefault restores the Rekordbox arrangement." :
            L"Layout customization is unavailable for this application build.",WS_CHILD|WS_VISIBLE,
            scale(h,20),scale(h,248),scale(h,550),scale(h,72),h,nullptr,extensionModule,nullptr);
        SendMessageW(ui->layoutNote,WM_SETFONT,reinterpret_cast<WPARAM>(ui->font),TRUE);
        if (!installComboInput(ui->combo) || !installComboInput(ui->wave) || !installComboInput(ui->decks))
            SetWindowTextW(ui->note,L"Mouse input could not be initialized.\nPlease close and reopen Preferences.");
        SetTimer(h,1,400,nullptr);
        return 0;
    }
    if (message == WM_TIMER && ui) {
        // Keep the embedded selection consistent with optional diagnostic tools.
        if (!SendMessageW(ui->combo,CB_GETDROPPEDSTATE,0,0) &&
            SendMessageW(ui->combo,CB_GETCURSEL,0,0)!=static_cast<LRESULT>(mode.load()))
            SendMessageW(ui->combo,CB_SETCURSEL,mode.load(),0);
        return 0;
    }
    if (message == WM_COMMAND && ui && LOWORD(w) == 1001 && HIWORD(w) == CBN_SELCHANGE) {
        const LRESULT selected = SendMessageW(ui->combo,CB_GETCURSEL,0,0);
        if (selected >= 0 && selected <= 2) {
            if (!setPreference(static_cast<uint32_t>(selected))) {
                SendMessageW(ui->combo,CB_SETCURSEL,mode.load(),0);
                MessageBoxW(h,L"Could not save the selection to rb-bpm.ini.",L"BPM / Tempo Step",MB_OK|MB_ICONERROR);
                return 0;
            }
            reapplyKnownDecks();
            SetWindowTextW(ui->note,L"Saved. Applies to the live tempo of Performance decks.\nOriginal BPM and beatgrids remain unchanged.");
        }
        return 0;
    }
    if (message==WM_COMMAND && ui && (LOWORD(w)==1002 || LOWORD(w)==1003) && HIWORD(w)==CBN_SELCHANGE) {
        const bool waves=LOWORD(w)==1002;
        const HWND combo=waves ? ui->wave : ui->decks;
        const LRESULT selected=SendMessageW(combo,CB_GETCURSEL,0,0);
        if (selected>=0 && selected<=24 && !saveLayoutOrder(waves,static_cast<unsigned>(selected))) {
            SendMessageW(combo,CB_SETCURSEL,waves ? waveOrder : deckOrder,0);
            MessageBoxW(h,L"Could not save the selection to rb-bpm.ini.",L"RB PLUS",MB_OK|MB_ICONERROR);
        }
        return 0;
    }
    if ((message == WM_CTLCOLORSTATIC || message == WM_CTLCOLORLISTBOX) && ui) {
        SetTextColor(reinterpret_cast<HDC>(w),RGB(205,205,205));
        SetBkColor(reinterpret_cast<HDC>(w),RGB(32,32,32));
        return reinterpret_cast<LRESULT>(panelBrush);
    }
    if (message == WM_NCDESTROY && ui) {
        removeComboInput(ui->combo);
        removeComboInput(ui->wave);
        removeComboInput(ui->decks);
        KillTimer(h,1);
        DeleteObject(ui->font);
        SetWindowLongPtrW(h,GWLP_USERDATA,0);
        delete ui;
    }
    return DefWindowProcW(h,message,w,l);
}

#include "preferences_tabs.h"
static LRESULT CALLBACK watchWindows(int code, WPARAM w, LPARAM l) {
    rbqUiTelemetry[6]++;
    if (code >= 0 && hookOwnerThread != guiThread && GetCurrentThreadId() == guiThread) {
        // A diagnostic remote bootstrap thread is short-lived. Transfer hook
        // ownership to the real GUI thread before that bootstrap thread exits.
        HHOOK replacement=SetWindowsHookExW(WH_CALLWNDPROC,watchWindows,extensionModule,guiThread);
        if (replacement) {
            HHOOK old=windowHook; windowHook=replacement; hookOwnerThread=guiThread;
            UnhookWindowsHookEx(old);
        }
    }
    if (code >= 0) {
        const auto data = reinterpret_cast<const CWPSTRUCT*>(l);
        if (data->message == ReapplyMessage) reapplyKnownDecks();
        if (data->message == AttachMessage || data->message == WM_SHOWWINDOW || data->message == WM_ACTIVATE)
            attachPreferences(data->hwnd);
    }
    return CallNextHookEx(windowHook,code,w,l);
}
static BOOL CALLBACK notifyExisting(HWND h, LPARAM) {
    DWORD_PTR result=0;
    SendMessageTimeoutW(h,AttachMessage,0,0,SMTO_ABORTIFHUNG,3000,&result);
    return TRUE;
}

extern "C" __declspec(dllexport) DWORD WINAPI rbqBootstrapOnThread(void* value) {
    if (booted.exchange(true)) return 0;
    if (!GetModuleHandleExW(GET_MODULE_HANDLE_EX_FLAG_FROM_ADDRESS|GET_MODULE_HANDLE_EX_FLAG_PIN,
                            reinterpret_cast<LPCWSTR>(&rbqBootstrapOnThread),&extensionModule)) return 20;
    const DWORD length = GetModuleFileNameW(extensionModule,configPath,32768);
    if (!length || length >= 32750) return 21;
    wchar_t* slash = wcsrchr(configPath,L'\\');
    if (!slash) return 22;
    wcscpy_s(slash+1,static_cast<size_t>(32768-(slash+1-configPath)),L"rb-bpm.ini");
    Config cfg{Magic,0,{}};
    const DWORD result = rbqInstall(&cfg);
    if (result) return result;
    autoEnroll.store(true);
    cfg.mode = loadMode();
    rbqConfigure(&cfg);
    guiThread = value ? *static_cast<const DWORD*>(value) : GetCurrentThreadId();
    loadLayoutOrders();
    installLayout();
    panelBrush = CreateSolidBrush(RGB(32,32,32));
    WNDCLASSW cls{};
    cls.hInstance=extensionModule; cls.lpfnWndProc=panelProc; cls.lpszClassName=PanelClass;
    cls.hCursor=LoadCursorW(nullptr,MAKEINTRESOURCEW(32512)); cls.hbrBackground=panelBrush;
    if (!RegisterClassW(&cls) && GetLastError()!=ERROR_CLASS_ALREADY_EXISTS) return 23;
    hookOwnerThread=GetCurrentThreadId();
    windowHook=SetWindowsHookExW(WH_CALLWNDPROC,watchWindows,extensionModule,guiThread);
    if (!windowHook) return 24;
    EnumThreadWindows(guiThread,notifyExisting,0);
    return 0;
}
extern "C" __declspec(dllexport) DWORD WINAPI rbqBootstrap() { return rbqBootstrapOnThread(nullptr); }
static BOOL CALLBACK notifyReapply(HWND h, LPARAM) {
    DWORD_PTR result=0;
    SendMessageTimeoutW(h,ReapplyMessage,0,0,SMTO_ABORTIFHUNG,3000,&result);
    return FALSE;
}
extern "C" __declspec(dllexport) DWORD WINAPI rbqSetPreference(void* value) {
    if (!value || *static_cast<const DWORD*>(value)>2) return 1;
    if (!setPreference(*static_cast<const DWORD*>(value))) return 25;
    EnumThreadWindows(guiThread,notifyReapply,0);
    return 0;
}
extern "C" __declspec(dllexport) DWORD WINAPI rbqDetachUi(void*) {
    if (windowHook) { UnhookWindowsHookEx(windowHook); windowHook=nullptr; }
    return rbqStop(nullptr);
}
