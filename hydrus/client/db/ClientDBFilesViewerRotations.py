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
        
    
    def ClearViewerRotations( self, hashes ):
        
        # just these files go back to how they are, not turned
        hash_ids = self.modules_hashes_local_cache.GetHashIds( hashes )
        
        self._ExecuteMany( 'DELETE FROM file_viewer_rotations WHERE hash_id = ?;', ( ( hash_id, ) for hash_id in hash_ids ) )
        
    
    def GetNumViewerRotations( self, hashes = None ) -> int:
        
        # every file's, or just these files'
        if hashes is None:
            
            ( num_rotations, ) = self._Execute( 'SELECT COUNT( * ) FROM file_viewer_rotations;' ).fetchone()
            
            return num_rotations
            
        
        hash_ids = self.modules_hashes_local_cache.GetHashIds( hashes )
        
        with self._MakeTemporaryIntegerTable( hash_ids, 'hash_id' ) as temp_hash_ids_table_name:
            
            ( num_rotations, ) = self._Execute( f'SELECT COUNT( * ) FROM {temp_hash_ids_table_name} CROSS JOIN file_viewer_rotations USING ( hash_id );' ).fetchone()
            
        
        return num_rotations
        
    
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
            
        
    
