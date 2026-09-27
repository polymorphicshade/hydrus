import math

from qtpy import QtCore as QC
from qtpy import QtWidgets as QW

from hydrus.client import ClientConstants as CC
from hydrus.client.gui import ClientGUIFunctions
from hydrus.client.gui import QtPorting as QP
from hydrus.client.gui.panels import ClientGUIScrolledPanels
from hydrus.client.gui.widgets import ClientGUICommon

# these effects are ffmpeg audio filters, which mpv can run live on its output via its 'af' property
# be careful adding new filters or options: mpv reports a bad filter graph as an 'error' log line, which our mpv log handler treats as a media problem
# so stick to filters and options that have been in ffmpeg a long time, since users have all sorts of libmpv builds

LOW_PASS_MIN_CUTOFF_HZ = 20
LOW_PASS_MAX_CUTOFF_HZ = 20000
LOW_PASS_ROLL_OFFS_DB = ( 6, 12, 24, 36, 48 )

DEFAULT_LOW_PASS_CUTOFF_HZ = 1000
DEFAULT_LOW_PASS_ROLL_OFF_DB = 12

DEFAULT_REVERB_ROOM_SIZE = 40
DEFAULT_REVERB_REVERBERANCE = 50
DEFAULT_REVERB_WET_LEVEL = 30

