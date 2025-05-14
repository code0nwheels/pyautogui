# pyautogui_snegg.py - PyAutoGUI implementation using snegg (Python wrapper for libei)

import pyautogui
import sys
import os
import subprocess
from pyautogui import LEFT, MIDDLE, RIGHT
from pathlib import Path

# Import snegg module for libei
import snegg.ei

BUTTON_NAME_MAPPING = {LEFT: 1, MIDDLE: 2, RIGHT: 3, 1: 1, 2: 2, 3: 3, 4: 4, 5: 5, 6: 6, 7: 7}

if sys.platform in ('java', 'darwin', 'win32'):
    raise Exception('The pyautogui_snegg module should only be loaded on a Unix system that supports libei.')

# Initialize snegg sender client
_client = None
_pointer = None
_keyboard = None
_emulating = False

def _ensure_connected():
    """Ensures that we have an active connection to the libei server."""
    global _client, _pointer, _keyboard
    if _client is None:
        # Initialize snegg client connection for input sending
        # Using socket connection with default path (uses LIBEI_SOCKET env var)
        _client = snegg.ei.Sender.create_for_socket(None, "PyAutoGUI")
        
        # Connect to the server and wait for events
        _client.dispatch()
        
        # Create devices
        # First, we need to bind to a seat to get devices
        for event in _client.events:
            if event.event_type == snegg.ei.EventType.SEAT_ADDED:
                seat = event.seat
                # Bind to pointer and keyboard capabilities
                capabilities = (
                    snegg.ei.DeviceCapability.POINTER,
                    snegg.ei.DeviceCapability.POINTER_ABSOLUTE,
                    snegg.ei.DeviceCapability.BUTTON,
                    snegg.ei.DeviceCapability.KEYBOARD,
                    snegg.ei.DeviceCapability.SCROLL
                )
                seat.bind(capabilities)
                break
        
        # Wait for device creation events
        _client.dispatch()
        for event in _client.events:
            if event.event_type == snegg.ei.EventType.DEVICE_ADDED:
                device = event.device
                if snegg.ei.DeviceCapability.POINTER in device.capabilities:
                    _pointer = device
                if snegg.ei.DeviceCapability.KEYBOARD in device.capabilities:
                    _keyboard = device

def _start_emulating():
    """Start emulating if not already emulating."""
    global _emulating
    if not _emulating:
        if _pointer:
            _pointer.start_emulating()
        if _keyboard:
            _keyboard.start_emulating()
        _emulating = True

def _stop_emulating():
    """Stop emulating."""
    global _emulating
    if _emulating:
        if _pointer:
            _pointer.stop_emulating()
        if _keyboard:
            _keyboard.stop_emulating()
        _emulating = False

def _position():
    """Returns the current xy coordinates of the mouse cursor as a two-integer tuple."""
    # snegg/libei doesn't provide position query, use external tool
    import subprocess
    try:
        output = subprocess.check_output(['xdotool', 'getmouselocation'])
        parts = output.decode().strip().split()
        x = int(parts[0].split(':')[1])
        y = int(parts[1].split(':')[1])
        return x, y
    except (subprocess.SubprocessError, IndexError, ValueError):
        return 0, 0

def _size():
    """Returns the width and height of the screen."""
    # Using external tools for screen size
    import subprocess
    try:
        output = subprocess.check_output(['xrandr', '--current'])
        for line in output.decode().split('\n'):
            if ' connected' in line and 'primary' in line:
                parts = line.split()
                for part in parts:
                    if 'x' in part and part[0].isdigit():
                        width, height = map(int, part.split('x')[0].split('+')[0].split('x'))
                        return width, height
    except (subprocess.SubprocessError, IndexError, ValueError):
        pass
    
    # Default fallback
    return 1920, 1080

def _vscroll(clicks, x=None, y=None):
    """Performs vertical scrolling."""
    clicks = int(clicks)
    if clicks == 0:
        return
    
    _ensure_connected()
    _start_emulating()
    
    if x is None or y is None:
        x, y = _position()
    
    # Move to position first
    _pointer.pointer_motion_absolute(x, y)
    
    # Scroll in the appropriate direction
    # Note: For scroll wheel, negative is up, positive is down (opposite of X11 button numbers)
    direction = -1 if clicks > 0 else 1
    
    for _ in range(abs(clicks)):
        # Use scroll delta for continuous scrolling
        _pointer.scroll_delta(0, direction)
        # Also send discrete scroll events for compatibility
        _pointer.scroll_discrete(0, direction)
        _pointer.frame()
    
    # Send scroll stop event
    _pointer.scroll_stop(False, True)
    _pointer.frame()

