// Extensions navigation bridge. All UI Automation calls run on a dedicated
// MTA thread; the GUI thread only applies snapshots and owns native controls.
#include <objbase.h>
#include <oleauto.h>
#include <UIAutomation.h>
#include <wrl/client.h>
#pragma comment(lib, "ole32.lib")
#pragma comment(lib, "oleaut32.lib")
#pragma comment(lib, "uiautomationcore.lib")
#pragma comment(lib, "uuid.lib")
using Microsoft::WRL::ComPtr;

static constexpr UINT TabsSnapshotMessage = WM_APP + 0x653;
static constexpr wchar_t PrefsProperty[] = L"RBQ.ExtensionsUi";
static constexpr wchar_t TabsProperty[] = L"RBQ.ExtensionsTabs";
static constexpr const wchar_t* TabNames[] = {L"STEMS",L"Video",L"Lighting",L"RB PLUS"};
struct PreferencesUi {
    HWND panel = nullptr, tabs = nullptr;
    HFONT font = nullptr;
    bool extensions = false, plus = false;
    int nativeTab = 0;
};
struct TabsSnapshot { HWND window; unsigned generation, revision; bool extensions; int nativeTab; };
static std::atomic<HWND> preferencesWindow{nullptr};
static std::atomic<unsigned> preferencesGeneration{0}, preferencesRevision{0};
static std::atomic<int> requestedNativeTab{-1};
static HANDLE navigationWake = nullptr;
static SRWLOCK snapshotLock = SRWLOCK_INIT;
static TabsSnapshot navigationSnapshot{};
extern "C" __declspec(dllexport) DWORD rbqTabsTelemetry[8]{};

static ComPtr<IUIAutomationElement> findButton(IUIAutomation* automation, IUIAutomationElement* root,
                                              const wchar_t* name) {
    if (!automation || !root) return {};
    VARIANT value{}; value.vt=VT_BSTR; value.bstrVal=SysAllocString(name);
    ComPtr<IUIAutomationCondition> named, button, both;
    HRESULT hr=automation->CreatePropertyCondition(UIA_NamePropertyId,value,&named);
    VariantClear(&value);
    value.vt=VT_I4; value.lVal=UIA_ButtonControlTypeId;
    if (SUCCEEDED(hr)) hr=automation->CreatePropertyCondition(UIA_ControlTypePropertyId,value,&button);
    if (SUCCEEDED(hr) && named && button) hr=automation->CreateAndCondition(named.Get(),button.Get(),&both);
    ComPtr<IUIAutomationElement> found;
    if (SUCCEEDED(hr) && both) root->FindFirst(TreeScope_Descendants,both.Get(),&found);
    return found;
}
static bool readToggle(IUIAutomationElement* element, bool* on) {
    if (!element) return false;
    ComPtr<IUIAutomationTogglePattern> pattern;
    ToggleState selected=ToggleState_Off;
    const HRESULT result=element->GetCurrentPatternAs(UIA_TogglePatternId,IID_PPV_ARGS(&pattern));
    // A disappearing JUCE provider can return S_OK with a null interface.
    // Confirmed in the crash dump at the former unchecked pattern dereference.
    if (SUCCEEDED(result) && !pattern) ++rbqTabsTelemetry[7];
    const bool valid=SUCCEEDED(result) && pattern && SUCCEEDED(pattern->get_CurrentToggleState(&selected));
    *on=valid && selected==ToggleState_On;
    return valid;
}
static DWORD WINAPI navigationWorker(void*) {
    const HRESULT initialized=CoInitializeEx(nullptr,COINIT_MULTITHREADED);
    if (FAILED(initialized)) { rbqTabsTelemetry[5]=initialized; return 1; }
    ComPtr<IUIAutomation> automation;
    const HRESULT created=CoCreateInstance(CLSID_CUIAutomation,nullptr,CLSCTX_INPROC_SERVER,IID_PPV_ARGS(&automation));
    if (FAILED(created) || !automation) { rbqTabsTelemetry[5]=FAILED(created) ? created : E_NOINTERFACE; CoUninitialize(); return 2; }
    HWND cachedWindow=nullptr;
    unsigned cachedGeneration=0;
    ComPtr<IUIAutomationElement> root;
    for (;;) {
        const HWND beforeWait=preferencesWindow.load();
        // WM_SHOWWINDOW precedes the visible style change. Do not sleep forever
        // after consuming that notification while the new dialog is still hidden.
        WaitForSingleObject(navigationWake,beforeWait ? 200 : INFINITE);
        const HWND window=preferencesWindow.load();
        if (!window || !IsWindowVisible(window)) continue;
        const unsigned generation=preferencesGeneration.load(), revision=preferencesRevision.load();
        TabsSnapshot snapshot{window,generation,revision,false,0};
        if (window!=cachedWindow || generation!=cachedGeneration) {
            root.Reset();
            cachedWindow=window; cachedGeneration=generation;
        }
        if (!root) automation->ElementFromHandle(window,&root);
        if (root) {
            // JUCE replaces category/button providers without always reporting
            // old references as unavailable. Resolve these controls afresh.
            auto extensions=findButton(automation.Get(),root.Get(),L"Extensions");
            if (!extensions) extensions=findButton(automation.Get(),root.Get(),L"Erweiterungen");
            readToggle(extensions.Get(),&snapshot.extensions);
            const int request=requestedNativeTab.exchange(-1);
            if (snapshot.extensions) {
                for (int i=0;i<3;++i) {
                    auto tab=findButton(automation.Get(),root.Get(),TabNames[i]);
                    if (request==i && tab && preferencesWindow.load()==window &&
                        preferencesGeneration.load()==generation) {
                        ComPtr<IUIAutomationInvokePattern> invoke;
                        HRESULT hr=tab->GetCurrentPatternAs(UIA_InvokePatternId,IID_PPV_ARGS(&invoke));
                        if (SUCCEEDED(hr)) hr=invoke ? invoke->Invoke() : E_NOINTERFACE;
                        rbqTabsTelemetry[6]=hr;
                    }
                    bool on=false;
                    readToggle(tab.Get(),&on);
                    if (on) snapshot.nativeTab=i;
                }
            }
        } else ++rbqTabsTelemetry[1];
        if (preferencesWindow.load()!=window || preferencesGeneration.load()!=generation) continue;
        AcquireSRWLockExclusive(&snapshotLock);
        navigationSnapshot=snapshot;
        ReleaseSRWLockExclusive(&snapshotLock);
        ++rbqTabsTelemetry[0]; rbqTabsTelemetry[2]=snapshot.extensions;
        rbqTabsTelemetry[3]=snapshot.nativeTab;
        PostMessageW(window,TabsSnapshotMessage,0,0);
    }
}

