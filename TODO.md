# Instructions
For each item, create a side branch and implement it. Do not merge anything.
Name each branch in the form `#-branch-title` where `#` is a number from 1-N where N is the number of TODO items to do.

Any new features added should have an accompanying API access point (if applicable).

# TODO
1. Highlight last opened window with a magenta (#FF00FF) background, but only when enabled in options (pick where to do it, including customizing the background color).
2. Allow user a right-click menu somewhere that let's them replace the image, video, etc with a specific file (use a file dialog)
   - i.e. for when a user wants to fix a media item and replace the deprecated one
3. Allow user to "sync" playback with another media item viewer window (both then start at 0).
   - for when the user wants to have 2 things playing at the exact same time
4. Add ability to mirror horizontally/vertically (put in a menu somewhere that makes sense).
5. Add a "crops" menu (near the "snapshots" menu).
   - alow user to use the overlay rectangle to "crop" an image
   - image is added to a separate "crops" collection (like how snapshots work)
6. Remove the ability to double-click to close a media viewer item (unless there's already a setting for that, in which case just let me know).
7. In a playlist playback, right click menu somewhere called "save playlist AB" - this acts like the normal "save ab" right-click, but uses the current a..b playback from its playlist entry
8. Add a hotkey shortcut (enabled by default) that toggles the visibility of the left/right text (tags, notes, etc) in a media view
   - maybe use CTRL+F10 or something like that
   - the idea is to make the content more immersive
9. Make it so when there's an MPV crash, it recovers gracefully, and without having to restart the app.
10. Change the Notes feature to be a markdown editor and renderer
    - i.e. notes is a tabbed view: "edit" and "view" (view renders the markdown)
11. Sometimes an audio playlist will loop even though I told it to just play each file only once. Fix this bug.

# Future TODO
(ignore this list for now)
1. AI features
   - remove background music
   - remove background noise (keep music)