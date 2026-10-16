---
title: This Fork's Client API
---

# this fork's Client API

These endpoints are for the features this fork adds: counters, playlists, virtual paths, snapshots, what the media viewer remembers for each file, tag presets, screen locations, media viewer layouts, and exporting video, audio, and playlists. They work just like hydrus's own [Client API](developer_api.md): the same access keys and session keys, json in and out, and the same errors. The [command line tool](command_line.md) can use all of them.

`/api_version` has a `fork_api_version`, which goes up when these change. It is `5` now.

## permissions

Each group of endpoints has its own permission. The numbers start at 100, so they never clash with ones hydrus adds later.

| number | permission | endpoints |
| --- | --- | --- |
| 100 | edit file counters | `/manage_counters/...` |
| 101 | manage playlists | `/manage_playlists/...`, and `/manage_media_viewers/open_playlist` with 'manage pages' |
| 102 | edit file virtual paths | `/manage_virtual_paths/...` |
| 103 | manage snapshots | `/manage_snapshots/...`. `add_snapshot` needs 'import and delete files' too |
| 104 | edit media viewer file data | `/manage_file_viewer_data/...`, apart from `set_scripted_events` |
| 105 | manage tag presets | `/manage_tag_presets/...` |
| 106 | manage screen locations | `/manage_screen_locations/...` |
| 107 | edit scripted events | `/manage_file_viewer_data/set_scripted_events` |
| 108 | export videos, audio, and playlists | `/manage_exports/...`. `export_playlist` needs 'manage playlists' too |
| 4 | manage pages | `/manage_media_viewers/...` |

!!! danger "Scripted events"
    Scripted events are shell commands that run on the client's computer when playback gets to them. Being able to set them is being able to run anything there, so 'permits everything' does **not** include permission 107. A key only has it if it is ticked for that key, or asked for by number in `/request_new_permissions`. `/verify_access_key` lists it for a 'permits everything' key only when it has it as well.

## the usual parameters

**Files**: endpoints that take files use the usual `hash`, `hashes`, `file_id`, or `file_ids`, like the rest of the Client API. Some only take one file, and say so.

**Counters**: `counter_id`, the counter's id in hex, or `counter_name`. Names are not case-sensitive.

**Playlists**: `playlist_id`, or `playlist_name`. Names are not case-sensitive, and extra spaces do not count.

**Times** are in milliseconds into the file. **A center** is `[ x, y ]`, the point of the file in the middle of the media viewer, as a fraction of the file's width and height. `null` means centered.

Errors are as usual: 400 for a bad parameter, 403 for a missing permission, 404 for a counter, playlist, or tag preset that does not exist, 409 for a name that is taken or a playlist that cannot be played, and 422 for a snapshot that will not import.

## counters

### **GET `/manage_counters/get_counters`**

Every counter.

```json
{ "counters" : [ { "counter_id" : "4a2f...", "name" : "watched" } ] }
```

### **POST `/manage_counters/add_counter`**

Arguments: `name`. The name cannot already be taken. Returns the new `counter`.

### **POST `/manage_counters/rename_counter`**

Arguments: a counter, `new_name`. Its counts stay with it. Returns the `counter`.

### **POST `/manage_counters/delete_counter`**

Arguments: a counter. Every file's count for it is deleted too.

### **GET `/manage_counters/get_counts`**

Arguments: files. A count is left out when it is 0.

```json
{
  "counters" : [ { "counter_id" : "4a2f...", "name" : "watched" } ],
  "counts" : { "6c37..." : { "4a2f..." : 3 } }
}
```

### **POST `/manage_counters/set_count`**

Arguments: files, a counter, `count` (0 or more).

### **POST `/manage_counters/increment_count`**

Arguments: files, a counter, `delta` (optional, default 1, can be less than 0). A count never goes below 0.

### **POST `/manage_counters/convert_tags_to_counters`**

Turns "namespace:number" tags into counters, like _tags->to counter_. The tags are deleted, and a counter is made for any namespace that does not have one. A file with more than one, like items:3 and items:5, gets the higher number.

Arguments: `tag_service_key` (a local tag service), `tag_filter` (like `items:*` or `items:72`), `preview` (optional, default false: with true, nothing changes).

```json
{
  "namespaces" : { "items" : { "num_tags" : 4, "num_files" : 3, "new_counter" : true } },
  "num_tags" : 4,
  "num_files" : 3
}
```

`num_tags` and `num_files` are only there when it was not a preview.

