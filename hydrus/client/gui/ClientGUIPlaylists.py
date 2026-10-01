import collections.abc
import os

from qtpy import QtCore as QC
from qtpy import QtWidgets as QW

from hydrus.core import HydrusConstants as HC
from hydrus.core import HydrusData
from hydrus.core import HydrusExceptions
from hydrus.core import HydrusLists
from hydrus.core import HydrusNumbers
from hydrus.core import HydrusPaths

from hydrus.client import ClientConstants as CC
from hydrus.client import ClientGlobals as CG
from hydrus.client import ClientLocation
from hydrus.client.exporting import ClientExportingPlaylists
from hydrus.client.gui import ClientGUIDialogsMessage
from hydrus.client.gui import ClientGUIDialogsQuick
from hydrus.client.gui import ClientGUIFunctions
from hydrus.client.gui import ClientGUITopLevelWindowsPanels
from hydrus.client.gui import QtPorting as QP
from hydrus.client.gui.canvas import ClientGUICanvasMedia
from hydrus.client.gui.lists import ClientGUIListBoxes
from hydrus.client.gui.panels import ClientGUIScrolledPanels
from hydrus.client.gui.widgets import ClientGUICommon
from hydrus.client.media import ClientMedia
from hydrus.client.media import ClientMediaPlaylists
from hydrus.client.media import ClientMediaResult
from hydrus.client.media import ClientMediaSingle

# ( hash, start_ms, end_ms )
PlaylistItem = tuple[ bytes, int | None, int | None ]

# where the last playlist export went, this session, so the next one starts there
LAST_PLAYLIST_EXPORT_DIR = None

def ConvertPlaylistItemToPretty( name: str, start_ms: int | None, end_ms: int | None ) -> str:
    
    if start_ms is None or end_ms is None:
        
        return name
        
    
    return f'{name} ({ClientGUICanvasMedia.ConvertPlaybackTimestampToString( start_ms )} - {ClientGUICanvasMedia.ConvertPlaybackTimestampToString( end_ms )})'
    

def ConvertPlaylistToPretty( playlist: ClientMediaPlaylists.PlaylistSummary ) -> str:
    
    ( playlist_id, name, num_items ) = playlist
    
    return f'{name} ({HydrusNumbers.ToHumanInt( num_items )} items)'
    

def EditPlaylists( win: QW.QWidget ):
    
    playlists = CG.client_controller.Read( 'playlists' )
    
    with ClientGUITopLevelWindowsPanels.DialogEdit( win, 'edit playlists' ) as dlg:
        
        panel = EditPlaylistsPanel( dlg, playlists )
        
        dlg.SetPanel( panel )
        
        if dlg.exec() == QW.QDialog.DialogCode.Accepted:
            
            CG.client_controller.Write( 'playlists', panel.GetValue() )
            
            for ( playlist_id, items ) in panel.GetEditedItems().items():
                
                CG.client_controller.Write( 'playlist_items', playlist_id, items )
                
            
        
    

def ExportPlaylist( win: QW.QWidget, playlist_name: str, playlist_items: list[ tuple[ ClientMediaResult.MediaResult, int | None, int | None ] ] ):
    
    # asks where to save the mp4, and then makes it in the background, with a popup to follow along
    global LAST_PLAYLIST_EXPORT_DIR
    
    filename = HydrusPaths.SanitizeFilename( playlist_name, False ).strip()
    
    if filename == '':
        
        filename = 'playlist'
        
    
    starting_dir = LAST_PLAYLIST_EXPORT_DIR if LAST_PLAYLIST_EXPORT_DIR is not None else os.path.expanduser( '~' )
    
    starting_path = os.path.join( starting_dir, filename + '.mp4' )
    
    options = QW.QFileDialog.Option.DontResolveSymlinks
    
    if CG.client_controller.new_options.GetBoolean( 'use_qt_file_dialogs' ):
        
        options |= QW.QFileDialog.Option.DontUseNativeDialog
        
    
    wildcard = 'mp4 video (*.mp4)'
    
    path = QW.QFileDialog.getSaveFileName( win, 'export playlist as mp4', starting_path, filter = wildcard, selectedFilter = wildcard, options = options )[0]
    
    if path == '':
        
        return
        
    
    if not path.lower().endswith( '.mp4' ):
        
        path += '.mp4'
        
    
    LAST_PLAYLIST_EXPORT_DIR = os.path.dirname( path )
    
    ClientExportingPlaylists.StartPlaylistExport( playlist_name, playlist_items, path )
    

