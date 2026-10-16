from hydrus.client.gui import ClientGUIMediaViewerABRepeat

# the slideshows of the media viewers that are open now, for the Client API

def _GetSlideshowCanvases( canvas_key: bytes | None ) -> list:
    
    # just the media viewers that can run a slideshow. a playlist moves itself along, and the filters go at your pace
    canvas_windows = [ canvas_window for canvas_window in ClientGUIMediaViewerABRepeat.GetOpenMediaViewerCanvases() if canvas_window.SupportsSlideshow() ]
    
    if canvas_key is not None:
        
        canvas_windows = [ canvas_window for canvas_window in canvas_windows if canvas_window.GetCanvasKey() == canvas_key ]
        
    
    return canvas_windows
    

def GetOpenMediaViewersSlideshows() -> list[ dict ]:
    
    # every media viewer that is open now, in the order they were opened
    return [
        {
            'canvas_key' : canvas_window.GetCanvasKey().hex(),
            'supports_slideshow' : canvas_window.SupportsSlideshow(),
            'running' : canvas_window.SlideshowIsRunning(),
            'period' : canvas_window.GetSlideshowPeriod()
        }
        for canvas_window in ClientGUIMediaViewerABRepeat.GetOpenMediaViewerCanvases()
    ]
    

def StartOpenMediaViewersSlideshow( period: float, canvas_key: bytes | None = None ) -> int:
    
    # starts one media viewer's slideshow, or all of them with no canvas_key. returns how many it was started for
    canvas_windows = _GetSlideshowCanvases( canvas_key )
    
    for canvas_window in canvas_windows:
        
        canvas_window.StartSlideshow( period )
        
    
    return len( canvas_windows )
    

def StopOpenMediaViewersSlideshow( canvas_key: bytes | None = None ) -> int:
    
    canvas_windows = _GetSlideshowCanvases( canvas_key )
    
    for canvas_window in canvas_windows:
        
        canvas_window.StopSlideshow()
        
    
    return len( canvas_windows )
    
