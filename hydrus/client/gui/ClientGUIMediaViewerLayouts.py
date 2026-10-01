import os

from qtpy import QtWidgets as QW

from hydrus.core import HydrusData
from hydrus.core import HydrusNumbers

from hydrus.client import ClientConstants as CC
from hydrus.client import ClientGlobals as CG
from hydrus.client import ClientLocation
from hydrus.client import ClientMediaViewerLayouts
from hydrus.client import ClientScreenLocations
from hydrus.client.gui import ClientGUIDialogsMessage
from hydrus.client.gui import ClientGUIScreenLocations
from hydrus.client.gui.canvas import ClientGUICanvas
from hydrus.client.gui.canvas import ClientGUICanvasFrame
from hydrus.client.media import ClientMedia

# where the last layout file was saved or loaded, this session, so the next one starts there
LAST_MEDIA_VIEWER_LAYOUT_DIR = None

MEDIA_VIEWER_LAYOUT_FILE_WILDCARD = 'media viewer layout (*.json)'

def CanvasIsSaveableInALayout( canvas_window ) -> bool:
    
    # the normal media viewer. the filters and playlists have their own state, so they are left out
    return type( canvas_window ) is ClientGUICanvas.CanvasMediaListBrowser
    

def GetMediaViewerLayoutForFrame( canvas_frame: ClientGUICanvasFrame.CanvasFrame ) -> ClientMediaViewerLayouts.MediaViewerLayout | None:
    
    canvas_window = canvas_frame.GetCanvas()
    
    if canvas_window is None or not CanvasIsSaveableInALayout( canvas_window ):
        
        return None
        
    
    view = canvas_window.GetMediaViewerLayoutView()
    
    if view is None:
        
        return None
        
    
    ( hashes, current_hash, relative_zoom, center, playback_ms ) = view
    
    hashes = ClientMediaViewerLayouts.GetHashesAroundCurrent( hashes, current_hash, ClientMediaViewerLayouts.MEDIA_VIEWER_LAYOUT_MAX_HASHES )
    
    screen = canvas_frame.screen()
    screen_geometry = screen.geometry()
    
    maximised = canvas_frame.isMaximized()
    fullscreen = canvas_frame.isFullScreen()
    
    if maximised or fullscreen:
        
        # where it goes back to when it is a normal window again
        geometry = canvas_frame.normalGeometry()
        
        ( x, y ) = ( geometry.x(), geometry.y() )
        
    else:
        
        geometry = canvas_frame.frameGeometry()
        
        ( x, y ) = ( geometry.x(), geometry.y() )
        
        geometry = canvas_frame.geometry()
        
    
    return ClientMediaViewerLayouts.MediaViewerLayout(
        hashes,
        current_hash,
        screen.name(),
        x - screen_geometry.x(),
        y - screen_geometry.y(),
        max( 1, geometry.width() ),
        max( 1, geometry.height() ),
        maximised = maximised,
        fullscreen = fullscreen,
        relative_zoom = relative_zoom,
        center = center,
        playback_ms = playback_ms
    )
    

def GetOpenMediaViewerLayouts() -> list[ ClientMediaViewerLayouts.MediaViewerLayout ]:
    
    # every normal media viewer that is open now, in the order they were opened
    media_viewer_layouts = []
    
    for canvas_frame in CG.client_controller.gui.GetCanvasFrames():
        
        if not canvas_frame.isVisible():
            
            # it is closing
            continue
            
        
        media_viewer_layout = GetMediaViewerLayoutForFrame( canvas_frame )
        
        if media_viewer_layout is not None:
            
            media_viewer_layouts.append( media_viewer_layout )
            
        
    
    return media_viewer_layouts
    

