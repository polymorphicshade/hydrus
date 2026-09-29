from qtpy import QtWidgets as QW

from hydrus.core import HydrusConstants as HC
from hydrus.core import HydrusExceptions

from hydrus.client import ClientConstants as CC
from hydrus.client.gui import ClientGUIDialogsQuick
from hydrus.client.gui import ClientGUIMenus
from hydrus.client.gui import ClientGUITopLevelWindowsPanels
from hydrus.client.gui import QtPorting as QP
from hydrus.client.gui.canvas import ClientGUICanvasMedia
from hydrus.client.gui.lists import ClientGUIListBoxes
from hydrus.client.gui.panels import ClientGUIScrolledPanels
from hydrus.client.gui.widgets import ClientGUICommon

# ( timestamp_ms, name )
Segment = tuple[ int, str ]

def AddSegment( segments: list[ Segment ], segment: Segment ) -> list[ Segment ]:
    
    return sorted( set( segments ).union( [ segment ] ) )
    

def AppendSegmentsMenu( menu: QW.QMenu, segments: list[ Segment ], add_callable, go_to_callable, manage_callable ) -> QW.QMenu:
    
    # the media viewer's segments menu. go_to_callable takes the timestamp to jump to
    segments_menu = ClientGUIMenus.GenerateMenu( menu )
    
    ClientGUIMenus.AppendMenuItem( segments_menu, 'add' + HC.UNICODE_ELLIPSIS, 'Mark this point in playback, and give it a name, so you can jump back to it later.', add_callable )
    
    go_to_menu = ClientGUIMenus.GenerateMenu( segments_menu )
    
    for segment in sorted( segments ):
        
        ( timestamp_ms, name ) = segment
        
        ClientGUIMenus.AppendMenuItem( go_to_menu, ConvertSegmentToPretty( segment ), f'Jump playback to "{name}".', go_to_callable, timestamp_ms )
        
    
    go_to_action = ClientGUIMenus.AppendMenu( segments_menu, go_to_menu, 'go to' )
    
    go_to_action.setEnabled( len( segments ) > 0 )
    
    ClientGUIMenus.AppendMenuItem( segments_menu, 'manage' + HC.UNICODE_ELLIPSIS, 'See this file\'s segments, and rename, move, remove, or clear them.', manage_callable )
    
    ClientGUIMenus.AppendMenu( menu, segments_menu, f'segments ({len( segments )})' if len( segments ) > 0 else 'segments' )
    
    return segments_menu
    

def ConvertSegmentToPretty( segment: Segment ) -> str:
    
    ( timestamp_ms, name ) = segment
    
    return f'{ClientGUICanvasMedia.ConvertPlaybackTimestampToString( timestamp_ms )}: {name}'
    

def EditSegment( win: QW.QWidget, title: str, segment: Segment, duration_ms: int | None ) -> Segment:
    
    # raises CancelledException if the user backs out
    with ClientGUITopLevelWindowsPanels.DialogEdit( win, title ) as dlg:
        
        panel = EditSegmentPanel( dlg, segment, duration_ms )
        
        dlg.SetPanel( panel )
        
        if dlg.exec() == QW.QDialog.DialogCode.Accepted:
            
            return panel.GetValue()
            
        
        raise HydrusExceptions.CancelledException( 'Dialog cancelled.' )
        
    

def ManageSegments( win: QW.QWidget, segments: list[ Segment ], duration_ms: int | None ) -> list[ Segment ]:
    
    # raises CancelledException if the user backs out
    with ClientGUITopLevelWindowsPanels.DialogEdit( win, 'manage segments' ) as dlg:
        
        panel = ManageSegmentsPanel( dlg, segments, duration_ms )
        
        dlg.SetPanel( panel )
        
        if dlg.exec() == QW.QDialog.DialogCode.Accepted:
            
            return panel.GetValue()
            
        
        raise HydrusExceptions.CancelledException( 'Dialog cancelled.' )
        
    