## playlists

An item is `{ "hash" : "...", "start_ms" : null, "end_ms" : null, "reverse" : false }` for a file, where a null start and end is the whole file, or `{ "blank_ms" : 1500 }` for a blank: a stretch of nothing, 1ms to an hour. Most of these return the `playlist`: `{ "playlist_id" : 3, "name" : "morning run", "num_items" : 4 }`.

### **GET `/manage_playlists/get_playlists`**

Every playlist. With a file, just the ones that file is in, and `num_items` is how many times it is in each.

```json
{ "playlists" : [ { "playlist_id" : 3, "name" : "morning run", "num_items" : 4 } ] }
```

### **GET `/manage_playlists/get_playlist`**

Arguments: a playlist. Returns the `playlist`, with its `items` in order.

### **POST `/manage_playlists/new_playlist`**

Arguments: `name`. Makes an empty playlist. The name cannot already be taken.

### **POST `/manage_playlists/rename_playlist`**

Arguments: a playlist, `new_name`.

### **POST `/manage_playlists/delete_playlist`**

Arguments: a playlist.

### **POST `/manage_playlists/add_files`**

Arguments: a playlist, files, `start_ms` and `end_ms` (optional, both or neither). The files go on the end, in the order given.

### **POST `/manage_playlists/add_blank`**

Arguments: a playlist, `blank_ms`. The blank goes on the end.

### **POST `/manage_playlists/remove_files`**

Arguments: a playlist, files. Every item of each file goes, whatever its span.

### **POST `/manage_playlists/set_items`**

Arguments: a playlist, `items`. All of its items, in order, replacing what it had.

## virtual paths

Paths are cleaned up the way the client does it: not case-sensitive, with no spaces or empty folders, so `TV Shows\Action` is `tv_shows/action`. A path cannot have a `*` in it.

### **GET `/manage_virtual_paths/get_paths`**

Arguments: files.

```json
{ "paths" : { "6c37..." : [ "tv_shows/action" ] } }
```

### **GET `/manage_virtual_paths/get_all_paths`**

Every path any file has, as `paths`.

### **POST `/manage_virtual_paths/set_paths`**, **`add_paths`**, **`remove_paths`**

Arguments: files, `paths`. `set_paths` gives each file exactly those paths, and an empty list clears them. Each returns every file's `paths` afterwards.

## snapshots

### **GET `/manage_snapshots/get_snapshots`**

Arguments: files. The snapshots taken from each, in the order they come in the file. `snapshots_file_service_key` is the snapshots file domain, which is `null` until the first snapshot is taken.

```json
{
  "snapshots_file_service_key" : "9e1d...",
  "snapshots" : { "6c37..." : [ "0b7a...", "f3c2..." ] }
}
```

### **POST `/manage_snapshots/add_snapshot`**

Imports an image as a snapshot of a file. Needs 'import and delete files' too, since it imports from a path.

