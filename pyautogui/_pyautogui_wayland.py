"""
PyAutoGUI implementation using snegg (libei Python wrapper) for Linux Wayland environments.

The snegg library provides Python bindings for libei, a library that enables
emulated input on modern Linux systems, particularly Wayland compositors.
This module provides PyAutoGUI compatibility for Wayland using the libei protocol.

Requires:
- snegg (Python bindings for libei): pip install git+http://gitlab.freedesktop.org/whot/snegg
- libei/libeis/liboeffis installed on the system
"""

import pyautogui
import sys
import os
import time
import subprocess
from pyautogui import LEFT, MIDDLE, RIGHT

# Import snegg for libei functionality
try:
    import snegg.ei
    import snegg.oeffis
except ImportError:
    raise ImportError("The snegg module is required. Install via: pip install git+http://gitlab.freedesktop.org/whot/snegg")

# Check if we're on Linux
if sys.platform not in ('linux', 'linux2'):
    raise Exception('The pyautogui_libei module should only be loaded on a Linux system with Wayland.')

# Map PyAutoGUI button names to libei button codes
BUTTON_NAME_MAPPING = {LEFT: 1, MIDDLE: 2, RIGHT: 3, 1: 1, 2: 2, 3: 3, 4: 4, 5: 5, 6: 6, 7: 7}

# Initialize libei
def initialize_libei():
    """Initialize libei context and devices."""
    # Try to use portal first for permission handling
    try:
        # Create a context through the RemoteDesktop portal
        portal = snegg.oeffis.Portal()
        fd = portal.get_fd()
        ctx = snegg.ei.Sender.create_for_fd(fd)
    except Exception:
        # Fall back to direct connection if portal not available
        ctx = snegg.ei.Sender.create_for_socket("pyautogui")
    
    # Configure the connection
    ctx.connect()
    
    # Create a default seat
    seat = ctx.get_seat("default")
    
    # Create devices with different capabilities
    pointer = seat.create_pointer()
    keyboard = seat.create_keyboard()
    
    return ctx, pointer, keyboard

# Global objects for libei
_libei_ctx, _libei_pointer, _libei_keyboard = initialize_libei()

# Get display dimensions
def _get_display_dimensions():
    """Get the current display dimensions."""
    try:
        # Try using snegg/libei's capabilities to get dimensions if available
        return 1920, 1080  # Default fallback
    except:
        # Use the traditional pyautogui method as fallback
        return 1920, 1080  # Replace with actual screen detection

def _position():
    """Returns the current xy coordinates of the mouse cursor as a two-integer tuple.

    Returns:
      (x, y) tuple of the current xy coordinates of the mouse cursor.
    """
    # libei doesn't provide direct cursor position tracking
    # We need to track it in our module
    global _last_known_position
    return _last_known_position

def _size():
    """Returns the current screen resolution."""
    return _get_display_dimensions()

# Initialize position tracking
_last_known_position = (0, 0)

def _vscroll(clicks, x=None, y=None):
    """Performs a vertical scroll operation."""
    if clicks == 0:
        return
    
    # Move to location if specified
    if x is not None and y is not None:
        _moveTo(x, y)
    
    # Positive clicks scroll up, negative clicks scroll down
    for i in range(abs(clicks)):
        if clicks > 0:
            # Scroll up - use wheel scrolling in libei
            _libei_pointer.scroll(0, 1)
        else:
            # Scroll down
            _libei_pointer.scroll(0, -1)
        
        # Ensure events are delivered
        _libei_ctx.flush()
        time.sleep(0.01)  # Small delay between scroll events

def _hscroll(clicks, x=None, y=None):
    """Performs a horizontal scroll operation."""
    if clicks == 0:
        return
    
    # Move to location if specified
    if x is not None and y is not None:
        _moveTo(x, y)
    
    # Positive clicks scroll right, negative clicks scroll left
    for i in range(abs(clicks)):
        if clicks > 0:
            # Scroll right
            _libei_pointer.scroll(1, 0)
        else:
            # Scroll left
            _libei_pointer.scroll(-1, 0)
        
        # Ensure events are delivered
        _libei_ctx.flush()
        time.sleep(0.01)  # Small delay between scroll events

def _scroll(clicks, x=None, y=None):
    """Default scroll is vertical scrolling."""
    return _vscroll(clicks, x, y)

def _click(x, y, button):
    """Click at the specified position."""
    assert button in BUTTON_NAME_MAPPING.keys(), "button argument not in ('left', 'middle', 'right', 4, 5, 6, 7)"
    button_code = BUTTON_NAME_MAPPING[button]
    
    _mouseDown(x, y, button)
    _mouseUp(x, y, button)

