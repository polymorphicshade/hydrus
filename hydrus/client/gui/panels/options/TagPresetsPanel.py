from qtpy import QtWidgets as QW

from hydrus.core import HydrusExceptions
from hydrus.core import HydrusNumbers

from hydrus.client import ClientConstants as CC
from hydrus.client.gui import ClientGUIDialogsQuick
from hydrus.client.gui import QtPorting as QP
from hydrus.client.gui.lists import ClientGUIListBoxes
from hydrus.client.gui.panels.options import ClientGUIOptionsPanelBase
from hydrus.client.gui.search import ClientGUITagPresets
from hydrus.client.gui.widgets import ClientGUICommon

class TagPresetsPanel( ClientGUIOptionsPanelBase.OptionsPagePanel ):
    
    def __init__( self, parent, new_options ):
        
        super().__init__( parent )
        
        self._new_options = new_options
        
        # ( name, entries )
        self._tag_presets = self._new_options.GetTagPresets()
        
        help_text = 'Tag presets are named lists of search tags. Search for "system:presets my preset" and all of its tags go into the search, just as if you had typed each one.'
        help_text += '\n' * 2
        help_text += 'You can also right-click tags in any tag list and add them to a preset. Names are not case-sensitive, and underscores count as spaces.'
        
        st = ClientGUICommon.BetterStaticText( self, label = help_text )
        st.setWordWrap( True )
        
        self._tag_presets_list = ClientGUIListBoxes.BetterQListWidget( self )
        self._tag_presets_list.setSelectionMode( QW.QAbstractItemView.SelectionMode.ExtendedSelection )
        
        self._add_button = ClientGUICommon.BetterButton( self, 'add', self._Add )
        self._rename_button = ClientGUICommon.BetterButton( self, 'rename', self._Rename )
        self._edit_button = ClientGUICommon.BetterButton( self, 'edit tags', self._Edit )
        self._delete_button = ClientGUICommon.BetterButton( self, 'delete', self._Delete )
        
        #
        
        self._RefreshList()
        
        #
        
        button_hbox = QP.HBoxLayout()
        
        QP.AddToLayout( button_hbox, self._add_button, CC.FLAGS_EXPAND_BOTH_WAYS )
        QP.AddToLayout( button_hbox, self._rename_button, CC.FLAGS_EXPAND_BOTH_WAYS )
        QP.AddToLayout( button_hbox, self._edit_button, CC.FLAGS_EXPAND_BOTH_WAYS )
        QP.AddToLayout( button_hbox, self._delete_button, CC.FLAGS_EXPAND_BOTH_WAYS )
        
        vbox = QP.VBoxLayout()
        
        QP.AddToLayout( vbox, st, CC.FLAGS_EXPAND_PERPENDICULAR )
        QP.AddToLayout( vbox, self._tag_presets_list, CC.FLAGS_EXPAND_BOTH_WAYS )
        QP.AddToLayout( vbox, button_hbox, CC.FLAGS_EXPAND_PERPENDICULAR )
        
        self.setLayout( vbox )
        
        self._tag_presets_list.itemSelectionChanged.connect( self._UpdateButtons )
        self._tag_presets_list.itemDoubleClicked.connect( self._Edit )
        
        self._UpdateButtons()
        
    
    def _Add( self ):
        
        try:
            
            name = ClientGUITagPresets.EnterTagPresetName( self, '', self._GetOtherNames( None ) )
            
        except HydrusExceptions.VetoException:
            
            return
            
        
        try:
            
            entries = ClientGUITagPresets.EditTagPresetEntries( self, name, [] )
            
        except HydrusExceptions.CancelledException:
            
            return
            
        
        self._tag_presets.append( ( name, entries ) )
        
        self._RefreshList( select_index = len( self._tag_presets ) - 1 )
        
    
    def _Delete( self ):
        
        selected_indices = set( self._tag_presets_list.GetSelectedIndices() )
        
        if len( selected_indices ) == 0:
            
            return
            
        
        result = ClientGUIDialogsQuick.GetYesNo( self, f'Delete {HydrusNumbers.ToHumanInt( len( selected_indices ) )} tag presets?' )
        
        if result != QW.QDialog.DialogCode.Accepted:
            
            return
            
        
        self._tag_presets = [ tag_preset for ( i, tag_preset ) in enumerate( self._tag_presets ) if i not in selected_indices ]
        
        self._RefreshList()
        
    
    def _Edit( self ):
        
        index = self._GetSelectedIndex()
        
        if index is None:
            
            return
            
        
        ( name, entries ) = self._tag_presets[ index ]
        
        try:
            
            entries = ClientGUITagPresets.EditTagPresetEntries( self, name, entries )
            
        except HydrusExceptions.CancelledException:
            
            return
            
        
        self._tag_presets[ index ] = ( name, entries )
        
        self._RefreshList( select_index = index )
        
    
    def _GetOtherNames( self, index: int | None ) -> list[ str ]:
        
        return [ name for ( i, ( name, entries ) ) in enumerate( self._tag_presets ) if i != index ]
        
    
    def _GetSelectedIndex( self ) -> int | None:
        
        selected_indices = self._tag_presets_list.GetSelectedIndices()
        
        if len( selected_indices ) != 1:
            
            return None
            
        
        return selected_indices[0]
        
    
    def _RefreshList( self, select_index: int | None = None ):
        
        self._tag_presets_list.clear()
        
        for ( i, ( name, entries ) ) in enumerate( self._tag_presets ):
            
            self._tag_presets_list.Append( f'{name} ({HydrusNumbers.ToHumanInt( len( entries ) )} tags)', i, select = i == select_index )
            
        
        self._UpdateButtons()
        
    
    def _Rename( self ):
        
        index = self._GetSelectedIndex()
        
        if index is None:
            
            return
            
        
        ( name, entries ) = self._tag_presets[ index ]
        
        try:
            
            new_name = ClientGUITagPresets.EnterTagPresetName( self, name, self._GetOtherNames( index ) )
            
        except HydrusExceptions.VetoException:
            
            return
            
        
        self._tag_presets[ index ] = ( new_name, entries )
        
        self._RefreshList( select_index = index )
        
    
    def _UpdateButtons( self ):
        
        num_selected = self._tag_presets_list.GetNumSelected()
        
        self._rename_button.setEnabled( num_selected == 1 )
        self._edit_button.setEnabled( num_selected == 1 )
        self._delete_button.setEnabled( num_selected > 0 )
        
    
    def UpdateOptions( self ):
        
        self._new_options.SetTagPresets( self._tag_presets )
        
    
