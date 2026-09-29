// Rekordbox 7.2.18.0311 x64 only. See compatibility/reports for ABI evidence.
// Layout mutations run on the GUI thread. Paint uses the host's supplied
// Graphics in its existing render-thread paint context.
#include "layout_order.h"
static std::atomic<unsigned> waveOrder{0}, deckOrder{0};
static std::atomic<bool> layoutInstalled{false};
static bool applyingLayout=false;
using Resized=void(__fastcall*)(Ptr);
using Paint=void(__fastcall*)(Ptr,Ptr);
static Resized originalPanelResized=nullptr;
static Paint originalWavePaint=nullptr;
extern "C" __declspec(dllexport) DWORD rbqLayoutTelemetry[8]{};
struct LayoutRect { int x,y,width,height; };
struct LayoutContext {
    Ptr panel, waves[2], sources[4], helpers[4], active[4], drag[4];
    LayoutRect slots[4];
};
static Ptr currentPlayerPanel() noexcept {
    __try {
        const Ptr main=field<Ptr>(base,0x5d1f260);
        if (!main || field<Ptr>(main)!=base+0x3818028) return 0;
        const Ptr manager=field<Ptr>(main,0x490);
        const Ptr player=field<Ptr>(manager,0xe0);
        if (!player || field<Ptr>(player)!=base+0x384ec68) return 0;
        const int count=field<int>(player,0x64);
        if (count<1 || count>100) return 0;
        const Ptr children=field<Ptr>(player,0x58);
        for (int i=0;i<count;++i) {
            const Ptr child=field<Ptr>(children,i*sizeof(Ptr));
            if (field<Ptr>(child)==base+0x384f080 && field<Ptr>(child,0x30)==player) return child;
        }
    } __except(EXCEPTION_EXECUTE_HANDLER) {}
    return 0;
}
static bool layoutContext(Ptr panel, LayoutContext* out) noexcept {
    __try {
        if (!panel || field<Ptr>(panel)!=base+0x384f080 || field<int>(panel,0x5b8)!=0x14) return false;
        const Ptr main=field<Ptr>(base,0x5d1f260);
        if (!main || field<Ptr>(main)!=base+0x3818028) return false;
        const Ptr applicationMode=field<Ptr>(main,0x428);
        if (!applicationMode || field<Ptr>(applicationMode)!=base+0x3690870 ||
            !(field<unsigned>(applicationMode,0x98)&2)) return false;
        if (field<int>(panel,0x5b4)!=4 || field<int>(panel,0x64c)!=4 || field<int>(panel,0x65c)!=4) return false;
        out->panel=panel;
        for (int i=0;i<2;++i) {
            out->waves[i]=field<Ptr>(panel,0x3b8+i*sizeof(Ptr));
            if (field<Ptr>(out->waves[i])!=base+0x38b7aa0 ||
                field<Ptr>(field<Ptr>(out->waves[i],0x168))!=base+0x38b5bd0) return false;
        }
        for (int i=0;i<4;++i) {
            out->sources[i]=field<Ptr>(field<Ptr>(panel,0x5a8),i*sizeof(Ptr));
            if (field<Ptr>(out->sources[i]+0x648)!=base+0x38b4668) return false;
            out->helpers[i]=field<Ptr>(panel,0x4f8+i*sizeof(Ptr));
            if (field<Ptr>(out->helpers[i])!=panel || field<int>(out->helpers[i],8)!=i) return false;
            out->active[i]=field<Ptr>(field<Ptr>(panel,0x640),i*sizeof(Ptr));
            out->drag[i]=field<Ptr>(field<Ptr>(panel,0x650),i*sizeof(Ptr));
            if (field<Ptr>(out->active[i],0x30)!=panel || field<Ptr>(out->drag[i],0x30)!=panel) return false;
            out->slots[i]=field<LayoutRect>(panel,0x5c8+i*sizeof(LayoutRect));
            if (out->slots[i].width<=0 || out->slots[i].height<=0) return false;
        }
        return true;
    } __except(EXCEPTION_EXECUTE_HANDLER) { return false; }
}
static void applyLayout(Ptr panel) {
    if (!layoutInstalled || (!waveOrder && !deckOrder) || GetCurrentThreadId()!=guiThread) return;
    LayoutContext ctx{};
    if (!layoutContext(panel,&ctx)) { ++rbqLayoutTelemetry[2]; return; }
    if (waveOrder) {
        const auto order=rbq::layoutOrder(waveOrder);
        using SetSource=void(__fastcall*)(Ptr,int,Ptr);
        const auto setSource=reinterpret_cast<SetSource>(base+0x194e340);
        for (int pair=0;pair<2;++pair) {
            for (int slot=0;slot<4;++slot)
                setSource(ctx.waves[pair],slot,slot<2 ? ctx.sources[order[pair*2+slot]] : 0);
        }
        for (const Ptr wave : ctx.waves)
            reinterpret_cast<Resized>(field<Ptr>(field<Ptr>(wave),0x118))(wave);
    }
    if (deckOrder) {
        const auto order=rbq::layoutOrder(deckOrder);
        using LayoutDeck=void(__fastcall*)(Ptr,int,const LayoutRect*,bool);
        using SetBounds=void(__fastcall*)(Ptr,const LayoutRect*);
        const auto layoutDeck=reinterpret_cast<LayoutDeck>(base+0x181c820);
        const auto setBounds=reinterpret_cast<SetBounds>(base+0x2aeac60);
        for (int slot=0;slot<4;++slot) {
            const int deck=order[slot];
            const auto& rect=ctx.slots[slot];
            // The host's hit testing and both highlights use these per-deck rectangles.
            *reinterpret_cast<LayoutRect*>(panel+0x5c8+deck*sizeof(LayoutRect))=rect;
            layoutDeck(ctx.helpers[deck],0x14,&rect,true);
            setBounds(ctx.active[deck],&rect);
            setBounds(ctx.drag[deck],&rect);
        }
    }
    ++rbqLayoutTelemetry[1];
}
static void __fastcall wavePaint(Ptr wave, Ptr graphics) {
    InterlockedIncrement(reinterpret_cast<volatile LONG*>(&rbqLayoutTelemetry[3]));
    rbqLayoutTelemetry[4]=GetCurrentThreadId();
    rbqLayoutTelemetry[5]=guiThread;
    LayoutContext ctx{};
    const unsigned selected=waveOrder.load();
    if (!layoutInstalled || !selected ||
        !layoutContext(field<Ptr>(wave,0x30),&ctx) || (wave!=ctx.waves[0] && wave!=ctx.waves[1])) {
        originalWavePaint(wave,graphics); return;
    }
    InterlockedIncrement(reinterpret_cast<volatile LONG*>(&rbqLayoutTelemetry[6]));
    // The original 4-horizontal paint branch only fills the background and
    // draws cached number images. Its 1234/3124 preference cannot express an
    // arbitrary permutation. Draw the same native images for the chosen rows.
    using Colour=void(__fastcall*)(Ptr,unsigned);
    using Fill=void(__fastcall*)(Ptr,const LayoutRect*);
    using ImageAt=void(__fastcall*)(Ptr,Ptr,int,int,bool);
    reinterpret_cast<Colour>(base+0x29ea970)(graphics,field<unsigned>(base,0x5d54f08));
    const LayoutRect area{0,0,field<int>(wave,0x40),field<int>(wave,0x44)};
    reinterpret_cast<Fill>(base+0x29e8270)(graphics,&area);
    const auto order=rbq::layoutOrder(selected);
    const int first=wave==ctx.waves[0] ? 0 : 2;
    for (int row=0;row<2;++row) {
        const Ptr number=wave+0x1b0+order[first+row]*sizeof(Ptr);
        for (int x : {0,area.width-12})
            reinterpret_cast<ImageAt>(base+0x29e67d0)(graphics,number,x,19+48*row,false);
    }
}
static void __fastcall panelResized(Ptr panel) {
    originalPanelResized(panel);
    if (applyingLayout) return;
    applyingLayout=true;
    applyLayout(panel);
    applyingLayout=false;
}
static void reapplyLayout() {
    if (!layoutInstalled || GetCurrentThreadId()!=guiThread) return;
    const Ptr panel=currentPlayerPanel();
    if (panel) panelResized(panel);
}
static void loadLayoutOrders() {
    wchar_t value[32]{};
    GetPrivateProfileStringW(L"Layout",L"WaveOrder",L"default",value,32,configPath);
    waveOrder=rbq::parseLayoutOrder(value);
    GetPrivateProfileStringW(L"Layout",L"DeckOrder",L"default",value,32,configPath);
    deckOrder=rbq::parseLayoutOrder(value);
}
static bool saveLayoutOrder(bool waves, unsigned selection) {
    if (selection>24) return false;
    wchar_t value[5]{};
    const auto order=rbq::layoutOrder(selection);
    for (int i=0;i<4;++i) value[i]=static_cast<wchar_t>(L'1'+order[i]);
    if (!WritePrivateProfileStringW(L"Layout",waves ? L"WaveOrder" : L"DeckOrder",
                                    selection ? value : L"default",configPath)) return false;
    (waves ? waveOrder : deckOrder)=selection;
    reapplyLayout();
    return true;
}
static bool installLayout() {
    // Independent guards: no guessed fallback for another build or changed vtable.
    const unsigned char resizeSig[]={0x48,0x8b,0xc4,0x55,0x53,0x56,0x57,0x41,0x54,0x41,0x55,0x41,0x56,0x41,0x57,0x48};
    const unsigned char deckSig[]={0x48,0x8b,0xc4,0x89,0x50,0x10,0x48,0x83,0xec,0x78,0x48,0x89,0x58,0x08,0x48,0x8b};
    const unsigned char waveSig[]={0x83,0xfa,0x04,0x73,0x0c,0x48,0x8b,0x89,0x68,0x01,0x00,0x00,0xe9,0x5f,0xa2,0xff};
    const unsigned char boundsSig[]={0x48,0x83,0xec,0x38,0x8b,0x42,0x0c,0x44,0x8b,0x4a,0x08,0x44,0x8b,0x42,0x04,0x8b};
    const unsigned char paintSig[]={0x48,0x89,0x5c,0x24,0x08,0x48,0x89,0x74,0x24,0x10,0x55,0x57,0x41,0x56,0x48,0x8b};
    const unsigned char colourSig[]={0x48,0x89,0x5c,0x24,0x08,0x57,0x48,0x83,0xec,0x50,0x8b,0xda,0x89,0x51,0x11,0x48};
    const unsigned char fillSig[]={0x48,0x83,0xec,0x28,0x48,0x8b,0x49,0x08,0x45,0x33,0xc0,0x48,0x8b,0x01,0xff,0x90};
    const unsigned char imageSig[]={0x48,0x83,0xec,0x48,0x66,0x41,0x0f,0x6e,0xc0,0x4c,0x8d,0x44,0x24,0x20,0x0f,0x5b};
    if (std::memcmp(reinterpret_cast<void*>(base+0x180ed40),resizeSig,sizeof(resizeSig)) ||
        std::memcmp(reinterpret_cast<void*>(base+0x181c820),deckSig,sizeof(deckSig)) ||
        std::memcmp(reinterpret_cast<void*>(base+0x194e340),waveSig,sizeof(waveSig)) ||
        std::memcmp(reinterpret_cast<void*>(base+0x2aeac60),boundsSig,sizeof(boundsSig)) ||
        std::memcmp(reinterpret_cast<void*>(base+0x194b710),paintSig,sizeof(paintSig)) ||
        std::memcmp(reinterpret_cast<void*>(base+0x29ea970),colourSig,sizeof(colourSig)) ||
        std::memcmp(reinterpret_cast<void*>(base+0x29e8270),fillSig,sizeof(fillSig)) ||
        std::memcmp(reinterpret_cast<void*>(base+0x29e67d0),imageSig,sizeof(imageSig))) return false;
    originalPanelResized=reinterpret_cast<Resized>(base+0x180ed40);
    originalWavePaint=reinterpret_cast<Paint>(base+0x194b710);
    auto paintSlot=reinterpret_cast<void* volatile*>(base+0x38b7aa0+26*sizeof(Ptr));
    auto slot=reinterpret_cast<void* volatile*>(base+0x384f080+0x118);
    if (*slot!=reinterpret_cast<void*>(originalPanelResized) || *paintSlot!=reinterpret_cast<void*>(originalWavePaint)) return false;
    DWORD protection=0,ignored=0;
    if (!VirtualProtect(const_cast<void**>(paintSlot),sizeof(void*),PAGE_READWRITE,&protection)) return false;
    const auto previousPaint=InterlockedCompareExchangePointer(paintSlot,reinterpret_cast<void*>(&wavePaint),
                                                               reinterpret_cast<void*>(originalWavePaint));
    if (!VirtualProtect(const_cast<void**>(paintSlot),sizeof(void*),protection,&ignored) ||
        previousPaint!=reinterpret_cast<void*>(originalWavePaint)) return false;
    if (!VirtualProtect(const_cast<void**>(slot),sizeof(void*),PAGE_READWRITE,&protection)) return false;
    const auto previous=InterlockedCompareExchangePointer(slot,reinterpret_cast<void*>(&panelResized),
                                                          reinterpret_cast<void*>(originalPanelResized));
    const bool restored=VirtualProtect(const_cast<void**>(slot),sizeof(void*),protection,&ignored)!=FALSE;
    layoutInstalled=restored && previous==reinterpret_cast<void*>(originalPanelResized);
    rbqLayoutTelemetry[0]=layoutInstalled ? 1 : 0;
    return layoutInstalled;
}
