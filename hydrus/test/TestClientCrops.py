import os
import tempfile
import unittest

from unittest import mock

from PIL import Image as PILImage

from hydrus.core import HydrusExceptions

from hydrus.client import ClientCrops
from hydrus.client import ClientGlobals as CG
from hydrus.client import ClientLocation
from hydrus.client import ClientSnapshots
from hydrus.client.gui import ClientGUIMenus
from hydrus.client.gui.canvas import ClientGUICanvas
from hydrus.client.gui.canvas import ClientGUICanvasOverlays
from hydrus.client.gui.media import ClientGUIMediaMenus
from hydrus.client.gui.media import ClientGUIMediaSimpleActions

HASH = b'\x01' * 32
CROP_HASH = b'\x02' * 32

RED = ( 255, 0, 0 )
BLUE = ( 0, 0, 255 )
WHITE = ( 255, 255, 255 )

def GetTestImage() -> PILImage.Image:
    
    # 200x100, white, with a red top-left corner pixel and a blue right half
    image = PILImage.new( 'RGB', ( 200, 100 ), WHITE )
    
    image.paste( BLUE, ( 100, 0, 200, 100 ) )
    
    image.putpixel( ( 0, 0 ), RED )
    
    return image
    

class TestCropMaths( unittest.TestCase ):
    
    def test_crop_rect( self ):
        
        # the file is shown at half size, at ( 50, 50 )
        media_rect = ( 50, 50, 100, 50 )
        image_size = ( 200, 100 )
        
        self.assertEqual( ClientCrops.GetCropRectInImage( ( 75, 50, 25, 25 ), media_rect, image_size ), ( 50, 0, 50, 50 ) )
        
        # the whole thing
        self.assertEqual( ClientCrops.GetCropRectInImage( media_rect, media_rect, image_size ), ( 0, 0, 200, 100 ) )
        
        # just the part over the file counts
        self.assertEqual( ClientCrops.GetCropRectInImage( ( 0, 0, 100, 75 ), media_rect, image_size ), ( 0, 0, 100, 50 ) )
        self.assertEqual( ClientCrops.GetCropRectInImage( ( 140, 90, 100, 100 ), media_rect, image_size ), ( 180, 80, 20, 20 ) )
        
        # none of it
        self.assertIsNone( ClientCrops.GetCropRectInImage( ( 0, 0, 40, 40 ), media_rect, image_size ) )
        self.assertIsNone( ClientCrops.GetCropRectInImage( ( 150, 50, 10, 10 ), media_rect, image_size ) )
        self.assertIsNone( ClientCrops.GetCropRectInImage( ( 75, 50, 25, 25 ), ( 50, 50, 0, 0 ), image_size ) )
        
    
    def test_rotating( self ):
        
        image = GetTestImage()
        
        self.assertIs( ClientCrops.RotatePILImageAsShown( image, 0 ), image )
        
        # turned clockwise, the top-left goes to the top-right
        turned = ClientCrops.RotatePILImageAsShown( image, 90 )
        
        self.assertEqual( turned.size, ( 100, 200 ) )
        self.assertEqual( turned.getpixel( ( 99, 0 ) ), RED )
        
        self.assertEqual( ClientCrops.RotatePILImageAsShown( image, 180 ).getpixel( ( 199, 99 ) ), RED )
        self.assertEqual( ClientCrops.RotatePILImageAsShown( image, 270 ).getpixel( ( 0, 199 ) ), RED )
        
        # any other angle fits in its bounding box, with see-through corners
        turned = ClientCrops.RotatePILImageAsShown( image, 45 )
        
        self.assertEqual( turned.mode, 'RGBA' )
        self.assertGreater( turned.size[0], 200 )
        self.assertEqual( turned.getpixel( ( 0, 0 ) )[3], 0 )
        
    
    def test_cropping( self ):
        
        image = GetTestImage()
        
        # shown at half size, the overlay over the right half
        crop = ClientCrops.CropPILImage( image, 0, ( 50, 0, 50, 50 ), ( 0, 0, 100, 50 ) )
        
        self.assertEqual( crop.size, ( 100, 100 ) )
        self.assertEqual( crop.getpixel( ( 0, 0 ) ), BLUE )
        
        # turned 90, the image is shown 50 wide and 100 tall. the top of it, as shown, is the left of the file
        crop = ClientCrops.CropPILImage( image, 90, ( 0, 0, 50, 50 ), ( 0, 0, 50, 100 ) )
        
        self.assertEqual( crop.size, ( 100, 100 ) )
        self.assertEqual( crop.getpixel( ( 99, 0 ) ), RED )
        
        with self.assertRaises( HydrusExceptions.VetoException ):
            
            ClientCrops.CropPILImage( image, 0, ( 500, 500, 10, 10 ), ( 0, 0, 100, 50 ) )
            
        
    
    def test_files( self ):
        
        temp_dir = tempfile.mkdtemp()
        
        try:
            
            source_path = os.path.join( temp_dir, 'source.png' )
            dest_path = os.path.join( temp_dir, 'dest.png' )
            
            GetTestImage().save( source_path, 'PNG' )
            
            ClientCrops.CropRectFromImageFile( source_path, ( 90, 0, 20, 10 ), dest_path )
            
            with PILImage.open( dest_path ) as crop:
                
                self.assertEqual( crop.size, ( 20, 10 ) )
                self.assertEqual( crop.convert( 'RGB' ).getpixel( ( 0, 0 ) ), WHITE )
                self.assertEqual( crop.convert( 'RGB' ).getpixel( ( 19, 0 ) ), BLUE )
                
            
            for bad_rect in ( ( 190, 0, 20, 10 ), ( -1, 0, 10, 10 ), ( 0, 0, 0, 10 ), ( 0, 95, 10, 10 ) ):
                
                with self.assertRaises( HydrusExceptions.VetoException ):
                    
                    ClientCrops.CropRectFromImageFile( source_path, bad_rect, dest_path )
                    
                
            
            # a palette image saves fine
            ClientCrops.SavePILImageAsPNG( GetTestImage().convert( 'P' ).convert( 'CMYK' ), dest_path )
            
            with PILImage.open( dest_path ) as saved:
                
                self.assertIn( saved.mode, ( 'RGB', 'RGBA' ) )
                
        finally:
            
            for name in os.listdir( temp_dir ):
                
                os.remove( os.path.join( temp_dir, name ) )
                
            
            os.rmdir( temp_dir )
            
        
    

