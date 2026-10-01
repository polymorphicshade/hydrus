# TODO
1. Add the ability to export sound from a video.
   - similar to exporting video, but simply just WAV or MP3
   - provide standard (simple) controls for quality
   - if A-B is defined, just export that segment of audio
2. Add the ability to export a clip from a video (using A-B to select start/end, and a)
   - "export video" menu item wil only export timestamps A to B (if both are defined, otherwise export the entire video)
3. in playlist editor, add ability to reverse play-back a playlist item
4. Add ability to restore the last open pages (along with their screen locations, zoom level, pan coordinates, etc)
5. Add ability to save/load which media items are open (and their coordinates, zoom levels, etc)
   - save/load as JSON
   - when loaded, it auto-opens each media item in their respective locations and configurations
   - for example: user wants to save where things are so when they reboot, they can quickly get back to viewing their media in the same manner
   - this is meant for groups of media items, so add a button under "special" when opening a new tab
6. Add ability to rotate the displayed media (photos and video)
   - have the media item remember a changed orientation (so the next time the media viewer opens, the media is already rotated)
   - add a context menu in the media item viewer called "orientation"
     - add menu items for 0, 90, 270, 360, custom... (custom shows a simple dialog to input the rotation angle)
7. Allow filtering by media items with snapshots
   - i.e. "system:snapshots" shows media items *with* snapshots
8. Add the ability to filter media items that belong to a specific playlist
   - i.e. "system:playlist my_playlist" - shows only media items that belong to the "my_playlist" playlist
   - u.e. "-system:playlist my_playlist" - shows only media items that *DO NOT* belong to the "my_playlist" playlist
9. Add the ability to open a media item from the playlist editor (so the user can see what it is while editing the playlist).
10. During a playlist playback, add ability to lock the current zoom and pan for all playlist items
    - in the context menu "playlist":
      - "lock position" - when enabled, all playlist items must have the same zoom level and pan coordinates; when disabled, playlist items will show using whatever zoom/pan they had before
11. During a playlist playback, add the ability to make each playlist item loop for X seconds (similar to how the slideshow stuff works).
    - in the "playlist" context menu
      - "looping" - user can specify the amount of loops until next item, or the time (i.e. item loops for N seconds until next item, similar to how the slideshow stuff works)
12. I want media items to also remember their last pan coordinates (saved with remembering last zoom level).








