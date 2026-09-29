import sqlite3

from hydrus.core import HydrusConstants as HC
from hydrus.core import HydrusDBBase

from hydrus.client.db import ClientDBDefinitionsCache
from hydrus.client.db import ClientDBModule

class ClientDBFilesViewerZooms( ClientDBModule.ClientDBModule ):
    
    def __init__(
        self,
        cursor: sqlite3.Cursor,
        modules_hashes_local_cache: ClientDBDefinitionsCache.ClientDBCacheLocalHashes
    ):
        
        self.modules_hashes_local_cache = modules_hashes_local_cache
        
        super().__init__( 'client files viewer zooms', cursor )
        
    
    def _GetInitialTableGenerationDict( self ) -> dict:
        
        return {
            'main.file_viewer_zooms' : ( 'CREATE TABLE IF NOT EXISTS {} ( hash_id INTEGER PRIMARY KEY, zoom REAL );', 688 )
        }
        
    
    def ClearAllViewerZooms( self ):
        
        # every file goes back to the normal default zoom
        self._Execute( 'DELETE FROM file_viewer_zooms;' )
        
    
    def GetNumViewerZooms( self ) -> int:
        
        ( num_zooms, ) = self._Execute( 'SELECT COUNT( * ) FROM file_viewer_zooms;' ).fetchone()
        
        return num_zooms
        
    
    def GetTablesAndColumnsThatUseDefinitions( self, content_type: int ) -> list[ tuple[ str, str ] ]:
        
        tables_and_columns = []
        
        if content_type == HC.CONTENT_TYPE_HASH:
            
            tables_and_columns.append( ( 'file_viewer_zooms', 'hash_id' ) )
            
        
        return tables_and_columns
        
    
    def GetViewerZoom( self, hash: bytes ) -> float | None:
        
        hash_id = self.modules_hashes_local_cache.GetHashId( hash )
        
        result = self._Execute( 'SELECT zoom FROM file_viewer_zooms WHERE hash_id = ?;', ( hash_id, ) ).fetchone()
        
        if result is None:
            
            return None
            
        
        ( zoom, ) = result
        
        return zoom
        
    
    def Repair( self, current_db_version, cursor_transaction_wrapper: HydrusDBBase.DBCursorTransactionWrapper ):
        
        # this table is not from an official db update, so a db from before it existed would otherwise get a scary 'missing tables' warning. we just quietly make it
        self.CreateInitialTables()
        
        cursor_transaction_wrapper.CommitAndBegin()
        
        super().Repair( current_db_version, cursor_transaction_wrapper )
        
    
    def SetViewerZoom( self, hash: bytes, zoom: float | None ):
        
        # None means the file goes back to the normal default zoom
        hash_id = self.modules_hashes_local_cache.GetHashId( hash )
        
        if zoom is None:
            
            self._Execute( 'DELETE FROM file_viewer_zooms WHERE hash_id = ?;', ( hash_id, ) )
            
        else:
            
            self._Execute( 'INSERT OR REPLACE INTO file_viewer_zooms ( hash_id, zoom ) VALUES ( ?, ? );', ( hash_id, zoom ) )
            
        
    
