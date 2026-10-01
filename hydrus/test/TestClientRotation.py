import os
import unittest

from hydrus.core import HydrusConstants as HC

from hydrus.client.gui.canvas import ClientGUICanvasMedia as M
from hydrus.client.media import ClientMediaSingle

from hydrus.test import HelperFunctions as HF

def GetFakeMedia( width, height, mime = HC.IMAGE_PNG ):
    
    media_result = HF.GetFakeMediaResult( os.urandom( 32 ), mime = mime )
    
    file_info_manager = media_result.GetFileInfoManager()
    
    file_info_manager.width = width
    file_info_manager.height = height
    
    return ClientMediaSingle.MediaSingle( media_result )
    

class TestMediaRotation( unittest.TestCase ):
    
    def test_normalise( self ):
        
        self.assertEqual( M.NormaliseRotation( 0 ), 0 )
        self.assertEqual( M.NormaliseRotation( 90 ), 90 )
        self.assertEqual( M.NormaliseRotation( 360 ), 0 )
        self.assertEqual( M.NormaliseRotation( 450 ), 90 )
        self.assertEqual( M.NormaliseRotation( -90 ), 270 )
        self.assertEqual( M.NormaliseRotation( 44.6 ), 45 )
        
        self.assertEqual( M.ConvertRotationToPrettyString( 90 ), '90°' )
        
    
    def test_bounding_size( self ):
        
        # right angles are exact
        self.assertEqual( M.GetRotatedBoundingSize( 1920, 1080, 0 ), ( 1920, 1080 ) )
        self.assertEqual( M.GetRotatedBoundingSize( 1920, 1080, 90 ), ( 1080, 1920 ) )
        self.assertEqual( M.GetRotatedBoundingSize( 1920, 1080, 180 ), ( 1920, 1080 ) )
        self.assertEqual( M.GetRotatedBoundingSize( 1920, 1080, 270 ), ( 1080, 1920 ) )
        
        # 45 degrees of a square is its diagonal both ways
        ( width, height ) = M.GetRotatedBoundingSize( 100, 100, 45 )
        
        self.assertAlmostEqual( width, 100 * 2 ** 0.5 )
        self.assertAlmostEqual( height, 100 * 2 ** 0.5 )
        
        # and back again
        ( width, height ) = M.GetUnrotatedSizeInBoundingSize( 100 * 2 ** 0.5, 100 * 2 ** 0.5, 100, 100, 45 )
        
        self.assertAlmostEqual( width, 100 )
        self.assertAlmostEqual( height, 100 )
        
        # a turned 1920x1080 at half size, in its box
        ( width, height ) = M.GetUnrotatedSizeInBoundingSize( 540, 960, 1920, 1080, 90 )
        
        self.assertAlmostEqual( width, 960 )
        self.assertAlmostEqual( height, 540 )
        
        ( box_width, box_height ) = M.GetRotatedBoundingSize( 1920, 1080, 30 )
        
        ( width, height ) = M.GetUnrotatedSizeInBoundingSize( box_width / 2, box_height / 2, 1920, 1080, 30 )
        
        self.assertAlmostEqual( width, 960 )
        self.assertAlmostEqual( height, 540 )
        
    
    def test_media_size( self ):
        
        media = GetFakeMedia( 1920, 1080 )
        
        self.assertEqual( M.CalculateMediaSize( media, 0.5 ), ( 960, 540 ) )
        self.assertEqual( M.CalculateMediaSize( media, 0.5, rotation = 90 ), ( 540, 960 ) )
        
        # turned on its side, a wide file fits a wide window by its old height
        zooms = M.CalculateCanvasZooms( M.QC.QSize( 1920, 1080 ), M.CC.CANVAS_MEDIA_VIEWER, 1.0, media, M.CC.MEDIA_VIEWER_ACTION_SHOW_WITH_NATIVE, rotation = 90 )
        
        canvas_zoom = zooms[ M.MEDIA_VIEWER_ZOOM_TYPE_CANVAS ]
        
        self.assertLessEqual( canvas_zoom * 1920, 1080 )
        
        unrotated_zooms = M.CalculateCanvasZooms( M.QC.QSize( 1920, 1080 ), M.CC.CANVAS_MEDIA_VIEWER, 1.0, media, M.CC.MEDIA_VIEWER_ACTION_SHOW_WITH_NATIVE )
        
        self.assertGreater( unrotated_zooms[ M.MEDIA_VIEWER_ZOOM_TYPE_CANVAS ], canvas_zoom )
        
    