def GetPlaylistItemNames( hashes: collections.abc.Collection[ bytes ] ) -> dict[ bytes, str ]:
    
    # something to know each file by in a list. its title tags if it has any, or its filetype and a bit of its hash
    media_results = CG.client_controller.Read( 'media_results', hashes )
    
    hashes_to_names = {}
    
    for media_result in media_results:
        
        hash = media_result.GetHash()
        
        name = ClientMediaSingle.MediaSingle( media_result ).GetTitleString()
        
        if name == '':
            
            name = f'{HC.mime_string_lookup.get( media_result.GetMime(), "file" )} {hash.hex()[:12]}'
            
        
        if not media_result.GetLocationsManager().IsLocal():
            
            name += ' (not in your files--it will be skipped)'
            
        
        hashes_to_names[ hash ] = name
        
    
    for hash in hashes:
        
        if hash not in hashes_to_names:
            
            hashes_to_names[ hash ] = f'unknown file {hash.hex()[:12]}'
            
        
    
    return hashes_to_names
    

def PickAndExportPlaylist( win: QW.QWidget ):
    
    playlists = CG.client_controller.Read( 'playlists' )
    
    if len( playlists ) == 0:
        
        ClientGUIDialogsMessage.ShowInformation( win, 'You do not have any playlists yet! Make one under playlists->editor, or add this file to a new one with right-click->playlist->add.' )
        
        return
        
    
    try:
        
        playlist_id = SelectPlaylist( win, 'export playlist', playlists )
        
    except HydrusExceptions.CancelledException:
        
        return
        
    
    playlist_name = { playlist_id : name for ( playlist_id, name, num_items ) in playlists }[ playlist_id ]
    
    items = CG.client_controller.Read( 'playlist_items', playlist_id )
    
    if len( items ) == 0:
        
        ClientGUIDialogsMessage.ShowInformation( win, f'"{playlist_name}" is empty!' )
        
        return
        
    
    media_results = CG.client_controller.Read( 'media_results', { hash for ( hash, start_ms, end_ms ) in items } )
    
    # a file that was deleted is skipped, like when the playlist plays
    hashes_to_media_results = { media_result.GetHash() : media_result for media_result in media_results if media_result.GetLocationsManager().IsLocal() }
    
    playlist_items = [ ( hashes_to_media_results[ hash ], start_ms, end_ms ) for ( hash, start_ms, end_ms ) in items if hash in hashes_to_media_results ]
    
    if len( playlist_items ) == 0:
        
        ClientGUIDialogsMessage.ShowWarning( win, f'None of the files in "{playlist_name}" are in your files any more--they were probably deleted.' )
        
        return
        
    
    ExportPlaylist( win, playlist_name, playlist_items )
    

def SelectPlaylist( win: QW.QWidget, title: str, playlists: list[ ClientMediaPlaylists.PlaylistSummary ] ) -> int:
    
    # raises CancelledException if the user backs out
    with ClientGUITopLevelWindowsPanels.DialogEdit( win, title, frame_key = 'quick_select_dialog' ) as dlg:
        
        panel = SelectPlaylistPanel( dlg, playlists )
        
        dlg.SetPanel( panel )
        
        if dlg.exec() == QW.QDialog.DialogCode.Accepted:
            
            return panel.GetValue()
            
        
        raise HydrusExceptions.CancelledException( 'Dialog cancelled.' )
        
    

def SelectPlaylistOrNewPlaylist( win: QW.QWidget, title: str, playlists: list[ ClientMediaPlaylists.PlaylistSummary ] ) -> int | str:
    
    # an existing playlist's id, or the name for a new one. raises CancelledException if the user backs out
    with ClientGUITopLevelWindowsPanels.DialogEdit( win, title, frame_key = 'quick_select_dialog' ) as dlg:
        
        panel = SelectPlaylistPanel( dlg, playlists, allow_new_playlist = True )
        
        dlg.SetPanel( panel )
        
        if dlg.exec() == QW.QDialog.DialogCode.Accepted:
            
            return panel.GetValue()
            
        
        raise HydrusExceptions.CancelledException( 'Dialog cancelled.' )
        
    

