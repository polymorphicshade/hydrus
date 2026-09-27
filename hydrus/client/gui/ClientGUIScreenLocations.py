from qtpy import QtWidgets as QW

from hydrus.core import HydrusExceptions

from hydrus.client import ClientConstants as CC
from hydrus.client import ClientGlobals as CG
from hydrus.client import ClientScreenLocations
from hydrus.client.gui import ClientGUIDialogsMessage
from hydrus.client.gui import ClientGUIDialogsQuick
from hydrus.client.gui import ClientGUITopLevelWindowsPanels
from hydrus.client.gui import QtPorting as QP
from hydrus.client.gui.panels import ClientGUIScrolledPanels
from hydrus.client.gui.widgets import ClientGUICommon

# plenty of room for big multi-monitor desktops, and for windows that hang off the top or left edge
MAX_COORDINATE = 100000

def EditScreenLocation( win: QW.QWidget, title: str, screen_location: ClientScreenLocations.ScreenLocation, other_names: list[ str ] ) -> ClientScreenLocations.ScreenLocation:
    
    # raises CancelledException if the user backs out
    with ClientGUITopLevelWindowsPanels.DialogEdit( win, title ) as dlg:
        
        panel = EditScreenLocationPanel( dlg, screen_location, other_names )
        
        dlg.SetPanel( panel )
        
        if dlg.exec() == QW.QDialog.DialogCode.Accepted:
            
            return panel.GetValue()
            
        
        raise HydrusExceptions.CancelledException( 'Dialog cancelled.' )
        
    

def GetCurrentScreenGeometries() -> list[ ClientScreenLocations.ScreenGeometry ]:
    
    # the primary screen goes first, so it is the fallback for a screen that is not connected
    primary_screen = QW.QApplication.primaryScreen()
    
    screens = sorted( QW.QApplication.screens(), key = lambda screen: screen is not primary_screen )
    
    screen_geometries = []
    
    for screen in screens:
        
        geometry = screen.geometry()
        
        screen_geometries.append( ( screen.name(), geometry.x(), geometry.y(), geometry.width(), geometry.height() ) )
        
    
    return screen_geometries
    

def GetScreenLocationForWindow( window: QW.QWidget, name: str ) -> ClientScreenLocations.ScreenLocation:
    
    screen = window.screen()
    
    screen_geometry = screen.geometry()
    frame_geometry = window.frameGeometry()
    
    return ( name, screen.name(), frame_geometry.x() - screen_geometry.x(), frame_geometry.y() - screen_geometry.y(), window.width(), window.height() )
    

def MoveWindowToScreenLocation( win: QW.QWidget, window: QW.QWidget, screen_location: ClientScreenLocations.ScreenLocation ):
    
    ( found_the_screen, x, y, width, height ) = ClientScreenLocations.GetTargetGeometry( screen_location, GetCurrentScreenGeometries() )
    
    if not found_the_screen:
        
        ( name, screen_name, saved_x, saved_y, saved_width, saved_height ) = screen_location
        
        ClientGUIDialogsMessage.ShowWarning( win, f'The screen "{screen_name}" does not seem to be connected right now, so the window is going to your main screen instead.' )
        
    
    # a fullscreen or maximised window ignores a move, so it goes back to a normal one first
    if window.isFullScreen() or window.isMaximized():
        
        window.showNormal()
        
    
    # moving onto a screen with a different scale can resize the window, so the size goes on once it is there
    window.move( x, y )
    window.resize( width, height )
    window.move( x, y )
    

def SaveScreenLocationForWindow( win: QW.QWidget, window: QW.QWidget ):
    
    new_options = CG.client_controller.new_options
    
    screen_locations = new_options.GetScreenLocations()
    
    other_names = [ screen_location[0] for screen_location in screen_locations ]
    
    try:
        
        screen_location = EditScreenLocation( win, 'save screen location', GetScreenLocationForWindow( window, '' ), other_names )
        
    except HydrusExceptions.CancelledException:
        
        return
        
    
    screen_locations.append( screen_location )
    
    new_options.SetScreenLocations( screen_locations )
    
    CG.client_controller.Write( 'serialisable', new_options )
    

