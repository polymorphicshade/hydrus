import os
import unittest

from qtpy import QtWidgets as QW

from hydrus.core import HydrusConstants as HC
from hydrus.core import HydrusExceptions

from hydrus.client.exporting import ClientExportingAudio as A
from hydrus.client.gui.exporting import ClientGUIExportAudio

from hydrus.test import HelperFunctions as HF

def GetFakeMediaResult( duration_ms = 60000, has_audio = True, mime = HC.VIDEO_MP4 ):
    
    media_result = HF.GetFakeMediaResult( os.urandom( 32 ), mime = mime )
    
    file_info_manager = media_result.GetFileInfoManager()
    
    file_info_manager.width = 1920
    file_info_manager.height = 1080
    file_info_manager.duration_ms = duration_ms
    file_info_manager.has_audio = has_audio
    
    return media_result
    

class TestAudioExport( unittest.TestCase ):
    
    def test_extensions( self ):
        
        self.assertEqual( A.GetAudioExportExtension( A.AUDIO_EXPORT_FORMAT_MP3 ), '.mp3' )
        self.assertEqual( A.GetAudioExportExtension( A.AUDIO_EXPORT_FORMAT_WAV ), '.wav' )
        
    
    def test_estimates( self ):
        
        # 192 kbps for 100 seconds is 2.4MB
        self.assertEqual( A.EstimateAudioExportSize( A.AudioExportSettings( mp3_kbps = 192 ), 100000 ), 2400000 )
        
        # a wav is exact, once we know the rate and channels
        settings = A.AudioExportSettings( export_format = A.AUDIO_EXPORT_FORMAT_WAV, sample_rate = 48000, channels = 2 )
        
        self.assertEqual( A.EstimateAudioExportSize( settings, 10000 ), 48000 * 2 * 2 * 10 )
        
        settings.wav_bit_depth = 24
        
        self.assertEqual( A.EstimateAudioExportSize( settings, 10000 ), 48000 * 2 * 3 * 10 )
        
        # but not before
        self.assertIsNone( A.EstimateAudioExportSize( A.AudioExportSettings( export_format = A.AUDIO_EXPORT_FORMAT_WAV ), 10000 ) )
        
        self.assertIsNone( A.EstimateAudioExportSize( A.AudioExportSettings(), None ) )
        
    
    def test_commands( self ):
        
        cmd = A.GetAudioExportFFMPEGCommand( 'ffmpeg', 'in.mkv', 'out.mp3', A.AudioExportSettings( mp3_kbps = 128 ) )
        
        self.assertEqual( cmd[ cmd.index( '-map' ) + 1 ], '0:a:0' )
        self.assertIn( '-vn', cmd )
        self.assertEqual( cmd[ cmd.index( '-c:a' ) + 1 ], 'libmp3lame' )
        self.assertEqual( cmd[ cmd.index( '-b:a' ) + 1 ], '128k' )
        self.assertNotIn( '-ar', cmd )
        self.assertNotIn( '-ac', cmd )
        self.assertNotIn( '-ss', cmd )
        self.assertEqual( cmd[-1], 'out.mp3' )
        
        settings = A.AudioExportSettings( export_format = A.AUDIO_EXPORT_FORMAT_WAV, wav_bit_depth = 24, sample_rate = 44100, channels = 1 )
        
        cmd = A.GetAudioExportFFMPEGCommand( 'ffmpeg', 'in.mkv', 'out.wav', settings, span_ms = ( 12345, 34000 ) )
        
        self.assertEqual( cmd[ cmd.index( '-c:a' ) + 1 ], 'pcm_s24le' )
        self.assertNotIn( '-b:a', cmd )
        self.assertEqual( cmd[ cmd.index( '-ar' ) + 1 ], '44100' )
        self.assertEqual( cmd[ cmd.index( '-ac' ) + 1 ], '1' )
        
        # the A-B part is read from the file, before the '-i'
        i = cmd.index( '-i' )
        
        self.assertEqual( cmd[ i - 4 : i ], [ '-ss', '12.345', '-t', '21.655' ] )
        
        with self.assertRaises( HydrusExceptions.UnsupportedFileException ):
            
            A.GetAudioExportFFMPEGCommand( 'ffmpeg', 'in.mkv', 'out.wav', A.AudioExportSettings( export_format = A.AUDIO_EXPORT_FORMAT_WAV, wav_bit_depth = 12 ) )
            
        
    
    def test_can_export_audio( self ):
        
        self.assertTrue( ClientGUIExportAudio.CanExportAudio( GetFakeMediaResult() ) )
        self.assertTrue( ClientGUIExportAudio.CanExportAudio( GetFakeMediaResult( mime = HC.AUDIO_FLAC ) ) )
        
        # no sound, nothing to export
        self.assertFalse( ClientGUIExportAudio.CanExportAudio( GetFakeMediaResult( has_audio = False ) ) )
        self.assertFalse( ClientGUIExportAudio.CanExportAudio( GetFakeMediaResult( mime = HC.IMAGE_PNG, has_audio = False ) ) )
        
    
    def test_panel( self ):
        
        dialog = QW.QDialog()
        
        media_result = GetFakeMediaResult()
        
        panel = ClientGUIExportAudio.EditAudioExportPanel( dialog, media_result, None )
        
        # the defaults: an mp3 as it is
        self.assertEqual( panel.GetValue(), A.AudioExportSettings() )
        
        self.assertTrue( panel._mp3_kbps.isEnabled() )
        self.assertFalse( panel._wav_bit_depth.isEnabled() )
        self.assertIn( 'approximate resulting file size', panel._estimate.text() )
        
        # a wav at the file's own rate can't say how big it will be
        panel._format.SetValue( A.AUDIO_EXPORT_FORMAT_WAV )
        panel._UpdateControls()
        
        self.assertFalse( panel._mp3_kbps.isEnabled() )
        self.assertTrue( panel._wav_bit_depth.isEnabled() )
        self.assertIn( 'depends', panel._estimate.text() )
        
        panel._sample_rate.SetValue( 44100 )
        panel._channels.SetValue( 2 )
        
        self.assertIn( 'approximate resulting file size', panel._estimate.text() )
        
        settings = panel.GetValue()
        
        self.assertEqual( settings, A.AudioExportSettings( export_format = A.AUDIO_EXPORT_FORMAT_WAV, sample_rate = 44100, channels = 2 ) )
        
        # the next one starts how this one was set
        panel = ClientGUIExportAudio.EditAudioExportPanel( dialog, media_result, settings, span_ms = ( 15000, 45000 ) )
        
        self.assertEqual( panel.GetValue(), settings )
        
        # and an A-B part is sized for its own length
        self.assertEqual( panel._duration_ms, 30000 )
        
        dialog.deleteLater()
        
    
