import collections.abc
import threading

from PIL import Image as PILImage

from hydrus.core import HydrusExceptions
from hydrus.core.files.images import HydrusImageHandling

from hydrus.client import ClientGlobals as CG
from hydrus.client import ClientLocation
from hydrus.client import ClientSnapshots

# crops are parts of a file the user cuts out in the media viewer, with an overlay's box. like snapshots, they go in a local file domain of their own, so they stay out of 'my files', and each one remembers the file it came from

CROPS_SERVICE_NAME = 'crops'

CROPS_SERVICE_KEY_OPTION = 'crops_file_service_key'

crops_service_lock = threading.Lock()

# ( x, y, width, height )
Rect = tuple[ int, int, int, int ]

def GetCropsServiceKey( create_if_missing = True ) -> bytes | None:
    
    return ClientSnapshots.GetOwnLocalFileDomainServiceKey( CROPS_SERVICE_KEY_OPTION, CROPS_SERVICE_NAME, crops_service_lock, create_if_missing = create_if_missing )
    

def GetCropsLocationContext() -> ClientLocation.LocationContext | None:
    
    service_key = GetCropsServiceKey( create_if_missing = False )
    
    if service_key is None:
        
        return None
        
    
    return ClientLocation.LocationContext.STATICCreateSimple( service_key )
    

def GetCropHashes( hash: bytes ) -> list[ bytes ]:
    
    # the crops taken from this file that are still in the crops domain, in the order they come in the file
    return GetCropHashesForFiles( [ hash ] )
    

def GetCropHashesForFiles( hashes: collections.abc.Sequence[ bytes ] ) -> list[ bytes ]:
    
    # all of these files' crops, file by file in the order given
    location_context = GetCropsLocationContext()
    
    if location_context is None or len( hashes ) == 0:
        
        return []
        
    
    return CG.client_controller.Read( 'file_crops_for_files', list( hashes ), location_context )
    

def GetCropRectInImage( overlay_rect: Rect, media_rect: Rect, image_size: tuple[ int, int ] ) -> Rect | None:
    
    # the overlay's box and where the file is shown, in the media viewer's coordinates, to the part of the image, as it is shown, under the box
    # just the part of the box that is over the file counts. None if none of it is
    ( overlay_x, overlay_y, overlay_width, overlay_height ) = overlay_rect
    ( media_x, media_y, media_width, media_height ) = media_rect
    ( image_width, image_height ) = image_size
    
    if media_width <= 0 or media_height <= 0 or image_width <= 0 or image_height <= 0:
        
        return None
        
    
    left = max( overlay_x, media_x )
    top = max( overlay_y, media_y )
    right = min( overlay_x + overlay_width, media_x + media_width )
    bottom = min( overlay_y + overlay_height, media_y + media_height )
    
    if right <= left or bottom <= top:
        
        return None
        
    
    x_scale = image_width / media_width
    y_scale = image_height / media_height
    
    x0 = max( 0, min( image_width, round( ( left - media_x ) * x_scale ) ) )
    y0 = max( 0, min( image_height, round( ( top - media_y ) * y_scale ) ) )
    x1 = max( 0, min( image_width, round( ( right - media_x ) * x_scale ) ) )
    y1 = max( 0, min( image_height, round( ( bottom - media_y ) * y_scale ) ) )
    
    if x1 - x0 < 1 or y1 - y0 < 1:
        
        return None
        
    
    return ( x0, y0, x1 - x0, y1 - y0 )
    

def RotatePILImageAsShown( pil_image: PILImage.Image, rotation: int ) -> PILImage.Image:
    
    # the media viewer turns files clockwise, and PIL turns them anticlockwise
    rotation = int( round( rotation ) ) % 360
    
    if rotation == 0:
        
        return pil_image
        
    
    transposes = {
        90 : PILImage.Transpose.ROTATE_270,
        180 : PILImage.Transpose.ROTATE_180,
        270 : PILImage.Transpose.ROTATE_90
    }
    
    if rotation in transposes:
        
        # exact, no smoothing
        return pil_image.transpose( transposes[ rotation ] )
        
    
    # the corners it leaves are see-through
    if pil_image.mode != 'RGBA':
        
        pil_image = pil_image.convert( 'RGBA' )
        
    
    return pil_image.rotate( - rotation, resample = PILImage.Resampling.BICUBIC, expand = True )
    

def CropPILImage( pil_image: PILImage.Image, rotation: int, overlay_rect: Rect, media_rect: Rect ) -> PILImage.Image:
    
    # the part of the image under the overlay, as it is shown, so turned if the media viewer turns it
    shown_image = RotatePILImageAsShown( pil_image, rotation )
    
    crop_rect = GetCropRectInImage( overlay_rect, media_rect, shown_image.size )
    
    if crop_rect is None:
        
        raise HydrusExceptions.VetoException( 'The overlay is not over the file, so there is nothing to crop!' )
        
    
    ( x, y, width, height ) = crop_rect
    
    return shown_image.crop( ( x, y, x + width, y + height ) )
    

def SavePILImageAsPNG( pil_image: PILImage.Image, path: str ):
    
    # png does not do every mode PIL does
    if pil_image.mode not in ( 'RGB', 'RGBA', 'L', 'LA' ):
        
        pil_image = pil_image.convert( 'RGBA' )
        
    
    pil_image.save( path, 'PNG' )
    

def LoadImageForCrop( path: str ) -> PILImage.Image:
    
    return HydrusImageHandling.GeneratePILImage( path, human_file_description = 'file to crop' )
    

def CropRectFromImageFile( source_path: str, crop_rect: Rect, dest_path: str ):
    
    # the part of an image file, in its own pixels, for the Client API
    pil_image = LoadImageForCrop( source_path )
    
    ( image_width, image_height ) = pil_image.size
    
    ( x, y, width, height ) = crop_rect
    
    if width < 1 or height < 1 or x < 0 or y < 0 or x + width > image_width or y + height > image_height:
        
        raise HydrusExceptions.VetoException( f'The crop {crop_rect} does not fit in the image, which is {image_width}x{image_height}!' )
        
    
    SavePILImageAsPNG( pil_image.crop( ( x, y, x + width, y + height ) ), dest_path )
    

def ImportCrop( path: str, hash: bytes, timestamp_ms: int | None ) -> bytes:
    
    # quietly, with no popups. this does db work, so it wants to be in a worker thread
    service_key = GetCropsServiceKey()
    
    crop_hash = ClientSnapshots.ImportFileToOwnLocalFileDomain( path, service_key, 'crop' )
    
    CG.client_controller.WriteSynchronous( 'file_crop_add', hash, crop_hash, timestamp_ms )
    
    return crop_hash
    
