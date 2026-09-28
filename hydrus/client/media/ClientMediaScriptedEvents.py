from hydrus.core import HydrusData
from hydrus.core.processes import HydrusSubprocess

from hydrus.client import ClientGlobals as CG

# scripted events are shell commands that run when playback of a file gets to a point in it. each file has its own, saved in the db

# ( timestamp_ms, command )
ScriptedEvent = tuple[ int, str ]

# playback moves on by less than this between two checks. a bigger jump is the user seeking, which does not run anything
SCRIPTED_EVENT_MAX_STEP_MS = 1500

def GetScriptedEventsToRun( scripted_events: list[ ScriptedEvent ], last_timestamp_ms: float | None, current_timestamp_ms: float, duration_ms: int | None ) -> list[ ScriptedEvent ]:
    
    # the events that normal playback went past since the last check, in the order it went past them
    scripted_events = sorted( scripted_events )
    
    if last_timestamp_ms is None:
        
        # the first check. if playback is at the start, anything at the start runs
        if current_timestamp_ms > SCRIPTED_EVENT_MAX_STEP_MS:
            
            return []
            
        
        return [ scripted_event for scripted_event in scripted_events if scripted_event[0] <= current_timestamp_ms ]
        
    
    if current_timestamp_ms >= last_timestamp_ms:
        
        if current_timestamp_ms - last_timestamp_ms > SCRIPTED_EVENT_MAX_STEP_MS:
            
            return []
            
        
        return [ scripted_event for scripted_event in scripted_events if last_timestamp_ms < scripted_event[0] <= current_timestamp_ms ]
        
    
    # playback went back. if it went from near the end to near the start, it looped round, so we catch the end and the start
    if duration_ms is None or last_timestamp_ms < duration_ms - SCRIPTED_EVENT_MAX_STEP_MS or current_timestamp_ms > SCRIPTED_EVENT_MAX_STEP_MS:
        
        return []
        
    
    end_scripted_events = [ scripted_event for scripted_event in scripted_events if scripted_event[0] > last_timestamp_ms ]
    start_scripted_events = [ scripted_event for scripted_event in scripted_events if scripted_event[0] <= current_timestamp_ms ]
    
    return end_scripted_events + start_scripted_events
    

def RunScriptedEventCommand( command: str ):
    
    # the command goes to the system shell, like typing it into a terminal or the run dialog. we do not wait on it
    def do_it():
        
        try:
            
            HydrusSubprocess.RunSubprocess( command, this_is_a_potentially_long_lived_external_guy = True, text = False, shell = True )
            
        except Exception as e:
            
            # the subprocess call has already shown the error
            HydrusData.Print( f'A scripted event failed to run. Its command was: {command}' )
            
        
    
    CG.client_controller.CallToThread( do_it )
    
