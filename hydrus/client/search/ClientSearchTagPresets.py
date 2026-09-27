import collections.abc

from hydrus.client.metadata import ClientTagsHandling
from hydrus.client.search import ClientSearchAutocomplete
from hydrus.client.search import ClientSearchPredicate

# a tag preset is a named list of search entries. searching for 'system:presets name' enters them all, as if the user had typed each one
# an entry is anything you can type in a search box: 'blue eyes', '-red hair', 'character:*', 'system:inbox'
# ( name, entries )
TagPreset = tuple[ str, list[ str ] ]

def AddEntriesToTagPreset( tag_presets: list[ TagPreset ], name: str, entries: collections.abc.Iterable[ str ] ) -> list[ TagPreset ]:
    
    # returns a new list. entries the preset already has are skipped, and the preset is made if it does not exist yet
    entries = [ NormaliseTagPresetEntry( entry ) for entry in entries ]
    
    entries = [ entry for entry in entries if entry != '' ]
    
    key = GetTagPresetLookupKey( name )
    
    new_tag_presets = []
    
    found_it = False
    
    for ( preset_name, preset_entries ) in tag_presets:
        
        preset_entries = list( preset_entries )
        
        if GetTagPresetLookupKey( preset_name ) == key:
            
            found_it = True
            
            preset_entries.extend( ( entry for entry in DedupeEntries( entries ) if entry not in preset_entries ) )
            
        
        new_tag_presets.append( ( preset_name, preset_entries ) )
        
    
    if not found_it:
        
        new_tag_presets.append( ( NormaliseTagPresetName( name ), DedupeEntries( entries ) ) )
        
    
    return new_tag_presets
    

def ConvertTagPresetEntryToPredicate( entry: str, tag_autocomplete_options: ClientTagsHandling.TagAutocompleteOptions ) -> ClientSearchPredicate.Predicate | None:
    
    # the same as pasting the text into a search box
    parsed_autocomplete_text = ClientSearchAutocomplete.ParsedAutocompleteText( entry, tag_autocomplete_options, collapse_search_characters = True )
    
    if not parsed_autocomplete_text.IsAcceptableForFileSearches():
        
        return None
        
    
    return parsed_autocomplete_text.GetImmediateFileSearchPredicate( allow_auto_wildcard_conversion = True )
    

def DedupeEntries( entries: collections.abc.Iterable[ str ] ) -> list[ str ]:
    
    deduped_entries = []
    
    for entry in entries:
        
        if entry not in deduped_entries:
            
            deduped_entries.append( entry )
            
        
    
    return deduped_entries
    

def ExpandTagPresetPredicates(
    predicates: collections.abc.Iterable[ ClientSearchPredicate.Predicate ],
    tag_presets: list[ TagPreset ],
    tag_autocomplete_options: ClientTagsHandling.TagAutocompleteOptions
) -> tuple[ list[ ClientSearchPredicate.Predicate ], list[ str ] ]:
    
    # swaps each preset predicate for the predicates of its entries. a preset can include another preset, but not itself
    # returns ( predicates, names of presets that do not exist )
    expanded_predicates = []
    missing_names = []
    
    def expand( predicate: ClientSearchPredicate.Predicate, presets_in_progress: set[ str ] ):
        
        if predicate.GetType() != ClientSearchPredicate.PREDICATE_TYPE_SYSTEM_TAG_PRESET:
            
            if predicate not in expanded_predicates:
                
                expanded_predicates.append( predicate )
                
            
            return
            
        
        name = predicate.GetValue()
        
        key = GetTagPresetLookupKey( name )
        
        if key in presets_in_progress:
            
            return
            
        
        tag_preset = GetTagPreset( tag_presets, name )
        
        if tag_preset is None:
            
            if name not in missing_names:
                
                missing_names.append( name )
                
            
            return
            
        
        ( preset_name, entries ) = tag_preset
        
        for entry in entries:
            
            entry_predicate = ConvertTagPresetEntryToPredicate( entry, tag_autocomplete_options )
            
            if entry_predicate is not None:
                
                expand( entry_predicate, presets_in_progress | { key } )
                
            
        
    
    for predicate in predicates:
        
        expand( predicate, set() )
        
    
    return ( expanded_predicates, missing_names )
    

def GetTagPreset( tag_presets: list[ TagPreset ], name: str ) -> TagPreset | None:
    
    key = GetTagPresetLookupKey( name )
    
    for tag_preset in tag_presets:
        
        if GetTagPresetLookupKey( tag_preset[0] ) == key:
            
            return tag_preset
            
        
    
    return None
    

def GetTagPresetLookupKey( name: str ) -> str:
    
    # names are not case-sensitive, and underscores count as spaces, so 'system:presets my_preset' finds 'My Preset'
    return ' '.join( name.replace( '_', ' ' ).lower().split() )
    

def NormaliseTagPresetEntry( entry: str ) -> str:
    
    return ' '.join( entry.split() ).lower()
    

def NormaliseTagPresetName( name: str ) -> str:
    
    return ' '.join( name.split() )
    
