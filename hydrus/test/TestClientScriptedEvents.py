import unittest

from qtpy import QtWidgets as QW

from hydrus.core import HydrusExceptions

from hydrus.client.gui.canvas import ClientGUICanvasMedia
from hydrus.client.gui.media import ClientGUIMediaScriptedEvents
from hydrus.client.media import ClientMediaScriptedEvents

class TestScriptedEvents( unittest.TestCase ):
    
    def test_scripted_events_to_run( self ):
        
        # at the start, at 5 seconds, twice at 13 seconds, and near the end of a 60 second file
        scripted_events = [ ( 13000, 'b' ), ( 0, 'start' ), ( 5000, 'a' ), ( 13000, 'c' ), ( 59900, 'end' ) ]
        
        def run( last_timestamp_ms, current_timestamp_ms ):
            
            return [ command for ( timestamp_ms, command ) in ClientMediaScriptedEvents.GetScriptedEventsToRun( scripted_events, last_timestamp_ms, current_timestamp_ms, 60000 ) ]
            
        
        # the first look at playback, at the start
        self.assertEqual( run( None, 0 ), [ 'start' ] )
        self.assertEqual( run( None, 40 ), [ 'start' ] )
        
        # opening somewhere else does not run what came before
        self.assertEqual( run( None, 30000 ), [] )
        
        # normal playback runs what it goes past, once
        self.assertEqual( run( 0, 40 ), [] )
        self.assertEqual( run( 4990, 5000 ), [ 'a' ] )
        self.assertEqual( run( 5000, 5040 ), [] )
        self.assertEqual( run( 12990, 13010 ), [ 'b', 'c' ] )
        
        # a big jump is the user seeking
        self.assertEqual( run( 1000, 20000 ), [] )
        self.assertEqual( run( 20000, 4000 ), [] )
        
        # looping round from the end catches the end and the start
        self.assertEqual( run( 59880, 20 ), [ 'end', 'start' ] )
        self.assertEqual( run( 59950, 20 ), [ 'start' ] )
        
        # no duration, no loop detection
        self.assertEqual( ClientMediaScriptedEvents.GetScriptedEventsToRun( scripted_events, 59880, 20, None ), [] )
        
        self.assertEqual( ClientMediaScriptedEvents.GetScriptedEventsToRun( [], 0, 40, 60000 ), [] )
        
    
    def test_parse_playback_timestamp( self ):
        
        for timestamp_ms in ( 0, 999, 1000, 65250, 3599999, 3723456 ):
            
            self.assertEqual( ClientGUICanvasMedia.ParsePlaybackTimestampString( ClientGUICanvasMedia.ConvertPlaybackTimestampToString( timestamp_ms ) ), timestamp_ms )
            
        
        self.assertEqual( ClientGUICanvasMedia.ParsePlaybackTimestampString( ' 2:05.5 ' ), 125500 )
        self.assertEqual( ClientGUICanvasMedia.ParsePlaybackTimestampString( '75' ), 75000 )
        self.assertEqual( ClientGUICanvasMedia.ParsePlaybackTimestampString( '1:00' ), 60000 )
        
        for bad_text in ( '', 'abc', '1:2:3:4', '1::00', '-5', 'inf', 'nan', '1:-2' ):
            
            with self.assertRaises( ValueError ):
                
                ClientGUICanvasMedia.ParsePlaybackTimestampString( bad_text )
                
            
        
    
    def test_scripted_event_panels( self ):
        
        dialog = QW.QDialog()
        
        # adding one at 1:00
        
        panel = ClientGUIMediaScriptedEvents.EditScriptedEventPanel( dialog, ( 60000, '' ), 120000 )
        
        self.assertEqual( panel._timestamp.text(), '1:00.000' )
        
        # it needs a command
        with self.assertRaises( HydrusExceptions.VetoException ):
            
            panel.GetValue()
            
        
        panel._command.setText( ' explorer C:\\ ' )
        
        self.assertEqual( panel.GetValue(), ( 60000, 'explorer C:\\' ) )
        
        panel._timestamp.setText( '1:30.5' )
        
        self.assertEqual( panel.GetValue(), ( 90500, 'explorer C:\\' ) )
        
        # and a point that is in the file
        for bad_text in ( 'soon', '2:00.001' ):
            
            panel._timestamp.setText( bad_text )
            
            with self.assertRaises( HydrusExceptions.VetoException ):
                
                panel.GetValue()
                
            
        
        # managing
        
        panel = ClientGUIMediaScriptedEvents.ManageScriptedEventsPanel( dialog, [ ( 5000, 'b' ), ( 0, 'a' ), ( 13000, 'c' ) ], 120000 )
        
        scripted_events_list = panel._scripted_events_list
        
        self.assertEqual( [ scripted_events_list.item( index ).text() for index in range( scripted_events_list.count() ) ], [ '0:00.000: a', '0:05.000: b', '0:13.000: c' ] )
        
        scripted_events_list.item( 1 ).setSelected( True )
        
        panel._Remove()
        
        self.assertEqual( panel.GetValue(), [ ( 0, 'a' ), ( 13000, 'c' ) ] )
        
        dialog.deleteLater()
        
    