def OpenMediaViewerLayouts( media_viewer_layouts: list[ ClientMediaViewerLayouts.MediaViewerLayout ] ) -> tuple[ int, int ]:
    
    # opens a media viewer for each one. returns ( num_opened, num_skipped ). one is skipped if none of its files can be shown any more
    if len( media_viewer_layouts ) == 0:
        
        return ( 0, 0 )
        
    
    all_hashes = set()
    
    for media_viewer_layout in media_viewer_layouts:
        
        all_hashes.update( media_viewer_layout.hashes )
        
    
    media_results = CG.client_controller.Read( 'media_results', all_hashes )
    
    # a file that was deleted, or that the media viewer cannot show, is left out
    hashes_to_media_results = { media_result.GetHash() : media_result for media_result in media_results if media_result.GetLocationsManager().IsLocal() and ClientMedia.CanDisplayMediaResult( media_result ) }
    
    screen_geometries = ClientGUIScreenLocations.GetCurrentScreenGeometries()
    
    num_opened = 0
    num_skipped = 0
    
    for media_viewer_layout in media_viewer_layouts:
        
        if OpenMediaViewerLayout( media_viewer_layout, hashes_to_media_results, screen_geometries ):
            
            num_opened += 1
            
        else:
            
            num_skipped += 1
            
        
    
    return ( num_opened, num_skipped )
    

def OpenMediaViewerLayout( media_viewer_layout: ClientMediaViewerLayouts.MediaViewerLayout, hashes_to_media_results: dict, screen_geometries: list[ ClientScreenLocations.ScreenGeometry ] ) -> bool:
    
    media_results = [ hashes_to_media_results[ hash ] for hash in media_viewer_layout.hashes if hash in hashes_to_media_results ]
    
    if len( media_results ) == 0:
        
        return False
        
    
    current_hash = media_viewer_layout.current_hash
    
    file_is_still_here = current_hash in hashes_to_media_results
    
    if not file_is_still_here:
        
        # it browses what is left, from the top
        current_hash = media_results[0].GetHash()
        
    
    gui = CG.client_controller.gui
    
    canvas_frame = ClientGUICanvasFrame.CanvasFrame( gui )
    
    page_key = HydrusData.GenerateKey()
    location_context = ClientLocation.LocationContext.STATICCreateSimple( CC.COMBINED_LOCAL_FILE_DOMAINS_SERVICE_KEY )
    
    canvas_window = ClientGUICanvas.CanvasMediaListBrowser( canvas_frame, page_key, location_context, media_results, current_hash )
    
    canvas_window.canvasWithHoversExiting.connect( gui.NotifyMediaViewerExiting )
    
    canvas_frame.SetCanvas( canvas_window )
    
    MoveWindowToMediaViewerLayout( canvas_frame, media_viewer_layout, screen_geometries )
    
    if file_is_still_here:
        
        canvas_window.SetPendingLayoutView( current_hash, media_viewer_layout.relative_zoom, media_viewer_layout.center, media_viewer_layout.playback_ms )
        
    
    return True
    

def MoveWindowToMediaViewerLayout( window: QW.QWidget, media_viewer_layout: ClientMediaViewerLayouts.MediaViewerLayout, screen_geometries: list[ ClientScreenLocations.ScreenGeometry ] ):
    
    # like going to a screen location, but quietly. if its screen is not connected, it goes to the main screen
    ( found_the_screen, x, y, width, height ) = ClientScreenLocations.GetTargetGeometry( media_viewer_layout.GetScreenLocation(), screen_geometries )
    
    if window.isFullScreen() or window.isMaximized():
        
        window.showNormal()
        
    
    # moving onto a screen with a different scale can resize the window, so the size goes on once it is there
    window.move( x, y )
    window.resize( width, height )
    window.move( x, y )
    
    if media_viewer_layout.fullscreen:
        
        window.showFullScreen()
        
    elif media_viewer_layout.maximised:
        
        window.showMaximized()
        
    


def _GetFileDialogOptions():
    
    options = QW.QFileDialog.Option.DontResolveSymlinks
    
    if CG.client_controller.new_options.GetBoolean( 'use_qt_file_dialogs' ):
        
        options |= QW.QFileDialog.Option.DontUseNativeDialog
        
    
    return options
    

