import sqlite3

from hydrus.core import HydrusConstants as HC
from hydrus.core import HydrusDBBase

from hydrus.client import ClientGlobals as CG
from hydrus.client import ClientLocation
from hydrus.client.db import ClientDBDefinitionsCache
from hydrus.client.db import ClientDBFilesStorage
from hydrus.client.db import ClientDBModule
from hydrus.client.db import ClientDBServices

class ClientDBFilesSnapshots( ClientDBModule.ClientDBModule ):
    
    def __init__(
        self,
        cursor: sqlite3.Cursor,
        modules_hashes_local_cache: ClientDBDefinitionsCache.ClientDBCacheLocalHashes,
        modules_files_storage: ClientDBFilesStorage.ClientDBFilesStorage,
        modules_services: ClientDBServices.ClientDBMasterServices
    ):
        
        self.modules_hashes_local_cache = modules_hashes_local_cache
        self.modules_files_storage = modules_files_storage
        self.modules_services = modules_services
        
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
        
    
    def GetHashIdsWithSnapshots( self, hash_ids_table_name: str ) -> set[ int ]:
        
        # the files in the table that have at least one snapshot still in the snapshots domain. ones that were all deleted do not count
        # the user can rename or delete the snapshots domain, so it is remembered by its key, like ClientSnapshots.GetSnapshotsServiceKey does
        snapshots_service_key = CG.client_controller.new_options.GetKey( 'snapshots_file_service_key' )
        
        if snapshots_service_key not in self.modules_services.GetServiceKeys():
            
            return set()
            
        
        service_id = self.modules_services.GetServiceId( snapshots_service_key )
        
        if self.modules_services.GetServiceType( service_id ) != HC.LOCAL_FILE_DOMAIN:
            
            return set()
            
        
        current_files_table_name = ClientDBFilesStorage.GenerateFilesTableName( service_id, HC.CONTENT_STATUS_CURRENT )
        
        query = f'SELECT DISTINCT {hash_ids_table_name}.hash_id FROM {hash_ids_table_name} CROSS JOIN file_snapshots ON ( {hash_ids_table_name}.hash_id = file_snapshots.hash_id ) CROSS JOIN {current_files_table_name} ON ( file_snapshots.snapshot_hash_id = {current_files_table_name}.hash_id );'
        
        return self._STS( self._Execute( query ) )
        
    
    def GetTablesAndColumnsThatUseDefinitions( self, content_type: int ) -> list[ tuple[ str, str ] ]:
        
        tables_and_columns = []
        
        if content_type == HC.CONTENT_TYPE_HASH:
            
            tables_and_columns.append( ( 'file_snapshots', 'hash_id' ) )
            tables_and_columns.append( ( 'file_snapshots', 'snapshot_hash_id' ) )
            
        
        return tables_and_columns
        
    
    def HasSnapshots( self ) -> bool:
        
        return self._Execute( 'SELECT 1 FROM file_snapshots LIMIT 1;' ).fetchone() is not None
        
    
    def Repair( self, current_db_version, cursor_transaction_wrapper: HydrusDBBase.DBCursorTransactionWrapper ):
        
        # this table is not from an official db update, so a db from before it existed would otherwise get a scary 'missing tables' warning. we just quietly make it
        if not self._TableExists( 'main.file_snapshots' ):
            
            self.CreateInitialTables()
            self.CreateInitialIndices()
            
            cursor_transaction_wrapper.CommitAndBegin()
            
        
        super().Repair( current_db_version, cursor_transaction_wrapper )
        
    
