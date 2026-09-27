from qtpy import QtWidgets as QW

from hydrus.core import HydrusExceptions
from hydrus.core import HydrusNumbers

from hydrus.client import ClientConstants as CC
from hydrus.client import ClientScreenLocations
from hydrus.client.gui import ClientGUIDialogsMessage
from hydrus.client.gui import ClientGUIDialogsQuick
from hydrus.client.gui import ClientGUIScreenLocations
from hydrus.client.gui import QtPorting as QP
from hydrus.client.gui.lists import ClientGUIListBoxes
from hydrus.client.gui.panels.options import ClientGUIOptionsPanelBase
from hydrus.client.gui.widgets import ClientGUICommon

class ScreenLocationsPanel( ClientGUIOptionsPanelBase.OptionsPagePanel ):
    
    def __init__( self, parent, new_options ):
        
        super().__init__( parent )
        
        self._new_options = new_options
        
        self._screen_locations = self._new_options.GetScreenLocations()
        
        help_text = 'Screen locations are spots on your monitors that a media viewer can snap to, size and all. To make one, put a media viewer where you like it and hit right-click->screen->save location. To snap a media viewer to one, hit right-click->screen->move to location.'
        
        st = ClientGUICommon.BetterStaticText( self, label = help_text )
        st.setWordWrap( True )
        
        self._screen_locations_list = ClientGUIListBoxes.BetterQListWidget( self )
        self._screen_locations_list.setSelectionMode( QW.QAbstractItemView.SelectionMode.ExtendedSelection )
        
        self._rename_button = ClientGUICommon.BetterButton( self, 'rename', self._Rename )
        self._edit_button = ClientGUICommon.BetterButton( self, 'edit', self._Edit )
        self._delete_button = ClientGUICommon.BetterButton( self, 'delete', self._Delete )
        
        #
        
        self._RefreshList()
        
        #
        
        button_hbox = QP.HBoxLayout()
        
        QP.AddToLayout( button_hbox, self._rename_button, CC.FLAGS_EXPAND_BOTH_WAYS )
        QP.AddToLayout( button_hbox, self._edit_button, CC.FLAGS_EXPAND_BOTH_WAYS )
        QP.AddToLayout( button_hbox, self._delete_button, CC.FLAGS_EXPAND_BOTH_WAYS )
        
        vbox = QP.VBoxLayout()
        
        QP.AddToLayout( vbox, st, CC.FLAGS_EXPAND_PERPENDICULAR )
        QP.AddToLayout( vbox, self._screen_locations_list, CC.FLAGS_EXPAND_BOTH_WAYS )
        QP.AddToLayout( vbox, button_hbox, CC.FLAGS_EXPAND_PERPENDICULAR )
        
        self.setLayout( vbox )
        
        self._screen_locations_list.itemSelectionChanged.connect( self._UpdateButtons )
        self._screen_locations_list.itemDoubleClicked.connect( self._Edit )
        
        self._UpdateButtons()
        
    
    def _Delete( self ):
        
        selected_screen_locations = self._screen_locations_list.GetData( only_selected = True )
        
        if len( selected_screen_locations ) == 0:
            
            return
            
        
        result = ClientGUIDialogsQuick.GetYesNo( self, f'Delete {HydrusNumbers.ToHumanInt( len( selected_screen_locations ) )} screen locations?' )
        
        if result != QW.QDialog.DialogCode.Accepted:
            
            return
            
        
        self._screen_locations = [ screen_location for screen_location in self._screen_locations if screen_location not in selected_screen_locations ]
        
        self._RefreshList()
        
    
    def _Edit( self ):
        
        index = self._GetSelectedIndex()
        
        if index is None:
            
            return
            
        
        screen_location = self._screen_locations[ index ]
        
        try:
            
            new_screen_location = ClientGUIScreenLocations.EditScreenLocation( self, 'edit screen location', screen_location, self._GetOtherNames( index ) )
            
        except HydrusExceptions.CancelledException:
            
            return
            
        
        self._screen_locations[ index ] = new_screen_location
        
        self._RefreshList( select_index = index )
        
    
    def _GetOtherNames( self, index: int ) -> list[ str ]:
        
        return [ screen_location[0] for ( i, screen_location ) in enumerate( self._screen_locations ) if i != index ]
        
    
    def _GetSelectedIndex( self ) -> int | None:
        
        selected_indices = self._screen_locations_list.GetSelectedIndices()
        
        if len( selected_indices ) != 1:
            
            return None
            
        
        return selected_indices[0]
        
    
    def _RefreshList( self, select_index: int | None = None ):
        
        self._screen_locations_list.clear()
        
        for ( i, screen_location ) in enumerate( self._screen_locations ):
            
            self._screen_locations_list.Append( ClientScreenLocations.ConvertScreenLocationToPretty( screen_location ), screen_location, select = i == select_index )
            
        
        self._UpdateButtons()
        
    
    def _Rename( self ):
        
        index = self._GetSelectedIndex()
        
        if index is None:
            
            return
            
        
        ( name, screen_name, x, y, width, height ) = self._screen_locations[ index ]
        
        try:
            
            new_name = ClientGUIDialogsQuick.EnterText( self, 'Enter a new name for this screen location.', default = name )
            
        except HydrusExceptions.CancelledException:
            
            return
            
        
        new_screen_location = ( ClientScreenLocations.NormaliseScreenLocationName( new_name ), screen_name, x, y, width, height )
        
        error = ClientScreenLocations.GetScreenLocationError( new_screen_location, self._GetOtherNames( index ) )
        
        if error is not None:
            
            ClientGUIDialogsMessage.ShowWarning( self, error )
            
            return
            
        
        self._screen_locations[ index ] = new_screen_location
        
        self._RefreshList( select_index = index )
        
    
    def _UpdateButtons( self ):
        
        num_selected = self._screen_locations_list.GetNumSelected()
        
        self._rename_button.setEnabled( num_selected == 1 )
        self._edit_button.setEnabled( num_selected == 1 )
        self._delete_button.setEnabled( num_selected > 0 )
        
    
    def UpdateOptions( self ):
        
        self._new_options.SetScreenLocations( self._screen_locations )
        
    
