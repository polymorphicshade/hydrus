import unittest

from unittest import mock

from hydrus.core import HydrusTime

from hydrus.client import ClientApplicationCommand as CAC
from hydrus.client.gui import ClientGUIMediaViewerABRepeat
from hydrus.client.gui import ClientGUIMediaViewerSlideshows
from hydrus.client.gui.canvas import ClientGUICanvas
from hydrus.client.gui.canvas import ClientGUICanvasMenus
from hydrus.client.media import ClientMediaSlideshows

from hydrus.test import TestGlobals as TG

NOW = 1000.0

class FakeMediaContainer( object ):
    
    def __init__( self, has_duration = True ):
        
        self.has_duration = has_duration
        self.has_played_once_through = False
        self.stop_for_slideshow = None
        
    
    def CurrentlyPresentingMediaWithDuration( self ):
        
        return self.has_duration
        
    
    def HasPlayedOnceThrough( self ):
        
        # like the real one, a file with nothing to play has always played through
        return self.has_played_once_through or not self.has_duration
        
    
    def StopForSlideshow( self, value ):
        
        self.stop_for_slideshow = value
        
    

class FakeCore( object ):
    
    def MenuIsOpen( self ):
        
        return False
        
    

class FakeHover( object ):
    
    def __init__( self ):
        
        self.period = None
        
    
    def SetSlideshowPeriod( self, value ):
        
        self.period = value
        
    

class TestSlideshowPeriods( unittest.TestCase ):
    
    def test_logic( self ):
        
        self.assertEqual( ClientMediaSlideshows.SLIDESHOW_PERIOD_ONCE_THROUGH, 0.0 )
        
        self.assertTrue( ClientMediaSlideshows.SlideshowPeriodIsValid( 0.0 ) )
        self.assertTrue( ClientMediaSlideshows.SlideshowPeriodIsValid( 0.08 ) )
        self.assertFalse( ClientMediaSlideshows.SlideshowPeriodIsValid( -1.0 ) )
        
        self.assertEqual( ClientMediaSlideshows.ConvertSlideshowPeriodToPretty( 0.0 ), 'each file once through' )
        self.assertEqual( ClientMediaSlideshows.ConvertSlideshowPeriodToPretty( 5.0 ), '5 seconds' )
        
    
    def test_still_period( self ):
        
        new_options = TG.test_controller.new_options
        
        slideshow_durations = new_options.GetSlideshowDurations()
        
        try:
            
            new_options.SetSlideshowDurations( [ 7.0, 30.0 ] )
            
            self.assertEqual( ClientMediaSlideshows.GetStillPeriod(), 7.0 )
            
        finally:
            
            new_options.SetSlideshowDurations( slideshow_durations )
            
        
    

