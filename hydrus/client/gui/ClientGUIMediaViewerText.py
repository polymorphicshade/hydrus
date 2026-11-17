from hydrus.client import ClientApplicationCommand as CAC
from hydrus.client import ClientGlobals as CG
from hydrus.client.gui import ClientGUIShortcuts

# the media viewer can hide its text--the tags on the left, the notes and file info on the right, and the rest it draws--for something more immersive. ctrl+f10 flips it, to start with

FLIP_TEXT_SHORTCUT_ADDED_OPTION = 'media_viewer_flip_text_shortcut_added'

def GetDefaultFlipTextShortcut() -> ClientGUIShortcuts.Shortcut:
    
    return ClientGUIShortcuts.Shortcut( ClientGUIShortcuts.SHORTCUT_TYPE_KEYBOARD_SPECIAL, ClientGUIShortcuts.SHORTCUT_KEY_SPECIAL_F10, ClientGUIShortcuts.SHORTCUT_PRESS_TYPE_PRESS, [ ClientGUIShortcuts.SHORTCUT_MODIFIER_CTRL ] )
    

def GetFlipTextCommand() -> CAC.ApplicationCommand:
    
    return CAC.ApplicationCommand.STATICCreateSimpleCommand( CAC.SIMPLE_MEDIA_VIEWER_FLIP_TEXT )
    

def AddDefaultFlipTextShortcut( shortcut_sets: list ):
    
    # a new client gets ctrl+f10 in its default 'media_viewer' shortcuts. an existing one gets it here, once, on boot, unless something else has ctrl+f10 there
    # returns the shortcut set that was changed, or None
    for shortcut_set in shortcut_sets:
        
        if shortcut_set.GetName() != 'media_viewer':
            
            continue
            
        
        if len( shortcut_set.GetShortcuts( CAC.SIMPLE_MEDIA_VIEWER_FLIP_TEXT ) ) > 0:
            
            return None
            
        
        shortcut = GetDefaultFlipTextShortcut()
        
        if shortcut_set.GetCommand( shortcut ) is not None:
            
            return None
            
        
        shortcut_set.SetCommand( shortcut, GetFlipTextCommand() )
        
        return shortcut_set
        
    
    return None
    

def AddDefaultFlipTextShortcutOnce( shortcut_sets: list ):
    
    # on boot, before the shortcuts manager is made. it only ever happens once, so if the user takes it out, it stays out
    new_options = CG.client_controller.new_options
    
    if new_options.GetBoolean( FLIP_TEXT_SHORTCUT_ADDED_OPTION ):
        
        return
        
    
    changed_shortcut_set = AddDefaultFlipTextShortcut( shortcut_sets )
    
    if changed_shortcut_set is not None:
        
        CG.client_controller.Write( 'serialisable', changed_shortcut_set )
        
    
    new_options.SetBoolean( FLIP_TEXT_SHORTCUT_ADDED_OPTION, True )
    
    CG.client_controller.Write( 'serialisable', new_options )
    

def GetOpenMediaViewersTextHidden() -> list[ dict ]:
    
    from hydrus.client.gui import ClientGUIMediaViewerABRepeat
    
    return [ { 'canvas_key' : canvas_window.GetCanvasKey().hex(), 'text_hidden' : canvas_window.IsHidingText() } for canvas_window in ClientGUIMediaViewerABRepeat.GetOpenMediaViewerCanvases() ]
    

def SetOpenMediaViewersTextHidden( text_hidden: bool, canvas_key: bytes | None = None ) -> int:
    
    # hides or shows the text of one media viewer, or all of them with no canvas_key. returns how many it was set for
    from hydrus.client.gui import ClientGUIMediaViewerABRepeat
    
    canvas_windows = ClientGUIMediaViewerABRepeat.GetOpenMediaViewerCanvases()
    
    if canvas_key is not None:
        
        canvas_windows = [ canvas_window for canvas_window in canvas_windows if canvas_window.GetCanvasKey() == canvas_key ]
        
    
    for canvas_window in canvas_windows:
        
        canvas_window.SetTextHidden( text_hidden )
        
    
    return len( canvas_windows )
    
    
