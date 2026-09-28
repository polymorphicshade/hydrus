from qtpy import QtWidgets as QW

from hydrus.core import HydrusConstants as HC
from hydrus.core import HydrusExceptions

from hydrus.client import ClientConstants as CC
from hydrus.client.gui import ClientGUIDialogsQuick
from hydrus.client.gui import ClientGUITopLevelWindowsPanels
from hydrus.client.gui import QtPorting as QP
from hydrus.client.gui.canvas import ClientGUICanvasMedia
from hydrus.client.gui.lists import ClientGUIListBoxes
from hydrus.client.gui.panels import ClientGUIScrolledPanels
from hydrus.client.gui.widgets import ClientGUICommon
from hydrus.client.media import ClientMediaScriptedEvents

def ConvertScriptedEventToPretty( scripted_event: ClientMediaScriptedEvents.ScriptedEvent ) -> str:
    
    ( timestamp_ms, command ) = scripted_event
    
    return f'{ClientGUICanvasMedia.ConvertPlaybackTimestampToString( timestamp_ms )}: {command}'
    

def EditScriptedEvent( win: QW.QWidget, title: str, scripted_event: ClientMediaScriptedEvents.ScriptedEvent, duration_ms: int | None ) -> ClientMediaScriptedEvents.ScriptedEvent:
    
    # raises CancelledException if the user backs out
    with ClientGUITopLevelWindowsPanels.DialogEdit( win, title ) as dlg:
        
        panel = EditScriptedEventPanel( dlg, scripted_event, duration_ms )
        
        dlg.SetPanel( panel )
        
        if dlg.exec() == QW.QDialog.DialogCode.Accepted:
            
            return panel.GetValue()
            
        
        raise HydrusExceptions.CancelledException( 'Dialog cancelled.' )
        
    

def ManageScriptedEvents( win: QW.QWidget, scripted_events: list[ ClientMediaScriptedEvents.ScriptedEvent ], duration_ms: int | None ) -> list[ ClientMediaScriptedEvents.ScriptedEvent ]:
    
    # raises CancelledException if the user backs out
    with ClientGUITopLevelWindowsPanels.DialogEdit( win, 'manage scripted events' ) as dlg:
        
        panel = ManageScriptedEventsPanel( dlg, scripted_events, duration_ms )
        
        dlg.SetPanel( panel )
        
        if dlg.exec() == QW.QDialog.DialogCode.Accepted:
            
            return panel.GetValue()
            
        
        raise HydrusExceptions.CancelledException( 'Dialog cancelled.' )
        
    

class EditScriptedEventPanel( ClientGUIScrolledPanels.EditPanel ):
    
    def __init__( self, parent: QW.QWidget, scripted_event: ClientMediaScriptedEvents.ScriptedEvent, duration_ms: int | None ):
        
        super().__init__( parent )
        
        self._duration_ms = duration_ms
        
        ( timestamp_ms, command ) = scripted_event
        
        help_text = 'When playback of this file gets to this point, the command runs, as if you had typed it into your system\'s shell. For instance, "explorer C:\\" opens an explorer window on Windows.'
        help_text += '\n' * 2
        help_text += 'It runs every time normal playback goes past the point, including when the file loops. Seeking past it, or scanning through it while paused, does not run it. The media viewer does not wait for the command to finish.'
        
        st = ClientGUICommon.BetterStaticText( self, label = help_text )
        st.setWordWrap( True )
        
        self._timestamp = QW.QLineEdit( self )
        self._timestamp.setToolTip( 'The point in playback, like 1:05.250, or 1:02:03.000 for an hour in.' )
        
        self._command = QW.QLineEdit( self )
        self._command.setPlaceholderText( 'e.g. explorer C:\\' )
        
        #
        
        self._timestamp.setText( ClientGUICanvasMedia.ConvertPlaybackTimestampToString( timestamp_ms ) )
        self._command.setText( command )
        
        #
        
        rows = []
        
        rows.append( ( 'at: ', self._timestamp ) )
        rows.append( ( 'command: ', self._command ) )
        
        gridbox = ClientGUICommon.WrapInGrid( self, rows )
        
        vbox = QP.VBoxLayout()
        
        QP.AddToLayout( vbox, st, CC.FLAGS_EXPAND_PERPENDICULAR )
        QP.AddToLayout( vbox, gridbox, CC.FLAGS_EXPAND_PERPENDICULAR )
        vbox.addStretch( 0 )
        
        self.widget().setLayout( vbox )
        
        self.setFocusProxy( self._command )
        
    
    def GetValue( self ) -> ClientMediaScriptedEvents.ScriptedEvent:
        
        try:
            
            timestamp_ms = ClientGUICanvasMedia.ParsePlaybackTimestampString( self._timestamp.text() )
            
        except ValueError:
            
            raise HydrusExceptions.VetoException( 'Sorry, I could not understand that point in playback! Put it like 1:05.250.' )
            
        
        if self._duration_ms is not None and timestamp_ms > self._duration_ms:
            
            raise HydrusExceptions.VetoException( f'That is after the end of the file, which is {ClientGUICanvasMedia.ConvertPlaybackTimestampToString( self._duration_ms )}!' )
            
        
        command = self._command.text().strip()
        
        if command == '':
            
            raise HydrusExceptions.VetoException( 'Please enter a command!' )
            
        
        return ( timestamp_ms, command )
        
    

