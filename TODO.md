# TODO
1. Add ability to associated virtual paths with a media item
   - for example: "collections/tv_shows/action" can be assigned to a media item so it can be searched for (i.e. system:path is collections/tv_shows/action)
   - spaces aren't supported (if a space is specified, replace with an underscore)
   - wild cards should be supported (i.e. "collections/*/action")
2. I want a playlist editor:
   - add a menu item at the top of the client called "playlists" (next to the "database" menu item)
     - "editor..." opens the playlist editor window:
       - can add/edit/remove playlists
       - editing the playlist content is done in the media viewer:
         - in context menu for media viewer, add a menu item called "playlist":
           - "add" - shows a popup letting the user select a playlist to add the media item to
             - if A-B is defined, only add that timespan to the playlist playback
           - "remove" - removes the media item from the playlist (all playlist items that are associated with that media item)
             - user can add multiple timespans from a media item, so removing the media item from the playlist will remove *all* timespans from the playlist
     - "open..." shows a playlist selection window
       - user can filter by a simple string contains (case-insensitive)
       - when the user selects a playlist to open, a media item viewer is shown (similar to how it works normally), but it plays back each item in the playlist
       - playlist playback can be looped like how normal media items work
   - playlists don't have tags - they are simply identified by name in the UI