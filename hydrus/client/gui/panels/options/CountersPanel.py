from hydrus.core import HydrusData
from hydrus.core import HydrusExceptions
from hydrus.core import HydrusSerialisable

from hydrus.client import ClientConstants as CC
from hydrus.client import ClientGlobals as CG
from hydrus.client.gui import ClientGUIDialogsMessage
from hydrus.client.gui import ClientGUIDialogsQuick
from hydrus.client.gui import QtPorting as QP
from hydrus.client.gui.lists import ClientGUIListBoxes
from hydrus.client.gui.panels.options import ClientGUIOptionsPanelBase
from hydrus.client.gui.widgets import ClientGUICommon

class CountersPanel( ClientGUIOptionsPanelBase.OptionsPagePanel ):
    
    def __init__( self, parent, new_options ):
        
        super().__init__( parent )
        
        self._new_options = new_options
        
        self._original_counters = self._new_options.GetCounters()
        
        help_text = 'Counters are tallies you keep for each file, like how many times you have watched it. In the media viewer, right-click->counters and click one to add one to that file\'s count, or use \'manage\' to set any of its counts to whatever number you like.'
        help_text += '\n' * 2
        help_text += 'You can search for them with system:counter, for instance "system:counter tally > 2". Names are not case-sensitive.'
        help_text += '\n' * 2
        help_text += 'Renaming a counter keeps its counts. Deleting a counter also deletes its counts for every file.'
        
        st = ClientGUICommon.BetterStaticText( self, label = help_text )
        st.setWordWrap( True )
        
        self._counters = ClientGUIListBoxes.AddEditDeleteListBox( self, 8, self._ConvertCounterToPretty, self._Add, self._Edit )
        
        #
        
        self._counters.AddDatas( self._original_counters )
        
        #
        
        vbox = QP.VBoxLayout()
        
        QP.AddToLayout( vbox, st, CC.FLAGS_EXPAND_PERPENDICULAR )
        QP.AddToLayout( vbox, self._counters, CC.FLAGS_EXPAND_BOTH_WAYS )
        
        self.setLayout( vbox )
        
    
    def _Add( self ) -> HydrusSerialisable.IdAndName:
        
        name = self._EnterName( '' )
        
        return HydrusSerialisable.IdAndName( HydrusData.GenerateKey(), name )
        
    
    def _ConvertCounterToPretty( self, counter: HydrusSerialisable.IdAndName ) -> str:
        
        return counter.name
        
    
    def _Edit( self, counter: HydrusSerialisable.IdAndName ) -> HydrusSerialisable.IdAndName:
        
        name = self._EnterName( counter.name, counter_being_edited = counter )
        
        # same id, so the counts stay with it
        return HydrusSerialisable.IdAndName( counter.object_id, name )
        
    
    def _EnterName( self, default: str, counter_being_edited: HydrusSerialisable.IdAndName | None = None ) -> str:
        
        try:
            
            name = ClientGUIDialogsQuick.EnterText( self, 'Enter a name for the counter.', default = default )
            
        except HydrusExceptions.CancelledException:
            
            raise HydrusExceptions.VetoException()
            
        
        name = name.strip()
        
        if name == '':
            
            raise HydrusExceptions.VetoException()
            
        
        other_names = { counter.name.lower() for counter in self._counters.GetData() if counter_being_edited is None or counter.object_id != counter_being_edited.object_id }
        
        if name.lower() in other_names:
            
            ClientGUIDialogsMessage.ShowWarning( self, f'There is already a counter called "{name}"!' )
            
            raise HydrusExceptions.VetoException()
            
        
        return name
        
    
    def UpdateOptions( self ):
        
        counters = self._counters.GetData()
        
        self._new_options.SetCounters( counters )
        
        # a deleted counter's counts go with it
        deleted_counter_ids = { counter.object_id for counter in self._original_counters }.difference( ( counter.object_id for counter in counters ) )
        
        if len( deleted_counter_ids ) > 0:
            
            CG.client_controller.Write( 'delete_file_counters', deleted_counter_ids )
            
        
    