def SelectScreenLocation( win: QW.QWidget ) -> ClientScreenLocations.ScreenLocation:
    
    # raises CancelledException if the user backs out or there is nothing to pick
    screen_locations = CG.client_controller.new_options.GetScreenLocations()
    
    if len( screen_locations ) == 0:
        
        ClientGUIDialogsMessage.ShowInformation( win, 'You do not have any screen locations yet! Put a media viewer where you like it and hit right-click->screen->save location.' )
        
        raise HydrusExceptions.CancelledException( 'No screen locations.' )
        
    
    choice_tuples = [ ( ClientScreenLocations.ConvertScreenLocationToPretty( screen_location ), screen_location ) for screen_location in screen_locations ]
    
    return ClientGUIDialogsQuick.SelectFromList( win, 'move to screen location', choice_tuples, allow_insta_one_item_select = False )
    

class EditScreenLocationPanel( ClientGUIScrolledPanels.EditPanel ):
    
    def __init__( self, parent: QW.QWidget, screen_location: ClientScreenLocations.ScreenLocation, other_names: list[ str ] ):
        
        super().__init__( parent )
        
        self._other_names = other_names
        
        ( name, screen_name, x, y, width, height ) = screen_location
        
        self._name = QW.QLineEdit( self )
        self._name.setPlaceholderText( 'e.g. left monitor, top half' )
        
        self._screen_name = ClientGUICommon.BetterChoice( self )
        
        current_screen_names = []
        
        for screen in QW.QApplication.screens():
            
            geometry = screen.geometry()
            
            model = screen.model().strip()
            
            label = f'{screen.name()} ({model}, {geometry.width()}x{geometry.height()})' if model != '' else f'{screen.name()} ({geometry.width()}x{geometry.height()})'
            
            self._screen_name.addItem( label, screen.name() )
            
            current_screen_names.append( screen.name() )
            
        
        if screen_name not in current_screen_names:
            
            self._screen_name.addItem( f'{screen_name} (not connected right now)', screen_name )
            
        
        self._x = ClientGUICommon.BetterSpinBox( self, min = - MAX_COORDINATE, max = MAX_COORDINATE )
        self._y = ClientGUICommon.BetterSpinBox( self, min = - MAX_COORDINATE, max = MAX_COORDINATE )
        self._width = ClientGUICommon.BetterSpinBox( self, min = 1, max = MAX_COORDINATE )
        self._height = ClientGUICommon.BetterSpinBox( self, min = 1, max = MAX_COORDINATE )
        
        tt = 'X and Y are where the top-left corner of the window goes, measured from the top-left corner of the screen.'
        
        self._x.setToolTip( tt )
        self._y.setToolTip( tt )
        
        #
        
        self._name.setText( name )
        self._screen_name.SetValue( screen_name )
        self._x.setValue( x )
        self._y.setValue( y )
        self._width.setValue( width )
        self._height.setValue( height )
        
        #
        
        rows = []
        
        rows.append( ( 'name: ', self._name ) )
        rows.append( ( 'screen: ', self._screen_name ) )
        rows.append( ( 'x: ', self._x ) )
        rows.append( ( 'y: ', self._y ) )
        rows.append( ( 'width: ', self._width ) )
        rows.append( ( 'height: ', self._height ) )
        
        gridbox = ClientGUICommon.WrapInGrid( self, rows )
        
        vbox = QP.VBoxLayout()
        
        QP.AddToLayout( vbox, gridbox, CC.FLAGS_EXPAND_BOTH_WAYS )
        
        self.widget().setLayout( vbox )
        
        self.setFocusProxy( self._name )
        
    
    def GetValue( self ) -> ClientScreenLocations.ScreenLocation:
        
        screen_location = (
            ClientScreenLocations.NormaliseScreenLocationName( self._name.text() ),
            self._screen_name.GetValue(),
            self._x.value(),
            self._y.value(),
            self._width.value(),
            self._height.value()
        )
        
        error = ClientScreenLocations.GetScreenLocationError( screen_location, self._other_names )
        
        if error is not None:
            
            raise HydrusExceptions.VetoException( error )
            
        
        return screen_location
        
    
