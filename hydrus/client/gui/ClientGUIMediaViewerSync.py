from hydrus.core import HydrusTime

from hydrus.client import ClientGlobals as CG
from hydrus.client.gui import QtPorting as QP
from hydrus.client.media import ClientMedia

# syncing playback: media viewers showing files with playback all go back to the start and play from there at the same moment, for when you want two things playing at exactly the same time

# players take a moment to land a seek, so they all seek to the start paused, and then all play together a moment later
SYNC_START_DELAY_S = 0.25

def GetSyncableMediaViewerCanvases() -> list:
    
    # the open media viewers that are showing a file with playback, in the order they were opened
    from hydrus.client.gui import ClientGUIMediaViewerABRepeat
    
    return [ canvas_window for canvas_window in ClientGUIMediaViewerABRepeat.GetOpenMediaViewerCanvases() if canvas_window.CanSyncPlayback() ]
    

def GetMediaViewerSyncLabel( index: int, canvas_window ) -> str:
    
    # like '2: mp4, 3m 20s', for the menu
    media = canvas_window.GetMedia()
    
    label = f'{index + 1}: {ClientMedia.GetMediasFiletypeSummaryString( [ media ] )}'
    
    duration_ms = media.GetDurationMS()
    
    if duration_ms is not None:
        
        label += f', {HydrusTime.MillisecondsDurationToPrettyTime( duration_ms )}'
        
    
    return label
    

def SyncMediaViewersPlayback( canvas_windows: list ) -> int:
    
    # returns how many were synced. the ones not showing a file with playback are left alone
    canvas_windows = [ canvas_window for canvas_window in canvas_windows if canvas_window.CanSyncPlayback() ]
    
    if len( canvas_windows ) == 0:
        
        return 0
        
    
    for canvas_window in canvas_windows:
        
        canvas_window.PrepareSyncedPlayback()
        
    
    def start_them():
        
        for canvas_window in canvas_windows:
            
            # one may have closed in the meantime
            if QP.isValid( canvas_window ):
                
                canvas_window.StartSyncedPlayback()
                
            
        
    
    CG.client_controller.CallLaterQtSafe( CG.client_controller.gui, SYNC_START_DELAY_S, 'start synced playback', start_them )
    
    return len( canvas_windows )
    

def SyncOpenMediaViewersPlayback( canvas_keys: list[ bytes ] | None = None ) -> int:
    
    # these media viewers, or all of them with no canvas_keys. returns how many were synced
    canvas_windows = GetSyncableMediaViewerCanvases()
    
    if canvas_keys is not None:
        
        canvas_windows = [ canvas_window for canvas_window in canvas_windows if canvas_window.GetCanvasKey() in canvas_keys ]
        
    
    return SyncMediaViewersPlayback( canvas_windows )
    
    
