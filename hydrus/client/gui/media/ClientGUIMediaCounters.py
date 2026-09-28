from qtpy import QtWidgets as QW

from hydrus.core import HydrusExceptions
from hydrus.core import HydrusSerialisable

from hydrus.client import ClientConstants as CC
from hydrus.client.gui import ClientGUITopLevelWindowsPanels
from hydrus.client.gui import QtPorting as QP
from hydrus.client.gui.panels import ClientGUIScrolledPanels
from hydrus.client.gui.widgets import ClientGUICommon

# as high as a count can be set by hand
MAX_COUNT = 1000000

def ManageFileCounters( win: QW.QWidget, counters: list[ HydrusSerialisable.IdAndName ], counter_ids_to_counts: dict[ bytes, int ] ) -> dict[ bytes, int ]:
    
    # the new counts, for just the counters the user changed. raises CancelledException if the user backs out
    with ClientGUITopLevelWindowsPanels.DialogEdit( win, 'manage counts' ) as dlg:
        
        panel = ManageFileCountersPanel( dlg, counters, counter_ids_to_counts )
        
        dlg.SetPanel( panel )
        
        if dlg.exec() == QW.QDialog.DialogCode.Accepted:
            
            return panel.GetValue()
            
        
        raise HydrusExceptions.CancelledException( 'Dialog cancelled.' )
        
    

class ManageFileCountersPanel( ClientGUIScrolledPanels.EditPanel ):
    
    def __init__( self, parent: QW.QWidget, counters: list[ HydrusSerialisable.IdAndName ], counter_ids_to_counts: dict[ bytes, int ] ):
        
        super().__init__( parent )
        
        self._original_counter_ids_to_counts = { counter.object_id : counter_ids_to_counts.get( counter.object_id, 0 ) for counter in counters }
        
        help_text = 'Set this file\'s counts. Only the ones you change are saved.'
        
        st = ClientGUICommon.BetterStaticText( self, label = help_text )
        st.setWordWrap( True )
        
        self._filter = QW.QLineEdit( self )
        self._filter.setPlaceholderText( 'filter by name' )
        
        # ( counter, label, spinbox )
        self._rows = []
        
        grid_rows = []
        
        for counter in sorted( counters, key = lambda counter: counter.name.lower() ):
            
            label = ClientGUICommon.BetterStaticText( self, label = counter.name )
            
            spinbox = ClientGUICommon.BetterSpinBox( self, initial = self._original_counter_ids_to_counts[ counter.object_id ], min = 0, max = MAX_COUNT )
            
            self._rows.append( ( counter, label, spinbox ) )
            
            grid_rows.append( ( label, spinbox ) )
            
        
        gridbox = ClientGUICommon.WrapInGrid( self, grid_rows )
        
        #
        
        vbox = QP.VBoxLayout()
        
        QP.AddToLayout( vbox, st, CC.FLAGS_EXPAND_PERPENDICULAR )
        QP.AddToLayout( vbox, self._filter, CC.FLAGS_EXPAND_PERPENDICULAR )
        QP.AddToLayout( vbox, gridbox, CC.FLAGS_EXPAND_PERPENDICULAR )
        vbox.addStretch( 0 )
        
        self.widget().setLayout( vbox )
        
        # a handful of counters do not need a filter
        self._filter.setVisible( len( counters ) > 5 )
        
        self._filter.textChanged.connect( self._UpdateFilter )
        
        if len( self._rows ) > 0:
            
            self.setFocusProxy( self._rows[0][2] )
            
        
    
    def _UpdateFilter( self ):
        
        filter_text = self._filter.text().strip().lower()
        
        for ( counter, label, spinbox ) in self._rows:
            
            visible = filter_text in counter.name.lower()
            
            label.setVisible( visible )
            spinbox.setVisible( visible )
            
        
    
    def GetValue( self ) -> dict[ bytes, int ]:
        
        counter_ids_to_counts = {}
        
        for ( counter, label, spinbox ) in self._rows:
            
            count = spinbox.value()
            
            if count != self._original_counter_ids_to_counts[ counter.object_id ]:
                
                counter_ids_to_counts[ counter.object_id ] = count
                
            
        
        return counter_ids_to_counts
        
    
