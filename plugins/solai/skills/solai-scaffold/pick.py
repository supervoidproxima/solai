# -*- coding: utf-8 -*-
"""The system file dialog, in a process of its own.

    py pick.py folder
    py pick.py files

Prints the chosen path, one per line, and nothing else. A cancelled dialog prints nothing and
exits 0, because cancelling is an answer rather than a failure.

Two dialogs, in order. On Windows the real one is asked for first: `IFileOpenDialog` with
`FOS_PICKFOLDERS`, which is the Explorer window a person recognises, called through `ctypes`
with no dependency added. If that is not available - another platform, or a Windows too old -
it falls back to Tk, whose folder chooser still works and looks like 2003.

Why a subprocess and not an import: Tk wants the main thread and COM wants its own apartment,
and a dialog raised inside the server would take the server down with it when either objects.
Shelling out is also what the surface already does for the engine, so this adds a script
rather than a way of working.

Why a system dialog and not the browser's: a browser hands a page bytes, never a path. The
whole design here is that documents are copied from where they already are, so a picker that
cannot name the folder would be the wrong picker.
"""
import sys

FOS_PICKFOLDERS = 0x00000020
FOS_FORCEFILESYSTEM = 0x00000040
FOS_ALLOWMULTISELECT = 0x00000200
SIGDN_FILESYSPATH = 0x80058000
CLSCTX_INPROC_SERVER = 1
S_OK = 0

# The vtable slots used below. IFileOpenDialog extends IFileDialog extends IModalWindow
# extends IUnknown, and a wrong index here calls a different method with the right-looking
# arguments, so they are named rather than written inline.
V_RELEASE = 2
V_SHOW = 3
V_SETOPTIONS = 9
V_GETOPTIONS = 10
V_GETRESULT = 20
V_GETRESULTS = 27          # IFileOpenDialog
V_ITEM_GETDISPLAYNAME = 5  # IShellItem
V_ARRAY_GETCOUNT = 7       # IShellItemArray
V_ARRAY_GETITEMAT = 8


def _dpi_aware():
    """Tell Windows this process draws at the real pixel density before any window exists.

    Without it the dialog is rendered at 96 DPI and stretched by the compositor, which is the
    blur. Three attempts, newest first: the per-monitor v2 context (Windows 10 1703 and up),
    the older per-monitor awareness, and finally the system-wide flag. All three are ignored
    if a window has already been made, which is why this runs first thing.
    """
    import ctypes
    try:
        ctypes.windll.user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))
        return
    except Exception:                                               # noqa: BLE001
        pass
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
        return
    except Exception:                                               # noqa: BLE001
        pass
    try:
        ctypes.windll.user32.SetProcessDPIAware()
    except Exception:                                               # noqa: BLE001
        pass


