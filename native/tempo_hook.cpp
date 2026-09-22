#define WIN32_LEAN_AND_MEAN
#define NOMINMAX
#include <windows.h>
#include <atomic>
#include <cstdint>
#include <cstring>
#include "quantizer.h"

using Ptr = uintptr_t;
using Setter = void(__fastcall*)(void*, float);
constexpr uint32_t Magic = 0x52425131;
constexpr size_t Slots = 8;
struct Config { uint32_t magic, mode; uint64_t owners[Slots]; };
struct Record {
    uint64_t owner, calls, changed, bypass;
    float input, output, bpm, target;
    uint32_t thread, mode;
    uint64_t grid;
};
static_assert(sizeof(Record) == 64);
struct Telemetry {
    uint32_t magic, abi, installed, mode;
    uint64_t calls, rejected, concurrent;
    Record records[Slots];
};
// Read-only from the controller. Counters/snapshots are diagnostic, not transactional.
extern "C" __declspec(dllexport) Telemetry rbqTelemetry = {Magic, 1};
struct Slot {
    std::atomic<Ptr> owner{0};
    std::atomic_flag busy = ATOMIC_FLAG_INIT;
    rbq::State state;
    Ptr grid = 0;
    uint32_t mode = 0;
    std::atomic<float> lastInput{0};
    std::atomic<Ptr> lastGrid{0};
};
static Slot bank[Slots];
static std::atomic<uint32_t> mode{0};
static Setter original = nullptr;
static Ptr base = 0;
static SRWLOCK controlLock = SRWLOCK_INIT;
static bool installed = false;
#ifdef RBQ_AUTOSTART
static std::atomic<bool> autoEnroll{false};
#endif

