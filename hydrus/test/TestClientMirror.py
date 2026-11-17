import unittest

from unittest import mock

from qtpy import QtCore as QC
from qtpy import QtGui as QG

from hydrus.client import ClientGlobals as CG
from hydrus.client.gui.canvas import ClientGUICanvasMedia
from hydrus.client.gui.canvas import ClientGUIMPV

POINTS = [ QC.QPointF( 3, 1 ), QC.QPointF( -2, 5 ), QC.QPointF( 0, -4 ) ]

def GetScreenTransform( rotation, mirror_horizontal, mirror_vertical ) -> QG.QTransform:
    
    # turned, and then mirrored as you see it
    transform = QG.QTransform()
    
    transform.scale( -1 if mirror_horizontal else 1, -1 if mirror_vertical else 1 )
    transform.rotate( rotation )
    
    return transform
    

def GetPlayerTransform( rotation, flip_horizontal, flip_vertical ) -> QG.QTransform:
    
    # mpv: flipped, and then turned
    transform = QG.QTransform()
    
    transform.rotate( rotation )
    transform.scale( -1 if flip_horizontal else 1, -1 if flip_vertical else 1 )
    
    return transform
    

def TransformsMatch( a: QG.QTransform, b: QG.QTransform ):
    
    for point in POINTS:
        
        ( pa, pb ) = ( a.map( point ), b.map( point ) )
        
        if abs( pa.x() - pb.x() ) > 1e-6 or abs( pa.y() - pb.y() ) > 1e-6:
            
            return False
            
        
    
    return True
    

