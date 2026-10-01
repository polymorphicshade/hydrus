import json
import os
import unittest

from hydrus.client import ClientMediaViewerLayouts as L
from hydrus.client.gui import ClientGUIMediaViewerLayouts
from hydrus.client.gui.canvas import ClientGUICanvas

class TestMediaViewerLayouts( unittest.TestCase ):
    
    def test_json( self ):
        
        hash_a = os.urandom( 32 )
        hash_b = os.urandom( 32 )
        
        layouts = [
            L.MediaViewerLayout( [ hash_a, hash_b ], hash_b, 'DISPLAY1', 100, 50, 1280, 720, relative_zoom = 2.5, center = ( 0.25, 0.75 ), playback_ms = 12345 ),
            L.MediaViewerLayout( [ hash_a ], hash_a, 'DISPLAY2', -8, 0, 1920, 1080, maximised = True )
        ]
        
        text = L.ConvertMediaViewerLayoutsToJSON( layouts )
        
        # it is plain json a person can read
        d = json.loads( text )
        
        self.assertEqual( d[ L.MEDIA_VIEWER_LAYOUT_JSON_KEY ], L.MEDIA_VIEWER_LAYOUT_JSON_VERSION )
        self.assertEqual( d[ 'media_viewers' ][0][ 'current_hash' ], hash_b.hex() )
        self.assertEqual( d[ 'media_viewers' ][0][ 'window' ][ 'screen' ], 'DISPLAY1' )
        self.assertEqual( d[ 'media_viewers' ][1][ 'zoom' ], None )
        
        self.assertEqual( L.ConvertJSONToMediaViewerLayouts( text ), layouts )
        
        self.assertEqual( layouts[0].GetScreenLocation(), ( '', 'DISPLAY1', 100, 50, 1280, 720 ) )
        
        self.assertEqual( L.ConvertJSONToMediaViewerLayouts( L.ConvertMediaViewerLayoutsToJSON( [] ) ), [] )
        
    
    def test_json_leniency( self ):
        
        hash_a = os.urandom( 32 )
        hash_b = os.urandom( 32 )
        
        # the optional bits can be missing, and the current file is always one it browses
        text = json.dumps( {
            L.MEDIA_VIEWER_LAYOUT_JSON_KEY : 1,
            'media_viewers' : [
                {
                    'hashes' : [ hash_a.hex() ],
                    'current_hash' : hash_b.hex(),
                    'window' : { 'screen' : 'x', 'x' : 0, 'y' : 0, 'width' : 640, 'height' : 480 },
                    'zoom' : -1
                }
            ]
        } )
        
        ( layout, ) = L.ConvertJSONToMediaViewerLayouts( text )
        
        self.assertEqual( layout.hashes, [ hash_a, hash_b ] )
        self.assertFalse( layout.maximised )
        self.assertFalse( layout.fullscreen )
        self.assertIsNone( layout.relative_zoom )
        self.assertIsNone( layout.center )
        self.assertIsNone( layout.playback_ms )
        
    
    def test_json_errors( self ):
        
        with self.assertRaises( ValueError ):
            
            L.ConvertJSONToMediaViewerLayouts( 'not json' )
            
        
        with self.assertRaises( ValueError ):
            
            L.ConvertJSONToMediaViewerLayouts( json.dumps( { 'something' : 'else' } ) )
            
        
        with self.assertRaises( ValueError ):
            
            L.ConvertJSONToMediaViewerLayouts( json.dumps( [ 1, 2, 3 ] ) )
            
        
        with self.assertRaises( ValueError ):
            
            L.ConvertJSONToMediaViewerLayouts( json.dumps( { L.MEDIA_VIEWER_LAYOUT_JSON_KEY : 1, 'media_viewers' : [ { 'hashes' : [ 'not hex' ] } ] } ) )
            
        
        with self.assertRaises( ValueError ):
            
            window = { 'screen' : 'x', 'x' : 0, 'y' : 0, 'width' : 0, 'height' : 480 }
            
            L.ConvertJSONToMediaViewerLayouts( json.dumps( { L.MEDIA_VIEWER_LAYOUT_JSON_KEY : 1, 'media_viewers' : [ { 'hashes' : [], 'current_hash' : os.urandom( 32 ).hex(), 'window' : window } ] } ) )
            
        
    
    def test_hashes_around_current( self ):
        
        hashes = [ bytes( [ i ] ) * 32 for i in range( 10 ) ]
        
        # few enough, they are all kept
        self.assertEqual( L.GetHashesAroundCurrent( hashes, hashes[3], 10 ), hashes )
        
        # otherwise, the current one goes in the middle
        self.assertEqual( L.GetHashesAroundCurrent( hashes, hashes[5], 4 ), hashes[ 3 : 7 ] )
        
        # but not off either end
        self.assertEqual( L.GetHashesAroundCurrent( hashes, hashes[0], 4 ), hashes[ 0 : 4 ] )
        self.assertEqual( L.GetHashesAroundCurrent( hashes, hashes[9], 4 ), hashes[ 6 : 10 ] )
        
    
    def test_saveable_canvases( self ):
        
        # just the normal media viewer, not the filters or playlists, which have their own state
        browser = ClientGUICanvas.CanvasMediaListBrowser.__new__( ClientGUICanvas.CanvasMediaListBrowser )
        playlist = ClientGUICanvas.CanvasPlaylist.__new__( ClientGUICanvas.CanvasPlaylist )
        archive_delete = ClientGUICanvas.CanvasMediaListFilterArchiveDelete.__new__( ClientGUICanvas.CanvasMediaListFilterArchiveDelete )
        
        self.assertTrue( ClientGUIMediaViewerLayouts.CanvasIsSaveableInALayout( browser ) )
        self.assertFalse( ClientGUIMediaViewerLayouts.CanvasIsSaveableInALayout( playlist ) )
        self.assertFalse( ClientGUIMediaViewerLayouts.CanvasIsSaveableInALayout( archive_delete ) )
        self.assertFalse( ClientGUIMediaViewerLayouts.CanvasIsSaveableInALayout( None ) )
        
    