class EditSegmentPanel( ClientGUIScrolledPanels.EditPanel ):
    
    def __init__( self, parent: QW.QWidget, segment: Segment, duration_ms: int | None ):
        
        super().__init__( parent )
        
        self._duration_ms = duration_ms
        
        ( timestamp_ms, name ) = segment
        
        help_text = 'A segment is a named point in this video. You can jump to it from the media viewer\'s right-click->segments->go to menu.'
        
        st = ClientGUICommon.BetterStaticText( self, label = help_text )
        st.setWordWrap( True )
        
        self._timestamp = QW.QLineEdit( self )
        self._timestamp.setToolTip( 'The point in playback, like 1:05.250, or 1:02:03.000 for an hour in.' )
        
        self._name = QW.QLineEdit( self )
        self._name.setPlaceholderText( 'e.g. chorus' )
        
        #
        
        self._timestamp.setText( ClientGUICanvasMedia.ConvertPlaybackTimestampToString( timestamp_ms ) )
        self._name.setText( name )
        
        #
        
        rows = []
        
        rows.append( ( 'name: ', self._name ) )
        rows.append( ( 'at: ', self._timestamp ) )
        
        gridbox = ClientGUICommon.WrapInGrid( self, rows )
        
        vbox = QP.VBoxLayout()
        
        QP.AddToLayout( vbox, st, CC.FLAGS_EXPAND_PERPENDICULAR )
        QP.AddToLayout( vbox, gridbox, CC.FLAGS_EXPAND_PERPENDICULAR )
        vbox.addStretch( 0 )
        
        self.widget().setLayout( vbox )
        
        self.setFocusProxy( self._name )
        
    
    def GetValue( self ) -> Segment:
        
        name = self._name.text().strip()
        
        if name == '':
            
            raise HydrusExceptions.VetoException( 'Please enter a name!' )
            
        
        try:
            
            timestamp_ms = ClientGUICanvasMedia.ParsePlaybackTimestampString( self._timestamp.text() )
            
        except ValueError:
            
            raise HydrusExceptions.VetoException( 'Sorry, I could not understand that point in playback! Put it like 1:05.250.' )
            
        
        if self._duration_ms is not None and timestamp_ms > self._duration_ms:
            
            raise HydrusExceptions.VetoException( f'That is after the end of the file, which is {ClientGUICanvasMedia.ConvertPlaybackTimestampToString( self._duration_ms )}!' )
            
        
        return ( timestamp_ms, name )
        
    

class ManageSegmentsPanel( ClientGUIScrolledPanels.EditPanel ):
    
    def __init__( self, parent: QW.QWidget, segments: list[ Segment ], duration_ms: int | None ):
        
        super().__init__( parent )
        
        self._duration_ms = duration_ms
        
        self._segments = sorted( set( segments ) )
        
        self._segments_list = ClientGUIListBoxes.BetterQListWidget( self, delete_callable = self._Remove )
        self._segments_list.setSelectionMode( QW.QAbstractItemView.SelectionMode.ExtendedSelection )
        
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
        
        QP.AddToLayout( vbox, self._segments_list, CC.FLAGS_EXPAND_BOTH_WAYS )
        QP.AddToLayout( vbox, button_hbox, CC.FLAGS_EXPAND_PERPENDICULAR )
        
        self.widget().setLayout( vbox )
        
        self._segments_list.itemSelectionChanged.connect( self._UpdateButtons )
        self._segments_list.itemDoubleClicked.connect( self._Edit )
        
        self._UpdateButtons()
        
    
    def _Clear( self ):
        
        if len( self._segments ) == 0:
            
            return
            
        
        result = ClientGUIDialogsQuick.GetYesNo( self, 'Remove all of this file\'s segments?' )
        
        if result != QW.QDialog.DialogCode.Accepted:
            
            return
            
        
        self._segments = []
        
        self._RefreshList()
        
    
    def _Edit( self ):
        
        selected_segments = self._segments_list.GetData( only_selected = True )
        
        if len( selected_segments ) != 1:
            
            return
            
        
        ( old_segment, ) = selected_segments
        
        try:
            
            new_segment = EditSegment( self, 'edit segment', old_segment, self._duration_ms )
            
        except HydrusExceptions.CancelledException:
            
            return
            
        
        self._segments.remove( old_segment )
        
        self._segments = AddSegment( self._segments, new_segment )
        
        self._RefreshList( select_segment = new_segment )
        
    
    def _RefreshList( self, select_segment = None ):
        
        self._segments_list.clear()
        
        for segment in self._segments:
            
            self._segments_list.Append( ConvertSegmentToPretty( segment ), segment, select = segment == select_segment )
            
        
        self._UpdateButtons()
        
    
    def _Remove( self ):
        
        selected_segments = self._segments_list.GetData( only_selected = True )
        
        if len( selected_segments ) == 0:
            
            return
            
        
        self._segments = [ segment for segment in self._segments if segment not in selected_segments ]
        
        self._RefreshList()
        
    
    def _UpdateButtons( self ):
        
        num_selected = self._segments_list.GetNumSelected()
        
        self._edit_button.setEnabled( num_selected == 1 )
        self._remove_button.setEnabled( num_selected > 0 )
        self._clear_button.setEnabled( len( self._segments ) > 0 )
        
    
    def GetValue( self ) -> list[ Segment ]:
        
        return list( self._segments )
        
    
