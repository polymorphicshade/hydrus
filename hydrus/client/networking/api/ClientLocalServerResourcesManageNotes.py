from hydrus.core import HydrusExceptions
from hydrus.core.networking import HydrusServerRequest

from hydrus.client import ClientAPI
from hydrus.client import ClientGlobals as CG
from hydrus.client.networking.api import ClientLocalServerCore
from hydrus.client.networking.api import ClientLocalServerResources

# notes are markdown, which the notes dialog's 'view' tab and the media viewer show rendered. this gives the same rendering as html, for anything that wants to show them like the client does
# setting notes is hydrus's own /add_notes/set_notes

class HydrusResourceClientAPIRestrictedManageNotes( ClientLocalServerResources.HydrusResourceClientAPIRestricted ):
    
    def _CheckAPIPermissions( self, request: HydrusServerRequest.HydrusRequest ):
        
        # it is reading what file_metadata can give
        request.client_api_permissions.CheckPermission( ClientAPI.CLIENT_API_PERMISSION_SEARCH_FILES )
        
    

class HydrusResourceClientAPIRestrictedManageNotesGetNotesHTML( HydrusResourceClientAPIRestrictedManageNotes ):
    
    def _threadDoGETJob( self, request: HydrusServerRequest.HydrusRequest ):
        
        hash = ClientLocalServerCore.ParseSingleHash( request )
        
        media_results = CG.client_controller.Read( 'media_results', ( hash, ) )
        
        if len( media_results ) == 0:
            
            raise HydrusExceptions.NotFoundException( f'Did not find the file {hash.hex()}!' )
            
        
        names_to_notes = media_results[0].GetNotesManager().GetNamesToNotes()
        
        def do_it():
            
            from hydrus.client.gui import ClientGUINotesMarkdown
            
            return { name : ClientGUINotesMarkdown.ConvertNoteToHTML( note ) for ( name, note ) in names_to_notes.items() }
            
        
        names_to_html = CG.client_controller.CallBlockingToQtTLW( do_it )
        
        return ClientLocalServerCore.GenerateJSONResponse( request, { 'notes' : names_to_notes, 'notes_html' : names_to_html } )
        
        
        
