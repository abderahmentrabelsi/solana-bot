import ctypes
from ctypes import wintypes
from ctypes import c_size_t
import os

import subprocess
import sys
import winreg
import ctypes

from loguru import logger

def set_max_open_file_descriptors(new_limit):
    SIZE_T = c_size_t

    LPHANDLE = ctypes.POINTER(wintypes.HANDLE)
    LPDWORD = ctypes.POINTER(wintypes.DWORD)

    GetCurrentProcess = ctypes.windll.kernel32.GetCurrentProcess
    GetCurrentProcess.restype = wintypes.HANDLE

    SetProcessWorkingSetSizeEx = ctypes.windll.kernel32.SetProcessWorkingSetSizeEx
    SetProcessWorkingSetSizeEx.argtypes = (
        wintypes.HANDLE,
        SIZE_T,
        SIZE_T,
        wintypes.DWORD
    )
    SetProcessWorkingSetSizeEx.restype = wintypes.BOOL

    PROCESS_SET_QUOTA = 0x0100

    OpenProcess = ctypes.windll.kernel32.OpenProcess
    OpenProcess.argtypes = (
        wintypes.DWORD,
        wintypes.BOOL,
        wintypes.DWORD
    )
    OpenProcess.restype = wintypes.HANDLE

    CloseHandle = ctypes.windll.kernel32.CloseHandle
    CloseHandle.argtypes = (wintypes.HANDLE,)
    CloseHandle.restype = wintypes.BOOL

    PROCESS_SET_INFORMATION = 0x0200

    # Set the new limit for the current process
    process_handle = OpenProcess(PROCESS_SET_QUOTA | PROCESS_SET_INFORMATION, False, os.getpid())
    if not process_handle:
        raise Exception("Error: Unable to open the current process.")

    try:
        if not SetProcessWorkingSetSizeEx(process_handle, new_limit, new_limit, 0):
            raise Exception("Error: Unable to set the new limit for open file descriptors.")
    finally:
        CloseHandle(process_handle)


def _is_admin() -> bool:
    try:
        return ctypes.windll.shell32.IsUserAnAdmin()
    except:
        return False

def _set_registry_value(key_path: str, value_name: str, value_type: int, value_data: int):
    try:
        key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, key_path, 0, winreg.KEY_SET_VALUE)
        winreg.SetValueEx(key, value_name, 0, value_type, value_data)
        winreg.CloseKey(key)
        logger.info(f"Set {value_name} to {value_data} in {key_path}")
    except Exception as e:
        logger.error(f"Failed to set {value_name} in {key_path}: {e}")

def _run_netsh_command(command: str):
    try:
        logger.info(f"Executing command: netsh {command}")
        result = subprocess.run(['netsh'] + command.split(), capture_output=True, text=True, check=True)
        logger.debug(f"Command output: {result.stdout}")
    except subprocess.CalledProcessError as e:
        logger.error(f"Command 'netsh {command}' failed with error: {e.stderr}")

def optimize_windows_network():
    if not _is_admin():
        logger.error("Script must be run as administrator.")
        sys.exit("Error: This script requires administrative privileges. Please run as admin.")

    # 1. Modify Registry Settings
    registry_changes = [
        # Increase MaxUserPort
        {
            'key_path': "SYSTEM\\CurrentControlSet\\Services\\Tcpip\\Parameters",
            'value_name': "MaxUserPort",
            'value_type': winreg.REG_DWORD,
            'value_data': 65534
        },
        # Reduce TcpTimedWaitDelay
        {
            'key_path': "SYSTEM\\CurrentControlSet\\Services\\Tcpip\\Parameters",
            'value_name': "TcpTimedWaitDelay",
            'value_type': winreg.REG_DWORD,
            'value_data': 30
        },
        # Increase MaxFreeTcbs
        {
            'key_path': "SYSTEM\\CurrentControlSet\\Services\\Tcpip\\Parameters",
            'value_name': "MaxFreeTcbs",
            'value_type': winreg.REG_DWORD,
            'value_data': 65535
        },
        # Increase MaxHashTableSize
        {
            'key_path': "SYSTEM\\CurrentControlSet\\Services\\Tcpip\\Parameters",
            'value_name': "MaxHashTableSize",
            'value_type': winreg.REG_DWORD,
            'value_data': 65535
        },
        # Increase TcpNumConnections
        {
            'key_path': "SYSTEM\\CurrentControlSet\\Services\\Tcpip\\Parameters",
            'value_name': "TcpNumConnections",
            'value_type': winreg.REG_DWORD,
            'value_data': 2147483647
        }
    ]

    for change in registry_changes:
        _set_registry_value(
            change['key_path'],
            change['value_name'],
            change['value_type'],
            change['value_data']
        )

    # 2. Execute netsh Commands
    netsh_commands = [
        "int ipv4 set dynamicport tcp start=10000 num=55535",
        "int ipv6 set dynamicport tcp start=10000 num=55535",
        "int tcp set global rss=enabled rsc=enabled autotuninglevel=normal fastopen=enabled",
    ]

    for cmd in netsh_commands:
        _run_netsh_command(cmd)

    logger.info("Windows network optimization completed. A system reboot is required for changes to take effect.")