def _moveTo(x, y):
    """Move the mouse to the specified position."""
    global _last_known_position
    
    # Get screen dimensions
    screen_width, screen_height = _size()
    
    # Ensure coordinates are within screen bounds
    x = max(0, min(x, screen_width - 1))
    y = max(0, min(y, screen_height - 1))
    
    # Convert to normalized coordinates for libei (0.0 to 1.0)
    norm_x = x / screen_width
    norm_y = y / screen_height
    
    # Move the pointer using libei
    _libei_pointer.motion_absolute(norm_x, norm_y)
    _libei_ctx.flush()
    
    # Update the last known position
    _last_known_position = (x, y)

def _mouseDown(x, y, button):
    """Press the mouse button at the specified position."""
    _moveTo(x, y)
    
    assert button in BUTTON_NAME_MAPPING.keys(), "button argument not in ('left', 'middle', 'right', 4, 5, 6, 7)"
    button_code = BUTTON_NAME_MAPPING[button]
    
    # Press the button using libei
    _libei_pointer.button_press(button_code)
    _libei_ctx.flush()

def _mouseUp(x, y, button):
    """Release the mouse button at the specified position."""
    _moveTo(x, y)
    
    assert button in BUTTON_NAME_MAPPING.keys(), "button argument not in ('left', 'middle', 'right', 4, 5, 6, 7)"
    button_code = BUTTON_NAME_MAPPING[button]
    
    # Release the button using libei
    _libei_pointer.button_release(button_code)
    _libei_ctx.flush()

# Create mapping between PyAutoGUI key names and libei key codes
keyboardMapping = {}

def _init_keyboard_mapping():
    """Initialize the mapping between PyAutoGUI key names and libei key codes."""
    global keyboardMapping
    
    # Start with all keys initialized to None
    keyboardMapping = dict([(key, None) for key in pyautogui.KEY_NAMES])
    
    # This would map to the appropriate libei keyboard codes
    # Here we would need to create a full mapping based on libei key codes
    # For example:
    keyboardMapping.update({
        'enter': 28,        # Return key
        'return': 28,       # Return key
        'tab': 15,          # Tab key
        'space': 57,        # Space key
        'backspace': 14,    # Backspace key
        'delete': 111,      # Delete key
        'escape': 1,        # Escape key
        'shift': 42,        # Left Shift key
        'shiftleft': 42,    # Left Shift key
        'shiftright': 54,   # Right Shift key
        'ctrl': 29,         # Left Ctrl key
        'ctrlleft': 29,     # Left Ctrl key
        'ctrlright': 97,    # Right Ctrl key
        'alt': 56,          # Left Alt key
        'altleft': 56,      # Left Alt key
        'altright': 100,    # Right Alt key
        # Add more key mappings as needed
    })
    
    # Populate letter keys (a-z, A-Z) and numbers
    for c in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ1234567890":
        # This is a placeholder - in reality you would map to the correct libei key codes
        # For simplicity, we're using a dummy mapping scheme here
        keyboardMapping[c] = ord(c.lower())

# Initialize keyboard mapping
_init_keyboard_mapping()

def _keyDown(key):
    """Press a keyboard key."""
    if key not in keyboardMapping or keyboardMapping[key] is None:
        return
    
    key_code = keyboardMapping[key]
    
    # Check if it's a key that needs shift
    needsShift = pyautogui.isShiftCharacter(key)
    
    if needsShift:
        # Press shift first
        _libei_keyboard.key_press(keyboardMapping['shift'])
        _libei_ctx.flush()
    
    # Press the key
    _libei_keyboard.key_press(key_code)
    _libei_ctx.flush()
    
    if needsShift:
        # Release shift after key press
        _libei_keyboard.key_release(keyboardMapping['shift'])
        _libei_ctx.flush()

def _keyUp(key):
    """Release a keyboard key."""
    if key not in keyboardMapping or keyboardMapping[key] is None:
        return
    
    key_code = keyboardMapping[key]
    
    # Release the key
    _libei_keyboard.key_release(key_code)
    _libei_ctx.flush()

# Cleanup function to properly close libei connection
def cleanup():
    """Clean up libei resources."""
    global _libei_ctx
    if _libei_ctx:
        try:
            _libei_ctx.disconnect()
        except:
            pass

# Register cleanup on exit
import atexit
atexit.register(cleanup)
