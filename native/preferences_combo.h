// The JUCE modal message loop rejects the native ComboLBox popup because it
// is not a child HWND of Preferences. Forward only this combo's mouse input
// on its own GUI thread before that filter cancels the dropdown.
static HWND inputCombo = nullptr, inputPopup = nullptr;
static HHOOK comboInputHook = nullptr;
extern "C" __declspec(dllexport) DWORD rbqComboTelemetry[4]{};

static LRESULT CALLBACK comboInput(int code, WPARAM w, LPARAM l) {
    const LRESULT result=CallNextHookEx(nullptr,code,w,l);
    if (code<0 || w!=PM_REMOVE || !inputCombo || !inputPopup) return result;
    auto message=reinterpret_cast<MSG*>(l);
    if (message->hwnd!=inputPopup || message->message<WM_MOUSEFIRST || message->message>WM_MOUSELAST)
        return result;
    const HWND root=GetAncestor(inputCombo,GA_ROOT);
    if (GetActiveWindow()!=root || !IsWindowEnabled(root) || GetFocus()!=inputCombo ||
        !IsWindowVisible(inputCombo) || !IsWindowVisible(inputPopup)) return result;
    // Consume once, before synchronous dispatch can run a nested message loop.
    // Preserve the popup's coordinates and native selection/cancellation logic.
    const MSG input=*message;
    message->hwnd=nullptr; message->message=WM_NULL; message->wParam=0; message->lParam=0;
    ++rbqComboTelemetry[0];
    SendMessageW(input.hwnd,input.message,input.wParam,input.lParam);
    return result;
}
static bool installComboInput(HWND combo) {
    if (!combo || comboInputHook) return false;
    COMBOBOXINFO info{sizeof(info)};
    if (!GetComboBoxInfo(combo,&info)) { rbqComboTelemetry[3]=GetLastError(); return false; }
    inputCombo=combo; inputPopup=info.hwndList;
    comboInputHook=SetWindowsHookExW(WH_GETMESSAGE,comboInput,extensionModule,GetCurrentThreadId());
    if (!comboInputHook) {
        rbqComboTelemetry[3]=GetLastError(); inputCombo=nullptr; inputPopup=nullptr; return false;
    }
    ++rbqComboTelemetry[1];
    return true;
}
static void removeComboInput(HWND combo) {
    if (combo!=inputCombo) return;
    inputCombo=nullptr; inputPopup=nullptr;
    if (comboInputHook) {
        UnhookWindowsHookEx(comboInputHook); comboInputHook=nullptr; ++rbqComboTelemetry[2];
    }
}
