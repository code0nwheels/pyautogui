"""
PyAutoGUI implementation using snegg (libei Python wrapper) for Linux Wayland environments.

The snegg library provides Python bindings for libei, a library that enables
emulated input on modern Linux systems, particularly Wayland compositors.
This module provides PyAutoGUI compatibility for Wayland using the libei protocol.

Requires:
- snegg (Python bindings for libei): pip install git+http://gitlab.freedesktop.org/whot/snegg
- libei/libeis/liboeffis installed on the system
"""

import os
import sys
import time
import subprocess
from pyautogui import LEFT, MIDDLE, RIGHT

# Import snegg for libei functionality
try:
    import snegg.ei
    import snegg.oeffis
    SNEGG_AVAILABLE = True
except ImportError:
    SNEGG_AVAILABLE = False
    print("Warning: snegg module not available. Install via: pip install git+http://gitlab.freedesktop.org/whot/snegg")

# Check if we're on Linux
if sys.platform not in ('linux', 'linux2'):
    raise Exception('The pyautogui_wayland module should only be loaded on a Linux system with Wayland.')

# Map PyAutoGUI button names to libei button codes
BUTTON_NAME_MAPPING = {LEFT: 1, MIDDLE: 2, RIGHT: 3, 1: 1, 2: 2, 3: 3, 4: 4, 5: 5, 6: 6, 7: 7}

# Global variables for fallback mode
_using_fallback = False
_last_known_position = (0, 0)
_screen_size = (1920, 1080)

def initialize_libei():
    """Initialize libei context and devices with better error handling."""
    global _using_fallback
    
    if not SNEGG_AVAILABLE:
        _using_fallback = True
        print("Using fallback mode: snegg not available")
        return None, None, None
        
    try:
        # Try to connect via XDG_RUNTIME_DIR socket if it exists
        xdg_runtime = os.environ.get('XDG_RUNTIME_DIR')
        if xdg_runtime:
            socket_path = os.path.join(xdg_runtime, 'ei-socket')
            if os.path.exists(socket_path):
                ctx = snegg.ei.Sender.create_for_socket("pyautogui", socket_path)
            else:
                # Try with default socket
                ctx = snegg.ei.Sender()
        else:
            # Default creation
            ctx = snegg.ei.Sender()
            
        # Configure the connection
        ctx.connect()
        
        # Create a default seat
        seat = ctx.get_seat("default")
        
        # Create devices with different capabilities
        pointer = seat.create_pointer()
        keyboard = seat.create_keyboard()
        
        return ctx, pointer, keyboard
    
    except Exception as e:
        _using_fallback = True
        print(f"Error initializing libei: {str(e)}")
        print("Using fallback mode with limited functionality")
        return None, None, None

# Global objects for libei
_libei_ctx, _libei_pointer, _libei_keyboard = None, None, None

# Try to initialize, but don't crash if it fails
try:
    _libei_ctx, _libei_pointer, _libei_keyboard = initialize_libei()
except Exception as e:
    print(f"Failed to initialize libei: {str(e)}")
    _using_fallback = True

# Get display dimensions
def _get_display_dimensions():
    """Get the current display dimensions."""
    global _screen_size
    
    try:
        # Try using wlr-randr or similar tool to get display info
        result = subprocess.run(['wlr-randr'], capture_output=True, text=True)
        if result.returncode == 0:
            # Parse output to get dimensions - simplified example
            output = result.stdout
            # Just a basic parsing example - this would need to be more robust
            if 'current' in output and 'x' in output:
                for line in output.split('\n'):
                    if 'current' in line:
                        parts = line.split()
                        for part in parts:
                            if 'x' in part:
                                width, height = map(int, part.split('x'))
                                _screen_size = (width, height)
                                return width, height
    except:
        pass
        
    # Fallback to getting size from environment variables
    try:
        from screeninfo import get_monitors
        monitors = get_monitors()
        if monitors:
            main_monitor = monitors[0]
            _screen_size = (main_monitor.width, main_monitor.height)
            return main_monitor.width, main_monitor.height
    except:
        # Return default fallback values
        pass
    
    return _screen_size

def _position():
    """Returns the current xy coordinates of the mouse cursor as a two-integer tuple."""
    global _last_known_position
    
    if not _using_fallback:
        # In real implementation we would try to get actual cursor position
        # but libei doesn't provide direct cursor position tracking
        pass
        
    return _last_known_position

def _size():
    """Returns the current screen resolution."""
    return _get_display_dimensions()

# Function implementations with fallback mode support
def _moveTo(x, y):
    """Move the mouse to the specified position."""
    global _last_known_position
    
    # Ensure coordinates are within screen bounds
    screen_width, screen_height = _size()
    x = max(0, min(x, screen_width - 1))
    y = max(0, min(y, screen_height - 1))
    
    if not _using_fallback and _libei_pointer:
        try:
            # Convert to normalized coordinates for libei (0.0 to 1.0)
            norm_x = x / screen_width
            norm_y = y / screen_height
            
            # Move the pointer using libei
            _libei_pointer.motion_absolute(norm_x, norm_y)
            _libei_ctx.flush()
        except Exception as e:
            print(f"Move error: {str(e)}")
    
    # Update the last known position
    _last_known_position = (x, y)

# Similar pattern for the other functions
def _mouseDown(x, y, button):
    """Press the mouse button at the specified position."""
    _moveTo(x, y)
    
    assert button in BUTTON_NAME_MAPPING.keys(), "button argument not in ('left', 'middle', 'right', 4, 5, 6, 7)"
    button_code = BUTTON_NAME_MAPPING[button]
    
    if not _using_fallback and _libei_pointer:
        try:
            # Press the button using libei
            _libei_pointer.button_press(button_code)
            _libei_ctx.flush()
        except Exception as e:
            print(f"Mouse down error: {str(e)}")

def _mouseUp(x, y, button):
    """Release the mouse button at the specified position."""
    _moveTo(x, y)
    
    assert button in BUTTON_NAME_MAPPING.keys(), "button argument not in ('left', 'middle', 'right', 4, 5, 6, 7)"
    button_code = BUTTON_NAME_MAPPING[button]
    
    if not _using_fallback and _libei_pointer:
        try:
            # Release the button using libei
            _libei_pointer.button_release(button_code)
            _libei_ctx.flush()
        except Exception as e:
            print(f"Mouse up error: {str(e)}")

def _click(x, y, button):
    """Click at the specified position."""
    assert button in BUTTON_NAME_MAPPING.keys(), "button argument not in ('left', 'middle', 'right', 4, 5, 6, 7)"
    
    _mouseDown(x, y, button)
    _mouseUp(x, y, button)

# Implement the other required functions with similar pattern...
