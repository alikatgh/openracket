#!/usr/bin/env python3
"""Generate conservative preview metadata. No document claims without Apple-event QA."""
import pathlib
import plistlib
import re
import sys

cargo = pathlib.Path(sys.argv[1]).read_text()
version = re.search(r'^version\s*=\s*"([0-9]+\.[0-9]+\.[0-9]+)"', cargo, re.M).group(1)
info = {
    'CFBundleDevelopmentRegion': 'en',
    'CFBundleExecutable': 'openracket',
    'CFBundleIdentifier': 'io.github.alikatgh.openracket',
    'CFBundleInfoDictionaryVersion': '6.0',
    'CFBundleName': 'OpenRacket',
    'CFBundleDisplayName': 'OpenRacket',
    'CFBundlePackageType': 'APPL',
    'CFBundleShortVersionString': version,
    'CFBundleVersion': version,
    'LSMinimumSystemVersion': '15.0',
    'NSHighResolutionCapable': True,
    'NSHumanReadableCopyright': 'OpenRacket contributors. MIT license; third-party notices included.',
}
pathlib.Path(sys.argv[2]).write_bytes(plistlib.dumps(info, sort_keys=True))
