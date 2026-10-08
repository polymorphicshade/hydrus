from qtpy import QtCore as QC
from qtpy import QtWidgets as QW

from hydrus.core import HydrusExceptions

from hydrus.client import ClientConstants as CC
from hydrus.client.gui import QtPorting as QP
from hydrus.client.gui.panels import ClientGUIScrolledPanels
from hydrus.client.gui.widgets import ClientGUICommon

class EditTextSpinboxPanel( ClientGUIScrolledPanels.EditPanel ):
    
    def __init__( self, parent: QW.QWidget, message: str, default = 0, min_value = None, max_value = None ):
        
        super().__init__( parent )
        
        self._spinbox = QW.QSpinBox( self )
        
        if min_value is not None:
            
            self._spinbox.setMinimum( min_value )
            
        
        if max_value is not None:
            
            self._spinbox.setMaximum( max_value )
            
        
        self._spinbox.setValue( default )
        
        #
        
        st_message = ClientGUICommon.BetterStaticText( self, message )
        st_message.setWordWrap( True )
        
        vbox = QP.VBoxLayout()
        
        QP.AddToLayout( vbox, st_message, CC.FLAGS_EXPAND_PERPENDICULAR )
        QP.AddToLayout( vbox, self._spinbox, CC.FLAGS_EXPAND_PERPENDICULAR )
        
        vbox.addStretch( 0 )
        
        self.widget().setLayout( vbox )
        
        self._spinbox.setFocus( QC.Qt.FocusReason.OtherFocusReason )
        
    
    def GetValue( self ):
        
        return self._spinbox.value()
        
    

class EditNumberRangePanel( ClientGUIScrolledPanels.EditPanel ):
    
    def __init__( self, parent: QW.QWidget, message: str, default_min = 0, default_max = 0, min_value = None, max_value = None ):
        
        super().__init__( parent )
        
        self._min_spinbox = QW.QSpinBox( self )
        self._max_spinbox = QW.QSpinBox( self )
        
        for spinbox in ( self._min_spinbox, self._max_spinbox ):
            
            if min_value is not None:
                
                spinbox.setMinimum( min_value )
                
            
            if max_value is not None:
                
                spinbox.setMaximum( max_value )
                
            
        
        self._min_spinbox.setValue( default_min )
        self._max_spinbox.setValue( default_max )
        
        #
        
        st_message = ClientGUICommon.BetterStaticText( self, message )
        st_message.setWordWrap( True )
        
        rows = []
        
        rows.append( ( 'min: ', self._min_spinbox ) )
        rows.append( ( 'max: ', self._max_spinbox ) )
        
        gridbox = ClientGUICommon.WrapInGrid( self, rows )
        
        vbox = QP.VBoxLayout()
        
        QP.AddToLayout( vbox, st_message, CC.FLAGS_EXPAND_PERPENDICULAR )
        QP.AddToLayout( vbox, gridbox, CC.FLAGS_EXPAND_SIZER_PERPENDICULAR )
        
        vbox.addStretch( 0 )
        
        self.widget().setLayout( vbox )
        
        self._min_spinbox.setFocus( QC.Qt.FocusReason.OtherFocusReason )
        
    
    def GetValue( self ) -> tuple[ int, int ]:
        
        min_number = self._min_spinbox.value()
        max_number = self._max_spinbox.value()
        
        if min_number > max_number:
            
            raise HydrusExceptions.VetoException( 'The min cannot be more than the max!' )
            
        
        return ( min_number, max_number )
        
    
