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
from hydrus.client.media import ClientMediaPlaybackFreezes

DEFAULT_PLAYBACK_FREEZE_DURATION_MS = 2000

def ConvertPlaybackFreezeToPretty( freeze: ClientMediaPlaybackFreezes.PlaybackFreeze ) -> str:
    
    ( timestamp_ms, duration_ms ) = freeze
    
    return f'{ClientGUICanvasMedia.ConvertPlaybackTimestampToString( timestamp_ms )}: hold for {ClientMediaPlaybackFreezes.ConvertPlaybackFreezeDurationToString( duration_ms )}'
    

def EditPlaybackFreeze( win: QW.QWidget, title: str, freeze: ClientMediaPlaybackFreezes.PlaybackFreeze, duration_ms: int | None ) -> ClientMediaPlaybackFreezes.PlaybackFreeze:
    
    # raises CancelledException if the user backs out
    with ClientGUITopLevelWindowsPanels.DialogEdit( win, title ) as dlg:
        
        panel = EditPlaybackFreezePanel( dlg, freeze, duration_ms )
        
        dlg.SetPanel( panel )
        
        if dlg.exec() == QW.QDialog.DialogCode.Accepted:
            
            return panel.GetValue()
            
        
        raise HydrusExceptions.CancelledException( 'Dialog cancelled.' )
        


def ManagePlaybackFreezes( win: QW.QWidget, freezes: list[ ClientMediaPlaybackFreezes.PlaybackFreeze ], duration_ms: int | None ) -> list[ ClientMediaPlaybackFreezes.PlaybackFreeze ]:
    
    # raises CancelledException if the user backs out
    with ClientGUITopLevelWindowsPanels.DialogEdit( win, 'manage freezes' ) as dlg:
        
        panel = ManagePlaybackFreezesPanel( dlg, freezes, duration_ms )
        
        dlg.SetPanel( panel )
        
        if dlg.exec() == QW.QDialog.DialogCode.Accepted:
            
            return panel.GetValue()
            
        
        raise HydrusExceptions.CancelledException( 'Dialog cancelled.' )
        


class EditPlaybackFreezePanel( ClientGUIScrolledPanels.EditPanel ):
    
    def __init__( self, parent: QW.QWidget, freeze: ClientMediaPlaybackFreezes.PlaybackFreeze, duration_ms: int | None ):
        
        super().__init__( parent )
        
        self._duration_ms = duration_ms
        
        ( timestamp_ms, freeze_duration_ms ) = freeze
        
        help_text = 'When playback of this file gets to this point, it pauses on that frame for this long, and then plays on by itself.'
        help_text += '\n' * 2
        help_text += 'It holds every time normal playback goes past the point, including when the file loops. Seeking past it, or scanning through it while paused, does not hold. Hitting play while it holds plays on straight away.'
        
        st = ClientGUICommon.BetterStaticText( self, label = help_text )
        st.setWordWrap( True )
        
        self._timestamp = QW.QLineEdit( self )
        self._timestamp.setToolTip( 'The point in playback, like 1:05.250, or 1:02:03.000 for an hour in.' )
        
        self._freeze_duration_s = QW.QDoubleSpinBox( self )
        self._freeze_duration_s.setDecimals( 3 )
        self._freeze_duration_s.setRange( ClientMediaPlaybackFreezes.MIN_PLAYBACK_FREEZE_DURATION_MS / 1000, ClientMediaPlaybackFreezes.MAX_PLAYBACK_FREEZE_DURATION_MS / 1000 )
        self._freeze_duration_s.setSingleStep( 0.5 )
        self._freeze_duration_s.setSuffix( ' seconds' )
        self._freeze_duration_s.setToolTip( 'How long to hold the frame for.' )
        
        #
        
        self._timestamp.setText( ClientGUICanvasMedia.ConvertPlaybackTimestampToString( timestamp_ms ) )
        self._freeze_duration_s.setValue( freeze_duration_ms / 1000 )
        
        #
        
        rows = []
        
        rows.append( ( 'at: ', self._timestamp ) )
        rows.append( ( 'hold for: ', self._freeze_duration_s ) )
        
        gridbox = ClientGUICommon.WrapInGrid( self, rows )
        
        vbox = QP.VBoxLayout()
        
        QP.AddToLayout( vbox, st, CC.FLAGS_EXPAND_PERPENDICULAR )
        QP.AddToLayout( vbox, gridbox, CC.FLAGS_EXPAND_PERPENDICULAR )
        vbox.addStretch( 0 )
        
        self.widget().setLayout( vbox )
        
        self.setFocusProxy( self._freeze_duration_s )
        
    
    def GetValue( self ) -> ClientMediaPlaybackFreezes.PlaybackFreeze:
        
        try:
            
            timestamp_ms = ClientGUICanvasMedia.ParsePlaybackTimestampString( self._timestamp.text() )
            
        except ValueError:
            
            raise HydrusExceptions.VetoException( 'Sorry, I could not understand that point in playback! Put it like 1:05.250.' )
            
        
        if self._duration_ms is not None and timestamp_ms > self._duration_ms:
            
            raise HydrusExceptions.VetoException( f'That is after the end of the file, which is {ClientGUICanvasMedia.ConvertPlaybackTimestampToString( self._duration_ms )}!' )
            
        
        freeze_duration_ms = int( round( self._freeze_duration_s.value() * 1000 ) )
        
        return ( timestamp_ms, freeze_duration_ms )
        