class ManageScriptedEventsPanel( ClientGUIScrolledPanels.EditPanel ):
    
    def __init__( self, parent: QW.QWidget, scripted_events: list[ ClientMediaScriptedEvents.ScriptedEvent ], duration_ms: int | None ):
        
        super().__init__( parent )
        
        self._duration_ms = duration_ms
        
        self._scripted_events = sorted( set( scripted_events ) )
        
        self._scripted_events_list = ClientGUIListBoxes.BetterQListWidget( self, delete_callable = self._Remove )
        self._scripted_events_list.setSelectionMode( QW.QAbstractItemView.SelectionMode.ExtendedSelection )
        
        self._edit_button = ClientGUICommon.BetterButton( self, 'edit' + HC.UNICODE_ELLIPSIS, self._Edit )
        self._remove_button = ClientGUICommon.BetterButton( self, 'remove', self._Remove )
        self._clear_button = ClientGUICommon.BetterButton( self, 'clear', self._Clear )
        
        #
        
        self._RefreshList()
        
        #
        
        button_hbox = QP.HBoxLayout()
        
        QP.AddToLayout( button_hbox, self._edit_button, CC.FLAGS_EXPAND_BOTH_WAYS )
        QP.AddToLayout( button_hbox, self._remove_button, CC.FLAGS_EXPAND_BOTH_WAYS )
        QP.AddToLayout( button_hbox, self._clear_button, CC.FLAGS_EXPAND_BOTH_WAYS )
        
        vbox = QP.VBoxLayout()
        
        QP.AddToLayout( vbox, self._scripted_events_list, CC.FLAGS_EXPAND_BOTH_WAYS )
        QP.AddToLayout( vbox, button_hbox, CC.FLAGS_EXPAND_PERPENDICULAR )
        
        self.widget().setLayout( vbox )
        
        self._scripted_events_list.itemSelectionChanged.connect( self._UpdateButtons )
        self._scripted_events_list.itemDoubleClicked.connect( self._Edit )
        
        self._UpdateButtons()
        
    
    def _Clear( self ):
        
        if len( self._scripted_events ) == 0:
            
            return
            
        
        result = ClientGUIDialogsQuick.GetYesNo( self, 'Remove all of this file\'s scripted events?' )
        
        if result != QW.QDialog.DialogCode.Accepted:
            
            return
            
        
        self._scripted_events = []
        
        self._RefreshList()
        
    
    def _Edit( self ):
        
        selected_scripted_events = self._scripted_events_list.GetData( only_selected = True )
        
        if len( selected_scripted_events ) != 1:
            
            return
            
        
        ( old_scripted_event, ) = selected_scripted_events
        
        try:
            
            new_scripted_event = EditScriptedEvent( self, 'edit scripted event', old_scripted_event, self._duration_ms )
            
        except HydrusExceptions.CancelledException:
            
            return
            
        
        self._scripted_events.remove( old_scripted_event )
        
        self._scripted_events = sorted( set( self._scripted_events + [ new_scripted_event ] ) )
        
        self._RefreshList( select_scripted_event = new_scripted_event )
        
    
    def _RefreshList( self, select_scripted_event = None ):
        
        self._scripted_events_list.clear()
        
        for scripted_event in self._scripted_events:
            
            self._scripted_events_list.Append( ConvertScriptedEventToPretty( scripted_event ), scripted_event, select = scripted_event == select_scripted_event )
            
        
        self._UpdateButtons()
        
    
    def _Remove( self ):
        
        selected_scripted_events = self._scripted_events_list.GetData( only_selected = True )
        
        if len( selected_scripted_events ) == 0:
            
            return
            
        
        self._scripted_events = [ scripted_event for scripted_event in self._scripted_events if scripted_event not in selected_scripted_events ]
        
        self._RefreshList()
        
    
    def _UpdateButtons( self ):
        
        num_selected = self._scripted_events_list.GetNumSelected()
        
        self._edit_button.setEnabled( num_selected == 1 )
        self._remove_button.setEnabled( num_selected > 0 )
        self._clear_button.setEnabled( len( self._scripted_events ) > 0 )
        
    
    def GetValue( self ) -> list[ ClientMediaScriptedEvents.ScriptedEvent ]:
        
        return list( self._scripted_events )
        
    