class TestOnceThroughSlideshow( unittest.TestCase ):
    
    def _GetCanvas( self, period, has_duration = True ):
        
        canvas = ClientGUICanvas.CanvasMediaListBrowser.__new__( ClientGUICanvas.CanvasMediaListBrowser )
        
        canvas._media_container = FakeMediaContainer( has_duration = has_duration )
        canvas._current_media = 'media'
        canvas._top_hover = FakeHover()
        
        canvas._playback_gap_move_on_callable = None
        
        canvas._slideshow_is_running = True
        canvas._last_slideshow_switch_time = NOW
        canvas._normal_slideshow_period = period
        canvas._special_slideshow_period_for_current_media = None
        canvas._slideshow_paused_for_sub_window_since = None
        canvas._slideshow_is_playing_once_through = False
        
        self.moves = []
        
        patches = [
            mock.patch.object( canvas, '_SubWindowIsOpen', return_value = False ),
            mock.patch.object( canvas, '_MoveOnWithPlaybackGap', side_effect = lambda move_on_callable: self.moves.append( move_on_callable ) ),
            mock.patch.object( ClientGUICanvas.CGC, 'core', return_value = FakeCore() )
        ]
        
        for patch in patches:
            
            patch.start()
            
            self.addCleanup( patch.stop )
            
        
        return canvas
        
    
    def _DoWorkAt( self, canvas, now ):
        
        with mock.patch.object( HydrusTime, 'GetNowFloat', return_value = now ):
            
            canvas._DoSlideshowWork()
            
        
    
    def test_a_file_with_playback_plays_once_and_moves_on( self ):
        
        canvas = self._GetCanvas( 0.0 )
        
        container = canvas._media_container
        
        # still playing, however long it has been
        self._DoWorkAt( canvas, NOW + 3600 )
        
        self.assertEqual( self.moves, [] )
        
        # it is told to stop at the end, not loop round
        self.assertTrue( container.stop_for_slideshow )
        
        # and as soon as it is done, we move on
        container.has_played_once_through = True
        
        self._DoWorkAt( canvas, NOW + 0.01 )
        
        self.assertEqual( len( self.moves ), 1 )
        
    
    def test_an_image_stays_up_for_the_still_period( self ):
        
        canvas = self._GetCanvas( 0.0, has_duration = False )
        
        with mock.patch.object( ClientMediaSlideshows, 'GetStillPeriod', return_value = 7.0 ):
            
            self._DoWorkAt( canvas, NOW + 6.9 )
            
            self.assertEqual( self.moves, [] )
            
            self._DoWorkAt( canvas, NOW + 7.1 )
            
            self.assertEqual( len( self.moves ), 1 )
            
        
        # nothing to tell to stop
        self.assertIsNone( canvas._media_container.stop_for_slideshow )
        
    
    def test_no_special_periods( self ):
        
        canvas = self._GetCanvas( 0.0 )
        
        # the options that move short or long files on early, or let them overspill, are about a period, which this does not have
        canvas._CalculateAnySpecialSlideshowPeriodForCurrentMedia()
        
        self.assertIsNone( canvas._special_slideshow_period_for_current_media )
        
    
    def test_normal_slideshows_are_the_same( self ):
        
        canvas = self._GetCanvas( 10.0 )
        
        container = canvas._media_container
        
        # a file with playback loops until the period is up, played through or not
        self._DoWorkAt( canvas, NOW + 9.9 )
        
        self.assertEqual( self.moves, [] )
        self.assertIsNone( container.stop_for_slideshow )
        
        self._DoWorkAt( canvas, NOW + 10.1 )
        
        self.assertEqual( len( self.moves ), 1 )
        
    
    def test_starting_and_resuming( self ):
        
        canvas = self._GetCanvas( None )
        
        canvas._slideshow_is_running = False
        
        with mock.patch.object( canvas, '_StopSlideshow' ), mock.patch.object( canvas, '_RegisterNextSlideshowPresentation' ):
            
            # 0 starts
            canvas._StartSlideshow( 0.0 )
            
            self.assertTrue( canvas._slideshow_is_running )
            self.assertEqual( canvas._normal_slideshow_period, 0.0 )
            self.assertEqual( canvas._top_hover.period, 0.0 )
            
            # less than 0 does not
            canvas._slideshow_is_running = False
            
            canvas._StartSlideshow( -1.0 )
            
            self.assertFalse( canvas._slideshow_is_running )
            
            # resuming a 0 slideshow is still 0, not the default
            canvas._PausePlaySlideshow()
            
            self.assertTrue( canvas._slideshow_is_running )
            self.assertEqual( canvas._normal_slideshow_period, 0.0 )
            
            # and one that never started gets the default
            canvas._slideshow_is_running = False
            canvas._normal_slideshow_period = None
            
            canvas._PausePlaySlideshow()
            
            self.assertTrue( canvas._slideshow_is_running )
            self.assertEqual( canvas._normal_slideshow_period, TG.test_controller.new_options.GetSlideshowDurations()[0] )
            
        
        # the api's way in
        with mock.patch.object( canvas, '_StartSlideshow' ) as start_slideshow:
            
            canvas.StartSlideshow( 0.0 )
            
            start_slideshow.assert_called_once_with( 0.0 )
            
        
        self.assertEqual( canvas.GetSlideshowPeriod(), canvas._normal_slideshow_period )
        
    
    def test_menu( self ):
        
        win = mock.Mock()
        menu = mock.Mock()
        
        items = []
        
        with mock.patch.object( ClientGUICanvasMenus.ClientGUIMenus, 'AppendMenuItem', side_effect = lambda menu, label, description, callable, *args: items.append( ( label, description, args ) ) ), mock.patch.object( ClientGUICanvasMenus.ClientGUIMenus, 'AppendMenuCheckItem' ), mock.patch.object( ClientGUICanvasMenus.ClientGUIMenus, 'AppendSeparator' ):
            
            ClientGUICanvasMenus.AppendSlideshowMenu( win, menu, False, do_submenu = False, slideshow_duration = 0.0 )
            
            labels = [ label for ( label, description, args ) in items ]
            
            # a 0 slideshow can be resumed, like any other
            self.assertIn( 'resume at each file once through', labels )
            
            ( label, description, args ) = [ item for item in items if item[0] == 'each file once through' ][0]
            
            self.assertEqual( args[0].GetSimpleAction(), CAC.SIMPLE_START_SLIDESHOW )
            self.assertEqual( args[0].GetSimpleData(), 0.0 )
            
            # one that never started has nothing to resume
            items.clear()
            
            ClientGUICanvasMenus.AppendSlideshowMenu( win, menu, False, do_submenu = False, slideshow_duration = None )
            
            self.assertFalse( any( label.startswith( 'resume' ) for ( label, description, args ) in items ) )
            
            items.clear()
            
            ClientGUICanvasMenus.AppendSlideshowMenu( win, menu, True, do_submenu = False, slideshow_duration = 0.0 )
            
            self.assertIn( 'stop (each file once through)', [ label for ( label, description, args ) in items ] )
            
        
    