def _windows(kind):
    """-> list of paths, or None if this machine cannot raise the dialog."""
    import ctypes
    from ctypes import POINTER, byref, c_void_p, c_ulong, c_wchar_p

    try:
        ole32 = ctypes.OleDLL('ole32')
        # CoTaskMemFree returns void. Called through OleDLL its leftover register would be
        # read as an HRESULT and a negative one would raise after the path was already in
        # hand, sending a correct answer down the fallback path and raising a second dialog.
        raw = ctypes.WinDLL('ole32')
    except Exception:                                               # noqa: BLE001
        return None

    class GUID(ctypes.Structure):
        _fields_ = [('a', ctypes.c_ulong), ('b', ctypes.c_ushort), ('c', ctypes.c_ushort),
                    ('d', ctypes.c_ubyte * 8)]

    def guid(text):
        g = GUID()
        if ole32.CLSIDFromString(c_wchar_p(text), byref(g)) != S_OK:
            raise OSError('bad guid %s' % text)
        return g

    def call(ptr, slot, restype, argtypes, *args):
        vtbl = ctypes.cast(ptr, POINTER(POINTER(c_void_p)))[0]
        fn = ctypes.WINFUNCTYPE(restype, c_void_p, *argtypes)(vtbl[slot])
        return fn(ptr, *args)

    CLSID_FileOpenDialog = '{DC1C5A9C-E88A-4DDE-A5A1-60F82A20AEF7}'
    IID_IFileOpenDialog = '{D57C7288-D4AD-4768-BE02-9D969532D960}'

    try:
        ole32.CoInitialize(None)
    except Exception:                                               # noqa: BLE001
        pass

    pfd = c_void_p()
    hr = ole32.CoCreateInstance(byref(guid(CLSID_FileOpenDialog)), None,
                                CLSCTX_INPROC_SERVER,
                                byref(guid(IID_IFileOpenDialog)), byref(pfd))
    if hr != S_OK or not pfd:
        return None

    try:
        opts = c_ulong()
        call(pfd, V_GETOPTIONS, ctypes.HRESULT, [POINTER(c_ulong)], byref(opts))
        want = opts.value | FOS_FORCEFILESYSTEM
        want |= FOS_PICKFOLDERS if kind == 'folder' else FOS_ALLOWMULTISELECT
        call(pfd, V_SETOPTIONS, ctypes.HRESULT, [c_ulong], want)

        try:
            call(pfd, V_SHOW, ctypes.HRESULT, [c_void_p], None)
        except OSError:
            return []          # cancelled: the dialog reports it as a failing HRESULT

        def path_of(item):
            buf = c_wchar_p()
            call(item, V_ITEM_GETDISPLAYNAME, ctypes.HRESULT,
                 [c_ulong, POINTER(c_wchar_p)], SIGDN_FILESYSPATH, byref(buf))
            out = buf.value
            raw.CoTaskMemFree(buf)
            return out

        out = []
        if kind == 'folder':
            item = c_void_p()
            call(pfd, V_GETRESULT, ctypes.HRESULT, [POINTER(c_void_p)], byref(item))
            if item:
                out.append(path_of(item))
                call(item, V_RELEASE, ctypes.c_ulong, [])
        else:
            arr = c_void_p()
            call(pfd, V_GETRESULTS, ctypes.HRESULT, [POINTER(c_void_p)], byref(arr))
            if arr:
                n = c_ulong()
                call(arr, V_ARRAY_GETCOUNT, ctypes.HRESULT, [POINTER(c_ulong)], byref(n))
                for i in range(n.value):
                    item = c_void_p()
                    call(arr, V_ARRAY_GETITEMAT, ctypes.HRESULT,
                         [c_ulong, POINTER(c_void_p)], i, byref(item))
                    if item:
                        out.append(path_of(item))
                        call(item, V_RELEASE, ctypes.c_ulong, [])
                call(arr, V_RELEASE, ctypes.c_ulong, [])
        return [p for p in out if p]
    finally:
        call(pfd, V_RELEASE, ctypes.c_ulong, [])


def _tk(kind):
    """The fallback. Older-looking, and it works everywhere Tk is installed."""
    try:
        import tkinter
        from tkinter import filedialog
    except Exception as err:                                        # noqa: BLE001
        sys.stderr.write('no dialog available on this machine: %s' % err)
        return None

    root = tkinter.Tk()
    root.withdraw()
    try:
        root.attributes('-topmost', True)
    except Exception:                                               # noqa: BLE001
        pass
    try:
        if kind == 'files':
            return list(filedialog.askopenfilenames(parent=root,
                                                    title='Choose the materials') or ())
        one = filedialog.askdirectory(parent=root, title='Choose the folder')
        return [one] if one else []
    finally:
        root.destroy()


def main():
    kind = sys.argv[1] if len(sys.argv) > 1 else 'folder'
    if kind not in ('folder', 'files'):
        sys.stderr.write('unknown kind %r. Say folder or files.' % kind)
        return 1

    chosen = None
    if sys.platform == 'win32':
        _dpi_aware()
        try:
            chosen = _windows(kind)
        except Exception:                                           # noqa: BLE001
            chosen = None      # a COM that misbehaves is a reason to fall back, not to fail
    if chosen is None:
        chosen = _tk(kind)
    if chosen is None:
        return 1
    if chosen:
        sys.stdout.write('\n'.join(chosen))
    return 0


if __name__ == '__main__':
    sys.exit(main())
