# Instructions
For each item, create a side branch and implement it. Do not merge anything.
Name each branch in the form `#-branch-title` where `#` is a number from 1-N where N is the number of TODO items to do.

Any new features added should have an accompanying API access point (if applicable).

# TODO
1. Currently media items remember their last positon, zoom, etc. Change it so media items remember these things, but make it per-screen. The goal is to have media items set themselves to their last remembered positon, zoom, etc when media items are moved between screens.
   - also have a context menu in a media item viewer where the user can click on a specific screen and have the media item viewer adjust to fit that screen's remembered postion, zoom, etc
2. Allow "0 second" slideshow advancement (if this doesn't exist already). I want to have the ability to have the slideshow play without looping the playback.
3. Add a context menu called "A-B" in the media item viewer:
   - let the user save the current A-B timestamps for a media item
   - a list of saved A-B timestamps the user can click on to automatically set A-B to the saved timestamps in the playback, so it does the A-B looping automatically
   - this is similar to how a user can save skips


# Future TODO
(ignore this list for now)
1. AI features
   - remove background music
   - remove background noise (keep music)