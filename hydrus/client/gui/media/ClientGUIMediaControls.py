from qtpy import QtCore as QC
from qtpy import QtWidgets as QW

from hydrus.client import ClientApplicationCommand as CAC
from hydrus.client import ClientConstants as CC
from hydrus.client import ClientGlobals as CG
from hydrus.client.gui import ClientGUIFunctions
from hydrus.client.gui import QtPorting as QP
from hydrus.client.gui.widgets import ClientGUICommon

AUDIO_GLOBAL = 0
AUDIO_MEDIA_VIEWER = 1
AUDIO_PREVIEW = 2

volume_types_str_lookup = {}

volume_types_str_lookup[ AUDIO_GLOBAL ] = 'global'
volume_types_str_lookup[ AUDIO_MEDIA_VIEWER ] = 'media viewer'
volume_types_str_lookup[ AUDIO_PREVIEW ] = 'preview'

volume_types_to_option_names = {}

volume_types_to_option_names[ AUDIO_GLOBAL ] = ( 'global_audio_mute', 'global_audio_volume' )
volume_types_to_option_names[ AUDIO_MEDIA_VIEWER ] = ( 'media_viewer_audio_mute', 'media_viewer_audio_volume' )
volume_types_to_option_names[ AUDIO_PREVIEW ] = ( 'preview_audio_mute', 'preview_audio_volume' )

def ChangeVolume( volume_type, volume ):
    
    ( mute_option_name, volume_option_name ) = volume_types_to_option_names[ volume_type ]
    
    CG.client_controller.new_options.SetInteger( volume_option_name, volume )
    
    CG.client_controller.pub( 'new_audio_volume' )
    

def FlipMute( volume_type ):
    
    ( mute_option_name, volume_option_name ) = volume_types_to_option_names[ volume_type ]
    
    CG.client_controller.new_options.FlipBoolean( mute_option_name )
    
    CG.client_controller.pub( 'notify_new_audio_mute_options' )
    

def SetMute( volume_type, mute ):
    
    ( mute_option_name, volume_option_name ) = volume_types_to_option_names[ volume_type ]
    
    CG.client_controller.new_options.SetBoolean( mute_option_name, mute )
    
    CG.client_controller.pub( 'notify_new_audio_mute_options' )
    

class AudioMuteButton( ClientGUICommon.IconButton ):
    
    def __init__( self, parent, volume_type ):
        
        self._volume_type = volume_type
        
        icon = self._GetCorrectIcon()
        
        super().__init__( parent, icon, FlipMute, self._volume_type )
        
        CG.client_controller.sub( self, 'NotifyNewAudioMuteOptions', 'notify_new_audio_mute_options' )
        
    
    def _GetCorrectIcon( self ):
        
        ( mute_option_name, volume_option_name ) = volume_types_to_option_names[ self._volume_type ]
        
        if CG.client_controller.new_options.GetBoolean( mute_option_name ):
            
            icon = CC.global_icons().mute
            
        else:
            
            icon = CC.global_icons().sound
            
        
        return icon
        
    
    def NotifyNewAudioMuteOptions( self ):
        
        icon = self._GetCorrectIcon()
        
        self.SetIconSmart( icon )
        
    

class PerPlayerAudioMuteButton( ClientGUICommon.IconButton ):
    
    def __init__( self, parent, mute_owner ):
        
        # the mute_owner is a media container. it has GetCurrentMuteState, FlipPerPlayerMuteState, and a muteStateChanged signal
        self._mute_owner = mute_owner
        
        icon = self._GetCorrectIcon()
        
        super().__init__( parent, icon, self._mute_owner.FlipPerPlayerMuteState )
        
        self.SetToolTipWithShortcuts( 'mute/unmute just this media viewer', CAC.SIMPLE_PER_PLAYER_AUDIO_MUTE_FLIP )
        
        self._mute_owner.muteStateChanged.connect( self.NotifyNewMuteState )
        
    
    def _GetCorrectIcon( self ):
        
        if self._mute_owner.GetCurrentMuteState():
            
            return CC.global_icons().mute
            
        else:
            
            return CC.global_icons().sound
            
        
    
    def NotifyNewMuteState( self ):
        
        self.SetIconSmart( self._GetCorrectIcon() )
        
    

