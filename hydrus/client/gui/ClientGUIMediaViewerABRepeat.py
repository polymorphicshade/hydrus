from hydrus.client import ClientGlobals as CG

# the A-B repeat of the media viewers that are open now, for the Client API

def GetOpenMediaViewerCanvases() -> list:
    
    canvas_windows = []
    
    for canvas_frame in CG.client_controller.gui.GetCanvasFrames():
        
        if not canvas_frame.isVisible():
            
            # it is closing
            continue
            
        
        canvas_window = canvas_frame.GetCanvas()
        
        if canvas_window is not None:
            
            canvas_windows.append( canvas_window )
            
        
    
    return canvas_windows
    

def GetOpenMediaViewersABRepeat() -> list[ dict ]:
    
    # every media viewer that is open now, in the order they were opened
    return [ canvas_window.GetABRepeatAPIInfo() for canvas_window in GetOpenMediaViewerCanvases() ]
    

def SetOpenMediaViewersABRepeatPingPong( ping_pong: bool, canvas_key: bytes | None = None ) -> int:
    
    # turns ping-pong on or off for one media viewer, or all of them with no canvas_key. returns how many it was set for
    canvas_windows = GetOpenMediaViewerCanvases()
    
    if canvas_key is not None:
        
        canvas_windows = [ canvas_window for canvas_window in canvas_windows if canvas_window.GetCanvasKey() == canvas_key ]
        
    
    for canvas_window in canvas_windows:
        
        canvas_window.SetABLoopPingPong( ping_pong )
        
    
    return len( canvas_windows )