def ViewPlaylistItems( win: QW.QWidget, items: list[ PlaylistItem ] ):
    
    # opens a media viewer on these items' files, so you can see what they are. it starts on the first one, at the start of its part
    # it belongs to win's window, so it works while that is a modal dialog, like the playlist editor
    # the canvas modules import this one, so we cannot import them at the top
    from hydrus.client.gui.canvas import ClientGUICanvas
    from hydrus.client.gui.canvas import ClientGUICanvasFrame
    
    hashes = HydrusLists.DedupeList( [ hash for ( hash, start_ms, end_ms ) in items ] )
    
    media_results = CG.client_controller.Read( 'media_results', hashes )
    
    # a file that was deleted, or that the media viewer cannot show, is skipped
    hashes_to_media_results = { media_result.GetHash() : media_result for media_result in media_results if media_result.GetLocationsManager().IsLocal() and ClientMedia.CanDisplayMediaResult( media_result ) }
    
    viewable_items = [ ( hash, start_ms, end_ms ) for ( hash, start_ms, end_ms ) in items if hash in hashes_to_media_results ]
    
    if len( viewable_items ) == 0:
        
        ClientGUIDialogsMessage.ShowWarning( win, 'Sorry, that file cannot be shown--it was probably deleted.' if len( hashes ) == 1 else 'Sorry, none of those files can be shown--they were probably deleted.' )
        
        return
        
    
    ( first_hash, first_start_ms, first_end_ms ) = viewable_items[0]
    
    media_results = [ hashes_to_media_results[ hash ] for hash in HydrusLists.DedupeList( [ hash for ( hash, start_ms, end_ms ) in viewable_items ] ) ]
    
    canvas_frame = ClientGUICanvasFrame.CanvasFrame( win.window(), set_parent = True )
    
    page_key = HydrusData.GenerateKey()
    location_context = ClientLocation.LocationContext.STATICCreateSimple( CC.COMBINED_LOCAL_FILE_DOMAINS_SERVICE_KEY )
    
    canvas_window = ClientGUICanvas.CanvasMediaListBrowser( canvas_frame, page_key, location_context, media_results, first_hash )
    
    canvas_window.canvasWithHoversExiting.connect( CG.client_controller.gui.NotifyMediaViewerExiting )
    
    if first_start_ms is not None:
        
        canvas_window.SetNextMediaStartMS( first_hash, first_start_ms )
        
    
    canvas_frame.SetCanvas( canvas_window )
    

