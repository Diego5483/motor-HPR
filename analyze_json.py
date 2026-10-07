import json
import os

folder = 'boveda y vitacoras'
for f in sorted(os.listdir(folder)):
    if f.endswith('.json'):
        path = os.path.join(folder, f)
        print(f'=== {f} ===')
        with open(path, 'r', encoding='utf-8') as fh:
            data = json.load(fh)
            # Print name, description, version if available
            name = data.get('name', 'N/A')
            version_id = data.get('versionId', 'N/A')[:8] if data.get('versionId') else 'N/A'
            nodes = data.get('nodes', [])
            connections = data.get('connections', {})
            print(f'  Name: {name}')
            print(f'  VersionId: {version_id}')
            print(f'  Nodes count: {len(nodes)}')
            print(f'  Connections count: {len(connections)}')
            # Print tags if available
            tags = data.get('tags', [])
            print(f'  Tags: {tags}')
            # Print settings
            settings = data.get('settings', {})
            print(f'  Settings keys: {list(settings.keys()) if isinstance(settings, dict) else settings}')
        print()