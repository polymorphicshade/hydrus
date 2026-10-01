import os

from qtpy import QtWidgets as QW

from hydrus.core import HydrusConstants as HC

from hydrus.client import ClientConstants as CC
from hydrus.client import ClientData
from hydrus.client import ClientGlobals as CG
from hydrus.client.exporting import ClientExportingAudio
from hydrus.client.exporting import ClientExportingSpans
from hydrus.client.gui import ClientGUITopLevelWindowsPanels
from hydrus.client.gui import QtPorting as QP
from hydrus.client.gui.panels import ClientGUIScrolledPanels
from hydrus.client.gui.widgets import ClientGUICommon
from hydrus.client.media import ClientMediaResult

# where the last audio export went, and how, this session, so the next one starts there
LAST_AUDIO_EXPORT_DIR = None
LAST_AUDIO_EXPORT_SETTINGS = None

def CanExportAudio( media_result: ClientMediaResult.MediaResult ) -> bool:
    
    mime = media_result.GetMime()
    
    return ( mime in HC.VIDEO or mime in HC.AUDIO ) and media_result.HasAudio() and media_result.GetLocationsManager().IsLocal()
    

def ExportAudio( win: QW.QWidget, media_result: ClientMediaResult.MediaResult, span_ms: tuple[ int, int ] | None = None ):
    
    # asks how to export it and where to put it, and then makes it in the background, with a popup to follow along
    # with a span, just that part of the audio is exported
    global LAST_AUDIO_EXPORT_DIR
    global LAST_AUDIO_EXPORT_SETTINGS
    
    with ClientGUITopLevelWindowsPanels.DialogEdit( win, 'export audio' ) as dlg:
        
        panel = EditAudioExportPanel( dlg, media_result, LAST_AUDIO_EXPORT_SETTINGS, span_ms = span_ms )
        
        dlg.SetPanel( panel )
        
        if dlg.exec() != QW.QDialog.DialogCode.Accepted:
            
            return
            
        
        settings = panel.GetValue()
        
    
    LAST_AUDIO_EXPORT_SETTINGS = settings
    
    ext = ClientExportingAudio.GetAudioExportExtension( settings.export_format )
    
    starting_dir = LAST_AUDIO_EXPORT_DIR if LAST_AUDIO_EXPORT_DIR is not None else os.path.expanduser( '~' )
    
    starting_path = os.path.join( starting_dir, media_result.GetHash().hex() + ClientExportingSpans.GetExportSpanFilenameSuffix( span_ms ) + ext )
    
    options = QW.QFileDialog.Option.DontResolveSymlinks
    
    if CG.client_controller.new_options.GetBoolean( 'use_qt_file_dialogs' ):
        
        options |= QW.QFileDialog.Option.DontUseNativeDialog
        
    
    wildcard = f'{ext[1:]} audio (*{ext})'
    
    path = QW.QFileDialog.getSaveFileName( win, 'export audio', starting_path, filter = wildcard, selectedFilter = wildcard, options = options )[0]
    
    if path == '':
        
        return
        
    
    if not path.lower().endswith( ext ):
        
        path += ext
        
    
    LAST_AUDIO_EXPORT_DIR = os.path.dirname( path )
    
    ClientExportingAudio.StartAudioExport( media_result, settings, path, span_ms = span_ms )
    