class EditPlaylistsPanel( ClientGUIScrolledPanels.EditPanel ):
    
    def __init__( self, parent: QW.QWidget, playlists: list[ ClientMediaPlaylists.PlaylistSummary ] ):
        
        super().__init__( parent )
        
        # ( playlist_id, name, num_items ). a new playlist has no id until we save
        self._playlists: list[ tuple[ int | None, str, int ] ] = list( playlists )
        
        help_text = 'Playlists are named lists of files to play one after another. They do not have tags--you just find them by name.'
        help_text += '\n' * 2
        help_text += 'To put a file in a playlist, open it in the media viewer and right-click->playlist->add. If the A-B repeat points are set, only that part of the file goes in. To play a playlist, hit playlists->open.'
        help_text += '\n' * 2
        help_text += 'Hit \'edit items\' to change the order a playlist plays in, repeat items, or take them out.'
        
        st = ClientGUICommon.BetterStaticText( self, label = help_text )
        st.setWordWrap( True )
        
        self._playlists_list = ClientGUIListBoxes.BetterQListWidget( self )
        self._playlists_list.setSelectionMode( QW.QAbstractItemView.SelectionMode.ExtendedSelection )
        
        # playlist_id : items. these are written when this dialog is OKed
        self._playlist_ids_to_edited_items: dict[ int, list[ PlaylistItem ] ] = {}
        
        self._add_button = ClientGUICommon.BetterButton( self, 'add', self._Add )
        self._rename_button = ClientGUICommon.BetterButton( self, 'rename', self._Rename )
        self._edit_items_button = ClientGUICommon.BetterButton( self, 'edit items' + HC.UNICODE_ELLIPSIS, self._EditItems )
        self._delete_button = ClientGUICommon.BetterButton( self, 'delete', self._Delete )
        
        #
        
        self._RefreshList()
        
        #
        
        button_hbox = QP.HBoxLayout()
        
        QP.AddToLayout( button_hbox, self._add_button, CC.FLAGS_EXPAND_BOTH_WAYS )
        QP.AddToLayout( button_hbox, self._rename_button, CC.FLAGS_EXPAND_BOTH_WAYS )
        QP.AddToLayout( button_hbox, self._edit_items_button, CC.FLAGS_EXPAND_BOTH_WAYS )
        QP.AddToLayout( button_hbox, self._delete_button, CC.FLAGS_EXPAND_BOTH_WAYS )
        
        vbox = QP.VBoxLayout()
        
        QP.AddToLayout( vbox, st, CC.FLAGS_EXPAND_PERPENDICULAR )
        QP.AddToLayout( vbox, self._playlists_list, CC.FLAGS_EXPAND_BOTH_WAYS )
        QP.AddToLayout( vbox, button_hbox, CC.FLAGS_EXPAND_PERPENDICULAR )
        
        self.widget().setLayout( vbox )
        
        self._playlists_list.itemSelectionChanged.connect( self._UpdateButtons )
        self._playlists_list.itemDoubleClicked.connect( self._Rename )
        
        self._UpdateButtons()
        
    
    def _Add( self ):
        
        try:
            
            name = self._EnterName( '' )
            
        except HydrusExceptions.VetoException:
            
            return
            
        
        playlist = ( None, name, 0 )
        
        self._playlists.append( playlist )
        
        self._RefreshList( select_playlist = playlist )
        
    
    def _Delete( self ):
        
        selected_playlists = self._playlists_list.GetData( only_selected = True )
        
        if len( selected_playlists ) == 0:
            
            return
            
        
        num_items = sum( ( num_items for ( playlist_id, name, num_items ) in selected_playlists ) )
        
        message = f'Delete {HydrusNumbers.ToHumanInt( len( selected_playlists ) )} playlists?'
        
        if num_items > 0:
            
            message += f' They have {HydrusNumbers.ToHumanInt( num_items )} items between them. The files themselves are not touched.'
            
        
        result = ClientGUIDialogsQuick.GetYesNo( self, message )
        
        if result != QW.QDialog.DialogCode.Accepted:
            
            return
            
        
        self._playlists = [ playlist for playlist in self._playlists if playlist not in selected_playlists ]
        
        self._RefreshList()
        
    
    def _EditItems( self ):
        
        selected_playlists = self._playlists_list.GetData( only_selected = True )
        
        if len( selected_playlists ) != 1:
            
            return
            
        
        ( selected_playlist, ) = selected_playlists
        
        index = self._playlists.index( selected_playlist )
        
        ( playlist_id, name, num_items ) = self._playlists[ index ]
        
        if playlist_id is None:
            
            # a new playlist has nothing in it yet
            return
            
        
        if playlist_id in self._playlist_ids_to_edited_items:
            
            items = self._playlist_ids_to_edited_items[ playlist_id ]
            
        else:
            
            items = CG.client_controller.Read( 'playlist_items', playlist_id )
            
        
        hashes_to_names = GetPlaylistItemNames( { hash for ( hash, start_ms, end_ms ) in items } )
        
        with ClientGUITopLevelWindowsPanels.DialogEdit( self, f'edit items: {name}' ) as dlg:
            
            panel = EditPlaylistItemsPanel( dlg, items, hashes_to_names )
            
            dlg.SetPanel( panel )
            
            if dlg.exec() != QW.QDialog.DialogCode.Accepted:
                
                return
                
            
            items = panel.GetValue()
            
        
        self._playlist_ids_to_edited_items[ playlist_id ] = items
        
        new_playlist = ( playlist_id, name, len( items ) )
        
        self._playlists[ index ] = new_playlist
        
        self._RefreshList( select_playlist = new_playlist )
        
    
    def _EnterName( self, default: str, playlist_being_edited: tuple[ int | None, str, int ] | None = None ) -> str:
        
        try:
            
            name = ClientGUIDialogsQuick.EnterText( self, 'Enter a name for the playlist.', default = default )
            
        except HydrusExceptions.CancelledException:
            
            raise HydrusExceptions.VetoException()
            
        
        name = ClientMediaPlaylists.NormalisePlaylistName( name )
        
        if name == '':
            
            raise HydrusExceptions.VetoException()
            
        
        other_names = { other_name.lower() for ( playlist_id, other_name, num_items ) in [ playlist for playlist in self._playlists if playlist is not playlist_being_edited ] }
        
        if name.lower() in other_names:
            
            ClientGUIDialogsMessage.ShowWarning( self, f'There is already a playlist called "{name}"!' )
            
            raise HydrusExceptions.VetoException()
            
        
        return name
        
    
    def _RefreshList( self, select_playlist = None ):
        
        self._playlists_list.clear()
        
        self._playlists.sort( key = lambda playlist: playlist[1].lower() )
        
        for playlist in self._playlists:
            
            self._playlists_list.Append( ConvertPlaylistToPretty( playlist ), playlist, select = playlist is select_playlist )
            
        
        self._UpdateButtons()
        
    
    def _Rename( self ):
        
        selected_playlists = self._playlists_list.GetData( only_selected = True )
        
        if len( selected_playlists ) != 1:
            
            return
            
        
        ( old_playlist, ) = selected_playlists
        
        # the list hands back copies, so find ours
        index = self._playlists.index( old_playlist )
        
        ( playlist_id, old_name, num_items ) = self._playlists[ index ]
        
        try:
            
            name = self._EnterName( old_name, playlist_being_edited = self._playlists[ index ] )
            
        except HydrusExceptions.VetoException:
            
            return
            
        
        # same id, so the items stay with it
        new_playlist = ( playlist_id, name, num_items )
        
        self._playlists[ index ] = new_playlist
        
        self._RefreshList( select_playlist = new_playlist )
        
    
    def _UpdateButtons( self ):
        
        num_selected = self._playlists_list.GetNumSelected()
        
        self._rename_button.setEnabled( num_selected == 1 )
        self._delete_button.setEnabled( num_selected > 0 )
        
        # a new playlist has no items to edit until it is saved and has had some added
        selected_playlists = self._playlists_list.GetData( only_selected = True )
        
        self._edit_items_button.setEnabled( len( selected_playlists ) == 1 and selected_playlists[0][0] is not None )
        
    
    def GetEditedItems( self ) -> dict[ int, list[ PlaylistItem ] ]:
        
        # the playlists whose items were edited, and are still here
        kept_playlist_ids = { playlist_id for ( playlist_id, name, num_items ) in self._playlists }
        
        return { playlist_id : items for ( playlist_id, items ) in self._playlist_ids_to_edited_items.items() if playlist_id in kept_playlist_ids }
        
    
    def GetValue( self ) -> list[ tuple[ int | None, str ] ]:
        
        return [ ( playlist_id, name ) for ( playlist_id, name, num_items ) in self._playlists ]
        
    

