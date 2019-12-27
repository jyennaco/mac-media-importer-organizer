#### Media Organizer ####
#
# Launch this Ruby file from the command line
# to get started.
#

APP_ROOT = File.dirname(__FILE__)

# "$:" contains an array of all the folders Ruby can look in to find files

$:.unshift(File.join(APP_ROOT, 'lib'))

require 'logger'
require 'printer'
require 'volumes'
require 'media_importer'
require 'backer_upper'

# Create log file name
time = Time.now
logFileName = "log-" + time.year.to_s + time.month.to_s.rjust(2, "0") + time.day.to_s.rjust(2, "0") + "-" + time.hour.to_s.rjust(2, "0") + time.min.to_s.rjust(2, "0") + time.sec.to_s.rjust(2, "0") + ".txt"
logFilePath = File.join(APP_ROOT, "log", logFileName)

puts "Creating log file: #{logFilePath}"

# Open the new log file for writing
begin
	file = File.new(logFilePath, "w")
rescue
	puts "Could not create new log file: #{logFilePath}"
	exit(1)
end

# Add text to log file
file.puts("This log file created by mac-media-importer-organizer at #{time.to_s}")

# Initialize logging
$log = Logger.new(file)
$log.level = Logger::DEBUG

# Run the MediaImporter!
$log.info("Init -- Running mac-media-importer-organizer!!")

input_array = ARGV
puts "Found command line args: #{input_array.to_s}"

if input_array.length > 0
  path = input_array[0]
else
  path = "None"
end
puts "Using import path: #{path}"

MediaImporter.import_media(path)
#BackerUpper.backup_files

$log.info("Init -- mac-media-importer-organizer completed!")

# Close the log file
begin
	file.close
rescue
	puts "WARN: Could not close log file!"
ensure
	file.close unless file.nil?
end

puts "Exiting mac-media-importer-organizer!"
exit(0)