class EditAudioExportPanel( ClientGUIScrolledPanels.EditPanel ):
    
    def __init__( self, parent: QW.QWidget, media_result: ClientMediaResult.MediaResult, last_settings: ClientExportingAudio.AudioExportSettings | None, span_ms: tuple[ int, int ] | None = None ):
        
        super().__init__( parent )
        
        self._span_ms = span_ms
        self._duration_ms = ClientExportingSpans.GetExportSpanDurationMS( span_ms, media_result.GetDurationMS() )
        
        if last_settings is None:
            
            last_settings = ClientExportingAudio.AudioExportSettings()
            
        
        if span_ms is None:
            
            help_text = 'Export the sound of this file on its own, as an mp3 or wav.'
            
        else:
            
            help_text = f'Export the sound of this file on its own, as an mp3 or wav, from A to B: {ClientExportingSpans.ConvertExportSpanToPrettyString( span_ms )}.'
            help_text += '\n' * 2
            help_text += 'To export all of it, clear the A-B repeat points first.'
            
        
        st = ClientGUICommon.BetterStaticText( self, label = help_text )
        st.setWordWrap( True )
        
        choice_tuples = [
            ( 'mp3', ClientExportingAudio.AUDIO_EXPORT_FORMAT_MP3, 'Compressed. Small, and plays almost anywhere.' ),
            ( 'wav', ClientExportingAudio.AUDIO_EXPORT_FORMAT_WAV, 'Uncompressed. Big, but nothing is lost, so it is good for editing.' )
        ]
        
        self._format = ClientGUICommon.BetterRadioBox( self, choice_tuples )
        
        #
        
        self._quality_box = ClientGUICommon.StaticBox( self, 'quality' )
        
        self._mp3_kbps = ClientGUICommon.BetterChoice( self._quality_box )
        
        for mp3_kbps in ClientExportingAudio.AUDIO_EXPORT_MP3_BITRATES_KBPS:
            
            self._mp3_kbps.addItem( f'{mp3_kbps} kbps', mp3_kbps )
            
        
        self._wav_bit_depth = ClientGUICommon.BetterChoice( self._quality_box )
        
        for ( bit_depth, codec ) in ClientExportingAudio.AUDIO_EXPORT_WAV_BIT_DEPTHS:
            
            self._wav_bit_depth.addItem( f'{bit_depth}-bit', bit_depth )
            
        
        self._sample_rate = ClientGUICommon.BetterChoice( self._quality_box )
        
        self._sample_rate.addItem( 'original', None )
        
        for sample_rate in ClientExportingAudio.AUDIO_EXPORT_SAMPLE_RATES:
            
            self._sample_rate.addItem( f'{sample_rate} Hz', sample_rate )
            
        
        self._channels = ClientGUICommon.BetterChoice( self._quality_box )
        
        self._channels.addItem( 'original', None )
        
        for ( label, channels ) in ClientExportingAudio.AUDIO_EXPORT_CHANNELS:
            
            self._channels.addItem( label, channels )
            
        
        self._estimate = ClientGUICommon.BetterStaticText( self, label = '' )
        self._estimate.setWordWrap( True )
        
        #
        
        self._format.SetValue( last_settings.export_format )
        self._mp3_kbps.SetValue( last_settings.mp3_kbps )
        self._wav_bit_depth.SetValue( last_settings.wav_bit_depth )
        self._sample_rate.SetValue( last_settings.sample_rate )
        self._channels.SetValue( last_settings.channels )
        
        #
        
        rows = []
        
        rows.append( ( 'mp3 bitrate: ', self._mp3_kbps ) )
        rows.append( ( 'wav bit depth: ', self._wav_bit_depth ) )
        rows.append( ( 'sample rate: ', self._sample_rate ) )
        rows.append( ( 'channels: ', self._channels ) )
        
        gridbox = ClientGUICommon.WrapInGrid( self._quality_box, rows )
        
        self._quality_box.Add( gridbox, CC.FLAGS_EXPAND_SIZER_PERPENDICULAR )
        
        vbox = QP.VBoxLayout()
        
        QP.AddToLayout( vbox, st, CC.FLAGS_EXPAND_PERPENDICULAR )
        QP.AddToLayout( vbox, self._format, CC.FLAGS_EXPAND_PERPENDICULAR )
        QP.AddToLayout( vbox, self._quality_box, CC.FLAGS_EXPAND_PERPENDICULAR )
        QP.AddToLayout( vbox, self._estimate, CC.FLAGS_EXPAND_PERPENDICULAR )
        vbox.addStretch( 0 )
        
        self.widget().setLayout( vbox )
        
        self._format.radioBoxChanged.connect( self._UpdateControls )
        self._mp3_kbps.currentIndexChanged.connect( self._UpdateControls )
        self._wav_bit_depth.currentIndexChanged.connect( self._UpdateControls )
        self._sample_rate.currentIndexChanged.connect( self._UpdateControls )
        self._channels.currentIndexChanged.connect( self._UpdateControls )
        
        self._UpdateControls()
        
    
    def _UpdateControls( self ):
        
        settings = self.GetValue()
        
        is_mp3 = settings.export_format == ClientExportingAudio.AUDIO_EXPORT_FORMAT_MP3
        
        self._mp3_kbps.setEnabled( is_mp3 )
        self._wav_bit_depth.setEnabled( not is_mp3 )
        
        estimate = ClientExportingAudio.EstimateAudioExportSize( settings, self._duration_ms )
        
        if estimate is not None:
            
            self._estimate.setText( f'approximate resulting file size: {ClientData.ToHumanBytes( estimate )}' )
            
        elif self._duration_ms is not None and self._duration_ms > 0 and not is_mp3:
            
            self._estimate.setText( 'resulting file size: it depends on the file\'s own sample rate and channels. set both to see a size.' )
            
        else:
            
            self._estimate.setText( 'resulting file size: unknown' )
            
        
    
    def GetValue( self ) -> ClientExportingAudio.AudioExportSettings:
        
        return ClientExportingAudio.AudioExportSettings(
            export_format = self._format.GetValue(),
            mp3_kbps = self._mp3_kbps.GetValue(),
            wav_bit_depth = self._wav_bit_depth.GetValue(),
            sample_rate = self._sample_rate.GetValue(),
            channels = self._channels.GetValue()
        )
        
    
