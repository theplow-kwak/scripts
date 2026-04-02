#!/usr/bin/env python3
"""
Utility to get accurate memory information on Linux systems.
"""

import os


def get_available_memory():
    """Get available memory in bytes by reading /proc/meminfo.
    
    Returns:
        int: Available memory in bytes, or 0 if unable to read.
    """
    try:
        with open('/proc/meminfo', 'r') as f:
            for line in f:
                if line.startswith('MemAvailable:'):
                    # Extract the number (in kB) and convert to bytes
                    mem_available_kb = int(line.split()[1])
                    return mem_available_kb * 1024
    except (FileNotFoundError, ValueError, IndexError):
        pass
    
    # Fallback to the original method if /proc/meminfo is not available
    try:
        page_size = os.sysconf('SC_PAGE_SIZE')
        avail_phys_pages = os.sysconf('SC_AVPHYS_PAGES')
        return page_size * avail_phys_pages
    except (ValueError, OSError):
        return 0


def get_total_memory():
    """Get total memory in bytes by reading /proc/meminfo.
    
    Returns:
        int: Total memory in bytes, or 0 if unable to read.
    """
    try:
        with open('/proc/meminfo', 'r') as f:
            for line in f:
                if line.startswith('MemTotal:'):
                    # Extract the number (in kB) and convert to bytes
                    mem_total_kb = int(line.split()[1])
                    return mem_total_kb * 1024
    except (FileNotFoundError, ValueError, IndexError):
        pass
    
    # Fallback to sysconf method
    try:
        page_size = os.sysconf('SC_PAGE_SIZE')
        phys_pages = os.sysconf('SC_PHYS_PAGES')
        return page_size * phys_pages
    except (ValueError, OSError):
        return 0


def get_memory_info():
    """Get comprehensive memory information.
    
    Returns:
        dict: Dictionary containing memory information in bytes.
    """
    return {
        'available': get_available_memory(),
        'total': get_total_memory(),
        'used': get_total_memory() - get_available_memory() if get_total_memory() > 0 else 0
    }


def format_bytes(bytes_value):
    """Format bytes into human readable format.
    
    Args:
        bytes_value: Number of bytes
        
    Returns:
        str: Formatted string (e.g., "4.2 GB")
    """
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if bytes_value < 1024.0:
            return f"{bytes_value:.1f} {unit}"
        bytes_value /= 1024.0
    return f"{bytes_value:.1f} PB"


if __name__ == "__main__":
    # Test the functions
    print("Memory Information:")
    print("-" * 30)
    
    mem_info = get_memory_info()
    
    print(f"Total:     {format_bytes(mem_info['total'])}")
    print(f"Available: {format_bytes(mem_info['available'])}")
    print(f"Used:      {format_bytes(mem_info['used'])}")
    
    if mem_info['total'] > 0:
        usage_percent = (mem_info['used'] / mem_info['total']) * 100
        print(f"Usage:     {usage_percent:.1f}%")