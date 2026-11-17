import collections
import collections.abc
import sqlite3

from hydrus.core import HydrusConstants as HC
from hydrus.core import HydrusDBBase

from hydrus.client import ClientLocation
from hydrus.client.db import ClientDBDefinitionsCache
from hydrus.client.db import ClientDBFilesStorage
from hydrus.client.db import ClientDBModule
from hydrus.client.db import ClientDBServices

class ClientDBFilesCrops( ClientDBModule.ClientDBModule ):
    
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
        
        super().__init__( 'client files crops', cursor )
        
    
    def _GetInitialIndexGenerationDict( self ) -> dict:
        
        index_generation_dict = {}
        
        index_generation_dict[ 'main.file_crops' ] = [
            ( [ 'crop_hash_id' ], False, 688 )
        ]
        
        return index_generation_dict
        
    
    def _GetInitialTableGenerationDict( self ) -> dict:
        
        # a crop is part of a file, or of a frame of it, cut out with an overlay's box and imported as a file of its own. timestamp_ms is where in the file the frame came from, NULL for an image or if we could not tell
        return {
            'main.file_crops' : ( 'CREATE TABLE IF NOT EXISTS {} ( hash_id INTEGER, crop_hash_id INTEGER, timestamp_ms INTEGER, PRIMARY KEY ( hash_id, crop_hash_id ) );', 688 )
        }
        
    
    def AddCrop( self, hash: bytes, crop_hash: bytes, timestamp_ms: int | None ):
        
        hash_id = self.modules_hashes_local_cache.GetHashId( hash )
        crop_hash_id = self.modules_hashes_local_cache.GetHashId( crop_hash )
        
        # the same crop taken again is the same file, so it just moves to its latest timestamp
        self._Execute( 'REPLACE INTO file_crops ( hash_id, crop_hash_id, timestamp_ms ) VALUES ( ?, ?, ? );', ( hash_id, crop_hash_id, timestamp_ms ) )
        
    
    def GetCropHashesForFiles( self, hashes: collections.abc.Sequence[ bytes ], location_context: ClientLocation.LocationContext ) -> list[ bytes ]:
        
        # file by file in the order given, and each file's in the order they come in it. a crop taken from more than one of the files is listed once, under the first
        if len( hashes ) == 0:
            
            return []
            
        
        hashes_to_hash_ids = { hash : hash_id for ( hash_id, hash ) in self.modules_hashes_local_cache.GetHashIdsToHashes( hashes = hashes ).items() }
        
        with self._MakeTemporaryIntegerTable( set( hashes_to_hash_ids.values() ), 'hash_id' ) as temp_hash_ids_table_name:
            
            rows = self._Execute( f'SELECT hash_id, crop_hash_id, timestamp_ms FROM {temp_hash_ids_table_name} CROSS JOIN file_crops USING ( hash_id );' ).fetchall()
            
        
        if len( rows ) == 0:
            
            return []
            
        
        crop_hash_ids_in_location = self.modules_files_storage.FilterHashIds( location_context, { crop_hash_id for ( hash_id, crop_hash_id, timestamp_ms ) in rows } )
        
        hash_ids_to_rows = collections.defaultdict( list )
        
        for ( hash_id, crop_hash_id, timestamp_ms ) in rows:
            
            if crop_hash_id in crop_hash_ids_in_location:
                
                hash_ids_to_rows[ hash_id ].append( ( -1 if timestamp_ms is None else timestamp_ms, crop_hash_id ) )
                
            
        
        crop_hash_ids = []
        seen_crop_hash_ids = set()
        
        for hash in hashes:
            
            hash_id = hashes_to_hash_ids[ hash ]
            
            for ( timestamp_ms, crop_hash_id ) in sorted( hash_ids_to_rows[ hash_id ] ):
                
                if crop_hash_id not in seen_crop_hash_ids:
                    
                    crop_hash_ids.append( crop_hash_id )
                    seen_crop_hash_ids.add( crop_hash_id )
                    
                
            
        
        hash_ids_to_hashes = self.modules_hashes_local_cache.GetHashIdsToHashes( hash_ids = crop_hash_ids )
        
        return [ hash_ids_to_hashes[ crop_hash_id ] for crop_hash_id in crop_hash_ids ]
        
    
    def GetTablesAndColumnsThatUseDefinitions( self, content_type: int ) -> list[ tuple[ str, str ] ]:
        
        tables_and_columns = []
        
        if content_type == HC.CONTENT_TYPE_HASH:
            
            tables_and_columns.append( ( 'file_crops', 'hash_id' ) )
            tables_and_columns.append( ( 'file_crops', 'crop_hash_id' ) )
            
        
        return tables_and_columns
        
    
    def Repair( self, current_db_version, cursor_transaction_wrapper: HydrusDBBase.DBCursorTransactionWrapper ):
        
        # this table is not from an official db update, so a db from before it existed would otherwise get a scary 'missing tables' warning. we just quietly make it
        if not self._TableExists( 'main.file_crops' ):
            
            self.CreateInitialTables()
            self.CreateInitialIndices()
            
            cursor_transaction_wrapper.CommitAndBegin()
            
        
        super().Repair( current_db_version, cursor_transaction_wrapper )
        
        
