import os

from qtpy import QtWidgets as QW

from hydrus.core import HydrusConstants as HC
from hydrus.core import HydrusExceptions

from hydrus.client import ClientConstants as CC
from hydrus.client import ClientData
from hydrus.client import ClientGlobals as CG
from hydrus.client.exporting import ClientExportingSpans
from hydrus.client.exporting import ClientExportingVideo
from hydrus.client.gui import ClientGUITopLevelWindowsPanels
from hydrus.client.gui import QtPorting as QP
from hydrus.client.gui.panels import ClientGUIScrolledPanels
from hydrus.client.gui.widgets import ClientGUICommon
from hydrus.client.media import ClientMediaResult

# where the last video export went, and how, this session, so the next one starts there
LAST_VIDEO_EXPORT_DIR = None
LAST_VIDEO_EXPORT_SETTINGS = None

BYTES_PER_MB = 1024 * 1024

def CanExportVideo( media_result: ClientMediaResult.MediaResult ) -> bool:
    
    return media_result.GetMime() in HC.VIDEO and media_result.GetLocationsManager().IsLocal()
    

def ExportVideo( win: QW.QWidget, media_result: ClientMediaResult.MediaResult, span_ms: tuple[ int, int ] | None = None ):
    
    # asks how to export it and where to put it, and then makes it in the background, with a popup to follow along
    # with a span, just that part of the video is exported
    global LAST_VIDEO_EXPORT_DIR
    global LAST_VIDEO_EXPORT_SETTINGS
    
    title = 'export video' if span_ms is None else 'export video clip'
    
    with ClientGUITopLevelWindowsPanels.DialogEdit( win, title ) as dlg:
        
        panel = EditVideoExportPanel( dlg, media_result, LAST_VIDEO_EXPORT_SETTINGS, span_ms = span_ms )
        
        dlg.SetPanel( panel )
        
        if dlg.exec() != QW.QDialog.DialogCode.Accepted:
            
            return
            
        
        settings = panel.GetValue()
        
    
    settings_to_remember = ClientExportingVideo.VideoExportSettings( **settings.__dict__ )
    
    if LAST_VIDEO_EXPORT_SETTINGS is not None:
        
        if not media_result.HasAudio():
            
            # a file with no audio did not get to pick, so the next one keeps what was picked before
            settings_to_remember.audio_kbps = LAST_VIDEO_EXPORT_SETTINGS.audio_kbps
            
        
        if span_ms is not None and LAST_VIDEO_EXPORT_SETTINGS.export_format == ClientExportingVideo.VIDEO_EXPORT_FORMAT_RAW:
            
            # a clip could not pick raw, so the next whole video keeps it
            settings_to_remember.export_format = ClientExportingVideo.VIDEO_EXPORT_FORMAT_RAW
            
        
    
    LAST_VIDEO_EXPORT_SETTINGS = settings_to_remember
    
    
    ext = ClientExportingVideo.GetVideoExportExtension( settings.export_format, media_result.GetMime() )
    
    starting_dir = LAST_VIDEO_EXPORT_DIR if LAST_VIDEO_EXPORT_DIR is not None else os.path.expanduser( '~' )
    
    starting_path = os.path.join( starting_dir, media_result.GetHash().hex() + ClientExportingSpans.GetExportSpanFilenameSuffix( span_ms ) + ext )
    
    options = QW.QFileDialog.Option.DontResolveSymlinks
    
    if CG.client_controller.new_options.GetBoolean( 'use_qt_file_dialogs' ):
        
        options |= QW.QFileDialog.Option.DontUseNativeDialog
        
    
    wildcard = f'{ext[1:]} video (*{ext})'
    
    path = QW.QFileDialog.getSaveFileName( win, 'export video', starting_path, filter = wildcard, selectedFilter = wildcard, options = options )[0]
    
    if path == '':
        
        return
        
    
    if not path.lower().endswith( ext ):
        
        path += ext
        
    
    LAST_VIDEO_EXPORT_DIR = os.path.dirname( path )
    
    ClientExportingVideo.StartVideoExport( media_result, settings, path, span_ms = span_ms )
    

