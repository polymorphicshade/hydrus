# TODO
1. Add the ability to mark a monitor and screen X/Y coordinates for use later.
   - Add a menu item "screen" to the context menu of the media viewer:
     - "save location..." - shows a dialog letting the user name the current screen and coordinates (and width and height), and saves this location to a global list of "screen locations" (manageable in the main options menu in its own category called "screen locations")
       - user can rename and delete screen locations saved here
     - "move to location" - shows a dialog where the user can click on a saved location (by name) and the media viewer window will snap to the screen and X/Y coordinates
       - the width and height will be saved too, so when the media item viewer is moved, it also resizes itself to the saved width and height
2. Add the ability to use tag presets (collection of search tags)
   - add an options category called "tag presets"
     - user can add/edit/remove tag presets by name
     - user can add/remove tags to a tag preset
     - user can quickly search for all tags in a preset by using a search filter like "system:presets my_preset" (this will auto-populate search tags and run the search as if the user entered each tag manually)
     - user can right-click a tag and add it to a tag preset