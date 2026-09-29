// The JUCE modal message loop rejects the native ComboLBox popup because it
// is not a child HWND of Preferences. Forward only our combos' mouse input
// on its own GUI thread before that filter cancels the dropdown.
struct ComboInput { HWND combo=nullptr, popup=nullptr; };
static ComboInput inputCombos[3];
static HHOOK comboInputHook = nullptr;
extern "C" __declspec(dllexport) DWORD rbqComboTelemetry[4]{};

static LRESULT CALLBACK comboInput(int code, WPARAM w, LPARAM l) {
    const LRESULT result=CallNextHookEx(nullptr,code,w,l);
    if (code<0 || w!=PM_REMOVE) return result;
    auto message=reinterpret_cast<MSG*>(l);
    if (message->message<WM_MOUSEFIRST || message->message>WM_MOUSELAST) return result;
    HWND inputCombo=nullptr,inputPopup=nullptr;
    for (const auto& input : inputCombos) {
        if (input.combo && message->hwnd==input.popup) { inputCombo=input.combo; inputPopup=input.popup; break; }
    }
    if (!inputCombo) return result;
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
    if (!combo) return false;
    ComboInput* available=nullptr;
    for (auto& input : inputCombos) {
        if (input.combo==combo) return true;
        if (!input.combo && !available) available=&input;
    }
    if (!available) return false;
    COMBOBOXINFO info{sizeof(info)};
    if (!GetComboBoxInfo(combo,&info)) { rbqComboTelemetry[3]=GetLastError(); return false; }
    if (!comboInputHook) {
        comboInputHook=SetWindowsHookExW(WH_GETMESSAGE,comboInput,extensionModule,GetCurrentThreadId());
        if (!comboInputHook) { rbqComboTelemetry[3]=GetLastError(); return false; }
        ++rbqComboTelemetry[1];
    }
    *available={combo,info.hwndList};
    return true;
}
static void removeComboInput(HWND combo) {
    bool remaining=false;
    for (auto& input : inputCombos) {
        if (input.combo==combo) input={};
        remaining=remaining || input.combo;
    }
    if (remaining) return;
    if (comboInputHook) {
        UnhookWindowsHookEx(comboInputHook); comboInputHook=nullptr; ++rbqComboTelemetry[2];
    }
}