class EditPlaylistItemsPanel( ClientGUIScrolledPanels.EditPanel ):
    
    def __init__( self, parent: QW.QWidget, items: list[ PlaylistItem ], hashes_to_names: dict[ bytes, str ] ):
        
        super().__init__( parent )
        
        self._hashes_to_names = hashes_to_names
        
        # the same item can be in here more than once, so each row gets its own key, and the list holds that
        self._keys_to_items: dict[ int, PlaylistItem ] = {}
        self._next_key = 0
        
        help_text = 'Drag and drop to change the order, or select some and move them up and down. Duplicate an item to have it play again somewhere else, and remove items you do not want.'
        help_text += '\n' * 2
        help_text += 'Double-click an item, or select some and hit \'view\', to see what they are in a media viewer. It starts on the first one, at the start of its part (with mpv), and you can step through the others.'
        
        st = ClientGUICommon.BetterStaticText( self, label = help_text )
        st.setWordWrap( True )
        
        self._items_list = ClientGUIListBoxes.BetterQListWidget( self, delete_callable = self._Remove )
        self._items_list.setSelectionMode( QW.QAbstractItemView.SelectionMode.ExtendedSelection )
        self._items_list.setDragDropMode( QW.QAbstractItemView.DragDropMode.InternalMove )
        self._items_list.setDefaultDropAction( QC.Qt.DropAction.MoveAction )
        
        self._view_button = ClientGUICommon.BetterButton( self, 'view', self._View )
        self._view_button.setToolTip( ClientGUIFunctions.WrapToolTip( 'Open the selected items in a media viewer, to see what they are.' ) )
        
        self._move_up_button = ClientGUICommon.BetterButton( self, 'move up', self._Move, -1 )
        self._move_down_button = ClientGUICommon.BetterButton( self, 'move down', self._Move, 1 )
        self._duplicate_button = ClientGUICommon.BetterButton( self, 'duplicate', self._Duplicate )
        self._remove_button = ClientGUICommon.BetterButton( self, 'remove', self._Remove )
        
        #
        
        for item in items:
            
            self._items_list.Append( '', self._AddItem( item ) )
            
        
        self._UpdateLabels()
        
        #
        
        button_hbox = QP.HBoxLayout()
        
        QP.AddToLayout( button_hbox, self._view_button, CC.FLAGS_EXPAND_BOTH_WAYS )
        QP.AddToLayout( button_hbox, self._move_up_button, CC.FLAGS_EXPAND_BOTH_WAYS )
        QP.AddToLayout( button_hbox, self._move_down_button, CC.FLAGS_EXPAND_BOTH_WAYS )
        QP.AddToLayout( button_hbox, self._duplicate_button, CC.FLAGS_EXPAND_BOTH_WAYS )
        QP.AddToLayout( button_hbox, self._remove_button, CC.FLAGS_EXPAND_BOTH_WAYS )
        
        vbox = QP.VBoxLayout()
        
        QP.AddToLayout( vbox, st, CC.FLAGS_EXPAND_PERPENDICULAR )
        QP.AddToLayout( vbox, self._items_list, CC.FLAGS_EXPAND_BOTH_WAYS )
        QP.AddToLayout( vbox, button_hbox, CC.FLAGS_EXPAND_PERPENDICULAR )
        
        self.widget().setLayout( vbox )
        
        self._items_list.itemSelectionChanged.connect( self._UpdateButtons )
        self._items_list.itemDoubleClicked.connect( self._View )
        
        # a drag and drop moves rows around by itself, so the numbers need catching up after
        self._items_list.model().rowsMoved.connect( self._NotifyRowsChanged )
        self._items_list.model().rowsInserted.connect( self._NotifyRowsChanged )
        
        self._UpdateButtons()
        
    
    def _AddItem( self, item: PlaylistItem ) -> int:
        
        key = self._next_key
        
        self._next_key += 1
        
        self._keys_to_items[ key ] = item
        
        return key
        
    
    def _Duplicate( self ):
        
        selected_indices = sorted( self._items_list.GetSelectedIndices() )
        
        if len( selected_indices ) == 0:
            
            return
            
        
        keys = self._items_list.GetData()
        
        new_keys = []
        
        # each copy goes right after its original. going from the bottom up keeps the indices good
        for index in reversed( selected_indices ):
            
            new_key = self._AddItem( self._keys_to_items[ keys[ index ] ] )
            
            list_widget_item = QW.QListWidgetItem()
            
            list_widget_item.setData( QC.Qt.ItemDataRole.UserRole, new_key )
            
            self._items_list.insertItem( index + 1, list_widget_item )
            
            new_keys.append( new_key )
            
        
        self._items_list.SelectData( new_keys )
        
        self._UpdateLabels()
        
    
    def _Move( self, direction: int ):
        
        selected_indices = self._items_list.GetSelectedIndices()
        
        if len( selected_indices ) == 0:
            
            return
            
        
        # a selection already at the end stays together rather than squashing up
        if direction < 0 and min( selected_indices ) == 0:
            
            return
            
        
        if direction > 0 and max( selected_indices ) == self._items_list.count() - 1:
            
            return
            
        
        self._items_list.MoveSelected( direction )
        
        self._UpdateLabels()
        
        self._UpdateButtons()
        
    
    def _NotifyRowsChanged( self, *args ):
        
        # this can come in the middle of a drop, so we wait for it to finish
        CG.client_controller.CallAfterQtSafe( self, self._UpdateLabels )
        
    
    def _Remove( self ):
        
        if self._items_list.GetNumSelected() == 0:
            
            return
            
        
        self._items_list.DeleteSelected()
        
        self._UpdateLabels()
        
    
    def _UpdateButtons( self ):
        
        selected_indices = self._items_list.GetSelectedIndices()
        
        num_selected = len( selected_indices )
        
        self._view_button.setEnabled( num_selected > 0 )
        self._move_up_button.setEnabled( num_selected > 0 and min( selected_indices ) > 0 )
        self._move_down_button.setEnabled( num_selected > 0 and max( selected_indices ) < self._items_list.count() - 1 )
        self._duplicate_button.setEnabled( num_selected > 0 )
        self._remove_button.setEnabled( num_selected > 0 )
        
    
    def _UpdateLabels( self ):
        
        for index in range( self._items_list.count() ):
            
            list_widget_item = self._items_list.item( index )
            
            key = list_widget_item.data( QC.Qt.ItemDataRole.UserRole )
            
            if key not in self._keys_to_items:
                
                continue
                
            
            ( hash, start_ms, end_ms ) = self._keys_to_items[ key ]
            
            name = self._hashes_to_names.get( hash, hash.hex()[:12] )
            
            list_widget_item.setText( f'{HydrusNumbers.ToHumanInt( index + 1 )}. {ConvertPlaylistItemToPretty( name, start_ms, end_ms )}' )
            
        
    
    def _GetSelectedItems( self ) -> list[ PlaylistItem ]:
        
        keys = self._items_list.GetData()
        
        return [ self._keys_to_items[ keys[ index ] ] for index in sorted( self._items_list.GetSelectedIndices() ) ]
        
    
    def _View( self, *args ):
        
        items = self._GetSelectedItems()
        
        if len( items ) == 0:
            
            return
            
        
        ViewPlaylistItems( self, items )
        
    
    def GetValue( self ) -> list[ PlaylistItem ]:
        
        return [ self._keys_to_items[ key ] for key in self._items_list.GetData() ]
        
    

