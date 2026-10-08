from qtpy import QtWidgets as QW

from hydrus.core import HydrusConstants as HC
from hydrus.core import HydrusData
from hydrus.core import HydrusNumbers

from hydrus.client import ClientConstants as CC
from hydrus.client import ClientGlobals as CG
from hydrus.client.gui import ClientGUIDialogsMessage
from hydrus.client.gui import ClientGUIDialogsQuick
from hydrus.client.gui import ClientGUITopLevelWindowsPanels
from hydrus.client.gui import QtPorting as QP
from hydrus.client.gui.panels import ClientGUIScrolledPanels
from hydrus.client.gui.widgets import ClientGUICommon
from hydrus.client.metadata import ClientCounters

# how many counters the 'are you sure?' message lists before it sums up the rest
MAX_PREVIEW_LINES = 20

def ConvertTagsToCounters( win: QW.QWidget, default_tag_service_key: bytes ):
    
    services_manager = CG.client_controller.services_manager
    
    if len( services_manager.GetServices( ( HC.LOCAL_TAG, ) ) ) == 0:
        
        ClientGUIDialogsMessage.ShowWarning( win, 'You have no local tag services, so there are no tags to convert!' )
        
        return
        
    
    with ClientGUITopLevelWindowsPanels.DialogEdit( win, 'convert tags to counters' ) as dlg:
        
        panel = EditTagsToCountersPanel( dlg, default_tag_service_key )
        
        dlg.SetPanel( panel )
        
        if dlg.exec() != QW.QDialog.DialogCode.Accepted:
            
            return
            
        
        ( tag_service_key, namespace_wildcard, subtag_wildcard ) = panel.GetValue()
        
    
    namespaces_to_numbers = CG.client_controller.Read( 'tags_to_counters_preview', tag_service_key, namespace_wildcard, subtag_wildcard )
    
    tag_service_name = services_manager.GetName( tag_service_key )
    
    if len( namespaces_to_numbers ) == 0:
        
        ClientGUIDialogsMessage.ShowInformation( win, f'No "namespace:number" tags in {tag_service_name} matched that filter.' )
        
        return
        
    
    new_options = CG.client_controller.new_options
    
    counters = new_options.GetCounters()
    
    # counter names are case-insensitive
    names_to_counter_ids = { counter.name.lower() : counter.object_id for counter in counters }
    
    namespaces = sorted( namespaces_to_numbers.keys() )
    
    lines = []
    
    for namespace in namespaces[ : MAX_PREVIEW_LINES ]:
        
        ( num_tags, num_files ) = namespaces_to_numbers[ namespace ]
        
        new_text = '' if namespace.lower() in names_to_counter_ids else ' (new counter)'
        
        lines.append( f'{namespace}{new_text}: {HydrusNumbers.ToHumanInt( num_tags )} tags on {HydrusNumbers.ToHumanInt( num_files )} files' )
        
    
    if len( namespaces ) > MAX_PREVIEW_LINES:
        
        lines.append( f'and {HydrusNumbers.ToHumanInt( len( namespaces ) - MAX_PREVIEW_LINES )} more counters' )
        
    
    message = 'These tags will become counters:'
    message += '\n' * 2
    message += '\n'.join( lines )
    message += '\n' * 2
    message += f'The tags will be deleted from {tag_service_name}, and any counts these files already have for these counters will be replaced. If a file has more than one, like items:3 and items:5, it gets the higher number.'
    
    result = ClientGUIDialogsQuick.GetYesNo( win, message )
    
    if result != QW.QDialog.DialogCode.Accepted:
        
        return
        
    
    namespaces_to_counter_ids = ClientCounters.GetCounterIdsForNamespaces( namespaces )
    
    def do_it():
        
        ( num_tags, num_files ) = CG.client_controller.WriteSynchronous( 'convert_tags_to_counters', tag_service_key, namespace_wildcard, subtag_wildcard, namespaces_to_counter_ids )
        
        HydrusData.ShowText( f'Converted {HydrusNumbers.ToHumanInt( num_tags )} tags on {HydrusNumbers.ToHumanInt( num_files )} files to counters.' )
        
    
    CG.client_controller.CallToThread( do_it )
    

class EditTagsToCountersPanel( ClientGUIScrolledPanels.EditPanel ):
    
    def __init__( self, parent: QW.QWidget, tag_service_key: bytes ):
        
        super().__init__( parent )
        
        help_text = 'Turn "namespace:number" tags into counters. Each tag becomes a count for its file, on a counter named after the namespace, and the tag is deleted. For instance, items:72 becomes a count of 72 on an "items" counter. A counter that does not exist yet is made for you.'
        help_text += '\n' * 2
        help_text += 'Enter the tags to convert. "items:72" is just that tag, and "items:*" or "items" is every items tag with a number. You can use * anywhere, so "*:*" is every namespaced tag with a number. Tags where the part after the colon is not a number are left alone.'
        help_text += '\n' * 2
        help_text += 'You will see what matched, and can back out, before anything changes.'
        
        st = ClientGUICommon.BetterStaticText( self, label = help_text )
        st.setWordWrap( True )
        
        self._tag_service = ClientGUICommon.BetterChoice( self )
        
        for service in CG.client_controller.services_manager.GetServices( ( HC.LOCAL_TAG, ) ):
            
            self._tag_service.addItem( service.GetName(), service.GetServiceKey() )
            
        
        self._tag_service.SetValue( tag_service_key )
        
        self._tag_filter = QW.QLineEdit( self )
        self._tag_filter.setPlaceholderText( 'items:*' )
        
        #
        
        rows = []
        
        rows.append( ( 'tag service: ', self._tag_service ) )
        rows.append( ( 'tags: ', self._tag_filter ) )
        
        gridbox = ClientGUICommon.WrapInGrid( self, rows )
        
        vbox = QP.VBoxLayout()
        
        QP.AddToLayout( vbox, st, CC.FLAGS_EXPAND_PERPENDICULAR )
        QP.AddToLayout( vbox, gridbox, CC.FLAGS_EXPAND_PERPENDICULAR )
        vbox.addStretch( 0 )
        
        self.widget().setLayout( vbox )
        
        self._tag_filter.setFocus()
        
    
    def GetValue( self ) -> tuple[ bytes, str, str ]:
        
        ( namespace_wildcard, subtag_wildcard ) = ClientCounters.ParseTagsToCountersFilter( self._tag_filter.text() )
        
        return ( self._tag_service.GetValue(), namespace_wildcard, subtag_wildcard )
        
    