static PreferencesUi* preferencesUi(HWND window) {
    return reinterpret_cast<PreferencesUi*>(GetPropW(window,PrefsProperty));
}
static void layoutExtensions(HWND parent, PreferencesUi* ui) {
    RECT rect{}; GetClientRect(parent,&rect);
    const int left=scale(parent,164), top=scale(parent,38), margin=scale(parent,4);
    const bool visible=ui->extensions && rect.right>=scale(parent,500) && rect.bottom>top+scale(parent,180);
    SetWindowPos(ui->tabs,HWND_TOP,left,margin,rect.right-left-margin,scale(parent,30),
                 SWP_NOACTIVATE|(visible ? SWP_SHOWWINDOW : SWP_HIDEWINDOW));
    SetWindowPos(ui->panel,HWND_TOP,left,top,rect.right-left-margin,rect.bottom-top-margin,
                 SWP_NOACTIVATE|(visible && ui->plus ? SWP_SHOWWINDOW : SWP_HIDEWINDOW));
    const int selected=ui->plus ? 3 : ui->nativeTab;
    if (TabCtrl_GetCurSel(ui->tabs)!=selected) {
        TabCtrl_SetCurSel(ui->tabs,selected);
    }
    InvalidateRect(ui->tabs,nullptr,FALSE);
    if (visible && ui->plus)
        RedrawWindow(ui->panel,nullptr,nullptr,RDW_INVALIDATE|RDW_ERASE|RDW_ALLCHILDREN|RDW_UPDATENOW);
    rbqTabsTelemetry[4]=ui->plus && visible;
}
static LRESULT CALLBACK tabsSubclass(HWND h, UINT m, WPARAM w, LPARAM l, UINT_PTR, DWORD_PTR) {
    if (m==WM_ERASEBKGND) return 1;
    if (m==WM_PAINT) {
        PAINTSTRUCT paint{}; HDC dc=BeginPaint(h,&paint);
        RECT area{}; GetClientRect(h,&area); FillRect(dc,&area,static_cast<HBRUSH>(GetStockObject(BLACK_BRUSH)));
        const auto ui=preferencesUi(GetParent(h));
        auto old=SelectObject(dc,ui ? ui->font : GetStockObject(DEFAULT_GUI_FONT));
        SetBkMode(dc,TRANSPARENT);
        const int selected=TabCtrl_GetCurSel(h);
        for (int i=0;i<4;++i) {
            RECT item{}; TabCtrl_GetItemRect(h,i,&item);
            const auto brush=CreateSolidBrush(i==selected ? RGB(24,112,232) : RGB(32,32,32));
            FillRect(dc,&item,brush); DeleteObject(brush);
            SetTextColor(dc,i==selected ? RGB(255,255,255) : RGB(185,185,185));
            DrawTextW(dc,TabNames[i],-1,&item,DT_CENTER|DT_VCENTER|DT_SINGLELINE);
            if (GetFocus()==h && TabCtrl_GetCurFocus(h)==i) { InflateRect(&item,-3,-3); DrawFocusRect(dc,&item); }
        }
        SelectObject(dc,old); EndPaint(h,&paint); return 0;
    }
    if (m==WM_KEYDOWN && w==VK_TAB) {
        const auto ui=preferencesUi(GetParent(h));
        if (ui && ui->plus) { SetFocus(GetDlgItem(ui->panel,1001)); return 0; }
    }
    if (m==WM_SETFOCUS || m==WM_KILLFOCUS) InvalidateRect(h,nullptr,FALSE);
    return DefSubclassProc(h,m,w,l);
}
static LRESULT CALLBACK comboNavigation(HWND h, UINT m, WPARAM w, LPARAM l, UINT_PTR, DWORD_PTR) {
    if (m==WM_KEYDOWN && w==VK_TAB) {
        const auto ui=preferencesUi(GetParent(GetParent(h)));
        if (ui) { SetFocus(ui->tabs); return 0; }
    }
    return DefSubclassProc(h,m,w,l);
}
static LRESULT CALLBACK prefsSubclass(HWND h, UINT m, WPARAM w, LPARAM l, UINT_PTR, DWORD_PTR) {
    const auto ui=preferencesUi(h);
    if (!ui) return DefSubclassProc(h,m,w,l);
    if (m==TabsSnapshotMessage) {
        TabsSnapshot snapshot{};
        AcquireSRWLockShared(&snapshotLock); snapshot=navigationSnapshot; ReleaseSRWLockShared(&snapshotLock);
        if (snapshot.window==h && snapshot.generation==preferencesGeneration.load() &&
            snapshot.revision==preferencesRevision.load()) {
            const bool changed=ui->extensions!=snapshot.extensions || ui->nativeTab!=snapshot.nativeTab ||
                               (!snapshot.extensions && ui->plus);
            if (!snapshot.extensions) ui->plus=false;
            ui->extensions=snapshot.extensions; ui->nativeTab=snapshot.nativeTab;
            if (changed) layoutExtensions(h,ui);
        }
        return 0;
    }
    if (m==WM_NOTIFY && reinterpret_cast<NMHDR*>(l)->hwndFrom==ui->tabs &&
        reinterpret_cast<NMHDR*>(l)->code==TCN_SELCHANGE) {
        const int selected=TabCtrl_GetCurSel(ui->tabs);
        ++preferencesRevision;
        ui->plus=selected==3;
        if (!ui->plus && selected>=0 && selected<3) {
            ui->nativeTab=selected; requestedNativeTab.store(selected); SetEvent(navigationWake);
        }
        layoutExtensions(h,ui); return 0;
    }
    // Hide our page before JUCE handles category/search navigation. A fresh
    // accessibility snapshot decides whether the Extensions strip belongs here.
    if ((m==WM_LBUTTONDOWN && static_cast<short>(LOWORD(l))<scale(h,160)) || m==WM_KEYDOWN) {
        ++preferencesRevision; ui->plus=false; ui->extensions=false; layoutExtensions(h,ui);
        SetEvent(navigationWake);
    }
    if (m==WM_LBUTTONUP || m==WM_KEYUP || m==WM_SHOWWINDOW) SetEvent(navigationWake);
    if (m==WM_SIZE || m==WM_DPICHANGED) {
        const auto result=DefSubclassProc(h,m,w,l); layoutExtensions(h,ui); return result;
    }
    if (m==WM_NCDESTROY) {
        preferencesWindow.store(nullptr); ++preferencesGeneration; requestedNativeTab.store(-1);
        SetEvent(navigationWake);
        RemovePropW(h,PanelProperty); RemovePropW(h,TabsProperty); RemovePropW(h,PrefsProperty);
        RemoveWindowSubclass(h,prefsSubclass,1);
        DeleteObject(ui->font); delete ui;
    }
    return DefSubclassProc(h,m,w,l);
}
static void attachPreferences(HWND h) {
    if (GetPropW(h,PrefsProperty) || GetWindowThreadProcessId(h,nullptr)!=guiThread) return;
    wchar_t title[128]{},className[128]{};
    GetWindowTextW(h,title,128); GetClassNameW(h,className,128);
    if (wcsncmp(className,L"JUCE_",5) || (wcscmp(title,L"Preferences") && wcscmp(title,L"Einstellungen"))) return;
    ++rbqUiTelemetry[0];
    if (!navigationWake) {
        navigationWake=CreateEventW(nullptr,FALSE,FALSE,nullptr);
        if (!navigationWake) return;
        HANDLE thread=CreateThread(nullptr,0,navigationWorker,nullptr,0,nullptr);
        if (!thread) { CloseHandle(navigationWake); navigationWake=nullptr; return; }
        CloseHandle(thread);
    }
    auto ui=new (std::nothrow) PreferencesUi{};
    if (!ui) return;
    if (!SetPropW(h,PrefsProperty,ui) || !SetWindowSubclass(h,prefsSubclass,1,0)) {
        RemovePropW(h,PrefsProperty); delete ui; return;
    }
    SetWindowLongPtrW(h,GWL_STYLE,GetWindowLongPtrW(h,GWL_STYLE)|WS_CLIPCHILDREN);
    INITCOMMONCONTROLSEX common{sizeof(common),ICC_TAB_CLASSES}; InitCommonControlsEx(&common);
    ui->panel=CreateWindowExW(WS_EX_CONTROLPARENT,PanelClass,L"RB PLUS",WS_CHILD|WS_CLIPCHILDREN,
                             0,0,0,0,h,nullptr,extensionModule,nullptr);
    ui->tabs=CreateWindowExW(0,WC_TABCONTROLW,L"Extensions",WS_CHILD|WS_TABSTOP|TCS_FIXEDWIDTH,
                            0,0,0,0,h,reinterpret_cast<HMENU>(1002),extensionModule,nullptr);
    if (!ui->panel || !ui->tabs) {
        if (ui->panel) DestroyWindow(ui->panel);
        if (ui->tabs) DestroyWindow(ui->tabs);
        RemoveWindowSubclass(h,prefsSubclass,1); RemovePropW(h,PrefsProperty); delete ui; return;
    }
    ui->font=CreateFontW(-scale(h,13),0,0,0,FW_NORMAL,FALSE,FALSE,FALSE,DEFAULT_CHARSET,
                         OUT_DEFAULT_PRECIS,CLIP_DEFAULT_PRECIS,CLEARTYPE_QUALITY,DEFAULT_PITCH,L"Segoe UI");
    SendMessageW(ui->tabs,WM_SETFONT,reinterpret_cast<WPARAM>(ui->font),FALSE);
    for (int i=0;i<4;++i) {
        TCITEMW item{}; item.mask=TCIF_TEXT; item.pszText=const_cast<wchar_t*>(TabNames[i]);
        SendMessageW(ui->tabs,TCM_INSERTITEMW,i,reinterpret_cast<LPARAM>(&item));
    }
    TabCtrl_SetItemSize(ui->tabs,scale(h,86),scale(h,28));
    SetWindowSubclass(ui->tabs,tabsSubclass,1,0);
    SetWindowSubclass(GetDlgItem(ui->panel,1001),comboNavigation,1,0);
    SetPropW(h,PanelProperty,ui->panel); SetPropW(h,TabsProperty,ui->tabs);
    ++rbqUiTelemetry[3];
    requestedNativeTab.store(-1); ++preferencesGeneration;
    preferencesWindow.store(h); SetEvent(navigationWake);
}
