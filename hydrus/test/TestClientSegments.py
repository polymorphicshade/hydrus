import unittest

from qtpy import QtWidgets as QW

from hydrus.core import HydrusExceptions

from hydrus.client.gui.media import ClientGUIMediaSegments

class TestSegments( unittest.TestCase ):
    
    def test_add_segment( self ):
        
        segments = [ ( 5000, 'b' ), ( 0, 'a' ) ]
        
        # in order
        self.assertEqual( ClientGUIMediaSegments.AddSegment( segments, ( 3000, 'c' ) ), [ ( 0, 'a' ), ( 3000, 'c' ), ( 5000, 'b' ) ] )
        
        # a second name at a point is fine, but the same one again is only there once
        self.assertEqual( ClientGUIMediaSegments.AddSegment( segments, ( 5000, 'z' ) ), [ ( 0, 'a' ), ( 5000, 'b' ), ( 5000, 'z' ) ] )
        self.assertEqual( ClientGUIMediaSegments.AddSegment( segments, ( 5000, 'b' ) ), [ ( 0, 'a' ), ( 5000, 'b' ) ] )
        
    
    def test_segment_panels( self ):
        
        dialog = QW.QDialog()
        
        # adding one at 1:00
        
        panel = ClientGUIMediaSegments.EditSegmentPanel( dialog, ( 60000, '' ), 120000 )
        
        self.assertEqual( panel._timestamp.text(), '1:00.000' )
        
        # it needs a name
        with self.assertRaises( HydrusExceptions.VetoException ):
            
            panel.GetValue()
            
        
        panel._name.setText( ' chorus ' )
        
        self.assertEqual( panel.GetValue(), ( 60000, 'chorus' ) )
        
        panel._timestamp.setText( '1:30.5' )
        
        self.assertEqual( panel.GetValue(), ( 90500, 'chorus' ) )
        
        # and a point that is in the file
        for bad_text in ( 'soon', '2:00.001' ):
            
            panel._timestamp.setText( bad_text )
            
            with self.assertRaises( HydrusExceptions.VetoException ):
                
                panel.GetValue()
                
            
        
        # managing
        
        panel = ClientGUIMediaSegments.ManageSegmentsPanel( dialog, [ ( 5000, 'b' ), ( 0, 'a' ), ( 13000, 'c' ) ], 120000 )
        
        segments_list = panel._segments_list
        
        self.assertEqual( [ segments_list.item( index ).text() for index in range( segments_list.count() ) ], [ '0:00.000: a', '0:05.000: b', '0:13.000: c' ] )
        
        self.assertFalse( panel._edit_button.isEnabled() )
        self.assertFalse( panel._remove_button.isEnabled() )
        self.assertTrue( panel._clear_button.isEnabled() )
        
        segments_list.item( 1 ).setSelected( True )
        
        self.assertTrue( panel._edit_button.isEnabled() )
        self.assertTrue( panel._remove_button.isEnabled() )
        
        panel._Remove()
        
        self.assertEqual( panel.GetValue(), [ ( 0, 'a' ), ( 13000, 'c' ) ] )
        
        dialog.deleteLater()
        
    
    def test_segments_menu( self ):
        
        window = QW.QWidget()
        
        menu = QW.QMenu( window )
        
        calls = []
        
        def add():
            
            calls.append( 'add' )
            
        
        def go_to( timestamp_ms ):
            
            calls.append( ( 'go to', timestamp_ms ) )
            
        
        def manage():
            
            calls.append( 'manage' )
            
        
        # with none yet, there is nowhere to go
        segments_menu = ClientGUIMediaSegments.AppendSegmentsMenu( menu, [], add, go_to, manage )
        
        self.assertEqual( menu.actions()[-1].text(), 'segments' )
        
        actions = segments_menu.actions()
        
        self.assertEqual( [ action.text() for action in actions ], [ 'add…', 'go to', 'manage…' ] )
        self.assertFalse( actions[1].isEnabled() )
        
        actions[0].trigger()
        actions[2].trigger()
        
        self.assertEqual( calls, [ 'add', 'manage' ] )
        
        # with some, they are listed in order, and clicking one goes there
        calls = []
        
        segments_menu = ClientGUIMediaSegments.AppendSegmentsMenu( menu, [ ( 90500, 'chorus' ), ( 5000, 'intro' ) ], add, go_to, manage )
        
        self.assertEqual( menu.actions()[-1].text(), 'segments (2)' )
        
        go_to_action = segments_menu.actions()[1]
        
        self.assertTrue( go_to_action.isEnabled() )
        
        go_to_actions = go_to_action.menu().actions()
        
        self.assertEqual( [ action.text() for action in go_to_actions ], [ '0:05.000: intro', '1:30.500: chorus' ] )
        
        go_to_actions[1].trigger()
        
        self.assertEqual( calls, [ ( 'go to', 90500 ) ] )
        
        window.deleteLater()
        
    
