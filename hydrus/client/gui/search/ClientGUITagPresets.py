from qtpy import QtWidgets as QW

from hydrus.core import HydrusExceptions

from hydrus.client import ClientConstants as CC
from hydrus.client import ClientGlobals as CG
from hydrus.client.gui import ClientGUIDialogsMessage
from hydrus.client.gui import ClientGUIDialogsQuick
from hydrus.client.gui import ClientGUITopLevelWindowsPanels
from hydrus.client.gui import QtPorting as QP
from hydrus.client.gui.lists import ClientGUIListBoxes
from hydrus.client.gui.panels import ClientGUIScrolledPanels
from hydrus.client.gui.widgets import ClientGUICommon
from hydrus.client.search import ClientSearchTagPresets

def AddTagsToTagPreset( win: QW.QWidget, name: str, tags: list[ str ] ):
    
    new_options = CG.client_controller.new_options
    
    new_options.SetTagPresets( ClientSearchTagPresets.AddEntriesToTagPreset( new_options.GetTagPresets(), name, tags ) )
    
    CG.client_controller.Write( 'serialisable', new_options )
    

def AddTagsToNewTagPreset( win: QW.QWidget, tags: list[ str ] ):
    
    other_names = [ name for ( name, entries ) in CG.client_controller.new_options.GetTagPresets() ]
    
    try:
        
        name = EnterTagPresetName( win, '', other_names )
        
    except HydrusExceptions.VetoException:
        
        return
        
    
    AddTagsToTagPreset( win, name, tags )
    

def EditTagPresetEntries( win: QW.QWidget, name: str, entries: list[ str ] ) -> list[ str ]:
    
    # raises CancelledException if the user backs out
    with ClientGUITopLevelWindowsPanels.DialogEdit( win, f'edit tag preset: {name}' ) as dlg:
        
        panel = EditTagPresetEntriesPanel( dlg, entries )
        
        dlg.SetPanel( panel )
        
        if dlg.exec() == QW.QDialog.DialogCode.Accepted:
            
            return panel.GetValue()
            
        
        raise HydrusExceptions.CancelledException( 'Dialog cancelled.' )
        
    

def EnterTagPresetName( win: QW.QWidget, default: str, other_names: list[ str ] ) -> str:
    
    # raises VetoException if the user backs out or the name is no good
    try:
        
        name = ClientGUIDialogsQuick.EnterText( win, 'Enter a name for the tag preset.', default = default )
        
    except HydrusExceptions.CancelledException:
        
        raise HydrusExceptions.VetoException()
        
    
    name = ClientSearchTagPresets.NormaliseTagPresetName( name )
    
    if name == '':
        
        raise HydrusExceptions.VetoException()
        
    
    # names are not case-sensitive, and underscores are spaces
    if ClientSearchTagPresets.GetTagPresetLookupKey( name ) in { ClientSearchTagPresets.GetTagPresetLookupKey( other_name ) for other_name in other_names }:
        
        ClientGUIDialogsMessage.ShowWarning( win, f'There is already a tag preset called "{name}"!' )
        
        raise HydrusExceptions.VetoException()
        
    
    return name
    

def GetEntryError( entry: str ) -> str | None:
    
    tag_autocomplete_options = CG.client_controller.tag_display_manager.GetTagAutocompleteOptions( CC.COMBINED_TAG_SERVICE_KEY )
    
    if ClientSearchTagPresets.ConvertTagPresetEntryToPredicate( entry, tag_autocomplete_options ) is None:
        
        return f'Sorry, "{entry}" does not look like something you can search for!'
        
    
    return None
    

class EditTagPresetEntriesPanel( ClientGUIScrolledPanels.EditPanel ):
    
    def __init__( self, parent: QW.QWidget, entries: list[ str ] ):
        
        super().__init__( parent )
        
        self._entries = list( entries )
        
        help_text = 'Add anything you would type in a search box: tags like "blue eyes", excluded tags like "-red hair", wildcards like "character:*", or system predicates like "system:inbox".'
        
        st = ClientGUICommon.BetterStaticText( self, label = help_text )
        st.setWordWrap( True )
        
        self._entries_list = ClientGUIListBoxes.BetterQListWidget( self )
        self._entries_list.setSelectionMode( QW.QAbstractItemView.SelectionMode.ExtendedSelection )
        
        self._new_entry = QW.QLineEdit( self )
        self._new_entry.setPlaceholderText( 'type a tag to add' )
        
        self._add_button = ClientGUICommon.BetterButton( self, 'add', self._Add )
        self._remove_button = ClientGUICommon.BetterButton( self, 'remove', self._Remove )
        
        #
        
        self._RefreshList()
        
        #
        
        add_hbox = QP.HBoxLayout()
        
        QP.AddToLayout( add_hbox, self._new_entry, CC.FLAGS_EXPAND_BOTH_WAYS )
        QP.AddToLayout( add_hbox, self._add_button, CC.FLAGS_CENTER_PERPENDICULAR )
        
        vbox = QP.VBoxLayout()
        
        QP.AddToLayout( vbox, st, CC.FLAGS_EXPAND_PERPENDICULAR )
        QP.AddToLayout( vbox, self._entries_list, CC.FLAGS_EXPAND_BOTH_WAYS )
        QP.AddToLayout( vbox, self._remove_button, CC.FLAGS_EXPAND_PERPENDICULAR )
        QP.AddToLayout( vbox, add_hbox, CC.FLAGS_EXPAND_PERPENDICULAR )
        
        self.widget().setLayout( vbox )
        
        self._entries_list.itemSelectionChanged.connect( self._UpdateButtons )
        
        self._UpdateButtons()
        
        self.setFocusProxy( self._new_entry )
        
    
    def _Add( self ):
        
        entry = ClientSearchTagPresets.NormaliseTagPresetEntry( self._new_entry.text() )
        
        if entry == '':
            
            return
            
        
        error = GetEntryError( entry )
        
        if error is not None:
            
            ClientGUIDialogsMessage.ShowWarning( self, error )
            
            return
            
        
        self._new_entry.clear()
        
        if entry not in self._entries:
            
            self._entries.append( entry )
            
        
        self._RefreshList()
        
    
    def _RefreshList( self ):
        
        self._entries_list.clear()
        
        for entry in self._entries:
            
            self._entries_list.Append( entry, entry )
            
        
        self._UpdateButtons()
        
    
    def _Remove( self ):
        
        selected_entries = self._entries_list.GetData( only_selected = True )
        
        self._entries = [ entry for entry in self._entries if entry not in selected_entries ]
        
        self._RefreshList()
        
    
    def _UpdateButtons( self ):
        
        self._remove_button.setEnabled( self._entries_list.GetNumSelected() > 0 )
        
    
    def GetValue( self ) -> list[ str ]:
        
        # if the user typed an entry and hit ok without adding it, they want it
        entries = list( self._entries )
        
        pending_entry = ClientSearchTagPresets.NormaliseTagPresetEntry( self._new_entry.text() )
        
        if pending_entry != '':
            
            error = GetEntryError( pending_entry )
            
            if error is not None:
                
                raise HydrusExceptions.VetoException( error )
                
            
            if pending_entry not in entries:
                
                entries.append( pending_entry )
                
            
        
        return entries
        
    
