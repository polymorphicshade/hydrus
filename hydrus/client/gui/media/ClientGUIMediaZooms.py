import collections.abc

from qtpy import QtWidgets as QW

from hydrus.core import HydrusExceptions
from hydrus.core import HydrusNumbers

from hydrus.client import ClientGlobals as CG
from hydrus.client.gui import ClientGUIDialogsMessage
from hydrus.client.gui import ClientGUIDialogsQuick

def GetResetSavedZoomsQuestion( num_file_viewer_zooms: int, num_file_viewer_rotations: int, num_files_with_zoom_timestamps: int ) -> tuple[ str, list[ tuple[ str, tuple[ bool, bool, bool ] ] ] ]:
    
    # the question to ask, and the buttons for it. each button's value is ( clear the saved zooms and pans, clear the rotations, clear the zoom timestamps ), like a page's reset
    lines = []
    
    if num_file_viewer_zooms > 0:
        
        lines.append( f'{HydrusNumbers.ToHumanInt( num_file_viewer_zooms )} files open at a zoom and pan you set on them.' )
        
    
    if num_file_viewer_rotations > 0:
        
        lines.append( f'{HydrusNumbers.ToHumanInt( num_file_viewer_rotations )} files are turned.' )
        
    
    if num_files_with_zoom_timestamps > 0:
        
        lines.append( f'{HydrusNumbers.ToHumanInt( num_files_with_zoom_timestamps )} files have position timestamps, which save a zoom, where the file was panned to, and how it was turned, at points in playback.' )
        
    
    message = '\n'.join( lines )
    message += '\n' * 2
    message += 'Resetting forgets them for every file, and those files go back to your normal default zoom, centered, and not turned. This cannot be undone.'
    
    has_positions = num_file_viewer_zooms > 0 or num_file_viewer_rotations > 0
    
    yes_tuples = []
    
    if has_positions and num_files_with_zoom_timestamps > 0:
        
        yes_tuples.append( ( 'reset everything', ( True, True, True ) ) )
        yes_tuples.append( ( 'keep the position timestamps', ( True, True, False ) ) )
        yes_tuples.append( ( 'just the position timestamps', ( False, False, True ) ) )
        
    elif has_positions:
        
        yes_tuples.append( ( 'reset them', ( True, True, False ) ) )
        
    else:
        
        yes_tuples.append( ( 'reset the position timestamps', ( False, False, True ) ) )
        
    
    return ( message, yes_tuples )
    

def AskToResetAllSavedZooms( win: QW.QWidget ):
    
    num_file_viewer_zooms = CG.client_controller.Read( 'num_file_viewer_zooms' )
    num_file_viewer_rotations = CG.client_controller.Read( 'num_file_viewer_rotations' )
    num_files_with_zoom_timestamps = CG.client_controller.Read( 'num_files_with_zoom_timestamps' )
    
    if num_file_viewer_zooms == 0 and num_file_viewer_rotations == 0 and num_files_with_zoom_timestamps == 0:
        
        ClientGUIDialogsMessage.ShowInformation( win, 'No files have a saved zoom, pan, turn, or position timestamps, so there is nothing to reset.' )
        
        return
        
    
    ( message, yes_tuples ) = GetResetSavedZoomsQuestion( num_file_viewer_zooms, num_file_viewer_rotations, num_files_with_zoom_timestamps )
    
    try:
        
        ( clear_file_viewer_zooms, clear_rotations, clear_zoom_timestamps ) = ClientGUIDialogsQuick.GetYesYesNo( win, message, title = 'reset all positions?', yes_tuples = yes_tuples, no_label = 'forget it' )
        
    except HydrusExceptions.CancelledException:
        
        return
        
    
    ResetAllSavedZooms( clear_file_viewer_zooms, clear_zoom_timestamps, clear_rotations = clear_rotations )
    

