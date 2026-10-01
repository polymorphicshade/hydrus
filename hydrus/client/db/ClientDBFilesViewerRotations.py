import sqlite3

from hydrus.core import HydrusConstants as HC
from hydrus.core import HydrusDBBase

from hydrus.client.db import ClientDBDefinitionsCache
from hydrus.client.db import ClientDBModule

class ClientDBFilesViewerRotations( ClientDBModule.ClientDBModule ):
    
    def __init__(
        self,
        cursor: sqlite3.Cursor,
        modules_hashes_local_cache: ClientDBDefinitionsCache.ClientDBCacheLocalHashes
    ):
        
        self.modules_hashes_local_cache = modules_hashes_local_cache
        
        super().__init__( 'client files viewer rotations', cursor )
        
    
    def _GetInitialTableGenerationDict( self ) -> dict:
        
        # rotation is clockwise, in degrees, 0 <= rotation < 360. a file that is not rotated has no row
        return {
            'main.file_viewer_rotations' : ( 'CREATE TABLE IF NOT EXISTS {} ( hash_id INTEGER PRIMARY KEY, rotation REAL );', 688 )
        }
        
    
    def GetTablesAndColumnsThatUseDefinitions( self, content_type: int ) -> list[ tuple[ str, str ] ]:
        
        tables_and_columns = []
        
        if content_type == HC.CONTENT_TYPE_HASH:
            
            tables_and_columns.append( ( 'file_viewer_rotations', 'hash_id' ) )
            
        
        return tables_and_columns
        
    
    def GetViewerRotation( self, hash: bytes ) -> float:
        
        hash_id = self.modules_hashes_local_cache.GetHashId( hash )
        
        result = self._Execute( 'SELECT rotation FROM file_viewer_rotations WHERE hash_id = ?;', ( hash_id, ) ).fetchone()
        
        if result is None:
            
            return 0.0
            
        
        ( rotation, ) = result
        
        return rotation
        
    
    def Repair( self, current_db_version, cursor_transaction_wrapper: HydrusDBBase.DBCursorTransactionWrapper ):
        
        # this table is not from an official db update, so a db from before it existed would otherwise get a scary 'missing tables' warning. we just quietly make it
        self.CreateInitialTables()
        
        cursor_transaction_wrapper.CommitAndBegin()
        
        super().Repair( current_db_version, cursor_transaction_wrapper )
        
    
    def SetViewerRotation( self, hash: bytes, rotation: float ):
        
        # no rotation means the file shows the way it is
        hash_id = self.modules_hashes_local_cache.GetHashId( hash )
        
        rotation = rotation % 360
        
        if rotation == 0:
            
            self._Execute( 'DELETE FROM file_viewer_rotations WHERE hash_id = ?;', ( hash_id, ) )
            
        else:
            
            self._Execute( 'INSERT OR REPLACE INTO file_viewer_rotations ( hash_id, rotation ) VALUES ( ?, ? );', ( hash_id, rotation ) )
            
        
    