class EditVideoExportPanel( ClientGUIScrolledPanels.EditPanel ):
    
    def __init__( self, parent: QW.QWidget, media_result: ClientMediaResult.MediaResult, last_settings: ClientExportingVideo.VideoExportSettings | None, span_ms: tuple[ int, int ] | None = None ):
        
        super().__init__( parent )
        
        self._span_ms = span_ms
        
        file_duration_ms = media_result.GetDurationMS()
        
        self._source_size = media_result.GetSize()
        self._source_resolution = media_result.GetResolution()
        self._source_framerate = media_result.GetFileInfoManager().GetFramerate()
        self._duration_ms = ClientExportingSpans.GetExportSpanDurationMS( span_ms, file_duration_ms )
        self._has_audio = media_result.HasAudio()
        
        if span_ms is not None and file_duration_ms is not None and file_duration_ms > 0:
            
            # the size guesses go by how big the clip's part of the file is
            self._source_size = int( self._source_size * self._duration_ms / file_duration_ms )
            
        
        if last_settings is None:
            
            last_settings = ClientExportingVideo.VideoExportSettings()
            
        
        if span_ms is None:
            
            help_text = 'Export this video as it is, or encode it again as an mp4 or webm, at a smaller resolution, framerate, quality, or file size.'
            
        else:
            
            help_text = f'Export a clip of this video, from A to B: {ClientExportingSpans.ConvertExportSpanToPrettyString( span_ms )}. It is encoded as an mp4 or webm, and you can make it a smaller resolution, framerate, quality, or file size.'
            help_text += '\n' * 2
            help_text += 'To export the whole video, clear the A-B repeat points first.'
            
        
        st = ClientGUICommon.BetterStaticText( self, label = help_text )
        st.setWordWrap( True )
        
        choice_tuples = [
            ( 'mp4', ClientExportingVideo.VIDEO_EXPORT_FORMAT_MP4, 'h.264 video and aac audio. Plays almost anywhere.' ),
            ( 'webm', ClientExportingVideo.VIDEO_EXPORT_FORMAT_WEBM, 'vp9 video and opus audio. Smaller for the same quality, but slower to make.' )
        ]
        
        if span_ms is None:
            
            # a clip has to be cut out and encoded, so the original file is no good for it
            choice_tuples.append( ( 'raw', ClientExportingVideo.VIDEO_EXPORT_FORMAT_RAW, f'The original {HC.mime_string_lookup.get( media_result.GetMime(), "file" )}, copied as it is.' ) )
            
        
        self._format = ClientGUICommon.BetterRadioBox( self, choice_tuples )
        
        #
        
        self._encode_box = ClientGUICommon.StaticBox( self, 'encoding' )
        
        self._resolution = ClientGUICommon.BetterChoice( self._encode_box )
        
        for ( label, resolution ) in ClientExportingVideo.GetVideoExportResolutionOptions( self._source_resolution ):
            
            self._resolution.addItem( label, resolution )
            
        
        self._framerate = ClientGUICommon.BetterChoice( self._encode_box )
        
        for ( label, framerate ) in ClientExportingVideo.GetVideoExportFramerateOptions( self._source_framerate ):
            
            self._framerate.addItem( label, framerate )
            
        
        self._audio = ClientGUICommon.BetterChoice( self._encode_box )
        
        if self._has_audio:
            
            for audio_kbps in ClientExportingVideo.VIDEO_EXPORT_AUDIO_BITRATES_KBPS:
                
                self._audio.addItem( f'{audio_kbps} kbps', audio_kbps )
                
            
        
        self._audio.addItem( 'no audio', None )
        
        size_mode_choice_tuples = [
            ( 'pick a quality', ClientExportingVideo.VIDEO_EXPORT_SIZE_MODE_QUALITY, 'Encode at a quality level. The file is as big as it comes out.' ),
            ( 'fit a file size', ClientExportingVideo.VIDEO_EXPORT_SIZE_MODE_TARGET, 'Encode to come out just under a file size. The quality is whatever fits. This encodes the video twice, so it takes about twice as long.' )
        ]
        
        self._size_mode = ClientGUICommon.BetterRadioBox( self._encode_box, size_mode_choice_tuples )
        
        self._quality = ClientGUICommon.BetterChoice( self._encode_box )
        
        for ( i, ( name, x264_crf, vp9_crf, bpp ) ) in enumerate( ClientExportingVideo.VIDEO_EXPORT_QUALITIES ):
            
            self._quality.addItem( name, i )
            
        
        self._target_size_mb = ClientGUICommon.BetterDoubleSpinBox( self._encode_box, min = 0.1, max = 100000.0 )
        self._target_size_mb.setDecimals( 1 )
        self._target_size_mb.setSuffix( ' MB' )
        
        self._estimate = ClientGUICommon.BetterStaticText( self, label = '' )
        self._estimate.setWordWrap( True )
        
        self._warning = ClientGUICommon.BetterStaticText( self, label = '' )
        self._warning.setWordWrap( True )
        self._warning.setObjectName( 'HydrusWarning' )
        
        #
        
        if span_ms is not None and last_settings.export_format == ClientExportingVideo.VIDEO_EXPORT_FORMAT_RAW:
            
            self._format.SetValue( ClientExportingVideo.VIDEO_EXPORT_FORMAT_MP4 )
            
        else:
            
            self._format.SetValue( last_settings.export_format )
            
        
        if self._has_audio:
            
            self._audio.SetValue( last_settings.audio_kbps )
            
        
        self._quality.SetValue( last_settings.quality_index )
        
        if self._duration_ms is None or self._duration_ms <= 0:
            
            # nothing to fit in a size
            self._size_mode.SetValue( ClientExportingVideo.VIDEO_EXPORT_SIZE_MODE_QUALITY )
            self._size_mode.setEnabled( False )
            
        else:
            
            self._size_mode.SetValue( last_settings.size_mode )
            
        
        if last_settings.target_size_bytes is not None:
            
            target_size_mb = last_settings.target_size_bytes / BYTES_PER_MB
            
        else:
            
            # smaller than it is now, or it would not be worth encoding
            target_size_mb = min( 8.0, self._source_size / BYTES_PER_MB / 2 )
            
        
        self._target_size_mb.setValue( max( 0.1, round( target_size_mb, 1 ) ) )
        
        #
        
        rows = []
        
        rows.append( ( 'resolution: ', self._resolution ) )
        rows.append( ( 'framerate: ', self._framerate ) )
        rows.append( ( 'audio: ', self._audio ) )
        
        gridbox = ClientGUICommon.WrapInGrid( self._encode_box, rows )
        
        self._encode_box.Add( gridbox, CC.FLAGS_EXPAND_SIZER_PERPENDICULAR )
        self._encode_box.Add( self._size_mode, CC.FLAGS_EXPAND_PERPENDICULAR )
        
        rows = []
        
        rows.append( ( 'quality: ', self._quality ) )
        rows.append( ( 'file size: ', self._target_size_mb ) )
        
        gridbox = ClientGUICommon.WrapInGrid( self._encode_box, rows )
        
        self._encode_box.Add( gridbox, CC.FLAGS_EXPAND_SIZER_PERPENDICULAR )
        
        vbox = QP.VBoxLayout()
        
        QP.AddToLayout( vbox, st, CC.FLAGS_EXPAND_PERPENDICULAR )
        QP.AddToLayout( vbox, self._format, CC.FLAGS_EXPAND_PERPENDICULAR )
        QP.AddToLayout( vbox, self._encode_box, CC.FLAGS_EXPAND_PERPENDICULAR )
        QP.AddToLayout( vbox, self._estimate, CC.FLAGS_EXPAND_PERPENDICULAR )
        QP.AddToLayout( vbox, self._warning, CC.FLAGS_EXPAND_PERPENDICULAR )
        vbox.addStretch( 0 )
        
        self.widget().setLayout( vbox )
        
        self._format.radioBoxChanged.connect( self._UpdateControls )
        self._size_mode.radioBoxChanged.connect( self._UpdateControls )
        self._resolution.currentIndexChanged.connect( self._UpdateControls )
        self._framerate.currentIndexChanged.connect( self._UpdateControls )
        self._audio.currentIndexChanged.connect( self._UpdateControls )
        self._quality.currentIndexChanged.connect( self._UpdateControls )
        self._target_size_mb.valueChanged.connect( self._UpdateControls )
        
        self._UpdateControls()
        
    
    def _GetSettings( self ) -> ClientExportingVideo.VideoExportSettings:
        
        return ClientExportingVideo.VideoExportSettings(
            export_format = self._format.GetValue(),
            resolution = self._resolution.GetValue(),
            framerate = self._framerate.GetValue(),
            audio_kbps = self._audio.GetValue(),
            size_mode = self._size_mode.GetValue(),
            quality_index = self._quality.GetValue(),
            target_size_bytes = int( self._target_size_mb.value() * BYTES_PER_MB )
        )
        
    
    def _UpdateControls( self ):
        
        settings = self._GetSettings()
        
        is_raw = settings.export_format == ClientExportingVideo.VIDEO_EXPORT_FORMAT_RAW
        
        self._encode_box.setEnabled( not is_raw )
        
        fit_size = settings.size_mode == ClientExportingVideo.VIDEO_EXPORT_SIZE_MODE_TARGET
        
        self._quality.setEnabled( not fit_size )
        self._target_size_mb.setEnabled( fit_size )
        
        source_size_text = ClientData.ToHumanBytes( self._source_size )
        
        now_text = f'it is {source_size_text} now' if self._span_ms is None else f'this part is about {source_size_text} now'
        
        problem = ClientExportingVideo.GetVideoExportProblem( settings, self._duration_ms )
        
        if is_raw:
            
            estimate_text = f'resulting file size: {source_size_text}, the same as it is now'
            
        elif problem is not None:
            
            if self._span_ms is None:
                
                estimate_text = f'This file is {source_size_text} now.'
                
            else:
                
                estimate_text = f'This part of the file is about {source_size_text} now.'
                
            
            
        else:
            
            estimate = ClientExportingVideo.EstimateVideoExportSize( settings, self._source_size, self._source_resolution, self._source_framerate, self._duration_ms )
            
            if estimate is None:
                
                estimate_text = f'resulting file size: unknown ({now_text})'
                
            else:
                
                estimate_text = f'approximate resulting file size: {ClientData.ToHumanBytes( estimate )} ({now_text})'
                
            
            if fit_size:
                
                video_kbps = ClientExportingVideo.GetVideoExportTargetVideoKBPS( settings.target_size_bytes, self._duration_ms, settings.audio_kbps )
                
                estimate_text += f'\nThe video will be about {video_kbps} kbps.'
                
            
        
        self._estimate.setText( estimate_text )
        
        if problem is None:
            
            warning = ClientExportingVideo.GetVideoExportWarning( settings, self._source_resolution, self._source_framerate, self._duration_ms )
            
        else:
            
            warning = problem
            
        
        self._warning.setText( '' if warning is None else warning )
        self._warning.setVisible( warning is not None )
        
    
    def GetValue( self ) -> ClientExportingVideo.VideoExportSettings:
        
        settings = self._GetSettings()
        
        problem = ClientExportingVideo.GetVideoExportProblem( settings, self._duration_ms )
        
        if problem is not None:
            
            raise HydrusExceptions.VetoException( problem )
            
        
        return settings
        
    
