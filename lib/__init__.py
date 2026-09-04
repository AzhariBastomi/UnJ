"""
lib/ — library internal JIG Test Framework.

File ini menambahkan folder lib/ ke sys.path secara otomatis
sehingga modul di dalam lib/ bisa saling import tanpa prefix.
"""
import sys, os
_lib_dir = os.path.dirname(__file__)
if _lib_dir not in sys.path:
    sys.path.insert(0, _lib_dir)
