import sqlite3

from hydrus.core import HydrusConstants as HC
from hydrus.core import HydrusDBBase

from hydrus.client.db import ClientDBDefinitionsCache
from hydrus.client.db import ClientDBModule

class ClientDBFilesViewerMirrors( ClientDBModule.ClientDBModule ):
    
    def __init__(
        self,
        cursor: sqlite3.Cursor,
        modules_hashes_local_cache: ClientDBDefinitionsCache.ClientDBCacheLocalHashes
    ):
        
        self.modules_hashes_local_cache = modules_hashes_local_cache
        
        super().__init__( 'client files viewer mirrors', cursor )
        
    
    def _GetInitialTableGenerationDict( self ) -> dict:
        
        # whether the media viewer shows a file flipped left to right, and/or upside down. a file that is not mirrored has no row
        return {
            'main.file_viewer_mirrors' : ( 'CREATE TABLE IF NOT EXISTS {} ( hash_id INTEGER PRIMARY KEY, mirror_horizontal INTEGER NOT NULL DEFAULT 0, mirror_vertical INTEGER NOT NULL DEFAULT 0 );', 688 )
        }
        
    
    def ClearAllViewerMirrors( self ):
        
        # every file goes back to how it is, not mirrored
        self._Execute( 'DELETE FROM file_viewer_mirrors;' )
        
    
    def ClearViewerMirrors( self, hashes ):
        
        # just these files go back to how they are, not mirrored
        hash_ids = self.modules_hashes_local_cache.GetHashIds( hashes )
        
        self._ExecuteMany( 'DELETE FROM file_viewer_mirrors WHERE hash_id = ?;', ( ( hash_id, ) for hash_id in hash_ids ) )
        
    
    def GetTablesAndColumnsThatUseDefinitions( self, content_type: int ) -> list[ tuple[ str, str ] ]:
        
        tables_and_columns = []
        
        if content_type == HC.CONTENT_TYPE_HASH:
            
            tables_and_columns.append( ( 'file_viewer_mirrors', 'hash_id' ) )
            
        
        return tables_and_columns
        
    
    def GetViewerMirror( self, hash: bytes ) -> tuple[ bool, bool ]:
        
        # ( mirror_horizontal, mirror_vertical )
        hash_id = self.modules_hashes_local_cache.GetHashId( hash )
        
        result = self._Execute( 'SELECT mirror_horizontal, mirror_vertical FROM file_viewer_mirrors WHERE hash_id = ?;', ( hash_id, ) ).fetchone()
        
        if result is None:
            
            return ( False, False )
            
        
        ( mirror_horizontal, mirror_vertical ) = result
        
        return ( bool( mirror_horizontal ), bool( mirror_vertical ) )
        
    
    def Repair( self, current_db_version, cursor_transaction_wrapper: HydrusDBBase.DBCursorTransactionWrapper ):
        
        # this table is not from an official db update, so a db from before it existed would otherwise get a scary 'missing tables' warning. we just quietly make it
        self.CreateInitialTables()
        
        cursor_transaction_wrapper.CommitAndBegin()
        
        super().Repair( current_db_version, cursor_transaction_wrapper )
        
    
    def SetViewerMirror( self, hash: bytes, mirror_horizontal: bool, mirror_vertical: bool ):
        
        # not mirrored means the file shows the way it is
        hash_id = self.modules_hashes_local_cache.GetHashId( hash )
        
        if not mirror_horizontal and not mirror_vertical:
            
            self._Execute( 'DELETE FROM file_viewer_mirrors WHERE hash_id = ?;', ( hash_id, ) )
            
        else:
            
            self._Execute( 'REPLACE INTO file_viewer_mirrors ( hash_id, mirror_horizontal, mirror_vertical ) VALUES ( ?, ?, ? );', ( hash_id, bool( mirror_horizontal ), bool( mirror_vertical ) ) )
            
            
            
