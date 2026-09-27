from qtpy import QtWidgets as QW

from hydrus.core import HydrusExceptions
from hydrus.core import HydrusNumbers

from hydrus.client import ClientConstants as CC
from hydrus.client import ClientGlobals as CG
from hydrus.client.gui import ClientGUIDialogsMessage
from hydrus.client.gui import ClientGUIDialogsQuick
from hydrus.client.gui import ClientGUITopLevelWindowsPanels
from hydrus.client.gui import QtPorting as QP
from hydrus.client.gui.lists import ClientGUIListBoxes
from hydrus.client.gui.panels import ClientGUIScrolledPanels
from hydrus.client.gui.widgets import ClientGUICommon
from hydrus.client.media import ClientMediaPlaylists

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
            
        
    

def SelectPlaylist( win: QW.QWidget, title: str, playlists: list[ ClientMediaPlaylists.PlaylistSummary ] ) -> int:
    
    # raises CancelledException if the user backs out
    with ClientGUITopLevelWindowsPanels.DialogEdit( win, title, frame_key = 'quick_select_dialog' ) as dlg:
        
        panel = SelectPlaylistPanel( dlg, playlists )
        
        dlg.SetPanel( panel )
        
        if dlg.exec() == QW.QDialog.DialogCode.Accepted:
            
            return panel.GetValue()
            
        
        raise HydrusExceptions.CancelledException( 'Dialog cancelled.' )
        
    

class EditPlaylistsPanel( ClientGUIScrolledPanels.EditPanel ):
    
    def __init__( self, parent: QW.QWidget, playlists: list[ ClientMediaPlaylists.PlaylistSummary ] ):
        
        super().__init__( parent )
        
        # ( playlist_id, name, num_items ). a new playlist has no id until we save
        self._playlists: list[ tuple[ int | None, str, int ] ] = list( playlists )
        
        help_text = 'Playlists are named lists of files to play one after another. They do not have tags--you just find them by name.'
        help_text += '\n' * 2
        help_text += 'To put a file in a playlist, open it in the media viewer and right-click->playlist->add. If the A-B repeat points are set, only that part of the file goes in. To play a playlist, hit playlists->open.'
        
        st = ClientGUICommon.BetterStaticText( self, label = help_text )
        st.setWordWrap( True )
        
        self._playlists_list = ClientGUIListBoxes.BetterQListWidget( self )
        self._playlists_list.setSelectionMode( QW.QAbstractItemView.SelectionMode.ExtendedSelection )
        
        self._add_button = ClientGUICommon.BetterButton( self, 'add', self._Add )
        self._rename_button = ClientGUICommon.BetterButton( self, 'rename', self._Rename )
        self._delete_button = ClientGUICommon.BetterButton( self, 'delete', self._Delete )
        
        #
        
        self._RefreshList()
        
        #
        
        button_hbox = QP.HBoxLayout()
        
        QP.AddToLayout( button_hbox, self._add_button, CC.FLAGS_EXPAND_BOTH_WAYS )
        QP.AddToLayout( button_hbox, self._rename_button, CC.FLAGS_EXPAND_BOTH_WAYS )
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
        
    
    def GetValue( self ) -> list[ tuple[ int | None, str ] ]:
        
        return [ ( playlist_id, name ) for ( playlist_id, name, num_items ) in self._playlists ]
        
    

class SelectPlaylistPanel( ClientGUIScrolledPanels.EditPanel ):
    
    def __init__( self, parent: QW.QWidget, playlists: list[ ClientMediaPlaylists.PlaylistSummary ] ):
        
        super().__init__( parent )
        
        self._playlists = playlists
        
        self._filter = QW.QLineEdit( self )
        self._filter.setPlaceholderText( 'filter by name' )
        
        self._playlists_list = ClientGUIListBoxes.BetterQListWidget( self )
        
        #
        
        self._RefreshList()
        
        #
        
        vbox = QP.VBoxLayout()
        
        QP.AddToLayout( vbox, self._filter, CC.FLAGS_EXPAND_PERPENDICULAR )
        QP.AddToLayout( vbox, self._playlists_list, CC.FLAGS_EXPAND_BOTH_WAYS )
        
        self.widget().setLayout( vbox )
        
        self._filter.textChanged.connect( self._RefreshList )
        self._playlists_list.itemDoubleClicked.connect( self._OKParent )
        
        self.setFocusProxy( self._filter )
        
    
    def _RefreshList( self ):
        
        self._playlists_list.clear()
        
        filtered_playlists = ClientMediaPlaylists.FilterPlaylistsByName( self._playlists, self._filter.text() )
        
        for ( i, playlist ) in enumerate( filtered_playlists ):
            
            # the top one is ready to go, so typing a filter and hitting enter works
            self._playlists_list.Append( ConvertPlaylistToPretty( playlist ), playlist, select = i == 0 )
            
        
    
    def GetValue( self ) -> int:
        
        selected_playlists = self._playlists_list.GetData( only_selected = True )
        
        if len( selected_playlists ) == 0:
            
            raise HydrusExceptions.VetoException( 'Please select a playlist!' )
            
        
        ( playlist_id, name, num_items ) = selected_playlists[0]
        
        return playlist_id
        
    