class TestOpenMediaViewerSlideshows( unittest.TestCase ):
    
    def _GetCanvas( self, canvas_key, supports_slideshow = True ):
        
        canvas = mock.Mock()
        
        canvas.GetCanvasKey.return_value = canvas_key
        canvas.SupportsSlideshow.return_value = supports_slideshow
        canvas.SlideshowIsRunning.return_value = False
        canvas.GetSlideshowPeriod.return_value = None
        
        return canvas
        
    
    def test_open_media_viewers( self ):
        
        browser = self._GetCanvas( b'\x01' * 32 )
        playlist = self._GetCanvas( b'\x02' * 32, supports_slideshow = False )
        
        browser.SlideshowIsRunning.return_value = True
        browser.GetSlideshowPeriod.return_value = 0.0
        
        with mock.patch.object( ClientGUIMediaViewerABRepeat, 'GetOpenMediaViewerCanvases', return_value = [ browser, playlist ] ):
            
            self.assertEqual( ClientGUIMediaViewerSlideshows.GetOpenMediaViewersSlideshows(), [
                { 'canvas_key' : ( b'\x01' * 32 ).hex(), 'supports_slideshow' : True, 'running' : True, 'period' : 0.0 },
                { 'canvas_key' : ( b'\x02' * 32 ).hex(), 'supports_slideshow' : False, 'running' : False, 'period' : None }
            ] )
            
            # a playlist moves itself along, so it is left alone
            self.assertEqual( ClientGUIMediaViewerSlideshows.StartOpenMediaViewersSlideshow( 0.0 ), 1 )
            
            browser.StartSlideshow.assert_called_once_with( 0.0 )
            playlist.StartSlideshow.assert_not_called()
            
            self.assertEqual( ClientGUIMediaViewerSlideshows.StartOpenMediaViewersSlideshow( 5.0, canvas_key = b'\x02' * 32 ), 0 )
            self.assertEqual( ClientGUIMediaViewerSlideshows.StartOpenMediaViewersSlideshow( 5.0, canvas_key = b'\x01' * 32 ), 1 )
            
            browser.StartSlideshow.assert_called_with( 5.0 )
            
            self.assertEqual( ClientGUIMediaViewerSlideshows.StopOpenMediaViewersSlideshow(), 1 )
            
            browser.StopSlideshow.assert_called_once_with()
            playlist.StopSlideshow.assert_not_called()
            
            
            
