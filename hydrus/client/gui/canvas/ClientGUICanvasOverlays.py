import os

from qtpy import QtCore as QC
from qtpy import QtGui as QG
from qtpy import QtWidgets as QW

from hydrus.core import HydrusConstants as HC
from hydrus.core import HydrusExceptions

from hydrus.client import ClientConstants as CC
from hydrus.client import ClientGlobals as CG
from hydrus.client.gui import ClientGUIAsync
from hydrus.client.gui import ClientGUIMenus
from hydrus.client.gui import ClientGUITopLevelWindowsPanels
from hydrus.client.gui import QtPorting as QP
from hydrus.client.gui.panels import ClientGUIScrolledPanels
from hydrus.client.gui.widgets import ClientGUIColourPicker
from hydrus.client.gui.widgets import ClientGUICommon
from hydrus.client.gui.widgets import ClientGUIPathWidgets

# an overlay is a see-through coloured box that sits on top of everything in the media viewer, to dim or hide part of it
# it is a window of its own, owned by the media viewer, since a see-through widget inside the media viewer cannot show mpv's video through it
# an image overlay is the same sort of window, but it draws a picture from your disk. each file can have one, which comes up whenever the file is shown

# ( x, y, width, height )
Rect = tuple[ int, int, int, int ]
# the same, as fractions of the media viewer's size, so an overlay follows the window when it is resized
RectFractions = tuple[ float, float, float, float ]

# ( left, top, right, bottom ). all False is a move
DragEdges = tuple[ bool, bool, bool, bool ]

OVERLAY_EDGE_MARGIN = 8
OVERLAY_MIN_SIZE = 16

OVERLAY_DEFAULT_FRACTIONS = ( 0.25, 0.25, 0.5, 0.5 )

# each new overlay goes a bit down and right of the last, so they don't sit exactly on top of each other
OVERLAY_NEW_OFFSET = 0.04

OVERLAY_MIN_OPACITY_PERCENT = 5

# the colour the next new overlay starts at, this session
LAST_OVERLAY_COLOUR = QG.QColor( 0, 0, 0, 153 )

# ( path, opacity, fractions, locked, stretch ). opacity is 0-1. a locked one lets clicks through to the media viewer, and a stretched one fills its box rather than keeping the image's shape
ImageOverlay = tuple[ str, float, RectFractions, bool, bool ]

IMAGE_OVERLAY_DEFAULT_OPACITY = 1.0
IMAGE_OVERLAY_FILL_FRACTIONS = ( 0.0, 0.0, 1.0, 1.0 )

IMAGE_OVERLAY_WILDCARD = 'images (*.png *.jpg *.jpeg *.gif *.webp *.bmp *.tif *.tiff);;all files (*)'

# where the last image overlay came from, this session, so the next one starts there
LAST_IMAGE_OVERLAY_DIR = None

