import unittest

from hydrus.core import HydrusSerialisable

from hydrus.client import ClientOptions
from hydrus.client import ClientScreenLocations

class TestScreenLocations( unittest.TestCase ):
    
    def test_errors( self ):
        
        good = ( 'left monitor', 'DISPLAY1', 0, 0, 800, 600 )
        
        self.assertIsNone( ClientScreenLocations.GetScreenLocationError( good, [] ) )
        self.assertIsNone( ClientScreenLocations.GetScreenLocationError( good, [ 'right monitor' ] ) )
        
        # names are not case-sensitive
        self.assertIsNotNone( ClientScreenLocations.GetScreenLocationError( good, [ 'Left Monitor' ] ) )
        
        self.assertIsNotNone( ClientScreenLocations.GetScreenLocationError( ( '', 'DISPLAY1', 0, 0, 800, 600 ), [] ) )
        self.assertIsNotNone( ClientScreenLocations.GetScreenLocationError( ( 'tiny', 'DISPLAY1', 0, 0, 0, 600 ), [] ) )
        
        self.assertEqual( ClientScreenLocations.NormaliseScreenLocationName( '  left   monitor ' ), 'left monitor' )
        
    
    def test_target_geometry( self ):
        
        # the primary screen is first. the second sits to the right, a little lower
        screens = [
            ( 'DISPLAY1', 0, 0, 1920, 1080 ),
            ( 'DISPLAY2', 1920, 200, 1280, 1024 )
        ]
        
        # x and y are from the screen's own top-left
        self.assertEqual( ClientScreenLocations.GetTargetGeometry( ( 'a', 'DISPLAY1', 100, 50, 800, 600 ), screens ), ( True, 100, 50, 800, 600 ) )
        self.assertEqual( ClientScreenLocations.GetTargetGeometry( ( 'b', 'DISPLAY2', 100, 50, 800, 600 ), screens ), ( True, 2020, 250, 800, 600 ) )
        
        # a screen that is not connected falls back to the primary
        self.assertEqual( ClientScreenLocations.GetTargetGeometry( ( 'c', 'DISPLAY3', 100, 50, 800, 600 ), screens ), ( False, 100, 50, 800, 600 ) )
        
        # a window snapped to an edge has its frame a few pixels off the screen, which is fine
        self.assertEqual( ClientScreenLocations.GetTargetGeometry( ( 'e', 'DISPLAY1', -8, -8, 800, 600 ), screens ), ( True, -8, -8, 800, 600 ) )
        
        # but the top-left stays about on the screen, even if it was saved on a bigger one or way off the top-left
        self.assertEqual( ClientScreenLocations.GetTargetGeometry( ( 'd', 'DISPLAY2', 3000, 2000, 800, 600 ), screens ), ( True, 1920 + 1280 - 32, 200 + 1024 - 32, 800, 600 ) )
        self.assertEqual( ClientScreenLocations.GetTargetGeometry( ( 'f', 'DISPLAY2', -500, -500, 800, 600 ), screens ), ( True, 1920 - 32, 200 - 32, 800, 600 ) )
        
    
    def test_options( self ):
        
        new_options = ClientOptions.ClientOptions()
        
        self.assertEqual( new_options.GetScreenLocations(), [] )
        
        screen_locations = [ ( 'left monitor', 'DISPLAY1', 0, 0, 960, 1080 ), ( 'right monitor', 'DISPLAY2', 0, 0, 1280, 1024 ) ]
        
        new_options.SetScreenLocations( screen_locations )
        
        self.assertEqual( new_options.GetScreenLocations(), screen_locations )
        
        # it survives saving, coming back as tuples
        loaded_options = HydrusSerialisable.CreateFromSerialisableTuple( new_options.GetSerialisableTuple() )
        
        self.assertEqual( loaded_options.GetScreenLocations(), screen_locations )
        
    
