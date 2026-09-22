"""Exercise the RB PLUS combo using real, process-guarded Windows input."""
import argparse
import ctypes as C
from ctypes import wintypes as W
import json
import time

u = C.WinDLL('user32', use_last_error=True)
class ComboInfo(C.Structure):
    _fields_ = [('size', W.DWORD), ('item', W.RECT), ('button', W.RECT),
                ('state', W.DWORD), ('combo', W.HWND), ('edit', W.HWND), ('list', W.HWND)]
class GuiInfo(C.Structure):
    _fields_ = [('size', W.DWORD), ('flags', W.DWORD)] + [(s, W.HWND) for s in
                ('active', 'focus', 'capture', 'menu', 'move', 'caret')] + [('rect', W.RECT)]
u.GetPropW.argtypes = [W.HWND, W.LPCWSTR]; u.GetPropW.restype = W.HANDLE
u.GetDlgItem.argtypes = [W.HWND, C.c_int]; u.GetDlgItem.restype = W.HWND
u.GetComboBoxInfo.argtypes = [W.HWND, C.POINTER(ComboInfo)]
u.GetWindowRect.argtypes = [W.HWND, C.POINTER(W.RECT)]
u.GetWindowThreadProcessId.argtypes = [W.HWND, C.POINTER(W.DWORD)]
u.IsWindowVisible.argtypes = [W.HWND]
u.IsChild.argtypes = [W.HWND, W.HWND]
u.SetForegroundWindow.argtypes = [W.HWND]
u.WindowFromPoint.argtypes = [W.POINT]; u.WindowFromPoint.restype = W.HWND
u.SendMessageTimeoutW.argtypes = [W.HWND, W.UINT, C.c_size_t, C.c_ssize_t,
                                W.UINT, W.UINT, C.POINTER(C.c_size_t)]
u.GetGUIThreadInfo.argtypes = [W.DWORD, C.POINTER(GuiInfo)]
u.mouse_event.argtypes = [W.DWORD, W.DWORD, W.DWORD, W.DWORD, C.c_size_t]
u.keybd_event.argtypes = [W.BYTE, W.BYTE, W.DWORD, C.c_size_t]

def send(h, msg, w=0, l=0):
    result = C.c_size_t()
    if not u.SendMessageTimeoutW(h, msg, w, l, 2, 2000, C.byref(result)):
        raise C.WinError(C.get_last_error())
    return result.value

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--preferences', type=int, required=True)
    parser.add_argument('--select', type=int, choices=range(3), required=True)
    parser.add_argument('--hover-ms', type=int, default=600)
    parser.add_argument('--keyboard', action='store_true')
    parser.add_argument('--cancel', choices=['escape', 'outside'])
    args = parser.parse_args()
    u.SetProcessDPIAware()
    prefs = args.preferences
    panel = u.GetPropW(prefs, 'RBQ.TempoPanel')
    combo = u.GetDlgItem(panel, 1001)
    if not combo or not u.IsWindowVisible(combo):
        raise RuntimeError('RB PLUS combo is not visible')
    pid = W.DWORD()
    thread = u.GetWindowThreadProcessId(prefs, C.byref(pid))
    info = ComboInfo(); info.size = C.sizeof(info)
    if not u.GetComboBoxInfo(combo, C.byref(info)):
        raise C.WinError(C.get_last_error())
    phases = []
    def sample(name):
        gui = GuiInfo(); gui.size = C.sizeof(gui)
        u.GetGUIThreadInfo(thread, C.byref(gui))
        phases.append(dict(phase=name, selection=send(combo, 0x147), dropped=send(combo, 0x157),
                           visible=bool(u.IsWindowVisible(panel)), focus=gui.focus,
                           capture=gui.capture, active=gui.active))
    def move(x, y):
        point = W.POINT(x, y)
        point_pid = W.DWORD()
        hit = u.WindowFromPoint(point)
        u.GetWindowThreadProcessId(hit, C.byref(point_pid))
        if point_pid.value != pid.value:
            raise RuntimeError('Click target is covered by another process')
        u.SetCursorPos(x, y)
    def click(x, y):
        move(x, y)
        u.mouse_event(2, 0, 0, 0, 0)
        time.sleep(.06)
        u.mouse_event(4, 0, 0, 0, 0)
    def key(vk):
        u.keybd_event(vk, 0, 0, 0); u.keybd_event(vk, 0, 2, 0)
        time.sleep(.08)
    saved = W.POINT(); u.GetCursorPos(C.byref(saved))
    try:
        u.SetForegroundWindow(prefs); time.sleep(.2)
        sample('before')
        if not send(combo, 0x157):
            rect = W.RECT(); u.GetWindowRect(combo, C.byref(rect))
            click(rect.right - 10, (rect.top + rect.bottom)//2)
        time.sleep(.2); sample('opened')
        if not send(combo, 0x157):
            raise RuntimeError('Mouse did not open the dropdown')
        if args.cancel == 'escape':
            key(0x1b)
        elif args.cancel == 'outside':
            rect = W.RECT(); u.GetWindowRect(combo, C.byref(rect))
            click(rect.left + 30, rect.bottom + 130)
        elif args.keyboard:
            key(0x24)
            for _ in range(args.select): key(0x28)
            key(0x0d)
        else:
            rect = W.RECT(); u.GetWindowRect(info.list, C.byref(rect))
            item_height = send(combo, 0x154, 0)
            x, y = rect.left + 30, rect.top + 1 + args.select*item_height + item_height//2
            move(x, y); time.sleep(args.hover_ms/1000); sample('hover')
            click(x, y)
        time.sleep(.6); sample('after')
    finally:
        u.mouse_event(4, 0, 0, 0, 0)
        u.SetCursorPos(saved.x, saved.y)
    expected = phases[0]['selection'] if args.cancel else args.select
    passed = phases[-1]['selection'] == expected and phases[-1]['dropped'] == 0 and phases[-1]['visible']
    print(json.dumps(dict(pid=pid.value, prefs=prefs, combo=combo, popup=info.list,
                         popup_is_child=bool(u.IsChild(prefs, info.list)),
                         expected=expected, passed=passed, phases=phases), indent=2))
    if not passed:
        raise RuntimeError('Real-input combo verification failed')

if __name__ == '__main__':
    main()
