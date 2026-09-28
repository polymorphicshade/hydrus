# TODO
1. Add the ability to randomize a playlist.
   - while playing a playlist, the context-menu should have a toggle called "randomize"
     - when toggled on, all next playlist items are in random order
     - when toggled off, the playlist returns to the video the user toggled-on the randomize feature
2. Add ability to change playlist order manually.
   - add a sub-window to the playlist editor that shows a re-orderable (draggable) list where the user can select an item, and move it up/down the list, or drag-drop it to change it's order
   - add ability to duplicate entries (so special repeats could be made)
   - add ability to remote items from a playlist
3. Add ability to add scripted events.
   - in context menu of media viewer, add "scripting"
     - "add" - shows a dialog representing the current frame (time) that should execute a command string (equivalent to invoking the OS's shell, i.e. "explorer C:\" to open explorer when timestamp is 1:00 or something like that)
     - "manage" - shows a dialog where user can remove or clear the list of scripts
4. Under "playlist -> "add ..." , in the dialog, add the ability to add a new playlist.
5. Fix the zoom timestamp so when setting a zoom level, it also remembers the X/Y coordinate of the output.
6. For the counters, in the media viewer window's context menu, I want a "manage" menu item where I can individually set counts for the media item (instead of having a static set... menu item with an ever-growing list of counters).




