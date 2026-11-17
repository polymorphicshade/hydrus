import os

from qtpy import QtWidgets as QW

from hydrus.core import HydrusData
from hydrus.core import HydrusExceptions

from hydrus.client import ClientFileReplace
from hydrus.client.gui import ClientGUIAsync
from hydrus.client.gui import ClientGUIDialogsFiles
from hydrus.client.gui import ClientGUIDialogsMessage
from hydrus.client.gui import ClientGUIDialogsQuick
from hydrus.client.gui import QtPorting as QP

# 'replace with file...': pick a file on disk to take this one's place, for when it is broken or there is a better copy

REPLACE_FILE_DESCRIPTION = 'Pick a file on your computer to take this file\'s place, like a better copy of a broken video. The new file is imported and gets this file\'s tags, ratings, notes, and urls (by your \'this is better\' duplicate metadata merge options), its places in playlists, its counters and virtual paths, and what the media viewer remembers for it. This file is then deleted.'

def GetReplacementPath( win: QW.QWidget ) -> str | None:
    
    with ClientGUIDialogsFiles.FileDialog( win, message = 'choose the file to replace this one with', fileMode = QW.QFileDialog.FileMode.ExistingFile ) as dlg:
        
        if dlg.exec() != QW.QDialog.DialogCode.Accepted:
            
            return None
            
        
        return dlg.GetPath()
        
    

def AskToReplaceFile( win: QW.QWidget, hash: bytes, on_replaced = None ):
    
    # on_replaced is called in the Qt thread with the old and new hashes when it is done
    path = GetReplacementPath( win )
    
    if path is None:
        
        return
        
    
    message = f'Replace this file with "{os.path.basename( path )}"?'
    message += '\n' * 2
    message += 'The new file is imported and gets this file\'s tags, ratings, notes, and urls, by your \'this is better\' duplicate metadata merge options. It takes this file\'s places in playlists, and gets its counters, virtual paths, snapshots, and what the media viewer remembers for it, like its zoom, skips, and A-B loops.'
    message += '\n' * 2
    message += 'This file is then deleted, and they are marked as duplicates, the new one better.'
    
    result = ClientGUIDialogsQuick.GetYesNo( win, message, yes_label = 'replace it', no_label = 'forget it' )
    
    if result != QW.QDialog.DialogCode.Accepted:
        
        return
        
    
    def work_callable():
        
        return ClientFileReplace.ReplaceFile( hash, path )
        
    
    def publish_callable( result ):
        
        ( new_hash, num_moved ) = result
        
        if on_replaced is not None:
            
            on_replaced( hash, new_hash )
            
        
    
    def errback_callable( etype, value, tb ):
        
        if isinstance( value, ( HydrusExceptions.VetoException, HydrusExceptions.NotFoundException ) ):
            
            if QP.isValid( win ):
                
                ClientGUIDialogsMessage.ShowWarning( win, f'Could not replace the file: {value}' )
                
        else:
            
            HydrusData.ShowExceptionTuple( etype, value, tb )
            
        
    
    job = ClientGUIAsync.AsyncQtJob( win, work_callable, publish_callable, errback_callable = errback_callable )
    
    job.start()
    
