# media_importer.rb
# 
# Joseph Yennaco, 14 September 2012
#
# The media importer class has one public method, import_media, which
# kicks off the media import process by calling Volume class's find_volumes 
# to find if there are available volumes to input from, then get_volumes 
# prompts the user to type one or more volume names separated by a comma, 
# or "done" to exit. After validating an collecting user input, 
# import_from_volumes uses the FileCopier class to import fines from the 
# selected volumes to the correct folders.

require 'fileutils'

class MediaImporter
	
	# Class vars store file types to import
	@@pic_extensions = [".jpg", ".jpeg", ".gif", ".bmp", ".png", ".tiff", ".tif"]
	@@vid_extensions = [".mov", ".3gp", ".mp4", ".m4v", ".avi", ".mpg", ".wmv"]
	
	# Root directories for Pics and Vids
	@@pic_dir = File.join(File.expand_path('~'), 'Pictures')
	@@vid_dir = File.join(File.expand_path('~'), 'Movies')
	#@@pic_dir = File.join(File.expand_path('~'), 'Test')
	#@@vid_dir = File.join(File.expand_path('~'), 'Test')
	
	# Counters
	@@num_pics = 0
	@@num_vids = 0
		
	# This is the public method kicking of the media import process
	def self.import_media
		Logger.output_major_status("Running Media Importer...")
		volumes = Volumes.get_volumes
		volumes.delete_if { |x| x.downcase.include?("backup") }
		
		if volumes.empty?
			Logger.output_minor_status("No Volumes to Import", :complete)  
			return
		end
		
		selected_volumes = Volumes.get_selected_volumes("Type volumes to import:")
		
		
		selected_volumes.each do |volume|
			if volume == "done"
				break
			else
				Logger.output_major_status("Importing from " + volume + "...")
				import_volume(volume)
				Logger.output_minor_status("SUMMARY: Processed #{@@num_pics} pics", :complete)
				Logger.output_minor_status("SUMMARY: Processed #{@@num_vids} vids", :complete)
				Logger.output_major_status("Import from " + volume + " Complete!")
			end
		end
		
		Logger.output_major_status("Done Running Media Importer.")
	end
	
	private # Private methods follow
	
	# This method checks to see if the volume exists and its a directory, 
	# if so, it kicks off the import_path method, which recursively
	# searches the volume for media files and imports
	def self.import_volume(volume)
		# Reset Counters for this volume
		@@num_pics = 0
		@@num_vids = 0
		
		# Build the absolute volume path
		volume_path = File.join('', 'Volumes', volume)
				
		# Log an error and return if the volume_path doesn't exist or
		# is not a directory
		if not Volumes.readable?(volume)
			Logger.output_error("#{volume} is not a readable device! Skipping...")
			return
		else
			# Otherwise scan the volume for importable media
			scan_path(volume_path)
		end
	end
	
	def self.scan_path(path)			
		# Call import_file if the path points to a readable file
		if File.file?(path) and File.readable?(path)
			import_file(path)
		
		# Recursively call scan_path if the path points to a readable 
		# directory
		elsif File.directory?(path) and File.readable?(path)
			
			# Get the contents of the directory
			contents = Dir.entries(path)
			
			# For each item in the directory recursively call scan_path
			contents.each do |item|
				scan_path(File.join(path, item)) unless item.start_with?(".")
			end
		end
	end
	
	def self.import_file(path)
		# Get the file extensions
		extension = File.extname(path).downcase
		
		# If the extension is a pic, set the target path and import the file
		if @@pic_extensions.include?(extension)
			Logger.output_minor_status("Importing Picture:\t#{path}", :none)
			@@num_pics = @@num_pics + 1 
			target_path = @@pic_dir # Set target path to the pic root directory
		
		# If the extension is a vid, set the target path and import the file
		elsif @@vid_extensions.include?(extension)
			Logger.output_minor_status("Importing Video:\t#{path}", :none)
			@@num_vids = @@num_vids + 1
			target_path = @@vid_dir # Set target path to the vid root directory
		
		# If the file is neither a pic nor vid, return
		else
			return
		end
			
		# Get file name and timestamp info
		fname = File.split(path)[1]
		tstamp = File.mtime(path)
		year = tstamp.year.to_s
		month = tstamp.month.to_s.rjust(2, "0")
		day = tstamp.day.to_s.rjust(2, "0")
		hour = tstamp.hour.to_s.rjust(2, "0")
		min = tstamp.min.to_s.rjust(2, "0")
		sec = tstamp.sec.to_s.rjust(2, "0")
		
		# Create new file name
		new_fname = year + "-" + month + "-" + day + "_" + 
					hour + min + sec + "_" + fname
		
		# Create the pic/vid root directory if it doesn't exist
		Dir.mkdir(target_path) unless File.exist?(target_path)
		
		# Create target path to the year
		target_path =  File.join(target_path, year)
		
		# Create the year directory if it doesn't exist
		Dir.mkdir(target_path) unless File.exist?(target_path)
		
		# Update target path to the month
		target_path = File.join(target_path, year + '-' + month)
		
		# Create the year-month directory if it doesn't exist
		Dir.mkdir(target_path) unless File.exist?(target_path)
		
		# Update the target path to include the file
		target_path = File.join(target_path, new_fname)
		
		# Copy the file to the target path if the target path doesn't exist already
		if File.exist?(target_path)
			Logger.output_minor_status("File Already Exists", :complete)
			puts ""
		elsif
			FileUtils.cp(path,target_path,:preserve=>true)
			Logger.output_minor_status("Imported To:\t\t#{target_path}", :none)
			puts ""
		end
	end
end