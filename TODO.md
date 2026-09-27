# TODO
1. Add "quick view" as a sub-button in the "special" category when opening a new file search page:
   - click this should open a simple text dialog for a single tag, or a tag preset
   - when clicking ok on this dialog, a new page is opened with the search tag (or tag preset, which auto-populates the search with the preset tags) in a random file order, and automatically opens the media viewer on the first item in the page
   - I want this to be a quick way (shortcut) for opening a file search tab, searching for tag(s), sorting by random, and opening the first media item
2. Make it so when modifying the displayed zoom level in a media item, the zoom level is saved for the next time the media item is opened in the viewer.
3. Add the ability to set a zoom level at a current timestamp in a media item's playback:
   - in the "zoom ..." context menu in the media item viewer:
     - add "save current zoom at timestamp" - when clicked, the current zoom level is saved for the next time the playback hits that timestamp (the zoom level is then maintained for the rest of the playback, until the end of playback, or when a new zoom level timestamp is hit)
     - add "clear zoom timestamps" - when clicked, delete all saved zoom timestamps for the current media item
     - the idea is the user can mark multiple points in playback where the zoom level should be changed (i.e. at 5 seconds, zoom to 150%, at 13 seconds, zoom to 70%, at end of playback, reset zoom to whatever the default was or what was saved before closing)