class VolumeControl( QW.QWidget ):
    
    def __init__( self, parent, canvas_type, direction = 'down', per_player_audio_owner = None ):
        
        # per_player_audio_owner is a media container. if we have one, our mute and volume only affect that player
        
        super().__init__( parent )
        
        self._canvas_type = canvas_type
        
        if per_player_audio_owner is None:
            
            self._global_mute = AudioMuteButton( self, AUDIO_GLOBAL )
            
            self._global_mute.setToolTip( ClientGUIFunctions.WrapToolTip( 'Global mute/unmute' ) )
            
        else:
            
            # a media viewer window mutes itself and leaves the other windows alone
            self._global_mute = PerPlayerAudioMuteButton( self, per_player_audio_owner )
            
        
        self._global_mute.setFocusPolicy( QC.Qt.FocusPolicy.NoFocus )
        
        vbox = QP.VBoxLayout( margin = 0, spacing = 0 )
        
        QP.AddToLayout( vbox, self._global_mute, CC.FLAGS_EXPAND_SIZER_BOTH_WAYS )
        
        self.setLayout( vbox )
        
        # TODO: same as with much of the media controls mess, this needs to be plugged into the layout system properly
        # we should have a custom layout here that specifies where the slider should go and do raise/show/hide while still reporting a nice small sizeHint
        
        self._popup_window = self._PopupWindow( self, canvas_type, direction = direction, per_player_audio_owner = per_player_audio_owner )
        
    
    def enterEvent( self, event ):
        
        if not self.isVisible():
            
            event.ignore()
            
            return
            
        
        self._popup_window.DoShowHide()
        
        event.ignore()
        
    
    def leaveEvent( self, event ):
        
        if not self.isVisible():
            
            self._popup_window.setVisible( False )
            
            event.ignore()
            
            return
            
        
        self._popup_window.DoShowHide()
        
        event.ignore()
        
    
    def moveEvent( self, event ):
        
        super().moveEvent( event )
        
        self._popup_window.DoShowHide()
        
    
    def PopupIsVisible( self ):
        
        return not self._popup_window.isHidden()
        
    
    def resizeEvent( self, event ):
        
        super().resizeEvent( event )
        
        CG.client_controller.CallAfterQtSafe( self, self._popup_window.DoShowHide )
        
    
    def setVisible( self, *args, **kwargs ):
        
        super().setVisible( *args, **kwargs )
        
        self._popup_window.DoShowHide()
        
    
    class _PopupWindow( QW.QFrame ):
        
        def __init__( self, parent, canvas_type, direction = 'down', per_player_audio_owner = None ):
            
            super().__init__( parent )
            
            self._canvas_type = canvas_type
            
            self._direction = direction
            
            self._per_player_audio_owner = per_player_audio_owner
            
            self.setWindowFlags( QC.Qt.WindowType.Tool | QC.Qt.WindowType.FramelessWindowHint )
            
            self.setAttribute( QC.Qt.WidgetAttribute.WA_ShowWithoutActivating )
            
            if self._canvas_type in CC.CANVAS_MEDIA_VIEWER_TYPES:
                
                option_to_use = 'media_viewer_uses_its_own_audio_volume'
                volume_type = AUDIO_MEDIA_VIEWER
                
            else:
                
                option_to_use = 'preview_uses_its_own_audio_volume'
                volume_type = AUDIO_PREVIEW
                
            
            if self._per_player_audio_owner is None:
                
                self._specific_mute = AudioMuteButton( self, volume_type )
                
                self._specific_mute.setToolTip( ClientGUIFunctions.WrapToolTip( 'Mute/unmute: {}'.format( CC.canvas_type_str_lookup[ self._canvas_type ] ) ) )
                
                if CG.client_controller.new_options.GetBoolean( option_to_use ):
                    
                    slider_volume_type = volume_type
                    
                else:
                    
                    slider_volume_type = AUDIO_GLOBAL
                    
                
                self._volume = VolumeSlider( self, slider_volume_type )
                
            else:
                
                # the specific mute button mutes every window of this canvas type, so a window that mutes itself does not offer it here
                self._specific_mute = None
                
                self._volume = PerPlayerVolumeSlider( self, self._per_player_audio_owner )
                
            
            vbox = QP.VBoxLayout()
            
            widgets = [ self._volume ] if self._specific_mute is None else [ self._specific_mute, self._volume ]
            
            if self._direction != 'down':
                
                widgets.reverse()
                
            
            for widget in widgets:
                
                QP.AddToLayout( vbox, widget, CC.FLAGS_CENTER )
                
            
            #vbox.setAlignment( self._volume, QC.Qt.AlignmentFlag.AlignHCenter )
            #vbox.setAlignment( self._specific_mute, QC.Qt.AlignmentFlag.AlignHCenter )
            
            self.setLayout( vbox )
            
            self.hide()
            
            self.adjustSize()
            
            CG.client_controller.sub( self, 'NotifyNewOptions', 'notify_new_options' )
            
        
        def DoReposition( self ):
            
            parent = self.parentWidget()
            
            if not parent.isVisible():
                
                self.hide()
                
                return
                
            
            horizontal_offset = ( self.width() - parent.width() ) // 2 
            
            if self._direction == 'down':
                
                pos = parent.mapToGlobal( parent.rect().bottomLeft() )
                
            else:
                
                pos = parent.mapToGlobal( parent.rect().topLeft() - self.rect().bottomLeft() )
                
            
            pos.setX( pos.x() - horizontal_offset )
            
            self.move( pos )
            
        
        def DoShowHide( self ):
            
            self.DoReposition()
            
            parent = self.parentWidget()
            
            if not parent.isVisible():
                
                self.hide()
                
                return
                
            
            over_parent = ClientGUIFunctions.MouseIsOverWidget( parent ) and parent.isEnabled()
            over_me = ClientGUIFunctions.MouseIsOverWidget( self )
            
            should_show = over_parent
            should_hide = not ( over_parent or over_me )
            
            if should_show:
                
                self.show()
                
            elif should_hide:
                
                self.hide()
                
            
        
        def leaveEvent( self, event ):
            
            if self.isVisible():
                
                self.DoShowHide()
                
            
            event.ignore()
            
        
        def NotifyNewOptions( self ):
            
            if self._per_player_audio_owner is not None:
                
                # our slider follows the player, not the options
                return
                
            
            if self._canvas_type in CC.CANVAS_MEDIA_VIEWER_TYPES:
                
                option_to_use = 'media_viewer_uses_its_own_audio_volume'
                volume_type = AUDIO_MEDIA_VIEWER
                
            else:
                
                option_to_use = 'preview_uses_its_own_audio_volume'
                volume_type = AUDIO_PREVIEW
                
            
            if CG.client_controller.new_options.GetBoolean( option_to_use ):
                
                slider_volume_type = volume_type
                
            else:
                
                slider_volume_type = AUDIO_GLOBAL
                
            
            if slider_volume_type != self._volume.GetVolumeType():
                
                self._volume.SetVolumeType( slider_volume_type )
                
            
        
    