def _hscroll(clicks, x=None, y=None):
    """Performs horizontal scrolling."""
    clicks = int(clicks)
    if clicks == 0:
        return
    
    _ensure_connected()
    _start_emulating()
    
    if x is None or y is None:
        x, y = _position()
    
    # Move to position first
    _pointer.pointer_motion_absolute(x, y)
    
    # Scroll in the appropriate direction
    direction = 1 if clicks > 0 else -1
    
    for _ in range(abs(clicks)):
        # Use scroll delta for continuous scrolling
        _pointer.scroll_delta(direction, 0)
        # Also send discrete scroll events for compatibility
        _pointer.scroll_discrete(direction, 0)
        _pointer.frame()
    
    # Send scroll stop event
    _pointer.scroll_stop(True, False)
    _pointer.frame()

def _scroll(clicks, x=None, y=None):
    """Default scroll function is vertical scrolling."""
    return _vscroll(clicks, x, y)

def _click(x, y, button):
    """Performs a mouse click (down and up)."""
    assert button in BUTTON_NAME_MAPPING.keys(), "button argument not in ('left', 'middle', 'right', 4, 5, 6, 7)"
    button = BUTTON_NAME_MAPPING[button]
    
    _mouseDown(x, y, button)
    _mouseUp(x, y, button)

_mouse_is_swapped_setting = None

def _mouse_is_swapped():
    """Detects if mouse buttons are swapped in the system."""
    global _mouse_is_swapped_setting
    if _mouse_is_swapped_setting is None:
        try:
            proc = subprocess.Popen(['dconf', 'read', '/org/gnome/desktop/peripherals/mouse/left-handed'], stdout=subprocess.PIPE)
            stdout_bytes, stderr_bytes = proc.communicate()
            _mouse_is_swapped_setting = stdout_bytes.decode('utf-8') == 'true\n'
        except FileNotFoundError:
            # Non-Gnome environment, assume not swapped
            _mouse_is_swapped_setting = False
    return _mouse_is_swapped_setting

def _moveTo(x, y):
    """Moves the mouse pointer to the specified coordinates."""
    _ensure_connected()
    _start_emulating()
    
    # Use absolute motion to move to the exact coordinates
    _pointer.pointer_motion_absolute(x, y)
    # Frame event to mark the end of the sequence
    _pointer.frame()

def _mouseDown(x, y, button):
    """Presses a mouse button at the specified coordinates."""
    _ensure_connected()
    _start_emulating()
    
    # Move to position first
    _pointer.pointer_motion_absolute(x, y)
    # Send button press event
    _pointer.button_button(button, True)  # True for press
    _pointer.frame()

def _mouseUp(x, y, button):
    """Releases a mouse button at the specified coordinates."""
    _ensure_connected()
    
    # Move to position first (in case the position changed since mouseDown)
    _pointer.pointer_motion_absolute(x, y)
    # Send button release event
    _pointer.button_button(button, False)  # False for release
    _pointer.frame()

