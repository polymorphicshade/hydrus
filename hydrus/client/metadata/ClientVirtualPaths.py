import re

# virtual paths are folder-like labels you give files, like 'collections/tv_shows/action'. a file can have any number of them
# they are for searching with system:path, which takes wildcards

VIRTUAL_PATH_WILDCARD = '*'

def ConvertVirtualPathPatternToRegex( pattern: str ) -> re.Pattern:
    
    # '*' is anything within one folder, and '**' on its own is any number of folders, including none
    # we match against the path with a '/' on the end, so every folder in the regex can end with a '/' too
    pattern = NormaliseVirtualPath( pattern )
    
    regex = ''
    
    for folder in pattern.split( '/' ):
        
        if folder == '**':
            
            regex += '(?:[^/]+/)*'
            
        else:
            
            regex += ''.join( '[^/]*' if piece.startswith( VIRTUAL_PATH_WILDCARD ) else re.escape( piece ) for piece in re.split( r'(\*+)', folder ) if piece != '' )
            regex += '/'
            
        
    
    return re.compile( f'^{regex}$' )
    

def GetVirtualPathError( path: str ) -> str | None:
    
    if path == '':
        
        return 'The path is empty!'
        
    
    if VIRTUAL_PATH_WILDCARD in path:
        
        return f'A file\'s path cannot have a "{VIRTUAL_PATH_WILDCARD}" in it--that is for searching!'
        
    
    return None
    

def NormaliseVirtualPath( path: str ) -> str:
    
    # like tags, paths are not case-sensitive. they have no spaces, either, so 'tv shows' becomes 'tv_shows'
    path = path.strip().lower()
    
    path = path.replace( '\\', '/' )
    
    path = re.sub( r'\s', '_', path )
    
    # no empty folders
    path = re.sub( '/+', '/', path )
    
    return path.strip( '/' )
    

def VirtualPathMatchesPattern( path: str, pattern_regex: re.Pattern ) -> bool:
    
    return pattern_regex.match( f'{path}/' ) is not None
    
