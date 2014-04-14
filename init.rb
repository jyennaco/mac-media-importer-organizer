#### Media Organizer ####
#
# Launch this Ruby file from the command line
# to get started.
#

APP_ROOT = File.dirname(__FILE__)

# "$:" contains an array of all the folders Ruby can look in to find files

$:.unshift(File.join(APP_ROOT, 'lib'))

require 'logger'
require 'volumes'
require 'media_importer'
require 'backer_upper'

MediaImporter.import_media
#BackerUpper.backup_files