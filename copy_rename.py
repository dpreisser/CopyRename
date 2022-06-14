
import sys
import argparse

import os
import shutil

import json
import re


def listDirectory( directory, fileEndingList=None ):

    dirList = []
    fileList = []

    if not os.path.isdir( directory ):
        return dirList, fileList

    allItems = os.listdir( directory )

    for item in allItems:

        itemAbspath = os.path.abspath( os.path.join( directory, item ) )

        if os.path.isdir( itemAbspath ):
            dirList.append( item )

        if os.path.isfile( itemAbspath ):
            if None == fileEndingList:
                fileList.append( item )
            else:
                for fileEnding in fileEndingList:
                    if item.endswith( fileEnding ):
                        fileList.append( item )
                        break

    return dirList, fileList


class TraceHandler():

    def __init__( self ):

        self.trace_buf = ""
        self.trace_file_name = "trace_log.txt"
        self.trace_stream = open( self.trace_file_name, "wb" )

        self.trace( "TraceHandler.__init__" )

    def trace( self, msg ):
        self.trace_buf += msg + "\n"

    def trace_message( self, msg ):
        print( msg )
        self.trace( msg )

    def trace_error( self, error ):
        print( "ERROR:" )
        print( error )
        self.trace( error )

    def finalise( self ):

        self.trace( "TraceHandler.finalise" )

        # Trace
        self.trace_stream.write( self.trace_buf.encode("utf-8") )
        self.trace_stream.flush()
        self.trace_stream.close()
        self.trace_buf = ""


class CopyRename():

    def __init__( self, control_file=None, source_directory=None, target_directory=None ):

        self.trace_handler = TraceHandler()

        if control_file is None:
            self.control_file = "copy_rename_control.json"
        else:
            self.control_file = control_file

        self.source_directory = source_directory
        self.target_directory = target_directory

        self.target_file_structure = None

        self.trace_handler.trace( "CopyRename.__init__" )


    def initialise( self ):

        self.trace_handler.trace( "CopyRename.initialise" )

        if not os.path.isfile( self.control_file ):
            reason = "Can't open control file.\n"
            reason = "%s can not be found or is not a file." % self.control_file
            self.trace_handler.trace_error( reason )
            return False

        fs = open( self.control_file, "r", encoding="utf-8" )
        self.control = json.load( fs )
        fs.close()

        msg = "Content of control file %s:\n" % self.control_file
        msg += json.dumps( self.control, indent=4, sort_keys=True )
        self.trace_handler.trace( msg ) 

        if self.source_directory is None:
            if self.control["source_directory"] is None:
                reason = "A source directory must be provided either on the command line or in the control file."
                self.trace_handler.trace_error( reason )
                return False
            else:
                self.source_directory = self.control["source_directory"]

        if self.target_directory is None:
            if self.control["target_directory"] is None:
                reason = "A target directory must be provided either on the command line or in the control file."
                self.trace_handler.trace_error( reason )
                return False
            else:
                self.target_directory = self.control["target_directory"]

        if not os.path.isdir( self.source_directory ):
            reason = "Can not find source_directory %s." % self.source_directory
            self.trace_handler.trace_error( reason )
            return False

        self.target_file_structure_fname = self.control["target_file_structure_fname"]
        if self.target_file_structure_fname is None:
            reason = "A file name containing the target file structure must be provided in the control file."
            self.trace_handler.trace_error( reason )
            return False
            

        return True


    def evaluate( self ):

        self.trace_handler.trace( "CopyRename.evaluate" )

        msg = "Looking up files in directory %s with extension %s." \
            % ( self.source_directory, str(self.control["extension_filter"]) )
        self.trace_handler.trace( msg )

        dirList, fileList = listDirectory( self.source_directory, self.control["extension_filter"] )

        msg = "Found following files in directory %s:" % self.source_directory
        self.trace_handler.trace( msg )
        num_files_line = self.control["num_files_line"]
        self.trace_items_line( fileList, num_files_line )

        target_file_syntax = self.control["target_file_syntax"]
        self.target_file_structure = {}

        msg = "Using target file syntax: %s." %  target_file_syntax
        self.trace_handler.trace( msg )

        for source_file_name in fileList:

            source_file_components = source_file_name.split( self.control["component_separator"] )
            num_components = len( source_file_components )

            # Skip file names which do not have a amtching number of components!
            if num_components != self.control["num_components"]:
                continue

            extensions = source_file_name.split( os.path.extsep )

            if len(extensions) > 0:
                source_file_extension = extensions[-1]
                # Take the extension away from the last component
                if num_components > 0:
                    num_chars_ext = len(os.path.extsep) + len(source_file_extension)
                    source_file_components[-1] = source_file_components[-1][0:-num_chars_ext]
            else:
                source_file_extension = None

            target_file_name = target_file_syntax
            for idx in range( num_components ):
                comp_name = "comp" + str(idx)
                substitute = r"\$\(" + comp_name + r"\)"
                target_file_name = re.sub( substitute, source_file_components[idx], target_file_name )

            if source_file_extension is not None:
                substitute = r"\$\(ext\)"
                target_file_name = re.sub( substitute, source_file_extension, target_file_name )

            components = target_file_name.split( "\\" )
            directory_components = components[0:-1]
            target_file_name = components[-1]

            current_dir = self.target_file_structure
            current_file_list = current_dir
            dir_abspath = os.path.abspath( self.target_directory )

            num_directory_components = len(directory_components)
            for idx in range( num_directory_components ):

                dir_name = directory_components[idx]

                if dir_name in current_dir.keys():
                    if idx < num_directory_components - 1:
                        current_dir = current_dir[dir_name]
                    else:
                        current_file_list = current_dir[dir_name]
                else:   
                    if idx < num_directory_components - 1:
                        current_dir[dir_name] = {}
                        current_dir = current_dir[dir_name]
                    else:
                        current_dir[dir_name] = []
                        current_file_list = current_dir[dir_name]

            if not isinstance( current_file_list, list ):
                self.target_file_structure = []
                current_file_list = self.target_file_structure

            the_tuple = ( source_file_name, target_file_name )
            current_file_list.append( the_tuple )

        msg = "Saving the target file structure."
        self.trace_handler.trace( msg )

        # Save target_file_structure.
        fs = open( self.target_file_structure_fname, "w", encoding="utf-8" )
        json.dump( self.target_file_structure, fs, indent=4, sort_keys=True )
        fs.close()

        return True


    def copy_rename( self ):

        self.trace_handler.trace( "CopyRename.copy_rename" )

        if self.target_file_structure is None:

            if not os.path.isfile( self.target_file_structure_fname ):
                reason = "Can't open file containing the target file structure.\n"
                reason = "%s can not be found or is not a file." % self.target_file_structure_fname
                return False
            
            fs = open( self.target_file_structure_fname, "r", encoding="utf-8" )
            self.target_file_structure = json.load( fs )
            fs.close()

        self.source_directory_abspath = os.path.abspath( self.source_directory )
        curr_dir = self.target_file_structure
        dir_abspath = os.path.abspath( self.target_directory )

        self.walk_file_structure( curr_dir, dir_abspath )


    def walk_file_structure( self, current_dir, dir_abspath ):

        existing_directories = []
        if not dir_abspath in existing_directories:
            if not os.path.isdir( dir_abspath ):
                os.mkdir( dir_abspath )
                existing_directories.append( dir_abspath )

        if isinstance( current_dir, dict ):
            
            for dir_name in current_dir.keys():
                self.walk_file_structure( current_dir[dir_name], os.path.join(dir_abspath,dir_name) )

        else:

            action = self.control["action"]

            for the_tuple in current_dir:

                source_file_name = the_tuple[0]
                target_file_name = the_tuple[1]

                source_file_abspath = os.path.join( self.source_directory_abspath, source_file_name )
                target_file_abspath = os.path.join( dir_abspath, target_file_name )

                if "copy" == action:
                    shutil.copy2( source_file_abspath, target_file_abspath )
                elif "rename" == action:
                    shutil.move( source_file_abspath, target_file_abspath )
                    # os.rename( source_file_abspath, target_file_abspath ) 

        return True


    def trace_items_line( self, the_list, num_items_line ):

        # Provide num_items_line per line to trace.
        num_items = len(the_list)
        previous_lim = 0
        for current_lim in range( min(num_items_line,num_items), num_items+1, num_items_line ):
            line_list = []
            for idx in range( previous_lim, current_lim ):
                line_list.append( the_list[idx] )
            previous_lim = current_lim
            msg = ", ".join( line_list )
            self.trace_handler.trace( msg )

        line_list = []
        for idx in range( previous_lim, num_items ):
            line_list.append( the_list[idx] )
        msg = ", ".join( line_list )
        self.trace_handler.trace( msg )


