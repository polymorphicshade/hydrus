import collections

from qtpy import QtCore as QC
from qtpy import QtWidgets as QW

from hydrus.core import HydrusExceptions
from hydrus.core import HydrusNumbers

from hydrus.client import ClientConstants as CC
from hydrus.client.gui import ClientGUIDialogsMessage
from hydrus.client.gui import ClientGUIDialogsQuick
from hydrus.client.gui import QtPorting as QP
from hydrus.client.gui.lists import ClientGUIListBoxes
from hydrus.client.gui.panels import ClientGUIScrolledPanels
from hydrus.client.gui.widgets import ClientGUICommon
from hydrus.client.metadata import ClientVirtualPaths

class EditVirtualPathsPanel( ClientGUIScrolledPanels.EditPanel ):
    
    def __init__( self, parent: QW.QWidget, hashes_to_paths: dict[ bytes, list[ str ] ], all_known_paths: list[ str ] ):
        
        super().__init__( parent )
        
        self._all_hashes = frozenset( hashes_to_paths.keys() )
        
        self._paths_to_hashes: dict[ str, set[ bytes ] ] = collections.defaultdict( set )
        
        for ( hash, paths ) in hashes_to_paths.items():
            
            for path in paths:
                
                self._paths_to_hashes[ path ].add( hash )
                
            
        
        help_text = 'Virtual paths are folder-like labels for your files, like "collections/tv_shows/action". A file can have as many as you like. Search for them with system:path, which takes wildcards, like "system:path is collections/*/action".'
        help_text += '\n' * 2
        help_text += 'Spaces become underscores, and paths are not case-sensitive.'
        
        if len( self._all_hashes ) > 1:
            
            help_text += '\n' * 2
            help_text += f'You are editing {HydrusNumbers.ToHumanInt( len( self._all_hashes ) )} files. A path only some of them have says how many. Adding it again gives it to all of them.'
            
        
        st = ClientGUICommon.BetterStaticText( self, label = help_text )
        st.setWordWrap( True )
        
        self._paths_list = ClientGUIListBoxes.BetterQListWidget( self )
        self._paths_list.setSelectionMode( QW.QAbstractItemView.SelectionMode.ExtendedSelection )
        
        self._new_path = QW.QLineEdit( self )
        self._new_path.setPlaceholderText( 'type a path to add, like collections/tv_shows/action' )
        
        # the paths the user already uses elsewhere, so they can keep them consistent
        self._completer = QW.QCompleter( all_known_paths, self._new_path )
        self._completer.setCaseSensitivity( QC.Qt.CaseSensitivity.CaseInsensitive )
        self._completer.setFilterMode( QC.Qt.MatchFlag.MatchContains )
        self._completer.setCompletionMode( QW.QCompleter.CompletionMode.PopupCompletion )
        self._completer.setMaxVisibleItems( 10 )
        self._new_path.setCompleter( self._completer )
        
        self._add_button = ClientGUICommon.BetterButton( self, 'add', self._Add )
        self._rename_button = ClientGUICommon.BetterButton( self, 'rename', self._Rename )
        self._remove_button = ClientGUICommon.BetterButton( self, 'remove', self._Remove )
        
        #
        
        self._RefreshList()
        
        #
        
        add_hbox = QP.HBoxLayout()
        
        QP.AddToLayout( add_hbox, self._new_path, CC.FLAGS_EXPAND_BOTH_WAYS )
        QP.AddToLayout( add_hbox, self._add_button, CC.FLAGS_CENTER_PERPENDICULAR )
        
        button_hbox = QP.HBoxLayout()
        
        QP.AddToLayout( button_hbox, self._rename_button, CC.FLAGS_EXPAND_BOTH_WAYS )
        QP.AddToLayout( button_hbox, self._remove_button, CC.FLAGS_EXPAND_BOTH_WAYS )
        
        vbox = QP.VBoxLayout()
        
        QP.AddToLayout( vbox, st, CC.FLAGS_EXPAND_PERPENDICULAR )
        QP.AddToLayout( vbox, self._paths_list, CC.FLAGS_EXPAND_BOTH_WAYS )
        QP.AddToLayout( vbox, button_hbox, CC.FLAGS_EXPAND_PERPENDICULAR )
        QP.AddToLayout( vbox, add_hbox, CC.FLAGS_EXPAND_PERPENDICULAR )
        
        self.widget().setLayout( vbox )
        
        self._paths_list.itemSelectionChanged.connect( self._UpdateButtons )
        self._paths_list.itemDoubleClicked.connect( self._Rename )
        
        self._UpdateButtons()
        
    
    def _Add( self ):
        
        path = ClientVirtualPaths.NormaliseVirtualPath( self._new_path.text() )
        
        error = ClientVirtualPaths.GetVirtualPathError( path )
        
        if error is not None:
            
            ClientGUIDialogsMessage.ShowWarning( self, error )
            
            return
            
        
        self._new_path.clear()
        
        self._paths_to_hashes[ path ].update( self._all_hashes )
        
        self._RefreshList( select_path = path )
        
    
    def _ConvertPathToPretty( self, path: str ) -> str:
        
        num_hashes = len( self._paths_to_hashes[ path ] )
        
        if num_hashes < len( self._all_hashes ):
            
            return f'{path} ({HydrusNumbers.ValueRangeToPrettyString( num_hashes, len( self._all_hashes ) )} files)'
            
        
        return path
        
    
    def _EnterPath( self, default: str ) -> str:
        
        try:
            
            path = ClientGUIDialogsQuick.EnterText( self, 'Enter a path, like "collections/tv_shows/action".', default = default )
            
        except HydrusExceptions.CancelledException:
            
            raise HydrusExceptions.VetoException()
            
        
        path = ClientVirtualPaths.NormaliseVirtualPath( path )
        
        error = ClientVirtualPaths.GetVirtualPathError( path )
        
        if error is not None:
            
            ClientGUIDialogsMessage.ShowWarning( self, error )
            
            raise HydrusExceptions.VetoException()
            
        
        return path
        
    
    def _RefreshList( self, select_path: str | None = None ):
        
        self._paths_list.clear()
        
        for path in sorted( self._paths_to_hashes.keys() ):
            
            self._paths_list.Append( self._ConvertPathToPretty( path ), path, select = path == select_path )
            
        
        self._UpdateButtons()
        
    
    def _Remove( self ):
        
        for path in self._paths_list.GetData( only_selected = True ):
            
            del self._paths_to_hashes[ path ]
            
        
        self._RefreshList()
        
    
    def _Rename( self ):
        
        selected_paths = self._paths_list.GetData( only_selected = True )
        
        if len( selected_paths ) != 1:
            
            return
            
        
        ( old_path, ) = selected_paths
        
        try:
            
            new_path = self._EnterPath( old_path )
            
        except HydrusExceptions.VetoException:
            
            return
            
        
        if new_path == old_path:
            
            return
            
        
        # the files that had the old path get the new one. if another path already had that name, they merge
        hashes = self._paths_to_hashes.pop( old_path )
        
        self._paths_to_hashes[ new_path ].update( hashes )
        
        self._RefreshList( select_path = new_path )
        
    
    def _UpdateButtons( self ):
        
        num_selected = self._paths_list.GetNumSelected()
        
        self._rename_button.setEnabled( num_selected == 1 )
        self._remove_button.setEnabled( num_selected > 0 )
        
    
    def GetValue( self ) -> dict[ bytes, list[ str ] ]:
        
        paths_to_hashes = { path : set( hashes ) for ( path, hashes ) in self._paths_to_hashes.items() }
        
        # if the user typed a path and hit ok without adding it, they want it
        pending_path = ClientVirtualPaths.NormaliseVirtualPath( self._new_path.text() )
        
        if pending_path != '':
            
            error = ClientVirtualPaths.GetVirtualPathError( pending_path )
            
            if error is not None:
                
                raise HydrusExceptions.VetoException( error )
                
            
            paths_to_hashes.setdefault( pending_path, set() ).update( self._all_hashes )
            
        
        hashes_to_paths = { hash : [] for hash in self._all_hashes }
        
        for ( path, hashes ) in paths_to_hashes.items():
            
            for hash in hashes:
                
                hashes_to_paths[ hash ].append( path )
                
            
        
        return { hash : sorted( paths ) for ( hash, paths ) in hashes_to_paths.items() }
        
    
