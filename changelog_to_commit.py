#!/usr/bin/env python3

import sys
import re
from pathlib import Path

def extract_latest_entry(changelog_content):
    # Split on section headers (## [...])
    sections = re.split(r'(?m)^##\s+\[', changelog_content)
    
    # First section is the header and unreleased section, skip it
    # Second section (index 1) is the latest released version
    if len(sections) < 2:
        print("No released versions found in changelog", file=sys.stderr)
        sys.exit(1)
    
    # Skip the unreleased section if it exists
    latest_section = None
    for section in sections[1:]:  # Skip header
        if 'Unreleased' not in section:
            latest_section = section
            break
    
    if not latest_section:
        print("No released versions found in changelog", file=sys.stderr)
        sys.exit(1)
        
    # Add back the [version] part that was split off
    latest_section = f"[{latest_section.strip()}"
    
    # Extract version and date
    version_match = re.match(r'\[([\d\.]+)\]\s*-\s*(\d{4}-\d{2}-\d{2})', latest_section)
    if not version_match:
        print("Could not parse version and date from latest entry", file=sys.stderr)
        sys.exit(1)
        
    version, date = version_match.groups()
    
    # Extract changes
    current_section = None
    changes = []
    for line in latest_section.split('\n'):
        line = line.strip()
        if line.startswith('###'):
            current_section = line.replace('###', '').strip()
        elif line.startswith('- '):
            if current_section:
                changes.append(f"{current_section}: {line[2:]}")
            else:
                changes.append(line[2:])
            
    # Format commit message
    commit_msg = f"Release version {version}\n\n"
    commit_msg += '\n'.join(changes)
    
    return commit_msg

def main():
    if len(sys.argv) != 2:
        print(f"Usage: {sys.argv[0]} <changelog_file>", file=sys.stderr)
        sys.exit(1)
        
    changelog_path = Path(sys.argv[1])
    if not changelog_path.exists():
        print(f"Changelog file not found: {changelog_path}", file=sys.stderr)
        sys.exit(1)
        
    content = changelog_path.read_text()
    commit_msg = extract_latest_entry(content)
    print(commit_msg)

if __name__ == '__main__':
    main() 