class SelectPlaylistPanel( ClientGUIScrolledPanels.EditPanel ):
    
    def __init__( self, parent: QW.QWidget, playlists: list[ ClientMediaPlaylists.PlaylistSummary ], allow_new_playlist: bool = False ):
        
        super().__init__( parent )
        
        self._playlists = playlists
        
        # when the user makes a new playlist here, this is its name, and we are done
        self._new_playlist_name: str | None = None
        
        self._filter = QW.QLineEdit( self )
        self._filter.setPlaceholderText( 'filter by name' )
        
        self._playlists_list = ClientGUIListBoxes.BetterQListWidget( self )
        
        self._new_playlist_button = ClientGUICommon.BetterButton( self, 'new playlist' + HC.UNICODE_ELLIPSIS, self._NewPlaylist )
        self._new_playlist_button.setToolTip( 'Make a new playlist, and use that.' )
        
        #
        
        self._RefreshList()
        
        #
        
        vbox = QP.VBoxLayout()
        
        QP.AddToLayout( vbox, self._filter, CC.FLAGS_EXPAND_PERPENDICULAR )
        QP.AddToLayout( vbox, self._playlists_list, CC.FLAGS_EXPAND_BOTH_WAYS )
        QP.AddToLayout( vbox, self._new_playlist_button, CC.FLAGS_EXPAND_PERPENDICULAR )
        
        self.widget().setLayout( vbox )
        
        self._new_playlist_button.setVisible( allow_new_playlist )
        
        self._filter.textChanged.connect( self._RefreshList )
        self._playlists_list.itemDoubleClicked.connect( self._OKParent )
        
        self.setFocusProxy( self._filter )
        
    
    def _NewPlaylist( self ):
        
        try:
            
            name = ClientGUIDialogsQuick.EnterText( self, 'Enter a name for the new playlist.', default = self._filter.text().strip(), title = 'new playlist' )
            
        except HydrusExceptions.CancelledException:
            
            return
            
        
        name = ClientMediaPlaylists.NormalisePlaylistName( name )
        
        if name == '':
            
            return
            
        
        for playlist in self._playlists:
            
            if playlist[1].lower() == name.lower():
                
                # we already have one called that, so we just use it
                self._filter.clear()
                
                self._playlists_list.SelectData( [ playlist ] )
                
                self._OKParent()
                
                return
                
            
        
        self._new_playlist_name = name
        
        self._OKParent()
        
    
    def _RefreshList( self ):
        
        self._playlists_list.clear()
        
        filtered_playlists = ClientMediaPlaylists.FilterPlaylistsByName( self._playlists, self._filter.text() )
        
        for ( i, playlist ) in enumerate( filtered_playlists ):
            
            # the top one is ready to go, so typing a filter and hitting enter works
            self._playlists_list.Append( ConvertPlaylistToPretty( playlist ), playlist, select = i == 0 )
            
        
    
    def GetValue( self ) -> int | str:
        
        # a playlist id, or the name of a new playlist
        if self._new_playlist_name is not None:
            
            return self._new_playlist_name
            
        
        selected_playlists = self._playlists_list.GetData( only_selected = True )
        
        if len( selected_playlists ) == 0:
            
            raise HydrusExceptions.VetoException( 'Please select a playlist!' )
            
        
        ( playlist_id, name, num_items ) = selected_playlists[0]
        
        return playlist_id
        
    