class TestCrops( unittest.TestCase ):
    
    def test_crops_domain( self ):
        
        location_context = ClientLocation.LocationContext.STATICCreateSimple( b'\x09' * 32 )
        
        with mock.patch.object( ClientCrops, 'GetCropsLocationContext', return_value = None ), mock.patch.object( CG.client_controller, 'Read' ) as read:
            
            self.assertEqual( ClientCrops.GetCropHashes( HASH ), [] )
            
            read.assert_not_called()
            
        
        with mock.patch.object( ClientCrops, 'GetCropsLocationContext', return_value = location_context ), mock.patch.object( CG.client_controller, 'Read', return_value = [ CROP_HASH ] ) as read:
            
            self.assertEqual( ClientCrops.GetCropHashes( HASH ), [ CROP_HASH ] )
            
            read.assert_called_once_with( 'file_crops_for_files', [ HASH ], location_context )
            
        
        # its own domain, not the snapshots one
        with mock.patch.object( ClientSnapshots, 'GetOwnLocalFileDomainServiceKey', return_value = b'\x09' * 32 ) as get_service_key:
            
            ClientCrops.GetCropsServiceKey()
            
            ( args, kwargs ) = get_service_key.call_args
            
            self.assertEqual( args[ : 2 ], ( 'crops_file_service_key', 'crops' ) )
            
        
    
    def test_importing( self ):
        
        with mock.patch.object( ClientCrops, 'GetCropsServiceKey', return_value = b'\x09' * 32 ), mock.patch.object( ClientSnapshots, 'ImportFileToOwnLocalFileDomain', return_value = CROP_HASH ) as import_file, mock.patch.object( CG.client_controller, 'WriteSynchronous' ) as write:
            
            self.assertEqual( ClientCrops.ImportCrop( 'crop.png', HASH, 5000 ), CROP_HASH )
            
            import_file.assert_called_once_with( 'crop.png', b'\x09' * 32, 'crop' )
            write.assert_called_once_with( 'file_crop_add', HASH, CROP_HASH, 5000 )
            
        
    
    def _PatchMenus( self, menu_items ):
        
        def append_menu_item( menu, label, description, callable, *args, **kwargs ):
            
            menu_items.append( ( label, callable, args ) )
            
            return mock.Mock()
            
        
        patches = [
            mock.patch.object( ClientGUIMenus, 'GenerateMenu' ),
            mock.patch.object( ClientGUIMenus, 'AppendMenu', side_effect = lambda menu, submenu, label, *args, **kwargs: menu_items.append( ( label, None, () ) ) ),
            mock.patch.object( ClientGUIMenus, 'AppendSeparator' ),
            mock.patch.object( ClientGUIMenus, 'AppendMenuLabel', side_effect = lambda menu, label, *args, **kwargs: menu_items.append( ( label, None, () ) ) ),
            mock.patch.object( ClientGUIMenus, 'AppendMenuItem', side_effect = append_menu_item )
        ]
        
        for patch in patches:
            
            patch.start()
            
            self.addCleanup( patch.stop )
            
        
    
    def _GetCanvas( self, can_crop = True, can_take_snapshot = False ):
        
        canvas = ClientGUICanvas.CanvasMediaListBrowser.__new__( ClientGUICanvas.CanvasMediaListBrowser )
        
        canvas._current_media = mock.Mock()
        canvas._current_media.GetHash.return_value = HASH
        canvas._current_media.GetMime.return_value = 1
        
        canvas._media_container = mock.Mock()
        canvas._media_container.CanCrop.return_value = can_crop
        canvas._media_container.CanTakeSnapshot.return_value = can_take_snapshot
        canvas._media_container.GetRotation.return_value = 0
        
        return canvas
        
    
    def test_menu( self ):
        
        menu_items = []
        
        self._PatchMenus( menu_items )
        
        canvas = self._GetCanvas()
        
        overlays = [ mock.Mock(), mock.Mock() ]
        
        with mock.patch.object( ClientCrops, 'GetCropHashes', return_value = [ CROP_HASH ] ), mock.patch.object( ClientGUICanvasOverlays, 'GetOverlays', return_value = overlays ):
            
            canvas._AppendCropsMenu( mock.Mock() )
            
        
        self.assertEqual( [ label for ( label, callable, args ) in menu_items ], [ 'show crops (1)', 'crop to overlay 1', 'crop to overlay 2', 'crops (1)' ] )
        
        # each one crops to its overlay
        self.assertEqual( menu_items[2][2], ( overlays[1], ) )
        
        menu_items.clear()
        
        # no overlays, and no crops yet
        with mock.patch.object( ClientCrops, 'GetCropHashes', return_value = [] ), mock.patch.object( ClientGUICanvasOverlays, 'GetOverlays', return_value = [] ):
            
            canvas._AppendCropsMenu( mock.Mock() )
            
        
        self.assertEqual( [ label for ( label, callable, args ) in menu_items ], [ 'show crops (0)', 'add an overlay (overlays->add) to crop with', 'crops' ] )
        
        menu_items.clear()
        
        # audio has no menu
        canvas._media_container.CanCrop.return_value = False
        
        with mock.patch.object( ClientCrops, 'GetCropHashes', return_value = [] ):
            
            canvas._AppendCropsMenu( mock.Mock() )
            
        
        self.assertEqual( menu_items, [] )
        
    
    def test_cropping_an_image( self ):
        
        canvas = self._GetCanvas()
        
        temp_dir = tempfile.mkdtemp()
        
        source_path = os.path.join( temp_dir, 'source.png' )
        
        GetTestImage().save( source_path, 'PNG' )
        
        overlay = mock.Mock()
        
        # the overlay is the right half of a 400x200 canvas, and the file fills it
        overlay.GetFractions.return_value = ( 0.5, 0.0, 0.5, 1.0 )
        
        canvas._media_container.GetMediaRectIn.return_value = ( 0, 0, 400, 200 )
        
        imported = []
        
        def import_crop( path, hash, timestamp_ms ):
            
            with PILImage.open( path ) as crop:
                
                imported.append( ( crop.size, crop.convert( 'RGB' ).getpixel( ( 0, 0 ) ), hash, timestamp_ms ) )
                
            
            return CROP_HASH
            
        
        patches = [
            mock.patch.object( canvas, 'width', return_value = 400 ),
            mock.patch.object( canvas, 'height', return_value = 200 ),
            mock.patch.object( CG.client_controller, 'CallToThread', side_effect = lambda func, *args, **kwargs: func( *args, **kwargs ) ),
            mock.patch.object( CG.client_controller.client_files_manager, 'GetFilePath', return_value = source_path ),
            mock.patch.object( ClientCrops, 'ImportCrop', side_effect = import_crop )
        ]
        
        try:
            
            for patch in patches:
                
                patch.start()
                
            
            canvas._CropToOverlay( overlay )
            
        finally:
            
            for patch in patches:
                
                patch.stop()
                
            
            os.remove( source_path )
            os.rmdir( temp_dir )
            
        
        # the blue half, in the file's own pixels, from the file itself
        self.assertEqual( imported, [ ( ( 100, 100 ), BLUE, HASH, None ) ] )
        
    
    def test_overlay_not_over_the_file( self ):
        
        canvas = self._GetCanvas()
        
        overlay = mock.Mock()
        
        overlay.GetFractions.return_value = ( 0.0, 0.0, 0.1, 0.1 )
        
        canvas._media_container.GetMediaRectIn.return_value = ( 200, 100, 100, 50 )
        
        with mock.patch.object( canvas, 'width', return_value = 400 ), mock.patch.object( canvas, 'height', return_value = 200 ), mock.patch.object( ClientGUICanvas.ClientGUIDialogsMessage, 'ShowWarning' ) as show_warning, mock.patch.object( ClientCrops, 'ImportCrop' ) as import_crop:
            
            canvas._CropToOverlay( overlay )
            
            show_warning.assert_called_once()
            import_crop.assert_not_called()
            
        
    
    def test_thumbnail_menu( self ):
        
        menu_items = []
        
        self._PatchMenus( menu_items )
        
        media = mock.Mock()
        media.GetDisplayMedia.return_value.GetHash.return_value = HASH
        
        with mock.patch.object( ClientCrops, 'GetCropHashesForFiles', return_value = [] ):
            
            ClientGUIMediaMenus.AddCropsMenuItem( mock.Mock(), media )
            
        
        # none, no item
        self.assertEqual( menu_items, [] )
        
        with mock.patch.object( ClientCrops, 'GetCropHashesForFiles', return_value = [ CROP_HASH, CROP_HASH ] ):
            
            ClientGUIMediaMenus.AddCropsMenuItem( mock.Mock(), media )
            
        
        self.assertEqual( menu_items, [ ( 'crops (2)', ClientGUIMediaSimpleActions.ShowCropsInNewPage, ( [ HASH ], ) ) ] )
        
        
        
