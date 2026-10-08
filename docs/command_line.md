---
title: Command Line
---

# using the client from the command line

`hydrus_cli.py` lets you use a running client from a terminal. It talks to the client through the [Client API](client_api.md), so anything the Client API can do, the command line can do. It only needs Python 3--it does not need hydrus's own requirements or its venv.

## setting it up

**1. Turn the Client API on.** Either turn it on for good under _services->manage services->client api_, or start the client with it on just for that session:

```
python hydrus_client.py --client_api_port 45869
```

Add `--client_api_allow_non_local_connections` if you want to use it from another computer. See [launch arguments](launch_arguments.md).

**2. Get an access key.** In the client, open _services->review services->client api->add->from api request_. While that dialog is open, run:

```
python hydrus_cli.py request-key "command line" --everything --save
```

Click OK in the client, and the key is saved for the command line to use from then on. To ask for just some permissions, use `--permission` once for each, like `--permission manage_playlists --permission edit_counters`. `python hydrus_cli.py request-key --help` lists them.

Scripted events are shell commands that run on your computer when playback gets to them, so being able to set them is being able to run anything. `--everything` does not include that. If you want it, ask for it by name as well: `--permission edit_scripted_events`.

You can also make a key in the client yourself, under _services->review services->client api->add->manually_, and save it with:

```
python hydrus_cli.py config --key 0123456789abcdef...
```

**3. Check it works.**

```
python hydrus_cli.py verify
```

## where it looks for the address and key

In order, it uses:

- `--url` and `--key`
- the `HYDRUS_API_URL` and `HYDRUS_API_KEY` environment variables
- what you saved with `config`, which goes in `%APPDATA%\hydrus_cli\config.json` on Windows and `~/.config/hydrus_cli/config.json` elsewhere. `--config` uses a different file
- `http://127.0.0.1:45869`, for the address

## files, counters, and playlists

Wherever a command wants files, give each one as its sha256 hash, in hex, or its file_id. You can mix them. `search` gives you both.

A counter is its name or its id. A playlist is its name or its id. Names are not case-sensitive.

Everything comes back as json. Commands that take json can take it in the command, from a file with `@path`, or from stdin with `-`.

## examples

```
# find files, and look at one
python hydrus_cli.py search "blue eyes" "system:inbox"
python hydrus_cli.py metadata 1234

# import things
python hydrus_cli.py add-file "C:\pictures\cat.png"
python hydrus_cli.py add-url "https://example.com/post/123"

# counters
python hydrus_cli.py counters add watched
python hydrus_cli.py counters inc watched 1234 1235
python hydrus_cli.py counters get 1234
python hydrus_cli.py counters convert 6c6f63616c2074616773 "items:*" --preview

# playlists
python hydrus_cli.py playlists new "morning run"
python hydrus_cli.py playlists add "morning run" 1234 1235
python hydrus_cli.py playlists add "morning run" 1236 --start-ms 30000 --end-ms 90000
python hydrus_cli.py playlists add-blank "morning run" 2000
python hydrus_cli.py playlists show "morning run"
python hydrus_cli.py playlists play "morning run"

# virtual paths
python hydrus_cli.py paths add 1234 1235 --path "tv shows/action"
python hydrus_cli.py paths all

# the media viewer's saved data for a file
python hydrus_cli.py viewer get 1234
python hydrus_cli.py viewer rotate 90 1234
python hydrus_cli.py viewer segments 1234 "[ { \"timestamp_ms\" : 0, \"name\" : \"intro\" } ]"
python hydrus_cli.py viewer skips 1234 @skips.json

# exports, which the client makes in the background
python hydrus_cli.py export video 1234 "C:\exports\clip" --start-ms 30000 --end-ms 45000 --resolution 1280 720
python hydrus_cli.py export audio 1234 "C:\exports\song" --format wav
python hydrus_cli.py export playlist "morning run" "C:\exports\morning run"

# save the open media viewers, and open them again later
python hydrus_cli.py viewers layout > viewers.json
python hydrus_cli.py viewers open-layout @viewers.json
```

## everything else

`call` reaches any Client API endpoint, including all of hydrus's own. `-p name=value` adds a parameter--a value that is json, like `5`, `true`, or `["a","b"]`, goes in as that--and `--json` gives them all at once:

```
python hydrus_cli.py call GET /manage_pages/get_pages
python hydrus_cli.py call GET /get_files/file_metadata -p file_id=1234 -p only_return_basic_information=true
python hydrus_cli.py call POST /add_tags/add_tags --json @tags.json
```

`python hydrus_cli.py --help` lists every command, and `--help` after any of them says more about it. The endpoints this fork added are in [this fork's Client API](developer_api_fork.md), and hydrus's own are in the [Client API help](developer_api.md).
