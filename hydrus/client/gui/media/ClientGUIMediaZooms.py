from qtpy import QtWidgets as QW

from hydrus.core import HydrusExceptions
from hydrus.core import HydrusNumbers

from hydrus.client import ClientGlobals as CG
from hydrus.client.gui import ClientGUIDialogsMessage
from hydrus.client.gui import ClientGUIDialogsQuick

def GetResetSavedZoomsQuestion( num_file_viewer_zooms: int, num_files_with_zoom_timestamps: int ) -> tuple[ str, list[ tuple[ str, tuple[ bool, bool ] ] ] ]:
    
    # the question to ask, and the buttons for it. each button's value is ( clear the saved zooms, clear the zoom timestamps )
    lines = []
    
    if num_file_viewer_zooms > 0:
        
        lines.append( f'{HydrusNumbers.ToHumanInt( num_file_viewer_zooms )} files open at a zoom you set on them.' )
        
    
    if num_files_with_zoom_timestamps > 0:
        
        lines.append( f'{HydrusNumbers.ToHumanInt( num_files_with_zoom_timestamps )} files have zoom timestamps, which save a zoom and where the file was panned to at points in playback.' )
        
    
    message = '\n'.join( lines )
    message += '\n' * 2
    message += 'Resetting forgets them for every file, and those files go back to your normal default zoom, centered. This cannot be undone.'
    
    yes_tuples = []
    
    if num_file_viewer_zooms > 0 and num_files_with_zoom_timestamps > 0:
        
        yes_tuples.append( ( 'reset both', ( True, True ) ) )
        yes_tuples.append( ( 'just the saved zooms', ( True, False ) ) )
        yes_tuples.append( ( 'just the zoom timestamps', ( False, True ) ) )
        
    elif num_file_viewer_zooms > 0:
        
        yes_tuples.append( ( 'reset the saved zooms', ( True, False ) ) )
        
    else:
        
        yes_tuples.append( ( 'reset the zoom timestamps', ( False, True ) ) )
        
    
    return ( message, yes_tuples )
    

def AskToResetAllSavedZooms( win: QW.QWidget ):
    
    num_file_viewer_zooms = CG.client_controller.Read( 'num_file_viewer_zooms' )
    num_files_with_zoom_timestamps = CG.client_controller.Read( 'num_files_with_zoom_timestamps' )
    
    if num_file_viewer_zooms == 0 and num_files_with_zoom_timestamps == 0:
        
        ClientGUIDialogsMessage.ShowInformation( win, 'No files have a saved zoom or zoom timestamps, so there is nothing to reset.' )
        
        return
        
    
    ( message, yes_tuples ) = GetResetSavedZoomsQuestion( num_file_viewer_zooms, num_files_with_zoom_timestamps )
    
    try:
        
        ( clear_file_viewer_zooms, clear_zoom_timestamps ) = ClientGUIDialogsQuick.GetYesYesNo( win, message, title = 'reset all saved zooms?', yes_tuples = yes_tuples, no_label = 'forget it' )
        
    except HydrusExceptions.CancelledException:
        
        return
        
    
    ResetAllSavedZooms( clear_file_viewer_zooms, clear_zoom_timestamps )
    

def ResetAllSavedZooms( clear_file_viewer_zooms: bool, clear_zoom_timestamps: bool ):
    
    if clear_file_viewer_zooms:
        
        CG.client_controller.WriteSynchronous( 'clear_all_file_viewer_zooms' )
        
    
    if clear_zoom_timestamps:
        
        CG.client_controller.WriteSynchronous( 'clear_all_file_zoom_timestamps' )
        
    
    # open media viewers hold on to what they loaded for their current file
    CG.client_controller.pub( 'reset_all_file_zooms', clear_file_viewer_zooms, clear_zoom_timestamps )
    