def GetImageOverlayTargetRect( image_size: tuple[ int, int ], box_size: tuple[ int, int ], stretch: bool ) -> Rect:
    
    # where in its box an image overlay draws its image. it keeps its shape, as big as fits and centered, unless it is stretched to fill the box
    ( box_width, box_height ) = box_size
    
    if stretch:
        
        return ( 0, 0, box_width, box_height )
        
    
    ( image_width, image_height ) = image_size
    
    if image_width <= 0 or image_height <= 0 or box_width <= 0 or box_height <= 0:
        
        return ( 0, 0, box_width, box_height )
        
    
    scale = min( box_width / image_width, box_height / image_height )
    
    width = max( 1, round( image_width * scale ) )
    height = max( 1, round( image_height * scale ) )
    
    return ( ( box_width - width ) // 2, ( box_height - height ) // 2, width, height )
    

def ApplyOverlayDrag( start_rect: Rect, edges: DragEdges, dx: int, dy: int, bounds: tuple[ int, int ], min_size: int = OVERLAY_MIN_SIZE ) -> Rect:
    
    # where a drag that started at start_rect ends up. it stays inside the media viewer
    ( x, y, width, height ) = start_rect
    ( bounds_width, bounds_height ) = bounds
    
    ( left_edge, top_edge, right_edge, bottom_edge ) = edges
    
    if not any( edges ):
        
        x = max( 0, min( x + dx, bounds_width - width ) )
        y = max( 0, min( y + dy, bounds_height - height ) )
        
        return ( x, y, width, height )
        
    
    left = x
    top = y
    right = x + width
    bottom = y + height
    
    if left_edge:
        
        left = max( 0, min( left + dx, right - min_size ) )
        
    
    if right_edge:
        
        right = min( bounds_width, max( right + dx, left + min_size ) )
        
    
    if top_edge:
        
        top = max( 0, min( top + dy, bottom - min_size ) )
        
    
    if bottom_edge:
        
        bottom = min( bounds_height, max( bottom + dy, top + min_size ) )
        
    
    return ( left, top, right - left, bottom - top )
    

def ConvertFractionsToRect( fractions: RectFractions, bounds: tuple[ int, int ] ) -> Rect:
    
    ( fx, fy, fwidth, fheight ) = fractions
    ( bounds_width, bounds_height ) = bounds
    
    return ( round( fx * bounds_width ), round( fy * bounds_height ), max( 1, round( fwidth * bounds_width ) ), max( 1, round( fheight * bounds_height ) ) )
    

def ConvertRectToFractions( rect: Rect, bounds: tuple[ int, int ] ) -> RectFractions:
    
    ( x, y, width, height ) = rect
    ( bounds_width, bounds_height ) = bounds
    
    bounds_width = max( 1, bounds_width )
    bounds_height = max( 1, bounds_height )
    
    return ( x / bounds_width, y / bounds_height, width / bounds_width, height / bounds_height )
    

def GetNewOverlayFractions( num_existing_overlays: int ) -> RectFractions:
    
    ( fx, fy, fwidth, fheight ) = OVERLAY_DEFAULT_FRACTIONS
    
    # it wraps round after a few, so it never goes off the edge
    offset = OVERLAY_NEW_OFFSET * ( num_existing_overlays % 6 )
    
    return ( fx + offset, fy + offset, fwidth, fheight )
    

def GetOverlayDragEdges( x: int, y: int, width: int, height: int, margin: int = OVERLAY_EDGE_MARGIN ) -> DragEdges:
    
    # which edges a press at ( x, y ) in an overlay grabs. in the middle, it grabs the whole thing
    # a small overlay gets a smaller margin, so there is always some middle to move it by
    margin_x = max( 1, min( margin, width // 4 ) )
    margin_y = max( 1, min( margin, height // 4 ) )
    
    return ( x < margin_x, y < margin_y, x >= width - margin_x, y >= height - margin_y )
    

def GetOverlayCursorShape( edges: DragEdges ) -> QC.Qt.CursorShape:
    
    ( left, top, right, bottom ) = edges
    
    if ( left and top ) or ( right and bottom ):
        
        return QC.Qt.CursorShape.SizeFDiagCursor
        
    elif ( right and top ) or ( left and bottom ):
        
        return QC.Qt.CursorShape.SizeBDiagCursor
        
    elif left or right:
        
        return QC.Qt.CursorShape.SizeHorCursor
        
    elif top or bottom:
        
        return QC.Qt.CursorShape.SizeVerCursor
        
    
    return QC.Qt.CursorShape.SizeAllCursor
    

def AddOverlay( canvas: QW.QWidget ):
    
    global LAST_OVERLAY_COLOUR
    
    try:
        
        colour = EditOverlayColour( canvas, LAST_OVERLAY_COLOUR )
        
    except HydrusExceptions.CancelledException:
        
        return
        
    
    LAST_OVERLAY_COLOUR = QG.QColor( colour )
    
    overlay = CanvasOverlay( canvas, colour, GetNewOverlayFractions( len( GetOverlays( canvas ) ) ) )
    
    overlay.ShowIfCanvasShown()
    

def AppendOverlaysMenu( menu: QW.QMenu, canvas: QW.QWidget, image_overlay_manager: 'CanvasImageOverlayManager | None' = None ):
    
    num_overlays = len( GetOverlays( canvas ) )
    
    overlays_menu = ClientGUIMenus.GenerateMenu( menu )
    
    ClientGUIMenus.AppendMenuItem( overlays_menu, 'add' + HC.UNICODE_ELLIPSIS, 'Put a see-through coloured box on top of the media viewer, to dim or hide part of what is shown. Drag it to move it, drag its edges to resize it, and right-click it to change its colour or remove it.', AddOverlay, canvas )
    
    remove_all_item = ClientGUIMenus.AppendMenuItem( overlays_menu, 'remove all', 'Remove all the overlays on this media viewer.', RemoveAllOverlays, canvas )
    
    remove_all_item.setEnabled( num_overlays > 0 )
    
    label = f'overlays ({num_overlays})' if num_overlays > 0 else 'overlays'
    
    if image_overlay_manager is not None and image_overlay_manager.HasMedia():
        
        ClientGUIMenus.AppendSeparator( overlays_menu )
        
        AppendImageOverlayMenuItems( overlays_menu, image_overlay_manager )
        
        if image_overlay_manager.GetImageOverlay() is not None:
            
            label += ' (and an image)'
            
        
    
    ClientGUIMenus.AppendMenu( menu, overlays_menu, label )
    
    return overlays_menu
    

def AppendImageOverlayMenuItems( menu: QW.QMenu, image_overlay_manager: 'CanvasImageOverlayManager' ):
    
    image_overlay = image_overlay_manager.GetImageOverlay()
    
    if image_overlay is None:
        
        ClientGUIMenus.AppendMenuItem( menu, 'set image for this file' + HC.UNICODE_ELLIPSIS, 'Pick an image on your disk to draw over the media viewer whenever this file is shown. A see-through background stays see-through, and you can set how see-through the rest is.', image_overlay_manager.EditImageOverlay )
        
        return
        
    
    ( path, opacity, fractions, locked, stretch ) = image_overlay
    
    ClientGUIMenus.AppendMenuItem( menu, 'change this file\'s image' + HC.UNICODE_ELLIPSIS, f'Change the image drawn over this file, or how see-through it is. It is now {os.path.basename( path )} at {round( opacity * 100 )}%.', image_overlay_manager.EditImageOverlay )
    ClientGUIMenus.AppendMenuItem( menu, 'fill the media viewer with the image', 'Make the image\'s box the whole media viewer.', image_overlay_manager.FillMediaViewer )
    ClientGUIMenus.AppendMenuCheckItem( menu, 'lock the image in place', 'When locked, clicks go through the image to the media viewer, so you can drag and right-click the file under it. Unlock it here to move or resize it again.', locked, image_overlay_manager.FlipLocked )
    ClientGUIMenus.AppendMenuCheckItem( menu, 'stretch the image to fill its box', 'Stretch the image to fill its box, rather than keeping its shape.', stretch, image_overlay_manager.FlipStretch )
    ClientGUIMenus.AppendMenuItem( menu, 'remove this file\'s image', 'Take the image off, and forget it for this file.', image_overlay_manager.RemoveImageOverlay )
    

def EditOverlayColour( win: QW.QWidget, colour: QG.QColor ) -> QG.QColor:
    
    # raises CancelledException if the user backs out
    with ClientGUITopLevelWindowsPanels.DialogEdit( win, 'overlay colour' ) as dlg:
        
        panel = EditOverlayColourPanel( dlg, colour )
        
        dlg.SetPanel( panel )
        
        if dlg.exec() == QW.QDialog.DialogCode.Accepted:
            
            return panel.GetValue()
            
        
        raise HydrusExceptions.CancelledException( 'Dialog cancelled.' )
        
    

def EditImageOverlay( win: QW.QWidget, image_overlay: ImageOverlay | None ) -> ImageOverlay:
    
    # raises CancelledException if the user backs out. a new one starts in the middle of the media viewer, like a box overlay
    global LAST_IMAGE_OVERLAY_DIR
    
    if image_overlay is None:
        
        image_overlay = ( '', IMAGE_OVERLAY_DEFAULT_OPACITY, OVERLAY_DEFAULT_FRACTIONS, False, False )
        
    
    with ClientGUITopLevelWindowsPanels.DialogEdit( win, 'image overlay' ) as dlg:
        
        panel = EditImageOverlayPanel( dlg, image_overlay )
        
        dlg.SetPanel( panel )
        
        if dlg.exec() == QW.QDialog.DialogCode.Accepted:
            
            image_overlay = panel.GetValue()
            
            LAST_IMAGE_OVERLAY_DIR = os.path.dirname( image_overlay[0] )
            
            return image_overlay
            
        
        raise HydrusExceptions.CancelledException( 'Dialog cancelled.' )
        
    

def GetOverlays( canvas: QW.QWidget ) -> list[ 'CanvasOverlay' ]:
    
    # the coloured boxes. an image overlay belongs to its file, and is looked after on its own
    return [ overlay for overlay in canvas.window().findChildren( CanvasOverlay ) if overlay.GetCanvas() is canvas and not overlay.IsRemoved() and not isinstance( overlay, CanvasImageOverlay ) ]
    

def RemoveAllOverlays( canvas: QW.QWidget ):
    
    for overlay in GetOverlays( canvas ):
        
        overlay.Remove()
        
    

class EditOverlayColourPanel( ClientGUIScrolledPanels.EditPanel ):
    
    def __init__( self, parent: QW.QWidget, colour: QG.QColor ):
        
        super().__init__( parent )
        
        help_text = 'The overlay is filled with this colour. The more opaque it is, the less you can see through it: black at 60% dims what is under it, and at 100% hides it.'
        
        st = ClientGUICommon.BetterStaticText( self, label = help_text )
        st.setWordWrap( True )
        
        self._colour = ClientGUIColourPicker.ColourPickerButton( self )
        
        self._opacity = ClientGUICommon.BetterSpinBox( self, min = OVERLAY_MIN_OPACITY_PERCENT, max = 100 )
        self._opacity.setSuffix( '%' )
        self._opacity.setToolTip( 'How much it covers. A little bit is always there, so you can still see it and grab it.' )
        
        #
        
        self._colour.SetColour( QG.QColor( colour.red(), colour.green(), colour.blue() ) )
        self._opacity.setValue( round( colour.alpha() * 100 / 255 ) )
        
        #
        
        rows = []
        
        rows.append( ( 'colour: ', self._colour ) )
        rows.append( ( 'opacity: ', self._opacity ) )
        
        gridbox = ClientGUICommon.WrapInGrid( self, rows )
        
        vbox = QP.VBoxLayout()
        
        QP.AddToLayout( vbox, st, CC.FLAGS_EXPAND_PERPENDICULAR )
        QP.AddToLayout( vbox, gridbox, CC.FLAGS_EXPAND_PERPENDICULAR )
        vbox.addStretch( 0 )
        
        self.widget().setLayout( vbox )
        
        self.setFocusProxy( self._opacity )
        
    
    def GetValue( self ) -> QG.QColor:
        
        colour = QG.QColor( self._colour.GetColour() )
        
        colour.setAlpha( round( self._opacity.value() * 255 / 100 ) )
        
        return colour
        
    

class EditImageOverlayPanel( ClientGUIScrolledPanels.EditPanel ):
    
    def __init__( self, parent: QW.QWidget, image_overlay: ImageOverlay ):
        
        super().__init__( parent )
        
        ( path, opacity, fractions, locked, stretch ) = image_overlay
        
        self._fractions = fractions
        self._locked = locked
        
        help_text = 'This image is drawn over the media viewer whenever this file is shown. A see-through background, like in a png, stays see-through. Drag it to move it, drag its edges to resize it, and right-click it for more. Lock it in place from the media viewer\'s overlays menu, and clicks go through it to the file under it.'
        help_text += '\n' * 2
        help_text += 'The image stays where it is on your disk, so if you move or delete it, it is not shown any more.'
        
        st = ClientGUICommon.BetterStaticText( self, label = help_text )
        st.setWordWrap( True )
        
        starting_directory = LAST_IMAGE_OVERLAY_DIR if LAST_IMAGE_OVERLAY_DIR is not None else os.path.expanduser( '~' )
        
        self._path = ClientGUIPathWidgets.FilePickerCtrl( self, wildcard = IMAGE_OVERLAY_WILDCARD, starting_directory = starting_directory )
        
        self._opacity = ClientGUICommon.BetterSpinBox( self, min = OVERLAY_MIN_OPACITY_PERCENT, max = 100 )
        self._opacity.setSuffix( '%' )
        self._opacity.setToolTip( 'How much it covers. 100% is the image as it is, and lower lets more of the file show through.' )
        
        self._stretch = QW.QCheckBox( self )
        self._stretch.setToolTip( 'Stretch the image to fill its box, rather than keeping its shape.' )
        
        #
        
        self._path.SetPath( path )
        self._opacity.setValue( round( opacity * 100 ) )
        self._stretch.setChecked( stretch )
        
        #
        
        rows = []
        
        rows.append( ( 'image: ', self._path ) )
        rows.append( ( 'opacity: ', self._opacity ) )
        rows.append( ( 'stretch to fill its box: ', self._stretch ) )
        
        gridbox = ClientGUICommon.WrapInGrid( self, rows )
        
        vbox = QP.VBoxLayout()
        
        QP.AddToLayout( vbox, st, CC.FLAGS_EXPAND_PERPENDICULAR )
        QP.AddToLayout( vbox, gridbox, CC.FLAGS_EXPAND_PERPENDICULAR )
        vbox.addStretch( 0 )
        
        self.widget().setLayout( vbox )
        
    
    def GetValue( self ) -> ImageOverlay:
        
        path = self._path.GetPath().strip()
        
        if path == '' or not os.path.isfile( path ):
            
            raise HydrusExceptions.VetoException( 'Please pick an image file!' )
            
        
        if QG.QImageReader( path ).size().isEmpty():
            
            raise HydrusExceptions.VetoException( 'Sorry, that file does not look like an image Qt can draw!' )
            
        
        return ( path, self._opacity.value() / 100, self._fractions, self._locked, self._stretch.isChecked() )
        
    

class CanvasOverlay( QW.QWidget ):
    
    def __init__( self, canvas: QW.QWidget, colour: QG.QColor, fractions: RectFractions ):
        
        # a frameless tool window that never takes focus, so the media viewer's shortcuts keep working. it stays above the media viewer, and goes when it goes
        flags = QC.Qt.WindowType.Tool | QC.Qt.WindowType.FramelessWindowHint | QC.Qt.WindowType.WindowDoesNotAcceptFocus | QC.Qt.WindowType.NoDropShadowWindowHint
        
        super().__init__( canvas.window(), flags )
        
        self.setAttribute( QC.Qt.WidgetAttribute.WA_TranslucentBackground )
        self.setAttribute( QC.Qt.WidgetAttribute.WA_ShowWithoutActivating )
        self.setFocusPolicy( QC.Qt.FocusPolicy.NoFocus )
        self.setMouseTracking( True )
        
        self._canvas = canvas
        self._colour = QG.QColor( colour )
        self._fractions = fractions
        
        self._removed = False
        self._hovered = False
        
        # ( global press position, the rect when it was pressed, the edges being dragged )
        self._drag_start: tuple[ QC.QPoint, Rect, DragEdges ] | None = None
        
        self._canvas.installEventFilter( self )
        self._canvas.window().installEventFilter( self )
        
        self._UpdateGeometry()
        
    
    def _CanvasIsShowing( self ) -> bool:
        
        if not QP.isValid( self._canvas ):
            
            return False
            
        
        return self._canvas.isVisible() and not self._canvas.window().isMinimized()
        
    
    def _ChangeColour( self ):
        
        global LAST_OVERLAY_COLOUR
        
        try:
            
            colour = EditOverlayColour( self._canvas, self._colour )
            
        except HydrusExceptions.CancelledException:
            
            return
            
        
        LAST_OVERLAY_COLOUR = QG.QColor( colour )
        
        self.SetColour( colour )
        
    
    def _GetBounds( self ) -> tuple[ int, int ]:
        
        size = self._canvas.size()
        
        return ( size.width(), size.height() )
        
    
    def _GetRect( self ) -> Rect:
        
        return ConvertFractionsToRect( self._fractions, self._GetBounds() )
        
    
    def _UpdateGeometry( self ):
        
        if self._removed or not QP.isValid( self._canvas ):
            
            return
            
        
        ( x, y, width, height ) = self._GetRect()
        
        top_left = self._canvas.mapToGlobal( QC.QPoint( x, y ) )
        
        self.setGeometry( top_left.x(), top_left.y(), width, height )
        
    
    def contextMenuEvent( self, event ):
        
        menu = ClientGUIMenus.GenerateMenu( self )
        
        ClientGUIMenus.AppendMenuItem( menu, 'change colour' + HC.UNICODE_ELLIPSIS, 'Change this overlay\'s colour and opacity.', self._ChangeColour )
        
        ClientGUIMenus.AppendSeparator( menu )
        
        ClientGUIMenus.AppendMenuItem( menu, 'remove', 'Remove this overlay.', self.Remove )
        ClientGUIMenus.AppendMenuItem( menu, 'remove all', 'Remove all the overlays on this media viewer.', RemoveAllOverlays, self._canvas )
        
        menu.exec( event.globalPos() )
        
        ClientGUIMenus.DestroyMenu( menu )
        
    
    def enterEvent( self, event ):
        
        self._hovered = True
        
        self.update()
        
    
    def eventFilter( self, watched, event ):
        
        try:
            
            if self._removed:
                
                return False
                
            
            event_type = event.type()
            
            if event_type in ( QC.QEvent.Type.Move, QC.QEvent.Type.Resize ):
                
                self._UpdateGeometry()
                
            elif event_type in ( QC.QEvent.Type.Show, QC.QEvent.Type.Hide, QC.QEvent.Type.WindowStateChange ):
                
                self.ShowIfCanvasShown()
                
            
        except Exception:
            
            pass
            
        
        return False
        
    
    def leaveEvent( self, event ):
        
        self._hovered = False
        
        if self._drag_start is None:
            
            self.unsetCursor()
            
        
        self.update()
        
    
    def mouseMoveEvent( self, event ):
        
        if self._drag_start is None:
            
            position = event.position().toPoint()
            
            edges = GetOverlayDragEdges( position.x(), position.y(), self.width(), self.height() )
            
            self.setCursor( QG.QCursor( GetOverlayCursorShape( edges ) ) )
            
        else:
            
            ( start_global_position, start_rect, edges ) = self._drag_start
            
            delta = event.globalPosition().toPoint() - start_global_position
            
            bounds = self._GetBounds()
            
            new_rect = ApplyOverlayDrag( start_rect, edges, delta.x(), delta.y(), bounds )
            
            self._fractions = ConvertRectToFractions( new_rect, bounds )
            
            self._UpdateGeometry()
            
        
        event.accept()
        
    
    def mousePressEvent( self, event ):
        
        if event.button() == QC.Qt.MouseButton.LeftButton:
            
            position = event.position().toPoint()
            
            edges = GetOverlayDragEdges( position.x(), position.y(), self.width(), self.height() )
            
            self._drag_start = ( event.globalPosition().toPoint(), self._GetRect(), edges )
            
            self.update()
            
        
        event.accept()
        
    
    def mouseReleaseEvent( self, event ):
        
        if event.button() == QC.Qt.MouseButton.LeftButton:
            
            self._drag_start = None
            
            self.update()
            
        
        event.accept()
        
    
    def paintEvent( self, event ):
        
        painter = QG.QPainter( self )
        
        painter.fillRect( self.rect(), self._colour )
        
        if self._hovered or self._drag_start is not None:
            
            # an outline while the mouse is over it, so you can see where to grab it
            pen = QG.QPen( QG.QColor( 255, 255, 255, 160 ) )
            pen.setStyle( QC.Qt.PenStyle.DashLine )
            
            painter.setPen( pen )
            painter.setBrush( QC.Qt.BrushStyle.NoBrush )
            
            painter.drawRect( self.rect().adjusted( 0, 0, -1, -1 ) )
            
        
        painter.end()
        
    
    def wheelEvent( self, event ):
        
        event.accept()
        
    
    def GetCanvas( self ) -> QW.QWidget:
        
        return self._canvas
        
    
    def GetColour( self ) -> QG.QColor:
        
        return QG.QColor( self._colour )
        
    
    def GetFractions( self ) -> RectFractions:
        
        return self._fractions
        
    
    def IsRemoved( self ) -> bool:
        
        return self._removed
        
    
    def Remove( self ):
        
        if self._removed:
            
            return
            
        
        self._removed = True
        
        if QP.isValid( self._canvas ):
            
            self._canvas.removeEventFilter( self )
            self._canvas.window().removeEventFilter( self )
            
        
        self.hide()
        
        self.deleteLater()
        
    
    def SetColour( self, colour: QG.QColor ):
        
        self._colour = QG.QColor( colour )
        
        self.update()
        
    
    def SetFractions( self, fractions: RectFractions ):
        
        self._fractions = fractions
        
        self._UpdateGeometry()
        
    
    def ShowIfCanvasShown( self ):
        
        if self._removed:
            
            return
            
        
        if self._CanvasIsShowing():
            
            self._UpdateGeometry()
            
            if not self.isVisible():
                
                self.show()
                
            
        else:
            
            if self.isVisible():
                
                self.hide()
                
            
        
    

class CanvasImageOverlay( CanvasOverlay ):
    
    def __init__( self, canvas: QW.QWidget, image_overlay: ImageOverlay, change_callable, edit_callable ):
        
        ( path, opacity, fractions, locked, stretch ) = image_overlay
        
        super().__init__( canvas, QG.QColor( 0, 0, 0, 0 ), fractions )
        
        if locked:
            
            # clicks go through it to the media viewer. it has not been shown yet, so this is fine to set now
            self.setWindowFlag( QC.Qt.WindowType.WindowTransparentForInput, True )
            
        
        self._path = path
        self._opacity = opacity
        self._locked = locked
        self._stretch = stretch
        
        # what to call with the new value when it is dragged, and to edit it
        self._change_callable = change_callable
        self._edit_callable = edit_callable
        
        self._pixmap = QG.QPixmap( path ) if os.path.isfile( path ) else QG.QPixmap()
        
    
    def contextMenuEvent( self, event ):
        
        menu = ClientGUIMenus.GenerateMenu( self )
        
        ClientGUIMenus.AppendMenuItem( menu, 'change image' + HC.UNICODE_ELLIPSIS, 'Change the image, or how see-through it is.', self._edit_callable )
        ClientGUIMenus.AppendMenuItem( menu, 'fill the media viewer', 'Make the image\'s box the whole media viewer.', self._FillMediaViewer )
        ClientGUIMenus.AppendMenuItem( menu, 'lock in place', 'Clicks go through the image to the media viewer, so you can drag and right-click the file under it. Unlock it from the media viewer\'s overlays menu.', self._Lock )
        
        ClientGUIMenus.AppendSeparator( menu )
        
        ClientGUIMenus.AppendMenuItem( menu, 'remove', 'Take the image off, and forget it for this file.', self._change_callable, None )
        
        menu.exec( event.globalPos() )
        
        ClientGUIMenus.DestroyMenu( menu )
        
    
    def _FillMediaViewer( self ):
        
        self.SetFractions( IMAGE_OVERLAY_FILL_FRACTIONS )
        
        self._change_callable( self.GetImageOverlay() )
        
    
    def _Lock( self ):
        
        ( path, opacity, fractions, locked, stretch ) = self.GetImageOverlay()
        
        self._change_callable( ( path, opacity, fractions, True, stretch ) )
        
    
    def mouseReleaseEvent( self, event ):
        
        was_dragging = self._drag_start is not None
        
        super().mouseReleaseEvent( event )
        
        if was_dragging and self._drag_start is None:
            
            # it was moved or resized, so the file remembers where it is now
            self._change_callable( self.GetImageOverlay() )
            
        
    
    def paintEvent( self, event ):
        
        painter = QG.QPainter( self )
        
        if self._pixmap.isNull():
            
            # the image has gone, or cannot be read. a box saying so, so it is not a mystery
            pen = QG.QPen( QG.QColor( 255, 255, 255, 200 ) )
            pen.setStyle( QC.Qt.PenStyle.DashLine )
            
            painter.setPen( pen )
            painter.setBrush( QG.QColor( 0, 0, 0, 120 ) )
            
            painter.drawRect( self.rect().adjusted( 0, 0, -1, -1 ) )
            
            painter.drawText( self.rect(), QC.Qt.AlignmentFlag.AlignCenter | QC.Qt.TextFlag.TextWordWrap, f'could not load {os.path.basename( self._path )}' )
            
        else:
            
            painter.setRenderHint( QG.QPainter.RenderHint.SmoothPixmapTransform )
            
            painter.setOpacity( self._opacity )
            
            ( x, y, width, height ) = GetImageOverlayTargetRect( ( self._pixmap.width(), self._pixmap.height() ), ( self.width(), self.height() ), self._stretch )
            
            painter.drawPixmap( QC.QRect( x, y, width, height ), self._pixmap )
            
            painter.setOpacity( 1.0 )
            
        
        if not self._locked and ( self._hovered or self._drag_start is not None ):
            
            # an outline while the mouse is over it, so you can see where to grab it
            pen = QG.QPen( QG.QColor( 255, 255, 255, 160 ) )
            pen.setStyle( QC.Qt.PenStyle.DashLine )
            
            painter.setPen( pen )
            painter.setBrush( QC.Qt.BrushStyle.NoBrush )
            
            painter.drawRect( self.rect().adjusted( 0, 0, -1, -1 ) )
            
        
        painter.end()
        
    
    def GetImageOverlay( self ) -> ImageOverlay:
        
        return ( self._path, self._opacity, self._fractions, self._locked, self._stretch )
        
    
    def SetImageOverlay( self, image_overlay: ImageOverlay ):
        
        # a new opacity, box, or stretch. a new image or lock gets a new window
        ( path, opacity, fractions, locked, stretch ) = image_overlay
        
        self._opacity = opacity
        self._stretch = stretch
        
        self.SetFractions( fractions )
        
        self.update()
        
    

class CanvasImageOverlayManager( QC.QObject ):
    
    # each file can have an image drawn over it in the media viewer. this looks after the one for the file the media viewer is showing now
    
    def __init__( self, canvas: QW.QWidget ):
        
        super().__init__( canvas )
        
        self._canvas = canvas
        
        self._hash: bytes | None = None
        self._image_overlay: ImageOverlay | None = None
        self._overlay_window: CanvasImageOverlay | None = None
        
        # goes up when the file changes, so a slow load for the file before is ignored
        self._load_id = 0
        
        CG.client_controller.sub( self, 'NotifyNewImageOverlay', 'new_file_image_overlay' )
        
    
    def _ApplyImageOverlay( self, image_overlay: ImageOverlay | None ):
        
        self._image_overlay = image_overlay
        
        if self._overlay_window is not None:
            
            self._overlay_window.Remove()
            
            self._overlay_window = None
            
        
        if image_overlay is not None and self._hash is not None:
            
            self._overlay_window = CanvasImageOverlay( self._canvas, image_overlay, self.SetImageOverlay, self.EditImageOverlay )
            
            self._overlay_window.ShowIfCanvasShown()
            
        
    
    def _ChangeImageOverlay( self, **changes ):
        
        # a new value from the menu, with one thing different
        if self._image_overlay is None:
            
            return
            
        
        ( path, opacity, fractions, locked, stretch ) = self._image_overlay
        
        values = { 'path' : path, 'opacity' : opacity, 'fractions' : fractions, 'locked' : locked, 'stretch' : stretch }
        
        values.update( changes )
        
        self.SetImageOverlay( ( values[ 'path' ], values[ 'opacity' ], values[ 'fractions' ], values[ 'locked' ], values[ 'stretch' ] ) )
        
    
    def ClearMedia( self ):
        
        self.SetMedia( None )
        
    
    def EditImageOverlay( self ):
        
        if self._hash is None:
            
            return
            
        
        try:
            
            image_overlay = EditImageOverlay( self._canvas, self._image_overlay )
            
        except HydrusExceptions.CancelledException:
            
            return
            
        
        self.SetImageOverlay( image_overlay )
        
    
    def FillMediaViewer( self ):
        
        self._ChangeImageOverlay( fractions = IMAGE_OVERLAY_FILL_FRACTIONS )
        
    
    def FlipLocked( self ):
        
        if self._image_overlay is not None:
            
            self._ChangeImageOverlay( locked = not self._image_overlay[3] )
            
        
    
    def FlipStretch( self ):
        
        if self._image_overlay is not None:
            
            self._ChangeImageOverlay( stretch = not self._image_overlay[4] )
            
        
    
    def GetImageOverlay( self ) -> ImageOverlay | None:
        
        return self._image_overlay
        
    
    def GetOverlayWindow( self ) -> CanvasImageOverlay | None:
        
        return self._overlay_window
        
    
    def HasMedia( self ) -> bool:
        
        return self._hash is not None
        
    
    def NotifyNewImageOverlay( self, hash: bytes, image_overlay: ImageOverlay | None, source: object ):
        
        # another media viewer showing the same file changed its image
        if source is self or hash != self._hash:
            
            return
            
        
        self._load_id += 1
        
        self._ApplyImageOverlay( image_overlay )
        
    
    def RemoveImageOverlay( self ):
        
        self.SetImageOverlay( None )
        
    
    def SetImageOverlay( self, image_overlay: ImageOverlay | None ):
        
        # a change from the menu or the overlay itself. the file remembers it, and any other media viewer showing the file follows
        if self._hash is None or image_overlay == self._image_overlay:
            
            return
            
        
        self._load_id += 1
        
        hash = self._hash
        
        if self._overlay_window is not None and image_overlay is not None and image_overlay[3] == self._image_overlay[3] and image_overlay[0] == self._image_overlay[0]:
            
            # a move, resize, or look change can go on the window we have, so it does not flicker
            self._image_overlay = image_overlay
            
            self._overlay_window.SetImageOverlay( image_overlay )
            
        else:
            
            self._ApplyImageOverlay( image_overlay )
            
        
        CG.client_controller.Write( 'file_image_overlay', hash, image_overlay )
        
        CG.client_controller.pub( 'new_file_image_overlay', hash, image_overlay, self )
        
    
    def SetMedia( self, media ):
        
        hash = None if media is None else media.GetHash()
        
        if hash == self._hash:
            
            return
            
        
        self._hash = hash
        
        self._load_id += 1
        
        self._ApplyImageOverlay( None )
        
        if hash is None:
            
            return
            
        
        load_id = self._load_id
        
        def work_callable():
            
            return CG.client_controller.Read( 'file_image_overlay', hash )
            
        
        def publish_callable( image_overlay ):
            
            # the file changed, or the image was changed, while we were waiting
            if load_id != self._load_id:
                
                return
                
            
            self._ApplyImageOverlay( image_overlay )
            
        
        job = ClientGUIAsync.AsyncQtJob( self._canvas, work_callable, publish_callable )
        
        job.start()
        
    
