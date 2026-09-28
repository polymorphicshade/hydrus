import sqlite3

from hydrus.core import HydrusConstants as HC
from hydrus.core import HydrusDBBase

from hydrus.client import ClientLocation
from hydrus.client.db import ClientDBDefinitionsCache
from hydrus.client.db import ClientDBFilesStorage
from hydrus.client.db import ClientDBModule

class ClientDBFilesSnapshots( ClientDBModule.ClientDBModule ):
    
    def __init__(
        self,
        cursor: sqlite3.Cursor,
        modules_hashes_local_cache: ClientDBDefinitionsCache.ClientDBCacheLocalHashes,
        modules_files_storage: ClientDBFilesStorage.ClientDBFilesStorage
    ):
        
        self.modules_hashes_local_cache = modules_hashes_local_cache
        self.modules_files_storage = modules_files_storage
        
        super().__init__( 'client files snapshots', cursor )
        
    
    def _GetInitialIndexGenerationDict( self ) -> dict:
        
        index_generation_dict = {}
        
        index_generation_dict[ 'main.file_snapshots' ] = [
            ( [ 'snapshot_hash_id' ], False, 688 )
        ]
        
        return index_generation_dict
        
    
    def _GetInitialTableGenerationDict( self ) -> dict:
        
        # a snapshot is a frame the user took from a file, imported as a file of its own. timestamp_ms is where in the file it came from, NULL if we could not tell
        return {
            'main.file_snapshots' : ( 'CREATE TABLE IF NOT EXISTS {} ( hash_id INTEGER, snapshot_hash_id INTEGER, timestamp_ms INTEGER, PRIMARY KEY ( hash_id, snapshot_hash_id ) );', 688 )
        }
        
    
    def AddSnapshot( self, hash: bytes, snapshot_hash: bytes, timestamp_ms: int | None ):
        
        hash_id = self.modules_hashes_local_cache.GetHashId( hash )
        snapshot_hash_id = self.modules_hashes_local_cache.GetHashId( snapshot_hash )
        
        # the same frame taken again is the same file, so it just moves to its latest timestamp
        self._Execute( 'REPLACE INTO file_snapshots ( hash_id, snapshot_hash_id, timestamp_ms ) VALUES ( ?, ?, ? );', ( hash_id, snapshot_hash_id, timestamp_ms ) )
        
    
    def GetSnapshotHashes( self, hash: bytes, location_context: ClientLocation.LocationContext ) -> list[ bytes ]:
        
        # in the order they come in the file. ones that are no longer in the location, e.g. deleted, are left out
        hash_id = self.modules_hashes_local_cache.GetHashId( hash )
        
        rows = self._Execute( 'SELECT snapshot_hash_id, timestamp_ms FROM file_snapshots WHERE hash_id = ?;', ( hash_id, ) ).fetchall()
        
        if len( rows ) == 0:
            
            return []
            
        
        snapshot_hash_ids_in_location = self.modules_files_storage.FilterHashIds( location_context, { snapshot_hash_id for ( snapshot_hash_id, timestamp_ms ) in rows } )
        
        rows = sorted( ( ( -1 if timestamp_ms is None else timestamp_ms, snapshot_hash_id ) for ( snapshot_hash_id, timestamp_ms ) in rows if snapshot_hash_id in snapshot_hash_ids_in_location ) )
        
        hash_ids_to_hashes = self.modules_hashes_local_cache.GetHashIdsToHashes( hash_ids = [ snapshot_hash_id for ( timestamp_ms, snapshot_hash_id ) in rows ] )
        
        return [ hash_ids_to_hashes[ snapshot_hash_id ] for ( timestamp_ms, snapshot_hash_id ) in rows ]
        
    
    def GetTablesAndColumnsThatUseDefinitions( self, content_type: int ) -> list[ tuple[ str, str ] ]:
        
        tables_and_columns = []
        
        if content_type == HC.CONTENT_TYPE_HASH:
            
            tables_and_columns.append( ( 'file_snapshots', 'hash_id' ) )
            tables_and_columns.append( ( 'file_snapshots', 'snapshot_hash_id' ) )
            
        
        return tables_and_columns
        
    
    def Repair( self, current_db_version, cursor_transaction_wrapper: HydrusDBBase.DBCursorTransactionWrapper ):
        
        # this table is not from an official db update, so a db from before it existed would otherwise get a scary 'missing tables' warning. we just quietly make it
        if not self._TableExists( 'main.file_snapshots' ):
            
            self.CreateInitialTables()
            self.CreateInitialIndices()
            
            cursor_transaction_wrapper.CommitAndBegin()
            
        
        super().Repair( current_db_version, cursor_transaction_wrapper )
        
    
