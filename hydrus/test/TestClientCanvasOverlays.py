import unittest

from qtpy import QtCore as QC
from qtpy import QtGui as QG
from qtpy import QtWidgets as QW

from hydrus.client.gui.canvas import ClientGUICanvasOverlays as O

from hydrus.test import TestGlobals as TG

def MouseEvent( event_type, local_position: QC.QPoint, global_position: QC.QPoint, button = QC.Qt.MouseButton.LeftButton ):
    
    buttons = QC.Qt.MouseButton.NoButton if event_type == QC.QEvent.Type.MouseButtonRelease else button
    
    return QG.QMouseEvent( event_type, QC.QPointF( local_position ), QC.QPointF( global_position ), button, buttons, QC.Qt.KeyboardModifier.NoModifier )
    

class TestCanvasOverlays( unittest.TestCase ):
    
    def test_drag_edges( self ):
        
        # the middle moves it
        self.assertEqual( O.GetOverlayDragEdges( 100, 100, 200, 200 ), ( False, False, False, False ) )
        
        # near an edge grabs that edge, and a corner grabs two
        self.assertEqual( O.GetOverlayDragEdges( 2, 100, 200, 200 ), ( True, False, False, False ) )
        self.assertEqual( O.GetOverlayDragEdges( 199, 199, 200, 200 ), ( False, False, True, True ) )
        self.assertEqual( O.GetOverlayDragEdges( 2, 2, 200, 200 ), ( True, True, False, False ) )
        
        # a small one still has a middle
        self.assertEqual( O.GetOverlayDragEdges( 10, 10, 20, 20 ), ( False, False, False, False ) )
        self.assertEqual( O.GetOverlayDragEdges( 0, 10, 20, 20 ), ( True, False, False, False ) )
        
        self.assertEqual( O.GetOverlayCursorShape( ( False, False, False, False ) ), QC.Qt.CursorShape.SizeAllCursor )
        self.assertEqual( O.GetOverlayCursorShape( ( True, True, False, False ) ), QC.Qt.CursorShape.SizeFDiagCursor )
        self.assertEqual( O.GetOverlayCursorShape( ( False, True, True, False ) ), QC.Qt.CursorShape.SizeBDiagCursor )
        self.assertEqual( O.GetOverlayCursorShape( ( False, False, False, True ) ), QC.Qt.CursorShape.SizeVerCursor )
        
    
    def test_drag_maths( self ):
        
        bounds = ( 1000, 800 )
        move = ( False, False, False, False )
        
        # moving
        self.assertEqual( O.ApplyOverlayDrag( ( 100, 100, 200, 100 ), move, 50, -20, bounds ), ( 150, 80, 200, 100 ) )
        
        # it stays inside
        self.assertEqual( O.ApplyOverlayDrag( ( 100, 100, 200, 100 ), move, -500, 5000, bounds ), ( 0, 700, 200, 100 ) )
        
        # the bottom right corner resizes
        self.assertEqual( O.ApplyOverlayDrag( ( 100, 100, 200, 100 ), ( False, False, True, True ), 50, 30, bounds ), ( 100, 100, 250, 130 ) )
        
        # the left edge moves the left side and leaves the right where it is
        self.assertEqual( O.ApplyOverlayDrag( ( 100, 100, 200, 100 ), ( True, False, False, False ), 60, 999, bounds ), ( 160, 100, 140, 100 ) )
        
        # it can't go smaller than the minimum, or turn inside out
        self.assertEqual( O.ApplyOverlayDrag( ( 100, 100, 200, 100 ), ( True, False, False, False ), 1000, 0, bounds ), ( 300 - O.OVERLAY_MIN_SIZE, 100, O.OVERLAY_MIN_SIZE, 100 ) )
        self.assertEqual( O.ApplyOverlayDrag( ( 100, 100, 200, 100 ), ( False, False, False, True ), 0, -1000, bounds ), ( 100, 100, 200, O.OVERLAY_MIN_SIZE ) )
        
        # or bigger than the media viewer
        self.assertEqual( O.ApplyOverlayDrag( ( 100, 100, 200, 100 ), ( True, True, True, True ), 0, 0, bounds ), ( 100, 100, 200, 100 ) )
        self.assertEqual( O.ApplyOverlayDrag( ( 100, 100, 200, 100 ), ( False, True, True, False ), 5000, -5000, bounds ), ( 100, 0, 900, 200 ) )
        
    
    def test_fractions( self ):
        
        bounds = ( 1000, 800 )
        
        fractions = O.ConvertRectToFractions( ( 250, 200, 500, 400 ), bounds )
        
        self.assertEqual( fractions, ( 0.25, 0.25, 0.5, 0.5 ) )
        
        self.assertEqual( O.ConvertFractionsToRect( fractions, bounds ), ( 250, 200, 500, 400 ) )
        
        # it follows a resize
        self.assertEqual( O.ConvertFractionsToRect( fractions, ( 500, 400 ) ), ( 125, 100, 250, 200 ) )
        
        # new ones step down and right, and wrap round
        self.assertEqual( O.GetNewOverlayFractions( 0 ), O.OVERLAY_DEFAULT_FRACTIONS )
        self.assertGreater( O.GetNewOverlayFractions( 1 )[0], O.GetNewOverlayFractions( 0 )[0] )
        self.assertEqual( O.GetNewOverlayFractions( 6 ), O.OVERLAY_DEFAULT_FRACTIONS )
        
        for i in range( 6 ):
            
            ( fx, fy, fwidth, fheight ) = O.GetNewOverlayFractions( i )
            
            self.assertLessEqual( fx + fwidth, 1.0 )
            self.assertLessEqual( fy + fheight, 1.0 )
            
        
    
    def test_colour_panel( self ):
        
        dialog = QW.QDialog()
        
        panel = O.EditOverlayColourPanel( dialog, QG.QColor( 255, 0, 0, 128 ) )
        
        self.assertEqual( panel._opacity.value(), 50 )
        
        colour = panel.GetValue()
        
        self.assertEqual( ( colour.red(), colour.green(), colour.blue(), colour.alpha() ), ( 255, 0, 0, 128 ) )
        
        panel._opacity.setValue( 100 )
        
        self.assertEqual( panel.GetValue().alpha(), 255 )
        
        # never all the way see-through, or you could not find it or click it
        panel._opacity.setValue( 0 )
        
        self.assertEqual( panel._opacity.value(), O.OVERLAY_MIN_OPACITY_PERCENT )
        self.assertGreater( panel.GetValue().alpha(), 0 )
        
        dialog.deleteLater()
        
    
    def _DoOverlayWindowTest( self ):
        
        window = QW.QWidget()
        
        layout = QW.QVBoxLayout( window )
        layout.setContentsMargins( 20, 20, 20, 20 )
        
        canvas = QW.QWidget( window )
        
        layout.addWidget( canvas )
        
        window.resize( 1040, 840 )
        window.show()
        
        QW.QApplication.processEvents()
        
        self.assertEqual( ( canvas.width(), canvas.height() ), ( 1000, 800 ) )
        
        self.assertEqual( O.GetOverlays( canvas ), [] )
        
        overlay = O.CanvasOverlay( canvas, QG.QColor( 0, 0, 0, 153 ), ( 0.25, 0.25, 0.5, 0.5 ) )
        
        overlay.ShowIfCanvasShown()
        
        QW.QApplication.processEvents()
        
        self.assertTrue( overlay.isVisible() )
        self.assertTrue( overlay.isWindow() )
        self.assertEqual( O.GetOverlays( canvas ), [ overlay ] )
        
        # it sits over its part of the canvas, in screen coordinates
        top_left = canvas.mapToGlobal( QC.QPoint( 250, 200 ) )
        
        self.assertEqual( overlay.geometry(), QC.QRect( top_left.x(), top_left.y(), 500, 400 ) )
        
        # dragging the middle moves it
        start_global = overlay.mapToGlobal( QC.QPoint( 250, 200 ) )
        
        overlay.mousePressEvent( MouseEvent( QC.QEvent.Type.MouseButtonPress, QC.QPoint( 250, 200 ), start_global ) )
        overlay.mouseMoveEvent( MouseEvent( QC.QEvent.Type.MouseMove, QC.QPoint( 350, 150 ), start_global + QC.QPoint( 100, -50 ) ) )
        overlay.mouseReleaseEvent( MouseEvent( QC.QEvent.Type.MouseButtonRelease, QC.QPoint( 350, 150 ), start_global + QC.QPoint( 100, -50 ) ) )
        
        self.assertEqual( O.ConvertFractionsToRect( overlay.GetFractions(), ( 1000, 800 ) ), ( 350, 150, 500, 400 ) )
        
        top_left = canvas.mapToGlobal( QC.QPoint( 350, 150 ) )
        
        self.assertEqual( overlay.geometry(), QC.QRect( top_left.x(), top_left.y(), 500, 400 ) )
        
        # dragging the bottom right corner resizes it
        start_global = overlay.mapToGlobal( QC.QPoint( 499, 399 ) )
        
        overlay.mousePressEvent( MouseEvent( QC.QEvent.Type.MouseButtonPress, QC.QPoint( 499, 399 ), start_global ) )
        overlay.mouseMoveEvent( MouseEvent( QC.QEvent.Type.MouseMove, QC.QPoint( 399, 299 ), start_global + QC.QPoint( -100, -100 ) ) )
        overlay.mouseReleaseEvent( MouseEvent( QC.QEvent.Type.MouseButtonRelease, QC.QPoint( 399, 299 ), start_global + QC.QPoint( -100, -100 ) ) )
        
        self.assertEqual( O.ConvertFractionsToRect( overlay.GetFractions(), ( 1000, 800 ) ), ( 350, 150, 400, 300 ) )
        
        # it follows the canvas when the window is resized
        window.resize( 540, 440 )
        
        QW.QApplication.processEvents()
        
        top_left = canvas.mapToGlobal( QC.QPoint( 175, 75 ) )
        
        self.assertEqual( overlay.geometry(), QC.QRect( top_left.x(), top_left.y(), 200, 150 ) )
        
        # and hides with it
        canvas.hide()
        
        QW.QApplication.processEvents()
        
        self.assertFalse( overlay.isVisible() )
        
        canvas.show()
        
        QW.QApplication.processEvents()
        
        self.assertTrue( overlay.isVisible() )
        
        # colour
        overlay.SetColour( QG.QColor( 255, 255, 255, 64 ) )
        
        self.assertEqual( overlay.GetColour().alpha(), 64 )
        
        # the menu
        menu = QW.QMenu( window )
        
        overlays_menu = O.AppendOverlaysMenu( menu, canvas )
        
        self.assertEqual( menu.actions()[-1].text(), 'overlays (1)' )
        self.assertTrue( overlays_menu.actions()[1].isEnabled() )
        
        # a second one, and removing them all
        second_overlay = O.CanvasOverlay( canvas, QG.QColor( 0, 0, 0, 153 ), O.GetNewOverlayFractions( 1 ) )
        
        self.assertEqual( len( O.GetOverlays( canvas ) ), 2 )
        
        overlays_menu.actions()[1].trigger()
        
        self.assertTrue( overlay.IsRemoved() )
        self.assertTrue( second_overlay.IsRemoved() )
        self.assertEqual( O.GetOverlays( canvas ), [] )
        self.assertFalse( overlay.isVisible() )
        
        menu = QW.QMenu( window )
        
        overlays_menu = O.AppendOverlaysMenu( menu, canvas )
        
        self.assertEqual( menu.actions()[-1].text(), 'overlays' )
        self.assertFalse( overlays_menu.actions()[1].isEnabled() )
        
        window.close()
        window.deleteLater()
        
    
    def test_overlay_window( self ):
        
        # showing windows and processing their events has to happen in the Qt thread
        TG.test_controller.CallBlockingToQtTLW( self._DoOverlayWindowTest )
        
    
