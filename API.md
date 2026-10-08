# Client API example: look up media and download a file

This example uses three Client API endpoints:

- `/get_files/search_files` to search by tags
- `/get_files/file_metadata` to get a file's details
- `/get_files/file` to download the file

## Before you start

- Turn the Client API on, under _services->manage services->client api_, or start the client with `--client_api_port 45869`.
- Get an access key with the **search for and fetch files** permission. Send it in the `Hydrus-Client-API-Access-Key` header.

## Python (standard library only)

```python
import json, urllib.parse, urllib.request

API = 'http://127.0.0.1:45869'
KEY = 'your-access-key-here'

def get(path, **params):
    # list/dict params are sent as JSON, then URL-encoded
    query = urllib.parse.urlencode({k: json.dumps(v) if isinstance(v, (list, dict)) else v for k, v in params.items()})
    req = urllib.request.Request(f'{API}{path}?{query}', headers={'Hydrus-Client-API-Access-Key': KEY})
    return urllib.request.urlopen(req)

# 1. look up media by tags
found = json.load(get('/get_files/search_files', tags=['samus aran', 'system:filetype is image'], return_hashes='true'))
hashes = found['hashes']
print(f'{len(hashes)} files found')

# 2. get metadata for the first result
meta = json.load(get('/get_files/file_metadata', hashes=hashes[:1]))['metadata'][0]
print(meta['hash'], meta['mime'], meta['size'], meta['ext'])

# 3. download it
with get('/get_files/file', hash=meta['hash']) as resp, open(meta['hash'] + meta['ext'], 'wb') as f:
    f.write(resp.read())
```

## curl

```bash
KEY=your-access-key-here

# search: returns {"hashes": [...]}
curl -G http://127.0.0.1:45869/get_files/search_files \
  -H "Hydrus-Client-API-Access-Key: $KEY" \
  --data-urlencode 'tags=["samus aran"]' \
  --data-urlencode 'return_hashes=true'

# download one by hash
curl -G http://127.0.0.1:45869/get_files/file \
  -H "Hydrus-Client-API-Access-Key: $KEY" \
  --data-urlencode 'hash=<sha256 from the search>' \
  -o out.jpg
```

## Notes

- **Tags:** you can mix ordinary tags with system predicates, like `system:filetype is image` or `system:limit is 10`.
- **IDs instead of hashes:** without `return_hashes=true`, the search returns `file_ids`. You can pass those to `file_metadata` (`file_ids=[...]`) and to `file` (`file_id=...`).
- **Viewing in a browser:** add `download=true` to the `/get_files/file` request to force a download.
- **From the command line:** `hydrus_cli.py` can do the same from a terminal. See [docs/command_line.md](docs/command_line.md).
- **Full reference:** see [docs/client_api.md](docs/client_api.md) and [docs/developer_api_fork.md](docs/developer_api_fork.md).