def GetResetFileViewerPositionsQuestion( num_files: int, num_file_viewer_zooms: int, num_file_viewer_rotations: int, num_files_with_zoom_timestamps: int ) -> tuple[ str, list[ tuple[ str, tuple[ bool, bool, bool ] ] ] ]:
    
    # the question to ask, and the buttons for it. each button's value is ( clear the saved zooms and pans, clear the rotations, clear the zoom timestamps )
    lines = [ f'Of the {HydrusNumbers.ToHumanInt( num_files )} files in this page:' ]
    
    lines.append( '' )
    
    if num_file_viewer_zooms > 0:
        
        lines.append( f'{HydrusNumbers.ToHumanInt( num_file_viewer_zooms )} open at a zoom and pan you set on them.' )
        
    
    if num_file_viewer_rotations > 0:
        
        lines.append( f'{HydrusNumbers.ToHumanInt( num_file_viewer_rotations )} are turned.' )
        
    
    if num_files_with_zoom_timestamps > 0:
        
        lines.append( f'{HydrusNumbers.ToHumanInt( num_files_with_zoom_timestamps )} have position timestamps, which save a zoom, where the file was panned to, and how it was turned, at points in playback.' )
        
    
    message = '\n'.join( lines )
    message += '\n' * 2
    message += 'Resetting forgets them for these files, and they go back to your normal default zoom, centered, and not turned. Other files keep theirs. This cannot be undone.'
    
    has_positions = num_file_viewer_zooms > 0 or num_file_viewer_rotations > 0
    
    yes_tuples = []
    
    if has_positions and num_files_with_zoom_timestamps > 0:
        
        yes_tuples.append( ( 'reset everything', ( True, True, True ) ) )
        yes_tuples.append( ( 'keep the position timestamps', ( True, True, False ) ) )
        
    elif has_positions:
        
        yes_tuples.append( ( 'reset them', ( True, True, False ) ) )
        
    else:
        
        yes_tuples.append( ( 'reset the position timestamps', ( False, False, True ) ) )
        
    
    return ( message, yes_tuples )
    

def AskToResetFileViewerPositions( win: QW.QWidget, hashes: collections.abc.Collection[ bytes ] ):
    
    hashes = list( hashes )
    
    if len( hashes ) == 0:
        
        ClientGUIDialogsMessage.ShowInformation( win, 'This page has no files, so there is nothing to reset.' )
        
        return
        
    
    num_file_viewer_zooms = CG.client_controller.Read( 'num_file_viewer_zooms', hashes )
    num_file_viewer_rotations = CG.client_controller.Read( 'num_file_viewer_rotations', hashes )
    num_files_with_zoom_timestamps = CG.client_controller.Read( 'num_files_with_zoom_timestamps', hashes )
    
    if num_file_viewer_zooms == 0 and num_file_viewer_rotations == 0 and num_files_with_zoom_timestamps == 0:
        
        ClientGUIDialogsMessage.ShowInformation( win, 'None of the files in this page have a saved zoom, pan, turn, or position timestamps, so there is nothing to reset.' )
        
        return
        
    
    ( message, yes_tuples ) = GetResetFileViewerPositionsQuestion( len( hashes ), num_file_viewer_zooms, num_file_viewer_rotations, num_files_with_zoom_timestamps )
    
    try:
        
        ( clear_file_viewer_zooms, clear_rotations, clear_zoom_timestamps ) = ClientGUIDialogsQuick.GetYesYesNo( win, message, title = 'reset positions?', yes_tuples = yes_tuples, no_label = 'forget it' )
        
    except HydrusExceptions.CancelledException:
        
        return
        
    
    ResetFileViewerPositions( hashes, clear_file_viewer_zooms, clear_rotations, clear_zoom_timestamps )
    

def ResetFileViewerPositions( hashes: collections.abc.Collection[ bytes ], clear_file_viewer_zooms: bool, clear_rotations: bool, clear_zoom_timestamps: bool ):
    
    hashes = set( hashes )
    
    CG.client_controller.WriteSynchronous( 'reset_file_viewer_positions', hashes, clear_file_viewer_zooms, clear_rotations, clear_zoom_timestamps )
    
    # open media viewers hold on to what they loaded for their current file
    CG.client_controller.pub( 'reset_file_viewer_positions', hashes, clear_file_viewer_zooms, clear_rotations, clear_zoom_timestamps )
    

def SetIgnoreSavedPositions( ignore_saved_positions: bool ):
    
    # while this is on, the media viewer leaves every file's saved zoom, pan, and position timestamps alone, so files always open at the default zoom. nothing is deleted
    CG.client_controller.new_options.SetBoolean( 'media_viewer_ignore_saved_positions', ignore_saved_positions )
    
    # open media viewers go to the default zoom, or back to what their current file has saved, straight away
    CG.client_controller.pub( 'media_viewer_ignore_saved_positions' )
    

def ResetAllSavedZooms( clear_file_viewer_zooms: bool, clear_zoom_timestamps: bool, clear_rotations: bool = False ):
    
    if clear_file_viewer_zooms:
        
        CG.client_controller.WriteSynchronous( 'clear_all_file_viewer_zooms' )
        
    
    if clear_rotations:
        
        CG.client_controller.WriteSynchronous( 'clear_all_file_viewer_rotations' )
        
    
    if clear_zoom_timestamps:
        
        CG.client_controller.WriteSynchronous( 'clear_all_file_zoom_timestamps' )
        
    
    # open media viewers hold on to what they loaded for their current file
    CG.client_controller.pub( 'reset_all_file_zooms', clear_file_viewer_zooms, clear_zoom_timestamps, clear_rotations = clear_rotations )
    