# Map from PyAutoGUI key names to linux/input-event-codes.h key codes
# This is based on linux/input-event-codes.h and matches the X11 version
def _build_keyboard_mapping():
    # Start with all keys set to None
    mapping = dict([(key, None) for key in pyautogui.KEY_NAMES])
    
    # Map alphanumeric keys using their respective input event codes
    for i, c in enumerate("abcdefghijklmnopqrstuvwxyz"):
        mapping[c] = 30 + i  # KEY_A is 30, KEY_B is 31, etc.
        mapping[c.upper()] = 30 + i  # Use same code for uppercase

    # Map numeric keys
    for i, c in enumerate("1234567890"):
        mapping[c] = 2 + i  # KEY_1 is 2, KEY_2 is 3, etc.
    
    # Map special keys
    special_keys = {
        'backspace': 14,      # KEY_BACKSPACE
        '\b': 14,             # KEY_BACKSPACE
        'tab': 15,            # KEY_TAB
        '\t': 15,             # KEY_TAB
        'enter': 28,          # KEY_ENTER
        'return': 28,         # KEY_ENTER
        '\n': 28,             # KEY_ENTER
        '\r': 28,             # KEY_ENTER
        'shift': 42,          # KEY_LEFTSHIFT
        'shiftleft': 42,      # KEY_LEFTSHIFT
        'shiftright': 54,     # KEY_RIGHTSHIFT
        'ctrl': 29,           # KEY_LEFTCTRL
        'ctrlleft': 29,       # KEY_LEFTCTRL
        'ctrlright': 97,      # KEY_RIGHTCTRL
        'alt': 56,            # KEY_LEFTALT
        'altleft': 56,        # KEY_LEFTALT
        'altright': 100,      # KEY_RIGHTALT
        'pause': 119,         # KEY_PAUSE
        'capslock': 58,       # KEY_CAPSLOCK
        'esc': 1,             # KEY_ESC
        'escape': 1,          # KEY_ESC
        '\e': 1,              # KEY_ESC
        'space': 57,          # KEY_SPACE
        ' ': 57,              # KEY_SPACE
        'pageup': 104,        # KEY_PAGEUP
        'pgup': 104,          # KEY_PAGEUP
        'pagedown': 109,      # KEY_PAGEDOWN
        'pgdn': 109,          # KEY_PAGEDOWN
        'end': 107,           # KEY_END
        'home': 102,          # KEY_HOME
        'left': 105,          # KEY_LEFT
        'up': 103,            # KEY_UP
        'right': 106,         # KEY_RIGHT
        'down': 108,          # KEY_DOWN
        'insert': 110,        # KEY_INSERT
        'delete': 111,        # KEY_DELETE
        'del': 111,           # KEY_DELETE
        'numlock': 69,        # KEY_NUMLOCK
        'scrolllock': 70,     # KEY_SCROLLLOCK
        'win': 125,           # KEY_LEFTMETA
        'winleft': 125,       # KEY_LEFTMETA
        'winright': 126,      # KEY_RIGHTMETA
        'apps': 127,          # KEY_COMPOSE
    }
    
    # Add function keys
    for i in range(1, 25):
        special_keys[f'f{i}'] = 58 + i  # F1 is KEY_F1 (59), F2 is KEY_F2 (60), etc.
    
    # Add numpad keys
    for i in range(10):
        special_keys[f'num{i}'] = 96 + i if i > 0 else 82  # KEY_KP1 is 79, etc. but KEY_KP0 is 82
    
    special_keys.update({
        'multiply': 55,    # KEY_KPASTERISK
        'add': 78,         # KEY_KPPLUS
        'separator': 83,   # KEY_KPCOMMA
        'subtract': 74,    # KEY_KPMINUS
        'decimal': 83,     # KEY_KPDOT
        'divide': 98,      # KEY_KPSLASH
    })
    
    # Add special characters
    char_mapping = {
        '!': 2,            # KEY_1 + SHIFT
        '@': 3,            # KEY_2 + SHIFT
        '#': 4,            # KEY_3 + SHIFT
        '$': 5,            # KEY_4 + SHIFT
        '%': 6,            # KEY_5 + SHIFT
        '^': 7,            # KEY_6 + SHIFT
        '&': 8,            # KEY_7 + SHIFT
        '*': 9,            # KEY_8 + SHIFT
        '(': 10,           # KEY_9 + SHIFT
        ')': 11,           # KEY_0 + SHIFT
        '-': 12,           # KEY_MINUS
        '_': 12,           # KEY_MINUS + SHIFT
        '=': 13,           # KEY_EQUAL
        '+': 13,           # KEY_EQUAL + SHIFT
        '[': 26,           # KEY_LEFTBRACE
        '{': 26,           # KEY_LEFTBRACE + SHIFT
        ']': 27,           # KEY_RIGHTBRACE
        '}': 27,           # KEY_RIGHTBRACE + SHIFT
        '\\': 43,          # KEY_BACKSLASH
        '|': 43,           # KEY_BACKSLASH + SHIFT
        ';': 39,           # KEY_SEMICOLON
        ':': 39,           # KEY_SEMICOLON + SHIFT
        "'": 40,           # KEY_APOSTROPHE
        '"': 40,           # KEY_APOSTROPHE + SHIFT
        '`': 41,           # KEY_GRAVE
        '~': 41,           # KEY_GRAVE + SHIFT
        ',': 51,           # KEY_COMMA
        '<': 51,           # KEY_COMMA + SHIFT
        '.': 52,           # KEY_DOT
        '>': 52,           # KEY_DOT + SHIFT
        '/': 53,           # KEY_SLASH
        '?': 53,           # KEY_SLASH + SHIFT
    }
    
    mapping.update(special_keys)
    mapping.update(char_mapping)
    
    return mapping

keyboardMapping = _build_keyboard_mapping()

def _keyDown(key):
    """Performs a keyboard key press without the release."""
    if key not in keyboardMapping or keyboardMapping[key] is None:
        return

    _ensure_connected()
    _start_emulating()
    
    # Handle direct keycodes
    if isinstance(key, int):
        _keyboard.keyboard_key(key, True)  # True for press
        _keyboard.frame()
        return

    # Handle shift for uppercase letters and special characters
    needsShift = pyautogui.isShiftCharacter(key)
    if needsShift:
        _keyboard.keyboard_key(42, True)  # 42 is KEY_LEFTSHIFT
        _keyboard.frame()
    
    _keyboard.keyboard_key(keyboardMapping[key], True)  # True for press
    _keyboard.frame()

def _keyUp(key):
    """Performs a keyboard key release."""
    if key not in keyboardMapping or keyboardMapping[key] is None:
        return

    _ensure_connected()
    
    # Handle direct keycodes
    if isinstance(key, int):
        _keyboard.keyboard_key(key, False)  # False for release
        _keyboard.frame()
        return

    _keyboard.keyboard_key(keyboardMapping[key], False)  # False for release
    _keyboard.frame()
    
    # Handle shift for uppercase letters and special characters
    needsShift = pyautogui.isShiftCharacter(key)
    if needsShift:
        _keyboard.keyboard_key(42, False)  # 42 is KEY_LEFTSHIFT
        _keyboard.frame()