template<typename T> static T field(Ptr p, size_t off = 0) noexcept {
    return *reinterpret_cast<const T*>(p + off);
}
struct Context { Ptr grid; float bpm, minimum, maximum; };
// Isolated SEH region: no objects requiring C++ unwinding. Any invalid context
// is passed through; never catch exceptions raised by the original application.
static bool context(Ptr owner, Context* out) noexcept {
    __try {
        if (field<Ptr>(owner) != base + 0x555c620 ||
            field<uint32_t>(owner, 0x130) != 0x5e715e28) return false;
        const Ptr core = field<Ptr>(owner, 0x48);
        if (field<Ptr>(core) != base + 0x556fb28 || field<Ptr>(core, 0x2e8) != owner) return false;
        const Ptr state = field<Ptr>(core, 0x220);
        if (field<Ptr>(state) != base + 0x55716a8) return false;
        const Ptr client = field<Ptr>(state, 0x30);
        // UiPlayer's secondary DjPlayerControl base, not its primary vtable.
        if (!client || field<Ptr>(client) != base + 0x3bb8068) return false;
        const Ptr holder = field<Ptr>(state, 0x28);
        if (!holder || field<Ptr>(holder) != base + 0x37af8f8) return false;
        const Ptr grid = field<Ptr>(holder, 0x18);
        if (!grid || field<Ptr>(grid) != base + 0x5559ad0) return false;
        const Ptr begin = field<Ptr>(grid, 0x18), end = field<Ptr>(grid, 0x20);
        if (!begin || end <= begin || (end - begin) % 16 || (end - begin) / 16 > 1000000) return false;
        const size_t count = (end - begin) / 16;
        const double ms = std::ceil(field<int32_t>(state, 0x14) * field<double>(base, 0x5b52288));
        size_t lo = 0, hi = count;
        while (lo < hi) {
            const size_t mid = (lo + hi) / 2;
            if (field<double>(begin + mid * 16, 8) < ms) lo = mid + 1;
            else hi = mid;
        }
        size_t index = (std::min)(lo, count - 1);
        if (index && field<double>(begin + index * 16, 8) > ms) --index;
        out->bpm = field<float>(begin + index * 16);
        out->minimum = field<float>(owner, 0x11c);
        out->maximum = field<float>(owner, 0x120);
        out->grid = grid;
        return field<Ptr>(core, 0x220) == state && field<Ptr>(state, 0x28) == holder &&
            field<Ptr>(holder, 0x18) == grid && field<Ptr>(grid, 0x18) == begin &&
            field<Ptr>(grid, 0x20) == end;
    } __except(EXCEPTION_EXECUTE_HANDLER) { return false; }
}
static void increment(uint64_t* value) noexcept {
    InterlockedIncrement64(reinterpret_cast<volatile LONG64*>(value));
}
static void __fastcall hooked(void* self, float input) {
    increment(&rbqTelemetry.calls);
    const Ptr owner = reinterpret_cast<Ptr>(self);
    size_t index = 0;
    for (; index < Slots; ++index) if (bank[index].owner.load() == owner) break;
#ifdef RBQ_AUTOSTART
    if (index == Slots && autoEnroll.load()) {
        Context checked{};
        if (context(owner, &checked)) {
            for (size_t i = 0; i < Slots; ++i) {
                Ptr empty = 0;
                if (bank[i].owner.compare_exchange_strong(empty, owner) || empty == owner) { index = i; break; }
            }
        }
    }
#endif
    if (index == Slots) { increment(&rbqTelemetry.rejected); original(self, input); return; }
    Slot& slot = bank[index];
    if (slot.busy.test_and_set(std::memory_order_acquire)) {
        increment(&rbqTelemetry.concurrent); original(self, input); return;
    }
    const uint32_t selected = mode.load(std::memory_order_acquire);
    Context ctx{};
    const bool valid = context(owner, &ctx);
    slot.lastInput.store(input);
    slot.lastGrid.store(valid ? ctx.grid : 0, std::memory_order_release);
    Record& record = rbqTelemetry.records[index];
    ++record.calls;
    record.owner = owner; record.input = input; record.output = input;
    record.thread = GetCurrentThreadId(); record.mode = selected;
    record.grid = valid ? ctx.grid : 0; record.bpm = valid ? ctx.bpm : 0; record.target = 0;
    float output = input;
    if (slot.grid != ctx.grid || slot.mode != selected) slot.state = {};
    slot.grid = ctx.grid; slot.mode = selected;
    if (selected && valid) {
        const auto result = rbq::quantize(input, ctx.bpm, selected == 1 ? 0.1 : 1.0,
                                         ctx.minimum, ctx.maximum, slot.state);
        if (result.quantized) {
            output = result.delta; record.target = static_cast<float>(result.target);
            ++record.changed;
        } else ++record.bypass;
    } else {
        slot.state = {};
        if (selected) ++record.bypass;
    }
    record.output = output;
    slot.busy.clear(std::memory_order_release);
    original(self, output);
}
static bool validHost() noexcept {
    const auto dos = reinterpret_cast<IMAGE_DOS_HEADER*>(base);
    if (dos->e_magic != IMAGE_DOS_SIGNATURE) return false;
    const auto nt = reinterpret_cast<IMAGE_NT_HEADERS64*>(base + dos->e_lfanew);
    if (nt->Signature != IMAGE_NT_SIGNATURE || nt->FileHeader.Machine != IMAGE_FILE_MACHINE_AMD64) return false;
    const unsigned char signature[] = {0x40,0x53,0x48,0x83,0xec,0x30,0x44,0x8b,0x81,0x2c,0x01,0x00,0x00};
    return nt->OptionalHeader.SizeOfImage > 0x5b52290 &&
        std::memcmp(reinterpret_cast<void*>(base + 0x2c07bd0), signature, sizeof(signature)) == 0;
}
static DWORD swapSlot(void* expected, void* replacement) noexcept {
    auto address = reinterpret_cast<void* volatile*>(base + 0x555c620 + 0x48);
    DWORD oldProtect = 0, ignored = 0;
    if (!VirtualProtect(const_cast<void**>(address), sizeof(void*), PAGE_READWRITE, &oldProtect)) return 10;
    const auto found = InterlockedCompareExchangePointer(address, replacement, expected);
    const bool restored = VirtualProtect(const_cast<void**>(address), sizeof(void*), oldProtect, &ignored) != 0;
    if (found != expected) return 11;
    return restored ? 0 : 12;
}
extern "C" __declspec(dllexport) DWORD WINAPI rbqInstall(void* data) {
    auto cfg = static_cast<const Config*>(data);
    if (!cfg || cfg->magic != Magic || cfg->mode > 2) return 1;
    AcquireSRWLockExclusive(&controlLock);
    base = reinterpret_cast<Ptr>(GetModuleHandleW(nullptr));
    DWORD result = 0;
    if (installed) result = 2;
    else if (!validHost()) result = 3;
    else {
        HMODULE pinned = nullptr;
        if (!GetModuleHandleExW(GET_MODULE_HANDLE_EX_FLAG_FROM_ADDRESS | GET_MODULE_HANDLE_EX_FLAG_PIN,
                               reinterpret_cast<LPCWSTR>(&rbqInstall), &pinned)) result = 4;
        else {
            for (size_t i = 0; i < Slots; ++i) { bank[i].owner.store(cfg->owners[i]); bank[i].state = {}; }
            original = reinterpret_cast<Setter>(base + 0x2c07bd0);
            mode.store(0); // Installation is always pass-through; activate separately.
            result = swapSlot(reinterpret_cast<void*>(original), reinterpret_cast<void*>(&hooked));
            if (result == 0 || result == 12) { installed = true; rbqTelemetry.installed = 1; }
        }
    }
    ReleaseSRWLockExclusive(&controlLock);
    return result;
}
extern "C" __declspec(dllexport) DWORD WINAPI rbqConfigure(void* data) {
    auto cfg = static_cast<const Config*>(data);
    if (!cfg || cfg->magic != Magic || cfg->mode > 2) return 1;
    AcquireSRWLockExclusive(&controlLock);
    const DWORD result = installed ? 0 : 5;
    if (!result) { mode.store(cfg->mode, std::memory_order_release); rbqTelemetry.mode = cfg->mode; }
    ReleaseSRWLockExclusive(&controlLock);
    return result;
}
extern "C" __declspec(dllexport) DWORD WINAPI rbqStop(void*) {
    AcquireSRWLockExclusive(&controlLock);
    mode.store(0, std::memory_order_release); rbqTelemetry.mode = 0;
    DWORD result = 0;
    if (installed) {
        result = swapSlot(reinterpret_cast<void*>(&hooked), reinterpret_cast<void*>(original));
        if (result == 0 || result == 12) { installed = false; rbqTelemetry.installed = 0; }
    }
    ReleaseSRWLockExclusive(&controlLock);
    // Keep the DLL pinned: another thread may have already loaded the old pointer.
    return result;
}
BOOL WINAPI DllMain(HINSTANCE, DWORD, LPVOID) { return TRUE; }