def initArgParser ():

    parser = argparse.ArgumentParser( description="Copy Rename Script" )

    # control_file
    parser.add_argument ( "-c", dest="control_file", action="store", default="copy_rename_control.json",
                          required=False, \
                          help="The location of the control file. Optional. Default: ." )

    # source_directory
    parser.add_argument ( "-s", dest="source_directory", action="store", default=None, \
                          required=False, \
                          help="Must be either provided on the command line or in the control file. Default: None" )

    # target_directory
    parser.add_argument ( "-t", dest="target_directory", action="store", default=None,
                          required=False, \
                          help="Must be either provided on the command line or in the control file. Default: None" )

    return parser


def run( args ):

    # Instantiation & Initialisation
    copyRename = CopyRename( args.control_file, args.source_directory, args.target_directory )
    status = copyRename.initialise()

    if not status:
        copyRename.trace_handler.finalise()
        return

    if copyRename.control["evaluate"]:

        try:

            status = copyRename.evaluate()

        except Exception as e:

            reason = "An exception has occurred:\n"
            reason += str(e)
            copyRename.trace_handler.trace_error( reason )
            status = False

        if not status or not copyRename.control["copy_rename"]:
            copyRename.trace_handler.finalise()
            return

    if copyRename.control["copy_rename"]:

        status = copyRename.copy_rename()

        try:

            # status = copyRename.copy_rename()
            pass

        except Exception as e:

            reason = "An exception has occurred:\n"
            reason += str(e)
            copyRename.trace_handler.trace_error( reason )
            status = False

    copyRename.trace_handler.finalise()


if __name__ == "__main__":

    import sys

    parser = initArgParser()

    # Read the aguments.
    try:
        args = parser.parse_args()
    except SystemExit:
        # exit on failure
        sys.exit()

    run( args )
