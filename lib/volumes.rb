# volumes.rb
#
# Joseph Yennaco 4 July 2014
#

class Volumes
	
	# Class var to maintain the list of connected volumes
	@@volumes = []
	
	def self.set_volumes	
		$log.debug("Volumes::set_volumes -- Setting the @@volumes array ...")
		# Assume this is a Mac, and set the @@volumes array
		set_volumes_mac
	end
	
	def self.get_volumes
		return @@volumes
	end

	# Prints the list of connected volumes 
	def self.print_volumes
		
		$log.debug("Volumes::print_volumes -- Printing the @@volumes array for user ...")
		
		puts ""
		if not @@volumes.empty?
			Printer.output_user_info("The Connected Volumes available are: "); puts ""
			puts "\t" + "*" * 30
			@@volumes.each { |volume| puts "\t*" + File.basename(volume).center(28) + "*" }
			puts "\t" + "*" * 30
			puts ""
		else
			Printer.output_user_alert("No Connected Volumes detected")
		end
	end

	# This class method prompts the user with the available connected volumes, 
	# and queries which ones to import media from
	# Input: "volumes" is an array of available volumes
	# Output: "selected_volumes" is an array of connected volumes typed by the user
	def self.get_selected_volumes(message="Type Volume Names")
		
		$log.debug("Volumes::get_selected_volumes -- Getting user input for which volumes to import ...")
		
		# Initialize the selected volumes
		selected_volumes = []
		
		# Loop request input until the user types "done" or provides valid input
		until not selected_volumes.empty? do
			print_volumes
			return if @@volumes.empty?
			Printer.get_user_input("#{message} (e.g. \"VOL1, VOL2\") or \"done\"")
			
			# Get the user input, chomp whitespace, split on ',' or whitespace
			# store user input as an array of selected volumes
			entries = gets.chomp.split(%r{,\s*})
			
			$log.info("Volumes::get_selected_volumes -- User entered: #{entries}")

			entries.each do |entry|
				
				$log.debug("Volumes::get_selected_volumes -- Checking if user entry matches: #{entry}")
				
				# Check for user entered "done" and return it if found
				if entry.downcase == "done" or entry.downcase == "exit" or entry.downcase == "quit"
					$log.info("Volumes::get_selected_volumes -- User entered done, exit, or quit.  Exiting ...")
					selected_volumes = ["done"]
					return selected_volumes
				end
				
				# Otherwise check to see if the user entry matches a volume
				@@volumes.each do |volume|
					
					$log.debug("Volumes::get_selected_volumes -- Check if #{entry} matches #{volume} ...")
					
					# Add the volume if it matches a user entry
					if volume.include?(entry)
						$log.debug("Volumes::get_selected_volumes -- #{entry} matched #{volume}, adding to the selected set ...")
						selected_volumes << volume
					else
						$log.debug("Volumes::get_selected_volumes -- #{entry} did not match #{volume}")
					end
				end
			end
		end
		
		# Return the list of selected volumes
		return selected_volumes.sort
	end

	def self.readable?(volume="")
		
		$log.debug("Volumes::readable? -- Determining if volume is readable: #{volume}")
		
		return false unless volume.class == String
		volume = volume.chomp
		# Check if the path exists, is a directory, and is readable
		return false unless File.exists?(volume)
		return false unless File.directory?(volume)
		return false unless File.readable?(volume)
		return true
	end
	
	def self.writable?(volume="")
		
		$log.debug("Volumes::writeable? -- Determining if volume is writable: #{volume}")
		
		return false unless volume.class == String
		volume = volume.chomp
		# Build the absolute volume path
		volume_path = File.join('', 'Volumes', volume)
		# Check if the path exists, is a directory, and is writeable
		return false unless File.exists?(volume_path)
		return false unless File.directory?(volume_path)
		return false unless File.writable?(volume_path)
		return true
	end
	
	private
	
	# This method determines which Volumes are connected
	def self.set_volumes_mac
		
		$log.debug("Volumes::set_volumes_mac -- Setting the @@volumes array on a Mac ...")
		
		# Clear the @@volumes
		@@volumes = []
		
		# Get attached volumes in the /Volumes directory
		volumes_directory = File.join('', 'Volumes')
		attached_volumes = Dir.entries(volumes_directory)
		
		# Delete any files in /Volumes
		attached_volumes.delete_if { |x| File.file?(x) }
		
		# Delete any entries starting with '.'
		attached_volumes.delete_if { |x| x.start_with?(".") }
		
		# Delete any entries with "backup" in the name
		attached_volumes.delete_if { |x| x.downcase.include?("backup") }
		
		# Exclude Macintosh HD (default HDD name on Mac)
		attached_volumes.delete("Macintosh HD")
		
		# Add remaining volumes from /Volumes to @@volumes
		attached_volumes.each do |attached_volume|
			attached_volume_path = File.join('', 'Volumes', attached_volume)
			@@volumes << attached_volume_path
			$log.debug("Volumes::set_volumes_mac -- Found attached volume: #{attached_volume_path}")
		end
		
		# Create the Photo Inbox on the Desktop of the current user
		photo_inbox_directory = File.join(File.expand_path('~'), 'Desktop', 'Photo_Inbox')
		
		# Create the Photo_Inbox if it doesn't exist
		FileUtils.mkdir_p photo_inbox_directory
		
		# Add the Photo_Inbox to @@volumes
		@@volumes << photo_inbox_directory
		
		# Sort the @@volumes list
		@@volumes.sort!
		
		$log.debug("Volumes::set_volumes_mac -- Found volumes: #{@@volumes}")
	end

end