Arguments: one file (the one it was taken from), `path` (the image, on the client's computer), `timestamp_ms` (optional, where in the file it was taken from). Returns the `snapshot_hash`.

## media viewer data

What the media viewer remembers for each file. Rotation and saved zoom are picked up the next time a media viewer shows the file. Position timestamps, playback skips, freezes, scripted events, and the image overlay are picked up straight away by media viewers that are showing it. Saved A-B loops are read each time the media viewer's _A-B_ menu opens.

A file's saved zoom and pan are kept for each screen it is shown on, so a media viewer moved to another monitor puts the file back how it was left there. Screens go by the name your system gives them, like `\\.\DISPLAY1` or a monitor's model name, which `/manage_media_viewers/get_screens` lists. A file can also have a zoom for any screen, which is what every saved zoom was before they were per screen: a screen without one of its own uses that, or else the default zoom.

### **GET `/manage_file_viewer_data/get_data`**

Arguments: one file.

```json
{
  "hash" : "6c37...",
  "rotation" : 90,
  "zoom" : { "zoom" : 2.0, "center" : [ 0.25, 0.75 ] },
  "screen_zooms" : [ { "screen_name" : "\\\\.\\DISPLAY2", "zoom" : 0.5, "center" : null } ],
  "position_timestamps" : [ { "timestamp_ms" : 1000, "zoom" : 1.5, "zoom_is_relative" : true, "center" : null, "rotation" : 90 } ],
  "playback_skips" : [ { "start_ms" : 0, "end_ms" : 500 } ],
  "playback_freezes" : [ { "timestamp_ms" : 3000, "duration_ms" : 2000 } ],
  "ab_loops" : [ { "a_ms" : 5250, "b_ms" : 12000 } ],
  "segments" : [ { "timestamp_ms" : 100, "name" : "intro" } ],
  "scripted_events" : [ { "timestamp_ms" : 50, "command" : "echo hi" } ],
  "image_overlay" : { "path" : "C:\\overlays\\frame.png", "opacity" : 0.5, "x" : 0.1, "y" : 0.2, "width" : 0.3, "height" : 0.4, "locked" : true, "stretch" : false }
}
```

`zoom` is the one for any screen, and `screen_zooms` are each screen's own. A null `zoom` is the normal default zoom. A screen's with a null `zoom` and `center` is the default zoom on that screen, whatever there is for any screen. A position timestamp's zoom is relative to the zoom that fits the file in the window, so 1.0 is 'fit'. Old ones from before that have `zoom_is_relative` false. Its `rotation` is null when it leaves the file turned however it is. `image_overlay` is null when there is not one.

### **GET `/manage_file_viewer_data/get_saved_zoom_counts`**

`num_files_with_saved_zoom` and `num_files_with_position_timestamps`.

### **POST `/manage_file_viewer_data/set_rotation`**

Arguments: files, `rotation`, in degrees clockwise. It is rounded to whole degrees, 0 to 359.

### **POST `/manage_file_viewer_data/set_zoom`**

Arguments: files, `zoom` (optional, more than 0), `center` (optional), `screen_name` (optional). Without a `screen_name`, it is the zoom for any screen without one of its own, and with neither `zoom` nor `center`, the files go back to normal. With one, it is just that screen's, and with neither, the files open at the default zoom on that screen.

### **POST `/manage_file_viewer_data/set_position_timestamps`**

Arguments: one file, `position_timestamps`: a list of `{ "timestamp_ms", "zoom", "center", "rotation" }`, where `center` and `rotation` are optional. They replace what the file had. A later one for the same time wins.

### **POST `/manage_file_viewer_data/set_playback_skips`**

Arguments: one file, `playback_skips`: a list of `{ "start_ms", "end_ms" }`. They replace what the file had, and ones that overlap or touch become one. Returns the `playback_skips` as saved.

### **POST `/manage_file_viewer_data/set_playback_freezes`**

Arguments: one file, `playback_freezes`: a list of `{ "timestamp_ms", "duration_ms" }`. When normal playback gets to `timestamp_ms`, the media viewer holds that frame for `duration_ms`, which is 100 to 3,600,000 (an hour), and then plays on. They replace what the file had. A point has one freeze, and a later one for the same point wins. Returns the `playback_freezes` as saved.

### **POST `/manage_file_viewer_data/set_ab_loops`**

Arguments: one file, `ab_loops`: a list of `{ "a_ms", "b_ms" }`. These are the A-B repeat loops saved on the file, which the media viewer's _A-B_ menu lists, to put back on with a click. `b_ms` has to be at least 100ms after `a_ms`, and a loop from the start of the file has an `a_ms` of 0. They replace what the file had, and the same loop is only saved once. Returns the `ab_loops` as saved. `/manage_media_viewers/set_ab_repeat` puts one on in a media viewer.

### **POST `/manage_file_viewer_data/set_segments`**

Arguments: one file, `segments`: a list of `{ "timestamp_ms", "name" }`. They replace what the file had.

### **POST `/manage_file_viewer_data/set_scripted_events`**

Needs permission 107. Arguments: one file, `scripted_events`: a list of `{ "timestamp_ms", "command" }`. They replace what the file had.

### **POST `/manage_file_viewer_data/set_image_overlay`**

Arguments: one file, `image_overlay`: `{ "path", "opacity", "x", "y", "width", "height", "locked", "stretch" }`, or null to take it away. `path` has to be an image file on the client's computer. `opacity` is 0 to 1, default 1. `x`, `y`, `width`, and `height` are fractions of the media viewer's size, default the whole of it. `locked` lets clicks go through it, and `stretch` fills its box rather than keeping its shape, both default false.

### **GET `/manage_file_viewer_data/get_ignore_saved_positions`**

Whether the media viewer is ignoring what files have saved, as `ignore_saved_positions`.

### **POST `/manage_file_viewer_data/set_ignore_saved_positions`**

Arguments: `ignore_saved_positions`. Like the media viewer's _zoom->ignore saved zooms and pans_. With true, the media viewer opens every file at the normal default zoom, fit to the window and centered, whatever saved zoom, pan, and position timestamps it has, and it does not save any new zoom or pan. How a file is turned still counts. Nothing is deleted, so with false, files open how they were left again. Media viewers that are open change straight away, and it stays set when the client restarts.

### **POST `/manage_file_viewer_data/reset_all_zooms`**

For every file at once, like _reset all saved zooms_. Arguments: `saved_zooms` and/or `position_timestamps`, set to true for what to clear.

### **POST `/manage_file_viewer_data/reset_positions`**

For some files, or every file in a page, like a page tab's _reset all positions_. Arguments: files, or a `page_key` (which needs 'manage pages' too), and what to reset: `saved_zooms` (the zoom and pan, default true), `rotations` (how it is turned, default true), and `position_timestamps` (default false). Media viewers showing one of the files go back to normal straight away. Returns `num_files`, how many files there were. A page_key for a page that does not exist gives a 404.

## tag presets

A tag preset is a named list of search entries that `system:presets name` expands to. Preset names are not case-sensitive, and an underscore counts as a space. Entries are lowercased, with extra spaces taken out. These all return every `tag_presets` afterwards.

### **GET `/manage_tag_presets/get_tag_presets`**

```json
{ "tag_presets" : [ { "name" : "Cute Cats", "entries" : [ "cat", "-dog", "system:inbox" ] } ] }
```

### **POST `/manage_tag_presets/set_tag_presets`**

Arguments: `tag_presets`, all of them, replacing what there was.

### **POST `/manage_tag_presets/add_to_tag_preset`**

Arguments: `name`, `entries`. The preset is made if it is new, and entries it already has are skipped.

### **POST `/manage_tag_presets/delete_tag_preset`**

Arguments: `name`.

## screen locations

A screen location is a named spot on a monitor that a media viewer can snap to. `x` and `y` are the window's top-left, relative to the top-left of that screen, and `width` and `height` are its inside size.

### **GET `/manage_screen_locations/get_screen_locations`**

```json
{ "screen_locations" : [ { "name" : "left", "screen_name" : "\\\\.\\DISPLAY1", "x" : 0, "y" : 0, "width" : 960, "height" : 1040 } ] }
```

### **POST `/manage_screen_locations/set_screen_locations`**

Arguments: `screen_locations`, all of them, replacing what there was. Names have to be different, not case-sensitive.

## exports

These make a new file on the client's computer, in the background, with a popup in the client to follow along. `path` has to be a full path, in a folder that exists, and the right extension goes on the end if it is missing. They never write over a file that is already there: you get a 409. Each returns the `path` it is making, and a `job_status_key`: the popup, which `/manage_popups/get_popups` can show you.

Like the media viewer's A-B repeat points, `start_ms` and `end_ms` (optional, both or neither) export just part of the file.

### **POST `/manage_exports/export_video`**

Arguments: one video, `path`, `start_ms` and `end_ms`, and these, all optional:

- `format`: `mp4` (h.264 and aac, the default), `webm` (vp9 and opus), or `original` (the file copied as it is. Not for part of a file)
- `resolution`: `[ width, height ]`, made even if it is not. Default is the file's own
- `framerate`: default is the file's own
- `audio_kbps`: one of 192, 128, 96, 64. Default 128, and null for no sound
- `quality`: `best`, `high` (the default), `medium`, `low`, or `lowest`
- `target_size_bytes`: fit it in this size, rather than going by `quality`

### **POST `/manage_exports/export_audio`**

Arguments: one video or audio file that has sound, `path`, `start_ms` and `end_ms`, and these, all optional:

- `format`: `mp3` (the default) or `wav`
- `mp3_kbps`: one of 320, 256, 192, 160, 128, 96, 64. Default 192
- `wav_bit_depth`: 16 (the default) or 24
- `sample_rate`: one of 48000, 44100, 32000, 22050. Default is the file's own
- `channels`: 2 or 1. Default is the file's own

### **POST `/manage_exports/export_playlist`**

Needs 'manage playlists' too. Arguments: a playlist, `path`. Makes one mp4 of it, in order. It always plays forwards, and blanks are black and silence. A file that was deleted is skipped. If none of its files can be exported, you get a 409.

## media viewers

These open windows in the client, so they need 'manage pages', like `/manage_pages/get_media_viewers`.

### **GET `/manage_media_viewers/get_layout`**

The media viewers that are open now, as a `layout`: the same json as a media viewer layout file saved from the client.

### **POST `/manage_media_viewers/open_layout`**

Arguments: `layout`. Opens its media viewers. One whose files can all no longer be shown is skipped. Returns `num_opened` and `num_skipped`.

### **POST `/manage_media_viewers/open_playlist`**

Needs 'manage playlists' too. Arguments: a playlist. Plays it in a new media viewer. If it is empty, or none of its files can be shown, nothing opens and you get a 409 saying why.

### **GET `/manage_media_viewers/get_screens`**

The screens connected now, the main one first, with where they are on the desktop, and the screen each media viewer that is open now is on, with the `hash` of the file it is showing (null for none).

```json
{
  "screens" : [ { "screen_name" : "\\\\.\\DISPLAY1", "x" : 0, "y" : 0, "width" : 1920, "height" : 1080, "primary" : true } ],
  "media_viewers" : [ { "canvas_key" : "a1b2...", "screen_name" : "\\\\.\\DISPLAY1", "hash" : "6c37..." } ]
}
```

### **POST `/manage_media_viewers/apply_screen_zoom`**

Arguments: `screen_name`, and `canvas_key` (optional, default every media viewer that is open). Like the media viewer's _screen->zoom and pan as on_: the file goes how it is zoomed and panned on that screen, and that is saved for the screen the media viewer is on. A screen it has nothing for is the default zoom, centered. Media viewers that do not remember zooms, like the duplicate filter, and ones set to ignore saved zooms leave their files alone. Returns `num_media_viewers`. A canvas_key for a media viewer that is not open gives a 404.

### **GET `/manage_media_viewers/get_slideshows`**

The slideshow of each media viewer that is open now. A null `period` is one that has not had a slideshow yet. A `period` of 0 is one that plays each file once through. Playlists and the filters cannot run a slideshow, so they have `supports_slideshow` false.

```json
{ "media_viewers" : [ { "canvas_key" : "a1b2...", "supports_slideshow" : true, "running" : true, "period" : 0.0 } ] }
```

### **POST `/manage_media_viewers/start_slideshow`**

Arguments: `period`, in seconds, and `canvas_key` (optional, default every media viewer that is open that can run one). A `period` of 0 plays each file once through, without looping, and moves on as soon as it is done. Images, which have nothing to play, stay up for the first of your slideshow durations, like they do in a playlist. Returns `num_media_viewers`, how many it was started in. A canvas_key for a media viewer that is not open, or cannot run a slideshow, gives a 404.

### **POST `/manage_media_viewers/stop_slideshow`**

Arguments: `canvas_key` (optional, default every media viewer that is open that can run one). Returns `num_media_viewers`. A canvas_key for a media viewer that is not open, or cannot run a slideshow, gives a 404.

### **GET `/manage_media_viewers/get_ab_repeat`**

The A-B repeat of each media viewer that is open now. `canvas_key` is the same one `/manage_pages/get_media_viewers` gives. A null `b_ms` means it is not looping, and a null `a_ms` means the loop starts at the start of the file.

```json
{ "media_viewers" : [ { "canvas_key" : "a1b2...", "a_ms" : 1000, "b_ms" : 4500, "ping_pong" : false } ] }
```

### **POST `/manage_media_viewers/set_ab_repeat`**

Arguments: `a_ms` and `b_ms` (both optional), and `canvas_key` (optional, default every media viewer that is open). Like the A and B buttons, or clicking a saved A-B loop: with a `b_ms`, the media viewer loops from `a_ms` (or the start, with none) to `b_ms`, and playback goes to the start of the loop so it plays straight away. `b_ms` has to be at least 100ms after that. With just an `a_ms`, it is marked and not looping yet, and with neither, the points are cleared. Media viewers showing a file with no playback leave it alone. Returns `num_media_viewers`, how many it was set for. A canvas_key for a media viewer that is not open gives a 404.

### **POST `/manage_media_viewers/set_ab_repeat_ping_pong`**

Arguments: `ping_pong`, and `canvas_key` (optional, default every media viewer that is open). Like the media viewer's _L_ button: with true, an A-B repeat plays backwards from B to A and then forwards again, rather than jumping back to A. It stays on for the files that media viewer shows next. Only mpv and the native animation player can play backwards, so with the Qt media player the loop jumps back as normal. Returns `num_media_viewers`, how many it was set for. A canvas_key for a media viewer that is not open gives a 404.