class TestMirror( unittest.TestCase ):
    
    def test_player_rotation_and_flips( self ):
        
        self.assertEqual( ClientGUIMPV.GetPlayerRotationAndFlips( 90, False, False ), ( 90, False, False ) )
        self.assertEqual( ClientGUIMPV.GetPlayerRotationAndFlips( 90, True, False ), ( 270, True, False ) )
        self.assertEqual( ClientGUIMPV.GetPlayerRotationAndFlips( 90, False, True ), ( 270, False, True ) )
        self.assertEqual( ClientGUIMPV.GetPlayerRotationAndFlips( 90, True, True ), ( 270, False, False ) )
        self.assertEqual( ClientGUIMPV.GetPlayerRotationAndFlips( 0, True, False ), ( 0, True, False ) )
        self.assertEqual( ClientGUIMPV.GetPlayerRotationAndFlips( 0, True, True ), ( 180, False, False ) )
        
        # whatever the turn, mpv's flip-then-turn looks the same as our turn-then-mirror
        for rotation in ( 0, 30, 90, 135, 180, 270, 359 ):
            
            for mirror_horizontal in ( False, True ):
                
                for mirror_vertical in ( False, True ):
                    
                    ( player_rotation, flip_horizontal, flip_vertical ) = ClientGUIMPV.GetPlayerRotationAndFlips( rotation, mirror_horizontal, mirror_vertical )
                    
                    # it never needs both flips
                    self.assertFalse( flip_horizontal and flip_vertical )
                    
                    screen_transform = GetScreenTransform( rotation, mirror_horizontal, mirror_vertical )
                    player_transform = GetPlayerTransform( player_rotation, flip_horizontal, flip_vertical )
                    
                    self.assertTrue( TransformsMatch( screen_transform, player_transform ), ( rotation, mirror_horizontal, mirror_vertical ) )
                    
                
            
        
    
    def test_mpv_filter_args( self ):
        
        self.assertEqual( ClientGUIMPV.ConvertMirrorToMPVVFArgs( True, False ), ( 'add', '@hydrusmirror:hflip' ) )
        self.assertEqual( ClientGUIMPV.ConvertMirrorToMPVVFArgs( False, True ), ( 'add', '@hydrusmirror:vflip' ) )
        self.assertEqual( ClientGUIMPV.ConvertMirrorToMPVVFArgs( False, False ), ( 'remove', '@hydrusmirror' ) )
        
    
    def test_painter( self ):
        
        # the painter turns and then mirrors, about the middle
        image = QG.QImage( 20, 10, QG.QImage.Format.Format_ARGB32 )
        
        painter = QG.QPainter( image )
        
        try:
            
            ClientGUICanvasMedia.TransformPainterForOrientation( painter, 10, 5, 90, True, False )
            
            expected = GetScreenTransform( 90, True, False )
            
            expected = expected * QG.QTransform.fromTranslate( 10, 5 )
            
            self.assertTrue( TransformsMatch( painter.transform(), expected ) )
            
        finally:
            
            painter.end()
            
        
    
    def test_pretty_string( self ):
        
        self.assertEqual( ClientGUICanvasMedia.ConvertOrientationToPrettyString( 0, False, False ), ClientGUICanvasMedia.ConvertRotationToPrettyString( 0 ) )
        self.assertTrue( ClientGUICanvasMedia.ConvertOrientationToPrettyString( 90, True, False ).endswith( ', mirrored horizontally' ) )
        self.assertTrue( ClientGUICanvasMedia.ConvertOrientationToPrettyString( 90, False, True ).endswith( ', mirrored vertically' ) )
        self.assertTrue( ClientGUICanvasMedia.ConvertOrientationToPrettyString( 0, True, True ).endswith( ', mirrored both ways' ) )
        
    
    def _GetContainer( self ):
        
        container = ClientGUICanvasMedia.MediaContainer.__new__( ClientGUICanvasMedia.MediaContainer )
        
        container._media = mock.Mock()
        container._media.GetHash.return_value = b'\x01' * 32
        
        container._mirror_horizontal = False
        container._mirror_vertical = False
        container._mirror_load_id = 0
        
        container._media_window = mock.Mock( spec = ClientGUICanvasMedia.StaticImage )
        
        patches = [
            mock.patch.object( container, 'CanRotate', return_value = True ),
            mock.patch.object( container, 'update' ),
            mock.patch.object( CG.client_controller, 'Write' )
        ]
        
        for patch in patches:
            
            patch.start()
            
            self.addCleanup( patch.stop )
            
        
        return container
        
    
    def test_media_container( self ):
        
        container = self._GetContainer()
        
        container.SetMirrorHorizontal( True )
        
        self.assertEqual( container.GetMirror(), ( True, False ) )
        
        container._media_window.SetMirror.assert_called_with( True, False )
        
        # saved for next time
        CG.client_controller.Write.assert_called_with( 'file_viewer_mirror', b'\x01' * 32, True, False )
        
        # the other way keeps this way
        container.SetMirrorVertical( True )
        
        self.assertEqual( container.GetMirror(), ( True, True ) )
        
        CG.client_controller.Write.assert_called_with( 'file_viewer_mirror', b'\x01' * 32, True, True )
        
        container.SetMirror( False, False )
        
        self.assertEqual( container.GetMirror(), ( False, False ) )
        
        container._media_window.SetMirror.assert_called_with( False, False )
        
        # anything still loading is out of date
        self.assertEqual( container._mirror_load_id, 3 )
        
        # something that cannot be turned cannot be mirrored either
        with mock.patch.object( container, 'CanRotate', return_value = False ):
            
            container.SetMirrorHorizontal( True )
            
        
        self.assertEqual( container.GetMirror(), ( False, False ) )
        
    
    def test_mpv_widget( self ):
        
        widget = ClientGUIMPV.MPVWidget.__new__( ClientGUIMPV.MPVWidget )
        
        widget._currently_in_media_load_error_state = False
        widget._rotation = 0
        widget._mirror_horizontal = False
        widget._mirror_vertical = False
        widget._player_orientation = ( 0, False, False )
        widget._mpv_mediator = mock.Mock()
        
        widget.SetRotation( 90 )
        
        widget._mpv_mediator.SetVideoRotation.assert_called_once_with( 90 )
        widget._mpv_mediator.SetVideoFlip.assert_not_called()
        
        # one mirror turns it the other way, and flips it
        widget.SetMirror( True, False )
        
        widget._mpv_mediator.SetVideoRotation.assert_called_with( 270 )
        widget._mpv_mediator.SetVideoFlip.assert_called_once_with( True, False )
        
        # both is a half turn, with no flip
        widget.SetMirror( True, True )
        
        widget._mpv_mediator.SetVideoFlip.assert_called_with( False, False )
        self.assertEqual( widget._player_orientation, ( 270, False, False ) )
        
        # nothing changes, so nothing is sent
        widget._mpv_mediator.reset_mock()
        
        widget.SetMirror( True, True )
        
        widget._mpv_mediator.SetVideoRotation.assert_not_called()
        widget._mpv_mediator.SetVideoFlip.assert_not_called()
        
        widget.SetMirror( False, False )
        
        widget._mpv_mediator.SetVideoRotation.assert_called_once_with( 90 )
        widget._mpv_mediator.SetVideoFlip.assert_not_called()
        
        
        
