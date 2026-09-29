from qtpy import QtCore as QC
from qtpy import QtGui as QG
from qtpy import QtWidgets as QW

from hydrus.core import HydrusConstants as HC
from hydrus.core import HydrusExceptions

from hydrus.client import ClientConstants as CC
from hydrus.client.gui import ClientGUIMenus
from hydrus.client.gui import ClientGUITopLevelWindowsPanels
from hydrus.client.gui import QtPorting as QP
from hydrus.client.gui.panels import ClientGUIScrolledPanels
from hydrus.client.gui.widgets import ClientGUIColourPicker
from hydrus.client.gui.widgets import ClientGUICommon

# an overlay is a see-through coloured box that sits on top of everything in the media viewer, to dim or hide part of it
# it is a window of its own, owned by the media viewer, since a see-through widget inside the media viewer cannot show mpv's video through it

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
    

def AppendOverlaysMenu( menu: QW.QMenu, canvas: QW.QWidget ):
    
    num_overlays = len( GetOverlays( canvas ) )
    
    overlays_menu = ClientGUIMenus.GenerateMenu( menu )
    
    ClientGUIMenus.AppendMenuItem( overlays_menu, 'add' + HC.UNICODE_ELLIPSIS, 'Put a see-through coloured box on top of the media viewer, to dim or hide part of what is shown. Drag it to move it, drag its edges to resize it, and right-click it to change its colour or remove it.', AddOverlay, canvas )
    
    remove_all_item = ClientGUIMenus.AppendMenuItem( overlays_menu, 'remove all', 'Remove all the overlays on this media viewer.', RemoveAllOverlays, canvas )
    
    remove_all_item.setEnabled( num_overlays > 0 )
    
    ClientGUIMenus.AppendMenu( menu, overlays_menu, f'overlays ({num_overlays})' if num_overlays > 0 else 'overlays' )
    
    return overlays_menu
    

def EditOverlayColour( win: QW.QWidget, colour: QG.QColor ) -> QG.QColor:
    
    # raises CancelledException if the user backs out
    with ClientGUITopLevelWindowsPanels.DialogEdit( win, 'overlay colour' ) as dlg:
        
        panel = EditOverlayColourPanel( dlg, colour )
        
        dlg.SetPanel( panel )
        
        if dlg.exec() == QW.QDialog.DialogCode.Accepted:
            
            return panel.GetValue()
            
        
        raise HydrusExceptions.CancelledException( 'Dialog cancelled.' )
        
    

def GetOverlays( canvas: QW.QWidget ) -> list[ 'CanvasOverlay' ]:
    
    return [ overlay for overlay in canvas.window().findChildren( CanvasOverlay ) if overlay.GetCanvas() is canvas and not overlay.IsRemoved() ]
    

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
                
            
        
    
