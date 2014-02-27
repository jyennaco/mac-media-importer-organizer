# volumes.rb
#
# Joseph Yennaco 22 September 2012
#

class Volumes
	
	# Class var to maintain the list of connected volumes
	@@volumes = []
	
	def self.get_volumes
		set_volumes
		return @@volumes
	end

	# Prints the list of connected volumes 
	def self.print_volumes
		set_volumes
		puts ""
		if not @@volumes.empty?
			Logger.output_user_info("The Connected Volumes available are: "); puts ""
			puts "\t" + "*" * 30
			@@volumes.each { |volume| puts "\t*" + volume.center(28) + "*" }
			puts "\t" + "*" * 30
			puts ""
		else
			Logger.output_user_alert("No Connected Volumes detected")
		end
	end

	# This class method prompts the user with the available connected volumes, 
	# and queries which ones to import media from
	# Input: "volumes" is an array of available volumes
	# Output: "selected_volumes" is an array of connected volumes typed by the user
	def self.get_selected_volumes(message="Type Volume Names")
		# Initialize the selected volumes
		selected_volumes = []
		
		# Loop request input until the user types "done" or provides valid input
		until not selected_volumes.empty? do
			print_volumes
			return if @@volumes.empty?
			Logger.get_user_input("#{message} (e.g. \"VOL1, VOL2\") or \"done\"")
			
			# Get the user input, chomp whitespace, split on ',' or whitespace
			# store user input as an array of selected volumes
			entries = gets.chomp.split(%r{,\s*})

			entries.each do |entry|
				if @@volumes.include?(entry)
					selected_volumes << entry
				elsif entry.downcase == "done" or entry.downcase == "exit" or entry.downcase == "quit"
					selected_volumes << "done"
				else	
					Logger.output_user_alert("#{entry} not recognized.")
				end
			end
		end
		
		# Return the list of selected volumes
		return selected_volumes.sort
	end

	def self.readable?(volume="")
		return false unless volume.class == String
		volume = volume.chomp
		# Build the absolute volume path
		volume_path = File.join('', 'Volumes', volume)
		# Check if the path exists, is a directory, and is readable
		return false unless File.exists?(volume_path)
		return false unless File.directory?(volume_path)
		return false unless File.readable?(volume_path)
		return true
	end
	
	def self.writable?(volume="")
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
	
	def self.set_volumes
		set_volumes_mac
	end
	
	# This method determines which Volumes are connected
	def self.set_volumes_mac
		volumes_directory = File.join('', 'Volumes')
		@@volumes = Dir.entries(volumes_directory)
		@@volumes.delete_if { |x| File.file?(x) }
		@@volumes.delete_if { |x| x.start_with?(".") }
		@@volumes.delete("Macintosh HD")
		#@@volumes.delete("BACKUP1")
		@@volumes.sort!
	end

end