def SetUpVolumeSliderLook( slider: QW.QSlider ):
    
    slider.setOrientation( QC.Qt.Orientation.Vertical )
    slider.setTickInterval( 1 )
    slider.setTickPosition( QW.QSlider.TickPosition.TicksBothSides )
    slider.setRange( 0, 100 )
    

class PerPlayerVolumeSlider( QW.QSlider ):
    
    def __init__( self, parent, volume_owner ):
        
        # the volume_owner is a media container. it has GetCurrentVolume, SetPerPlayerVolume, and a volumeChanged signal
        
        super().__init__( parent )
        
        self._volume_owner = volume_owner
        
        SetUpVolumeSliderLook( self )
        
        self.setValue( self._volume_owner.GetCurrentVolume() )
        
        self.setToolTip( ClientGUIFunctions.WrapToolTip( 'volume for just this media viewer' ) )
        
        self.valueChanged.connect( self._VolumeSliderMoved )
        
        self._volume_owner.volumeChanged.connect( self.NotifyNewVolume )
        
    
    def _VolumeSliderMoved( self ):
        
        self._volume_owner.SetPerPlayerVolume( self.value() )
        
    
    def NotifyNewVolume( self ):
        
        volume = self._volume_owner.GetCurrentVolume()
        
        if volume != self.value():
            
            # this came from elsewhere, so don't echo it back as a user change
            self.blockSignals( True )
            
            self.setValue( volume )
            
            self.blockSignals( False )
            
        
    

class VolumeSlider( QW.QSlider ):
    
    def __init__( self, parent, volume_type ):
        
        super().__init__( parent )
        
        self._volume_type = volume_type
        
        SetUpVolumeSliderLook( self )
        
        volume = self._GetCorrectValue()
        
        self.setValue( volume )
        
        self.valueChanged.connect( self._VolumeSliderMoved )
        
    
    def _GetCorrectValue( self ):
        
        ( mute_option_name, volume_option_name ) = volume_types_to_option_names[ self._volume_type ]
        
        return CG.client_controller.new_options.GetInteger( volume_option_name )
        
    
    def _VolumeSliderMoved( self ):
        
        ChangeVolume( self._volume_type, self.value() )
        
    
    def GetVolumeType( self ):
        
        return self._volume_type
        
    
    def SetVolumeType( self, volume_type ):
        
        self._volume_type = volume_type
        
        volume = self._GetCorrectValue()
        
        self.setValue( volume )
        
    
