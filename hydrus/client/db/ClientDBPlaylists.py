import collections.abc
import sqlite3

from hydrus.core import HydrusConstants as HC
from hydrus.core import HydrusDBBase

from hydrus.client.db import ClientDBDefinitionsCache
from hydrus.client.db import ClientDBModule
from hydrus.client.media import ClientMediaPlaylists

class ClientDBPlaylists( ClientDBModule.ClientDBModule ):
    
    def __init__(
        self,
        cursor: sqlite3.Cursor,
        modules_hashes_local_cache: ClientDBDefinitionsCache.ClientDBCacheLocalHashes
    ):
        
        self.modules_hashes_local_cache = modules_hashes_local_cache
        
        super().__init__( 'client playlists', cursor )
        
    
    def _GetInitialIndexGenerationDict( self ) -> dict:
        
        index_generation_dict = {}
        
        index_generation_dict[ 'main.playlist_items' ] = [
            ( [ 'hash_id' ], False, 688 )
        ]
        
        return index_generation_dict
        
    
    def _GetInitialTableGenerationDict( self ) -> dict:
        
        # start_ms and end_ms are both NULL when the item is the whole file
        return {
            'main.playlists' : ( 'CREATE TABLE IF NOT EXISTS {} ( playlist_id INTEGER PRIMARY KEY, name TEXT UNIQUE );', 688 ),
            'main.playlist_items' : ( 'CREATE TABLE IF NOT EXISTS {} ( playlist_id INTEGER, position INTEGER, hash_id INTEGER, start_ms INTEGER, end_ms INTEGER, PRIMARY KEY ( playlist_id, position ) );', 688 )
        }
        
    
    def AddPlaylistItem( self, playlist_id: int, hash: bytes, start_ms: int | None, end_ms: int | None ):
        
        hash_id = self.modules_hashes_local_cache.GetHashId( hash )
        
        ( max_position, ) = self._Execute( 'SELECT MAX( position ) FROM playlist_items WHERE playlist_id = ?;', ( playlist_id, ) ).fetchone()
        
        position = 0 if max_position is None else max_position + 1
        
        self._Execute( 'INSERT INTO playlist_items ( playlist_id, position, hash_id, start_ms, end_ms ) VALUES ( ?, ?, ?, ?, ? );', ( playlist_id, position, hash_id, start_ms, end_ms ) )
        
    
    def GetPlaylistItems( self, playlist_id: int ) -> list[ tuple[ bytes, int | None, int | None ] ]:
        
        rows = self._Execute( 'SELECT hash_id, start_ms, end_ms FROM playlist_items WHERE playlist_id = ? ORDER BY position;', ( playlist_id, ) ).fetchall()
        
        hash_ids_to_hashes = self.modules_hashes_local_cache.GetHashIdsToHashes( hash_ids = { hash_id for ( hash_id, start_ms, end_ms ) in rows } )
        
        return [ ( hash_ids_to_hashes[ hash_id ], start_ms, end_ms ) for ( hash_id, start_ms, end_ms ) in rows ]
        
    
    def GetPlaylists( self ) -> list[ ClientMediaPlaylists.PlaylistSummary ]:
        
        playlists = self._Execute( 'SELECT playlist_id, name, COUNT( hash_id ) FROM playlists LEFT OUTER JOIN playlist_items USING ( playlist_id ) GROUP BY playlist_id;' ).fetchall()
        
        return sorted( playlists, key = lambda playlist: playlist[1].lower() )
        
    
    def GetPlaylistsContainingFile( self, hash: bytes ) -> list[ ClientMediaPlaylists.PlaylistSummary ]:
        
        # the count here is how many times this file is in the playlist
        hash_id = self.modules_hashes_local_cache.GetHashId( hash )
        
        playlists = self._Execute( 'SELECT playlist_id, name, COUNT( * ) FROM playlists CROSS JOIN playlist_items USING ( playlist_id ) WHERE hash_id = ? GROUP BY playlist_id;', ( hash_id, ) ).fetchall()
        
        return sorted( playlists, key = lambda playlist: playlist[1].lower() )
        
    
    def GetTablesAndColumnsThatUseDefinitions( self, content_type: int ) -> list[ tuple[ str, str ] ]:
        
        tables_and_columns = []
        
        if content_type == HC.CONTENT_TYPE_HASH:
            
            tables_and_columns.append( ( 'playlist_items', 'hash_id' ) )
            
        
        return tables_and_columns
        
    
    def RemoveFileFromPlaylist( self, playlist_id: int, hash: bytes ):
        
        # every item of this file goes, whatever its span
        hash_id = self.modules_hashes_local_cache.GetHashId( hash )
        
        self._Execute( 'DELETE FROM playlist_items WHERE playlist_id = ? AND hash_id = ?;', ( playlist_id, hash_id ) )
        
    
    def Repair( self, current_db_version, cursor_transaction_wrapper: HydrusDBBase.DBCursorTransactionWrapper ):
        
        # these tables are not from an official db update, so a db from before they existed would otherwise get a scary 'missing tables' warning. we just quietly make them
        if not self._TableExists( 'main.playlists' ) or not self._TableExists( 'main.playlist_items' ):
            
            self.CreateInitialTables()
            self.CreateInitialIndices()
            
            cursor_transaction_wrapper.CommitAndBegin()
            
        
        super().Repair( current_db_version, cursor_transaction_wrapper )
        
    
    def SetPlaylists( self, playlists: collections.abc.Collection[ tuple[ int | None, str ] ] ):
        
        # ( playlist_id, name ), where a new playlist has no id yet. any existing playlist not in here is deleted, items and all
        existing_playlist_ids = self._STS( self._Execute( 'SELECT playlist_id FROM playlists;' ) )
        
        kept_playlist_ids = { playlist_id for ( playlist_id, name ) in playlists if playlist_id is not None }
        
        deletee_playlist_ids = existing_playlist_ids.difference( kept_playlist_ids )
        
        self._ExecuteMany( 'DELETE FROM playlist_items WHERE playlist_id = ?;', ( ( playlist_id, ) for playlist_id in deletee_playlist_ids ) )
        self._ExecuteMany( 'DELETE FROM playlists WHERE playlist_id = ?;', ( ( playlist_id, ) for playlist_id in deletee_playlist_ids ) )
        
        # names are unique, so renames that swap names would collide halfway through. we clear them all first
        self._ExecuteMany( 'UPDATE playlists SET name = NULL WHERE playlist_id = ?;', ( ( playlist_id, ) for playlist_id in kept_playlist_ids ) )
        
        for ( playlist_id, name ) in playlists:
            
            name = ClientMediaPlaylists.NormalisePlaylistName( name )
            
            if playlist_id is None:
                
                self._Execute( 'INSERT INTO playlists ( name ) VALUES ( ? );', ( name, ) )
                
            else:
                
                self._Execute( 'UPDATE playlists SET name = ? WHERE playlist_id = ?;', ( name, playlist_id ) )
                
            
        
    