def GenerateLowPassFilters( cutoff_hz: int, roll_off_db: int ) -> list[ str ]:
    
    # a one-pole lowpass is 6dB per octave, a two-pole is 12dB. we stack two-poles for anything steeper
    
    if roll_off_db <= 6:
        
        return [ f'lowpass=f={cutoff_hz}:p=1' ]
        
    
    num_stages = max( 1, roll_off_db // 12 )
    
    return [ f'lowpass=f={cutoff_hz}:p=2' ] * num_stages
    

def GenerateReverbFilter( room_size: int, reverberance: int, wet_level: int ) -> str | None:
    
    # ffmpeg has no simple reverb filter, so we fake one with aecho: a spray of echoes that get quieter over the length of the 'room'
    # room_size, reverberance, and wet_level are all 0-100
    
    if wet_level <= 0:
        
        return None
        
    
    # how long the echo tail lasts
    tail_ms = 50 + ( room_size * 15 )
    
    # about one echo every 20ms, which is dense enough to blur together rather than sound like a slapback
    num_echoes = max( 8, min( 48, round( tail_ms / 20 ) ) )
    
    # how quiet the tail gets by its end. more reverberance means a longer ring
    end_db = -60 + ( reverberance * 0.4 )
    
    golden_ratio_fraction = 0.6180339887
    
    delays_ms = []
    amplitudes = []
    
    for i in range( num_echoes ):
        
        # evenly spaced echoes make a buzzy comb filter, so we nudge each one by a fixed irregular amount
        nudge = ( ( ( i * golden_ratio_fraction ) % 1.0 ) - 0.5 ) * 0.6
        
        position = ( i + 0.7 + nudge ) / num_echoes
        
        delays_ms.append( tail_ms * position )
        amplitudes.append( 10 ** ( ( end_db * position ) / 20 ) )
        
    
    # scale the echoes so their combined power is wet_level times the dry signal's
    wet = wet_level / 100
    
    echo_power = math.sqrt( sum( ( amplitude ** 2 for amplitude in amplitudes ) ) )
    
    # aecho requires every decay to be above 0
    decays = [ max( 0.0001, wet * amplitude / echo_power ) for amplitude in amplitudes ]
    
    # keep the overall loudness the same as the dry signal. the echoes are spread out enough that their peaks rarely line up, so this does not clip in practice
    in_gain = 1.0
    out_gain = 1 / math.sqrt( 1 + ( wet ** 2 ) )
    
    delays_string = '|'.join( ( f'{delay_ms:.1f}' for delay_ms in delays_ms ) )
    decays_string = '|'.join( ( f'{decay:.4f}' for decay in decays ) )
    
    return f'aecho={in_gain:.2f}:{out_gain:.4f}:{delays_string}:{decays_string}'
    

class AudioEffects( object ):
    
    def __init__(
        self,
        low_pass_enabled = False,
        low_pass_cutoff_hz = DEFAULT_LOW_PASS_CUTOFF_HZ,
        low_pass_roll_off_db = DEFAULT_LOW_PASS_ROLL_OFF_DB,
        reverb_enabled = False,
        reverb_room_size = DEFAULT_REVERB_ROOM_SIZE,
        reverb_reverberance = DEFAULT_REVERB_REVERBERANCE,
        reverb_wet_level = DEFAULT_REVERB_WET_LEVEL
    ):
        
        self._low_pass_enabled = low_pass_enabled
        self._low_pass_cutoff_hz = low_pass_cutoff_hz
        self._low_pass_roll_off_db = low_pass_roll_off_db
        
        self._reverb_enabled = reverb_enabled
        self._reverb_room_size = reverb_room_size
        self._reverb_reverberance = reverb_reverberance
        self._reverb_wet_level = reverb_wet_level
        
    
    def GetFilterGraph( self ) -> str:
        
        # an ffmpeg filter graph for all the enabled effects, or an empty string if there are none
        
        filters = []
        
        if self._low_pass_enabled:
            
            filters.extend( GenerateLowPassFilters( self._low_pass_cutoff_hz, self._low_pass_roll_off_db ) )
            
        
        if self._reverb_enabled:
            
            reverb_filter = GenerateReverbFilter( self._reverb_room_size, self._reverb_reverberance, self._reverb_wet_level )
            
            if reverb_filter is not None:
                
                filters.append( reverb_filter )
                
            
        
        if len( filters ) == 0:
            
            return ''
            
        
        # the filters do their maths in float, so nothing clips between them
        filters.insert( 0, 'aformat=sample_fmts=fltp' )
        
        return ','.join( filters )
        
    
    def GetLowPass( self ):
        
        return ( self._low_pass_enabled, self._low_pass_cutoff_hz, self._low_pass_roll_off_db )
        
    
    def GetReverb( self ):
        
        return ( self._reverb_enabled, self._reverb_room_size, self._reverb_reverberance, self._reverb_wet_level )
        
    

class AudioEffectSlider( QW.QWidget ):
    
    valueChanged = QC.Signal()
    
    LOGARITHMIC_STEPS = 1000
    
    def __init__( self, parent, min_value: int, max_value: int, unit: str, logarithmic = False ):
        
        super().__init__( parent )
        
        self._min_value = min_value
        self._max_value = max_value
        self._unit = unit
        self._logarithmic = logarithmic
        
        self._slider = QW.QSlider( QC.Qt.Orientation.Horizontal, self )
        
        if self._logarithmic:
            
            # frequencies are heard logarithmically, so a linear 20-20000 slider would cram everything interesting into the first few pixels
            self._slider.setRange( 0, self.LOGARITHMIC_STEPS )
            
        else:
            
            self._slider.setRange( self._min_value, self._max_value )
            
        
        self._slider.setMinimumWidth( ClientGUIFunctions.ConvertTextToPixelWidth( self._slider, 24 ) )
        
        self._value_label = QW.QLabel( self )
        self._value_label.setMinimumWidth( ClientGUIFunctions.ConvertTextToPixelWidth( self._value_label, 8 ) )
        self._value_label.setAlignment( QC.Qt.AlignmentFlag.AlignRight | QC.Qt.AlignmentFlag.AlignVCenter )
        
        hbox = QP.HBoxLayout()
        
        QP.AddToLayout( hbox, self._slider, CC.FLAGS_EXPAND_BOTH_WAYS )
        QP.AddToLayout( hbox, self._value_label, CC.FLAGS_CENTER_PERPENDICULAR )
        
        self.setLayout( hbox )
        
        self._slider.valueChanged.connect( self._SliderMoved )
        
        self._UpdateLabel()
        
    
    def _SliderMoved( self ):
        
        self._UpdateLabel()
        
        self.valueChanged.emit()
        
    
    def _UpdateLabel( self ):
        
        self._value_label.setText( f'{self.GetValue()}{self._unit}' )
        
    
    def GetValue( self ) -> int:
        
        position = self._slider.value()
        
        if self._logarithmic:
            
            value = self._min_value * ( ( self._max_value / self._min_value ) ** ( position / self.LOGARITHMIC_STEPS ) )
            
            # a slider position lands on values like 998, so round to two significant figures for a tidy 1000
            magnitude = 10 ** ( math.floor( math.log10( value ) ) - 1 )
            
            return max( self._min_value, min( self._max_value, round( value / magnitude ) * magnitude ) )
            
        
        return position
        
    
    def SetValue( self, value: int ):
        
        value = max( self._min_value, min( self._max_value, value ) )
        
        if self._logarithmic:
            
            position = round( self.LOGARITHMIC_STEPS * math.log( value / self._min_value ) / math.log( self._max_value / self._min_value ) )
            
        else:
            
            position = value
            
        
        self._slider.setValue( position )
        
        self._UpdateLabel()
        
    

class AudioEffectsPanel( ClientGUIScrolledPanels.ReviewPanel ):
    
    def __init__( self, parent, media_container ):
        
        # the media_container has GetAudioEffects, SetAudioEffects, and IsUsingMPV
        
        super().__init__( parent )
        
        self._media_container = media_container
        
        self._help_st = ClientGUICommon.BetterStaticText( self, label = 'These effects apply to this media viewer while it is open, and reset when you close it. They only work on files playing in mpv.' )
        self._help_st.setWordWrap( True )
        
        self._not_mpv_st = ClientGUICommon.BetterStaticText( self, label = 'The current file is not playing in mpv, so you will not hear these effects on it.' )
        self._not_mpv_st.setWordWrap( True )
        self._not_mpv_st.setObjectName( 'HydrusWarning' )
        
        #
        
        self._low_pass_box = ClientGUICommon.StaticBox( self, 'low pass filter' )
        
        self._low_pass_enabled = QW.QCheckBox( 'on', self._low_pass_box )
        self._low_pass_enabled.setToolTip( ClientGUIFunctions.WrapToolTip( 'Cut the frequencies above the cutoff, muffling the sound.' ) )
        
        self._low_pass_cutoff_hz = AudioEffectSlider( self._low_pass_box, LOW_PASS_MIN_CUTOFF_HZ, LOW_PASS_MAX_CUTOFF_HZ, ' Hz', logarithmic = True )
        
        self._low_pass_roll_off_db = ClientGUICommon.BetterChoice( self._low_pass_box )
        
        for roll_off_db in LOW_PASS_ROLL_OFFS_DB:
            
            self._low_pass_roll_off_db.addItem( f'{roll_off_db} dB per octave', roll_off_db )
            
        
        self._low_pass_roll_off_db.setToolTip( ClientGUIFunctions.WrapToolTip( 'How sharply the sound above the cutoff drops away. Higher is a steeper, more obvious cut.' ) )
        
        #
        
        self._reverb_box = ClientGUICommon.StaticBox( self, 'reverb' )
        
        self._reverb_enabled = QW.QCheckBox( 'on', self._reverb_box )
        self._reverb_enabled.setToolTip( ClientGUIFunctions.WrapToolTip( 'Add a tail of echoes, as if the sound were playing in a room.' ) )
        
        self._reverb_room_size = AudioEffectSlider( self._reverb_box, 0, 100, '%' )
        self._reverb_room_size.setToolTip( ClientGUIFunctions.WrapToolTip( 'How long the echo tail lasts.' ) )
        
        self._reverb_reverberance = AudioEffectSlider( self._reverb_box, 0, 100, '%' )
        self._reverb_reverberance.setToolTip( ClientGUIFunctions.WrapToolTip( 'How slowly the echoes fade out.' ) )
        
        self._reverb_wet_level = AudioEffectSlider( self._reverb_box, 0, 100, '%' )
        self._reverb_wet_level.setToolTip( ClientGUIFunctions.WrapToolTip( 'How loud the echoes are compared to the original sound.' ) )
        
        #
        
        # dragging a slider fires a lot of changes, and each one makes mpv rebuild its audio filters, so we wait for a short pause
        self._apply_timer = QC.QTimer( self )
        self._apply_timer.setSingleShot( True )
        self._apply_timer.setInterval( 150 )
        self._apply_timer.timeout.connect( self._Apply )
        
        # the media viewer can move on to a file that is not in mpv at any time, so keep the warning current
        self._not_mpv_update_timer = QC.QTimer( self )
        self._not_mpv_update_timer.setInterval( 1000 )
        self._not_mpv_update_timer.timeout.connect( self._UpdateNotMPVWarning )
        
        #
        
        audio_effects: AudioEffects = self._media_container.GetAudioEffects()
        
        ( low_pass_enabled, low_pass_cutoff_hz, low_pass_roll_off_db ) = audio_effects.GetLowPass()
        
        self._low_pass_enabled.setChecked( low_pass_enabled )
        self._low_pass_cutoff_hz.SetValue( low_pass_cutoff_hz )
        self._low_pass_roll_off_db.SetValue( low_pass_roll_off_db )
        
        ( reverb_enabled, reverb_room_size, reverb_reverberance, reverb_wet_level ) = audio_effects.GetReverb()
        
        self._reverb_enabled.setChecked( reverb_enabled )
        self._reverb_room_size.SetValue( reverb_room_size )
        self._reverb_reverberance.SetValue( reverb_reverberance )
        self._reverb_wet_level.SetValue( reverb_wet_level )
        
        self._UpdateEnabled()
        self._UpdateNotMPVWarning()
        
        #
        
        rows = []
        
        rows.append( ( 'cutoff frequency: ', self._low_pass_cutoff_hz ) )
        rows.append( ( 'roll-off: ', self._low_pass_roll_off_db ) )
        
        gridbox = ClientGUICommon.WrapInGrid( self._low_pass_box, rows )
        
        self._low_pass_box.Add( self._low_pass_enabled, CC.FLAGS_EXPAND_PERPENDICULAR )
        self._low_pass_box.Add( gridbox, CC.FLAGS_EXPAND_SIZER_PERPENDICULAR )
        
        rows = []
        
        rows.append( ( 'room size: ', self._reverb_room_size ) )
        rows.append( ( 'reverberance: ', self._reverb_reverberance ) )
        rows.append( ( 'wet level: ', self._reverb_wet_level ) )
        
        gridbox = ClientGUICommon.WrapInGrid( self._reverb_box, rows )
        
        self._reverb_box.Add( self._reverb_enabled, CC.FLAGS_EXPAND_PERPENDICULAR )
        self._reverb_box.Add( gridbox, CC.FLAGS_EXPAND_SIZER_PERPENDICULAR )
        
        vbox = QP.VBoxLayout()
        
        QP.AddToLayout( vbox, self._help_st, CC.FLAGS_EXPAND_PERPENDICULAR )
        QP.AddToLayout( vbox, self._not_mpv_st, CC.FLAGS_EXPAND_PERPENDICULAR )
        QP.AddToLayout( vbox, self._low_pass_box, CC.FLAGS_EXPAND_PERPENDICULAR )
        QP.AddToLayout( vbox, self._reverb_box, CC.FLAGS_EXPAND_PERPENDICULAR )
        vbox.addStretch( 0 )
        
        self.widget().setLayout( vbox )
        
        #
        
        self._low_pass_enabled.clicked.connect( self._EnabledChanged )
        self._reverb_enabled.clicked.connect( self._EnabledChanged )
        
        self._low_pass_cutoff_hz.valueChanged.connect( self._apply_timer.start )
        self._low_pass_roll_off_db.currentIndexChanged.connect( self._apply_timer.start )
        self._reverb_room_size.valueChanged.connect( self._apply_timer.start )
        self._reverb_reverberance.valueChanged.connect( self._apply_timer.start )
        self._reverb_wet_level.valueChanged.connect( self._apply_timer.start )
        
        self._not_mpv_update_timer.start()
        
    
    def _Apply( self ):
        
        self._apply_timer.stop()
        
        if not QP.isValid( self._media_container ):
            
            return
            
        
        audio_effects = AudioEffects(
            low_pass_enabled = self._low_pass_enabled.isChecked(),
            low_pass_cutoff_hz = self._low_pass_cutoff_hz.GetValue(),
            low_pass_roll_off_db = self._low_pass_roll_off_db.GetValue(),
            reverb_enabled = self._reverb_enabled.isChecked(),
            reverb_room_size = self._reverb_room_size.GetValue(),
            reverb_reverberance = self._reverb_reverberance.GetValue(),
            reverb_wet_level = self._reverb_wet_level.GetValue()
        )
        
        self._media_container.SetAudioEffects( audio_effects )
        
    
    def _EnabledChanged( self ):
        
        self._UpdateEnabled()
        
        # on/off is a single click, so no need to wait
        self._Apply()
        
    
    def _UpdateEnabled( self ):
        
        low_pass_enabled = self._low_pass_enabled.isChecked()
        
        self._low_pass_cutoff_hz.setEnabled( low_pass_enabled )
        self._low_pass_roll_off_db.setEnabled( low_pass_enabled )
        
        reverb_enabled = self._reverb_enabled.isChecked()
        
        self._reverb_room_size.setEnabled( reverb_enabled )
        self._reverb_reverberance.setEnabled( reverb_enabled )
        self._reverb_wet_level.setEnabled( reverb_enabled )
        
    
    def _UpdateNotMPVWarning( self ):
        
        if not QP.isValid( self._media_container ):
            
            return
            
        
        self._not_mpv_st.setVisible( not self._media_container.IsUsingMPV() )