def _GetStartingDir() -> str:
    
    return LAST_MEDIA_VIEWER_LAYOUT_DIR if LAST_MEDIA_VIEWER_LAYOUT_DIR is not None else os.path.expanduser( '~' )
    

def LoadMediaViewerLayoutFromFile( win: QW.QWidget ):
    
    # asks for a layout file, and opens its media viewers where they were
    global LAST_MEDIA_VIEWER_LAYOUT_DIR
    
    path = QW.QFileDialog.getOpenFileName( win, 'load media viewer layout', _GetStartingDir(), filter = MEDIA_VIEWER_LAYOUT_FILE_WILDCARD, selectedFilter = MEDIA_VIEWER_LAYOUT_FILE_WILDCARD, options = _GetFileDialogOptions() )[0]
    
    if path == '':
        
        return
        
    
    LAST_MEDIA_VIEWER_LAYOUT_DIR = os.path.dirname( path )
    
    try:
        
        with open( path, 'r', encoding = 'utf-8' ) as f:
            
            text = f.read()
            
        
        media_viewer_layouts = ClientMediaViewerLayouts.ConvertJSONToMediaViewerLayouts( text )
        
    except ( OSError, UnicodeDecodeError, ValueError ) as e:
        
        ClientGUIDialogsMessage.ShowWarning( win, f'Could not load that media viewer layout!\n\n{e}' )
        
        return
        
    
    if len( media_viewer_layouts ) == 0:
        
        ClientGUIDialogsMessage.ShowInformation( win, 'That media viewer layout has no media viewers in it!' )
        
        return
        
    
    ( num_opened, num_skipped ) = OpenMediaViewerLayouts( media_viewer_layouts )
    
    if num_skipped > 0:
        
        message = f'{HydrusNumbers.ToHumanInt( num_skipped )} of the media viewers in that layout were not opened, since none of their files can be shown--they were probably deleted.'
        
        ClientGUIDialogsMessage.ShowWarning( win, message )
        
    

def SaveMediaViewerLayoutToFile( win: QW.QWidget ):
    
    # saves the media viewers that are open now, so they can all be opened again, just like this, later
    global LAST_MEDIA_VIEWER_LAYOUT_DIR
    
    media_viewer_layouts = GetOpenMediaViewerLayouts()
    
    if len( media_viewer_layouts ) == 0:
        
        ClientGUIDialogsMessage.ShowInformation( win, 'There are no media viewers open to save! Open the files you want, put their media viewers where you like them, zoom and pan them how you like, and then save them.' )
        
        return
        
    
    starting_path = os.path.join( _GetStartingDir(), 'media viewers.json' )
    
    path = QW.QFileDialog.getSaveFileName( win, 'save media viewer layout', starting_path, filter = MEDIA_VIEWER_LAYOUT_FILE_WILDCARD, selectedFilter = MEDIA_VIEWER_LAYOUT_FILE_WILDCARD, options = _GetFileDialogOptions() )[0]
    
    if path == '':
        
        return
        
    
    if not path.lower().endswith( '.json' ):
        
        path += '.json'
        
    
    LAST_MEDIA_VIEWER_LAYOUT_DIR = os.path.dirname( path )
    
    text = ClientMediaViewerLayouts.ConvertMediaViewerLayoutsToJSON( media_viewer_layouts )
    
    try:
        
        with open( path, 'w', encoding = 'utf-8' ) as f:
            
            f.write( text )
            
        
    except OSError as e:
        
        ClientGUIDialogsMessage.ShowWarning( win, f'Could not save the media viewer layout!\n\n{e}' )
        
        return
        
    
    HydrusData.ShowText( f'Saved {HydrusNumbers.ToHumanInt( len( media_viewer_layouts ) )} media viewers to {path}.' )
    