class ManagePlaybackFreezesPanel( ClientGUIScrolledPanels.EditPanel ):
    
    def __init__( self, parent: QW.QWidget, freezes: list[ ClientMediaPlaybackFreezes.PlaybackFreeze ], duration_ms: int | None ):
        
        super().__init__( parent )
        
        self._duration_ms = duration_ms
        
        self._freezes = ClientMediaPlaybackFreezes.NormalisePlaybackFreezes( freezes )
        
        self._freezes_list = ClientGUIListBoxes.BetterQListWidget( self, delete_callable = self._Remove )
        self._freezes_list.setSelectionMode( QW.QAbstractItemView.SelectionMode.ExtendedSelection )
        
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
        
        QP.AddToLayout( vbox, self._freezes_list, CC.FLAGS_EXPAND_BOTH_WAYS )
        QP.AddToLayout( vbox, button_hbox, CC.FLAGS_EXPAND_PERPENDICULAR )
        
        self.widget().setLayout( vbox )
        
        self._freezes_list.itemSelectionChanged.connect( self._UpdateButtons )
        self._freezes_list.itemDoubleClicked.connect( self._Edit )
        
        self._UpdateButtons()
        
    
    def _Clear( self ):
        
        if len( self._freezes ) == 0:
            
            return
            
        
        result = ClientGUIDialogsQuick.GetYesNo( self, 'Remove all of this file\'s freezes?' )
        
        if result != QW.QDialog.DialogCode.Accepted:
            
            return
            
        
        self._freezes = []
        
        self._RefreshList()
        
    
    def _Edit( self ):
        
        selected_freezes = self._freezes_list.GetData( only_selected = True )
        
        if len( selected_freezes ) != 1:
            
            return
            
        
        ( old_freeze, ) = selected_freezes
        
        try:
            
            new_freeze = EditPlaybackFreeze( self, 'edit freeze', old_freeze, self._duration_ms )
            
        except HydrusExceptions.CancelledException:
            
            return
            
        
        self._freezes.remove( old_freeze )
        
        # moving it onto another freeze's point replaces that one
        self._freezes = ClientMediaPlaybackFreezes.NormalisePlaybackFreezes( self._freezes + [ new_freeze ] )
        
        self._RefreshList( select_freeze = new_freeze )
        
    
    def _RefreshList( self, select_freeze = None ):
        
        self._freezes_list.clear()
        
        for freeze in self._freezes:
            
            self._freezes_list.Append( ConvertPlaybackFreezeToPretty( freeze ), freeze, select = freeze == select_freeze )
            
        
        self._UpdateButtons()
        
    
    def _Remove( self ):
        
        selected_freezes = self._freezes_list.GetData( only_selected = True )
        
        if len( selected_freezes ) == 0:
            
            return
            
        
        self._freezes = [ freeze for freeze in self._freezes if freeze not in selected_freezes ]
        
        self._RefreshList()
        
    
    def _UpdateButtons( self ):
        
        num_selected = self._freezes_list.GetNumSelected()
        
        self._edit_button.setEnabled( num_selected == 1 )
        self._remove_button.setEnabled( num_selected > 0 )
        self._clear_button.setEnabled( len( self._freezes ) > 0 )
        
    
    def GetValue( self ) -> list[ ClientMediaPlaybackFreezes.PlaybackFreeze ]:
        
        return list( self._freezes )
        
    
