import sqlite3

from hydrus.client.db import ClientDBDefinitionsCache
from hydrus.client.db import ClientDBModule

# when the user replaces a file with another, what this fork remembers for the old file moves to the new one. hydrus's own metadata (tags, ratings, notes, urls) goes over with the duplicate merge

# tables that have one or more rows for a file, by hash_id. where the new file has its own already, it keeps it
FILE_VIEWER_DATA_TABLES = (
    'file_ab_loops',
    'file_counters',
    'file_image_overlays',
    'file_playback_freezes',
    'file_playback_skips',
    'file_scripted_events',
    'file_segments',
    'file_viewer_mirrors',
    'file_viewer_rotations',
    'file_viewer_zooms',
    'file_virtual_paths',
    'file_zoom_timestamps'
)

class ClientDBFilesReplace( ClientDBModule.ClientDBModule ):
    
    def __init__(
        self,
        cursor: sqlite3.Cursor,
        modules_hashes_local_cache: ClientDBDefinitionsCache.ClientDBCacheLocalHashes
    ):
        
        self.modules_hashes_local_cache = modules_hashes_local_cache
        
        super().__init__( 'client files replace', cursor )
        
    
    def _GetInitialTableGenerationDict( self ) -> dict:
        
        # it works on the other modules' tables
        return {}
        
    
    def GetTablesAndColumnsThatUseDefinitions( self, content_type: int ) -> list[ tuple[ str, str ] ]:
        
        return []
        
    
    def MoveFileData( self, old_hash: bytes, new_hash: bytes ) -> int:
        
        # returns how many rows moved
        old_hash_id = self.modules_hashes_local_cache.GetHashId( old_hash )
        new_hash_id = self.modules_hashes_local_cache.GetHashId( new_hash )
        
        if old_hash_id == new_hash_id:
            
            return 0
            
        
        num_moved = 0
        
        for table_name in FILE_VIEWER_DATA_TABLES:
            
            self._Execute( f'UPDATE OR IGNORE {table_name} SET hash_id = ? WHERE hash_id = ?;', ( new_hash_id, old_hash_id ) )
            
            num_moved += self._GetRowCount()
            
        
        # snapshots taken from the old file are the new file's now, and if the old file was a snapshot, the new one is that snapshot
        self._Execute( 'UPDATE OR IGNORE file_snapshots SET hash_id = ? WHERE hash_id = ?;', ( new_hash_id, old_hash_id ) )
        
        num_moved += self._GetRowCount()
        
        self._Execute( 'UPDATE OR IGNORE file_snapshots SET snapshot_hash_id = ? WHERE snapshot_hash_id = ?;', ( new_hash_id, old_hash_id ) )
        
        num_moved += self._GetRowCount()
        
        # and the same for crops cut out of it, or a crop it was
        self._Execute( 'UPDATE OR IGNORE file_crops SET hash_id = ? WHERE hash_id = ?;', ( new_hash_id, old_hash_id ) )
        
        num_moved += self._GetRowCount()
        
        self._Execute( 'UPDATE OR IGNORE file_crops SET crop_hash_id = ? WHERE crop_hash_id = ?;', ( new_hash_id, old_hash_id ) )
        
        num_moved += self._GetRowCount()
        
        # the new file takes the old one's place in every playlist, with its span and direction
        self._Execute( 'UPDATE playlist_items SET hash_id = ? WHERE hash_id = ?;', ( new_hash_id, old_hash_id ) )
        
        num_moved += self._GetRowCount()
        
        return num_moved
        
        
